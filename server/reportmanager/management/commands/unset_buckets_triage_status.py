# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from datetime import timedelta
from logging import getLogger

from scipy.stats import poisson

from django.core.management import BaseCommand
from django.db.models import (
    Exists,
    F,
    FloatField,
    Max,
    OuterRef,
    Prefetch,
    Subquery,
)
from django.db.models.functions import Coalesce

from reportmanager.models import Bucket, BucketHit, ReportEntry

LOG = getLogger("reportmanager.unset_triage_status")

# Recent window: how many days to count as "recent" activity for spike detection.
SHORT_WINDOW = 3

# Baseline window: how far back to look when estimating the bucket's normal rate.
# The actual baseline excludes the SHORT_WINDOW, so it covers days 4–60.
LONG_WINDOW = 60

# Significance threshold: if the probability of seeing at least this many recent
# reports by chance is below this value, we treat it as a spike and untriage.
POISSON_P_VALUE = 0.01

# Minimum number of recent reports required before spike detection runs.
MIN_RECENT_REPORTS = 3


def is_poisson_spike(baseline_count: int, recent_count: int) -> bool:
    """Detect whether recent report activity is an unusual spike vs the baseline.

    Uses a Poisson model rather than the ratio check used on spikes page ("3x the
    baseline rate") because ratios are too noisy for low-volume buckets and can
    undo human triage decisions too easily.

    We use the bucket's past activity to estimate a normal report count for the
    recent window. If the actual recent count is much higher than that estimate,
    the bucket may need to be triaged again.

    We ask: under the baseline rate, how likely is it to see at least
    recent_count reports in the short window purely by chance? If that
    probability is below POISSON_P_VALUE (currently 1%), the count is too unlikely to be
    normal variation, and we flag it as a spike. We might need to adjust this
    value based on feedback depending on how often buckets are wrongly
    untriaged / spikes missed.

    Args:
        baseline_count: reports with comments in the LONG_WINDOW preceding the
            short window. Used to estimate the per-day baseline rate.
        recent_count: reports with comments in the SHORT_WINDOW (most recent days).

    Returns:
        True if recent_count is statistically improbable under the baseline rate
        (probability < 1%, controlled by POISSON_P_VALUE), False otherwise.
        Note: recent_count should meet minimum-volume threshold
        (recent_count >= MIN_RECENT_REPORTS)
    """
    if recent_count < MIN_RECENT_REPORTS:
        return False
    if baseline_count == 0:
        return True

    baseline_days = LONG_WINDOW - SHORT_WINDOW

    # expected number of reports in the recent window based on baseline,
    # i.e. if nothing changed, how many reports would we expect in the last SHORT_WINDOW days?
    lam = (baseline_count / baseline_days) * SHORT_WINDOW

    # We compute the probability of seeing at least this many events (not just exactly
    # this many), because any count >= recent_count would be equally or more extreme.
    # This "right tail" probability tells us how surprising the observed spike is
    # under the baseline rate. We want to include recent_count i.e. P(X >= recent_count),
    # so passing recent_count - 1.
    p_value = poisson.sf(recent_count - 1, lam)

    return p_value < POISSON_P_VALUE


class Command(BaseCommand):
    help = (
        "Check triaged buckets and automatically untriage them based on "
        "quality improvements (incomplete status) or spike detection (all statuses)"
    )

    def handle(self, *args, **options):
        LOG.info("Starting auto-untriage check")

        inomplete_untriaged = self.unset_incomplete()
        spike_untriaged = self.unset_status_if_spike()

        total = inomplete_untriaged + spike_untriaged
        LOG.info(
            f"Auto-untriage complete: {inomplete_untriaged} incomplete, "
            f"{spike_untriaged} spike-based, {total} total"
        )

    def unset_incomplete(self):
        """Untriage incomplete buckets if they received reports with better quality."""

        max_probability_at_triage = Subquery(
            ReportEntry.objects.filter(
                bucket=OuterRef("pk"),
                reported_at__lte=OuterRef("triaged_at"),
            )
            .order_by()
            .values("bucket")
            .annotate(max_probability_at_triage=Max("ml_valid_probability"))
            .values("max_probability_at_triage")[:1],
            output_field=FloatField(),
        )

        has_better_new_report = Exists(
            ReportEntry.objects.filter(
                bucket=OuterRef("pk"),
                reported_at__gt=OuterRef("triaged_at"),
                ml_valid_probability__gt=OuterRef("max_probability_at_triage"),
            )
        )

        to_untriage = (
            Bucket.objects.filter(
                cluster__isnull=False, triage_status=Bucket.TriageStatus.INCOMPLETE
            )
            .annotate(
                max_probability_at_triage=Coalesce(max_probability_at_triage, 0.0)
            )
            .annotate(has_better_new_report=has_better_new_report)
            .filter(has_better_new_report=True)
        )

        ids = list(to_untriage.values_list("id", flat=True))
        untriaged_count = Bucket.objects.filter(id__in=ids).update(triage_status=None)

        for bucket_id in ids:
            LOG.info(
                f"Auto-untriaged bucket {bucket_id} (incomplete): better quality report"
            )

        return untriaged_count

    def unset_status_if_spike(self):
        """Unset triaged status for cluster buckets experiencing a spike."""

        # Reports are delayed by 1 day, so use the
        # window to the most recent BucketHit instead of today.
        last_hit = (
            BucketHit.objects.filter(bucket__cluster__isnull=False)
            .order_by("-begin")
            .first()
        )

        if last_hit is None:
            return 0

        now = last_hit.begin
        short_window_start = now - timedelta(days=SHORT_WINDOW)
        long_window_start = now - timedelta(days=LONG_WINDOW)

        triaged_buckets = (
            Bucket.objects.filter(
                triage_status__isnull=False,
                cluster__isnull=False,
                triaged_at__isnull=False,
                buckethit__begin__gt=F("triaged_at"),
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "buckethit_set",
                    queryset=BucketHit.objects.filter(begin__gte=long_window_start),
                    to_attr="recent_hits",
                )
            )
        )

        untriaged_count = 0

        for bucket in triaged_buckets:
            recent_count = sum(
                h.count
                for h in bucket.recent_hits
                if h.begin >= short_window_start and h.begin > bucket.triaged_at
            )
            baseline_count = sum(
                h.count for h in bucket.recent_hits if h.begin < short_window_start
            )

            if is_poisson_spike(baseline_count, recent_count):
                status = bucket.triage_status
                bucket.triage_status = None
                bucket.save(update_fields=["triage_status"])
                untriaged_count += 1
                LOG.info(
                    f"Auto-untriaged bucket {bucket.id} ({status}): "
                    f"spike detected (recent={recent_count}, baseline={baseline_count})"
                )

        return untriaged_count
