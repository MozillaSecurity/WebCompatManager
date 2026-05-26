from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from reportmanager.management.commands.label_buckets import (
    get_or_create_source_label,
    reconcile_all_buckets_for_source,
    reconcile_bucket_for_label,
)
from reportmanager.models import (
    Bucket,
    BucketLabel,
    DomainEntry,
    DomainSource,
    Label,
)


def make_bucket(domain: str | None = None) -> Bucket:
    return Bucket.objects.create(signature='{"symptoms": []}', domain=domain)


@pytest.fixture
def nsfw_source(db):
    src = DomainSource.objects.create(
        name="nsfw",
        bq_table="t",
        bq_source_field="domain",
    )
    DomainEntry.objects.create(domain_source=src, domain="badsite.com")
    DomainEntry.objects.create(domain_source=src, domain="example.com")
    return src


@pytest.mark.django_db
class TestGetOrCreateSourceLabel:
    def test_creates_label_for_source(self, nsfw_source):
        label = get_or_create_source_label("nsfw")
        assert label is not None
        assert label.name == "nsfw"
        assert label.domain_source == nsfw_source

    def test_returns_existing_label(self, nsfw_source):
        label1 = get_or_create_source_label("nsfw")
        label2 = get_or_create_source_label("nsfw")
        assert label1.pk == label2.pk

    def test_returns_none_when_source_missing(self, db):
        assert get_or_create_source_label("does_not_exist") is None


@pytest.mark.django_db
class TestReconcileAllBucketsForSource:
    def test_labels_matching_bucket(self, nsfw_source):
        bucket = make_bucket(domain="www.example.com")
        reconcile_all_buckets_for_source("nsfw")
        bucket.refresh_from_db()
        assert bucket.labels.filter(label__name="nsfw").exists()

    def test_skips_non_matching(self, nsfw_source):
        bucket = make_bucket(domain="unrelated.com")
        reconcile_all_buckets_for_source("nsfw")
        bucket.refresh_from_db()
        assert not bucket.labels.exists()

    def test_skips_already_labeled(self, nsfw_source):
        bucket = make_bucket(domain="example.com")
        label = get_or_create_source_label("nsfw")
        BucketLabel.objects.get_or_create(bucket=bucket, label=label)
        reconcile_all_buckets_for_source("nsfw")
        assert BucketLabel.objects.filter(bucket=bucket, label=label).count() == 1

    def test_removes_stale_label_when_domain_no_longer_in_source(self, nsfw_source):
        bucket = make_bucket(domain="example.com")
        label = get_or_create_source_label("nsfw")
        BucketLabel.objects.get_or_create(bucket=bucket, label=label)
        DomainEntry.objects.filter(
            domain_source=nsfw_source, domain="example.com"
        ).delete()
        reconcile_all_buckets_for_source("nsfw")
        assert not BucketLabel.objects.filter(bucket=bucket, label=label).exists()

    def test_returns_created_and_removed_counts(self, nsfw_source):
        # Two buckets whose domains are in the source — should be labeled
        make_bucket(domain="badsite.com")
        make_bucket(domain="example.com")
        BucketLabel.objects.all().delete()

        # prelabel bucket even though its domain is not in the source
        label = get_or_create_source_label("nsfw")
        bucket_to_remove = make_bucket(domain="oldsite.com")
        BucketLabel.objects.create(bucket=bucket_to_remove, label=label)

        created, removed = reconcile_all_buckets_for_source("nsfw")
        assert created == 2
        assert removed == 1


@pytest.mark.django_db
class TestReconcileBucketForLabel:
    def test_labels_matching_bucket(self, nsfw_source):
        bucket = make_bucket(domain="www.example.com")
        BucketLabel.objects.all().delete()  # clear signal-applied labels
        created, removed = reconcile_bucket_for_label(bucket.pk, "nsfw")
        assert created
        assert not removed
        assert bucket.labels.filter(label__name="nsfw").exists()

    def test_skips_non_matching(self, nsfw_source):
        bucket = make_bucket(domain="unrelated.com")
        created, removed = reconcile_bucket_for_label(bucket.pk, "nsfw")
        assert not created
        assert not removed
        assert not bucket.labels.exists()

    def test_removes_label_when_no_normalized_domain(self, nsfw_source):
        bucket = make_bucket(domain="example.com")
        label = get_or_create_source_label("nsfw")
        BucketLabel.objects.get_or_create(bucket=bucket, label=label)

        # Clear domain_normalized to simulate a bucket without a domain
        Bucket.objects.filter(pk=bucket.pk).update(domain_normalized=None)

        created, removed = reconcile_bucket_for_label(bucket.pk, "nsfw")
        assert not created
        assert removed
        assert not BucketLabel.objects.filter(bucket=bucket, label=label).exists()

    def test_removes_label_when_domain_not_in_source(self, nsfw_source):
        bucket = make_bucket(domain="example.com")
        label = get_or_create_source_label("nsfw")
        BucketLabel.objects.get_or_create(bucket=bucket, label=label)

        # Remove the matching DomainEntry → label should be removed on reconcile
        DomainEntry.objects.filter(
            domain_source=nsfw_source, domain="example.com"
        ).delete()

        created, removed = reconcile_bucket_for_label(bucket.pk, "nsfw")
        assert not created
        assert removed
        assert not BucketLabel.objects.filter(bucket=bucket, label=label).exists()

    def test_returns_false_when_bucket_missing(self, nsfw_source):
        created, removed = reconcile_bucket_for_label(99999, "nsfw")
        assert not created
        assert not removed

    def test_returns_false_when_source_missing(self, db):
        bucket = make_bucket(domain="example.com")
        created, removed = reconcile_bucket_for_label(bucket.pk, "does_not_exist")
        assert not created
        assert not removed


@pytest.mark.django_db
class TestLabelBucketsCommand:
    def test_no_args_reconciles_all_sources(self, nsfw_source):
        bucket = make_bucket(domain="example.com")
        BucketLabel.objects.all().delete()
        out = StringIO()
        call_command("label_buckets", stdout=out)
        bucket.refresh_from_db()
        assert bucket.labels.filter(label__name="nsfw").exists()

    def test_with_source_name_only(self, nsfw_source):
        bucket = make_bucket(domain="example.com")
        BucketLabel.objects.all().delete()
        call_command("label_buckets", source_name="nsfw")
        bucket.refresh_from_db()
        assert bucket.labels.filter(label__name="nsfw").exists()

    def test_with_unknown_source_name_raises(self, db):
        with pytest.raises(CommandError):
            call_command("label_buckets", source_name="does_not_exist")

    def test_with_bucket_id_processes_one_bucket(self, nsfw_source):
        bucket_match = make_bucket(domain="example.com")
        bucket_other = make_bucket(domain="badsite.com")
        BucketLabel.objects.filter(bucket=bucket_other).delete()
        call_command("label_buckets", bucket_id=bucket_match.pk)
        assert bucket_match.labels.filter(label__name="nsfw").exists()
        assert not bucket_other.labels.exists()
