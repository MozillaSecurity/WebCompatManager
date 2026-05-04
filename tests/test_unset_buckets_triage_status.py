import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from reportmanager.management.commands.unset_buckets_triage_status import (
    Command,
    LONG_WINDOW,
    SHORT_WINDOW,
    is_poisson_spike,
)
from reportmanager.models import App, Bucket, BucketHit, Cluster, OS, ReportEntry


@pytest.fixture
def app(db):
    return App.objects.create(name="Firefox", version="150.0", channel="release")


@pytest.fixture
def os(db):
    return OS.objects.create(name="Linux")


def make_bucket(triage_status, triaged_at):
    cluster = Cluster.objects.create(domain="example.com")
    return Bucket.objects.create(
        description="test",
        signature="{}",
        triage_status=triage_status,
        triaged_at=triaged_at,
        cluster=cluster,
    )


def make_report(bucket, reported_at, ml_valid_probability, app, os, comments="test"):
    return ReportEntry.objects.create(
        bucket=bucket,
        cluster=bucket.cluster,
        reported_at=reported_at,
        ml_valid_probability=ml_valid_probability,
        app=app,
        os=os,
        comments=comments,
        details={},
        url="https://example.com/",
        uuid=uuid.uuid4(),
    )


@pytest.mark.django_db
class TestUnsetIncomplete:
    def test_untriages_when_new_report_beats_baseline(self, app, os):
        now = timezone.now()
        bucket = make_bucket("incomplete", now - timedelta(days=1))
        make_report(bucket, now - timedelta(days=2), 0.7, app, os)
        make_report(bucket, now, 0.9, app, os)

        count = Command().unset_incomplete()

        assert count == 1
        bucket.refresh_from_db()
        assert bucket.triage_status is None
        assert bucket.triaged_at is not None

    def test_no_untriage_when_new_report_does_not_beat_baseline(self, app, os):
        now = timezone.now()
        bucket = make_bucket("incomplete", now - timedelta(days=1))
        make_report(bucket, now - timedelta(days=2), 0.9, app, os)
        make_report(bucket, now, 0.2, app, os)

        count = Command().unset_incomplete()

        assert count == 0
        bucket.refresh_from_db()
        assert bucket.triage_status == "incomplete"

    def test_untriages_when_no_old_reports_and_new_report_has_positive_probability(
        self, app, os
    ):
        now = timezone.now()
        bucket = make_bucket("incomplete", now - timedelta(days=1))
        make_report(bucket, now, 0.2, app, os)  # baseline defaults to 0.0

        count = Command().unset_incomplete()

        assert count == 1
        bucket.refresh_from_db()
        assert bucket.triage_status is None
        assert bucket.triaged_at is not None

    def test_no_untriage_when_no_new_reports(self, app, os):
        now = timezone.now()
        bucket = make_bucket("incomplete", now - timedelta(days=1))
        make_report(bucket, now - timedelta(days=2), 0.9, app, os)

        count = Command().unset_incomplete()

        assert count == 0
        bucket.refresh_from_db()
        assert bucket.triage_status == "incomplete"

    def test_no_untriage_when_new_report_probability_is_none(self, app, os):
        now = timezone.now()
        bucket = make_bucket("incomplete", now - timedelta(days=1))
        make_report(bucket, now - timedelta(days=2), 0.6, app, os)
        make_report(bucket, now, None, app, os)

        count = Command().unset_incomplete()

        assert count == 0
        bucket.refresh_from_db()
        assert bucket.triage_status == "incomplete"

    def test_only_affects_incomplete_buckets(self, app, os):
        now = timezone.now()
        for status in ("worksforme", "cant_test", "invalid", "non_compat"):
            b = make_bucket(status, now - timedelta(days=1))
            make_report(b, now - timedelta(days=2), 0.4, app, os)
            make_report(b, now, 0.9, app, os)

        count = Command().unset_incomplete()

        assert count == 0

    def test_multiple_buckets_only_qualifying_ones_untriaged(self, app, os):
        now = timezone.now()
        good = make_bucket("incomplete", now - timedelta(days=1))
        make_report(good, now - timedelta(days=2), 0.4, app, os)
        make_report(good, now, 0.9, app, os)

        bad = make_bucket("incomplete", now - timedelta(days=1))
        make_report(bad, now - timedelta(days=2), 0.9, app, os)
        make_report(bad, now, 0.4, app, os)

        count = Command().unset_incomplete()

        assert count == 1
        good.refresh_from_db()
        assert good.triage_status is None
        bad.refresh_from_db()
        assert bad.triage_status == "incomplete"


def make_bucket_hits(bucket, *, recent_count, baseline_count):
    now = timezone.now()
    if recent_count:
        BucketHit.objects.create(bucket=bucket, begin=now, count=recent_count)
    if baseline_count:
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=SHORT_WINDOW + 1),
            count=baseline_count,
        )


class TestIsPoissonSpike:
    def test_clear_spike(self):
        # Based on real bucket data: 9 reports over the 57-day baseline gives an
        # expected rate of ~0.47 reports in 3 days, but 7 actually arrived — p≈0
        assert is_poisson_spike(baseline_count=9, recent_count=7)

    def test_normal_variation_not_a_spike(self):
        # ~2/day baseline means ~6 expected in 3 days; getting 3 is below average
        assert not is_poisson_spike(baseline_count=114, recent_count=3)

    def test_below_min_recent_returns_false(self):
        # 2 recent reports is below MIN_RECENT_REPORTS regardless of baseline
        assert not is_poisson_spike(baseline_count=30, recent_count=2)

    def test_zero_baseline_below_min_recent_returns_false(self):
        # no history and only 2 recent reports — too few to act on
        assert not is_poisson_spike(baseline_count=0, recent_count=2)

    def test_zero_baseline_at_min_recent_is_spike(self):
        # no history at all and 3 reports just appeared — treat as spike
        assert is_poisson_spike(baseline_count=0, recent_count=3)

    def test_low_volume_bucket_large_recent_count_is_spike(self):
        # only 3 reports in 57-day baseline (~0.05/day), so expected in 3 days ≈ 0.16;
        # getting 8 is unlikely
        assert is_poisson_spike(baseline_count=3, recent_count=8)

    def test_just_below_threshold_is_spike(self):
        # ~1/day baseline → expected 3 in 3 days; getting 10 → p ≈ 0.08%, below 1%
        assert is_poisson_spike(baseline_count=57, recent_count=10)

    def test_just_above_threshold_is_not_spike(self):
        # same baseline; getting 7 → p ≈ 3.4%, above the 1% threshold — normal variation
        assert not is_poisson_spike(baseline_count=57, recent_count=7)


@pytest.mark.django_db
class TestUnsetStatusIfSpike:
    def test_no_untriage_when_no_recent_reports(self):
        now = timezone.now()
        # Unrelated bucket with a hit at "now" to mimic recent activity
        anchor_bucket = make_bucket(None, None)
        BucketHit.objects.create(bucket=anchor_bucket, begin=now, count=1)

        bucket = make_bucket("worksforme", now - timedelta(days=30))
        make_bucket_hits(bucket, recent_count=0, baseline_count=9)

        count = Command().unset_status_if_spike()

        assert count == 0
        bucket.refresh_from_db()
        assert bucket.triage_status == "worksforme"

    def test_hits_outside_long_window_not_counted(self):
        now = timezone.now()
        bucket = make_bucket("worksforme", now - timedelta(days=30))
        # 9 hits outside the long window — should not contribute
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=LONG_WINDOW + 1),
            count=9,
        )
        make_bucket_hits(bucket, recent_count=7, baseline_count=0)

        count = Command().unset_status_if_spike()

        assert count == 1  # zero baseline + 7 recent triggers spike
        bucket.refresh_from_db()
        assert bucket.triage_status is None

    def test_untriages_any_triage_status(self):
        now = timezone.now()
        for status in (
            "worksforme",
            "cant_test",
            "invalid",
            "non_compat",
            "incomplete",
        ):
            bucket = make_bucket(status, now - timedelta(days=30))
            make_bucket_hits(bucket, recent_count=7, baseline_count=9)

        count = Command().unset_status_if_spike()

        assert count == 5

    def test_multiple_buckets_only_spiking_ones_untriaged(self):
        now = timezone.now()

        spiking = make_bucket("worksforme", now - timedelta(days=30))
        make_bucket_hits(spiking, recent_count=7, baseline_count=9)

        steady = make_bucket("worksforme", now - timedelta(days=30))
        make_bucket_hits(steady, recent_count=3, baseline_count=114)

        count = Command().unset_status_if_spike()

        assert count == 1
        spiking.refresh_from_db()
        assert spiking.triage_status is None
        steady.refresh_from_db()
        assert steady.triage_status == "worksforme"

    def test_pre_triage_spike_does_not_fire(self):
        now = timezone.now()
        # Triaged 12 hours ago, after a spike that started 2 days ago.
        # All recent activity predates triaged_at, so it should not count.
        bucket = make_bucket("worksforme", now - timedelta(hours=12))
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=2),
            count=7,
        )
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=SHORT_WINDOW + 1),
            count=9,
        )

        count = Command().unset_status_if_spike()

        assert count == 0
        bucket.refresh_from_db()
        assert bucket.triage_status == "worksforme"

    def test_ongoing_spike_after_triage_eventually_fires(self):
        now = timezone.now()
        # Spike started 4 days ago at ~5/day, human triaged 3 days ago mid-spike,
        # spike has continued at the same rate. The pre-triage portion is
        # ignored; the post-triage portion of 6 reports is 0.4 vs the ~0.5/day
        # baseline and should trigger a spike.
        bucket = make_bucket("worksforme", now - timedelta(days=3))
        # Pre-triage spike (excluded by triaged_at filter).
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=4),
            count=5,
        )
        # Post-triage continuation of the spike.
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=2),
            count=2,
        )
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=1),
            count=4,
        )

        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=30),
            count=30,
        )

        count = Command().unset_status_if_spike()

        assert count == 1
        bucket.refresh_from_db()
        assert bucket.triage_status is None
        assert bucket.triaged_at is not None

    def test_post_triage_spike_does_fire(self):
        now = timezone.now()
        # Triaged 5 days ago, with a fresh post-triage spike in the short window.
        bucket = make_bucket("worksforme", now - timedelta(days=5))
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(hours=12),
            count=7,
        )
        BucketHit.objects.create(
            bucket=bucket,
            begin=now - timedelta(days=SHORT_WINDOW + 1),
            count=9,
        )

        count = Command().unset_status_if_spike()

        assert count == 1
        bucket.refresh_from_db()
        assert bucket.triage_status is None
        assert bucket.triaged_at is not None
