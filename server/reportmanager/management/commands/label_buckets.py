# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from logging import getLogger

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models import Exists, OuterRef

from reportmanager.models import (
    Bucket,
    BucketLabel,
    DomainEntry,
    DomainSource,
    Label,
)

LOG = getLogger("reportmanager.label_buckets")

INSERT_BATCH_SIZE = 1000
ITER_CHUNK_SIZE = 1000


def get_or_create_source_label(source_name: str) -> Label | None:
    try:
        domain_source = DomainSource.objects.get(name=source_name)
    except DomainSource.DoesNotExist:
        return None

    label, _ = Label.objects.get_or_create(
        domain_source=domain_source,
        defaults={"name": source_name},
    )
    return label


def get_label_source_names(source_name: str | None = None) -> list[str]:
    source_names = [
        source["name"] for source in getattr(settings, "BIGQUERY_DOMAIN_SOURCES", [])
    ]
    if source_name is None:
        return source_names

    if source_name not in source_names:
        raise CommandError(f"No domain source configured for source '{source_name}'")
    return [source_name]


def reconcile_all_buckets_for_source(source_name: str) -> tuple[int, int]:
    """Reconcile the source-based label for all buckets against the DomainSource.

    Returns a tuple of (created_count, removed_count).
    """
    label = get_or_create_source_label(source_name)
    if label is None:
        return 0, 0

    missing_labels = (
        Bucket.objects.filter(domain_normalized__isnull=False)
        .annotate(
            has_domain_match=Exists(
                DomainEntry.objects.filter(
                    domain_source__name=source_name,
                    domain=OuterRef("domain_normalized"),
                )
            ),
            is_already_labeled=Exists(
                BucketLabel.objects.filter(
                    bucket=OuterRef("pk"),
                    label=label,
                )
            ),
        )
        .filter(has_domain_match=True, is_already_labeled=False)
        .only("id")
    )

    created = BucketLabel.objects.bulk_create(
        (
            BucketLabel(bucket=b, label=label)
            for b in missing_labels.iterator(chunk_size=ITER_CHUNK_SIZE)
        ),
        batch_size=INSERT_BATCH_SIZE,
        ignore_conflicts=True,
    )

    stale_labels = (
        BucketLabel.objects.filter(label=label)
        .annotate(
            has_domain_match=Exists(
                DomainEntry.objects.filter(
                    domain_source__name=source_name,
                    domain=OuterRef("bucket__domain_normalized"),
                )
            )
        )
        .filter(has_domain_match=False)
    )
    removed_count, _ = stale_labels.delete()
    return len(created), removed_count


def reconcile_bucket_for_label(bucket_id: int, source_name: str) -> tuple[bool, bool]:
    """Reconcile the source-based label for one bucket against the DomainSource.

    Returns a tuple of (created, removed).
    """
    label = get_or_create_source_label(source_name)
    if label is None:
        return False, False

    try:
        bucket = Bucket.objects.only("id", "domain_normalized").get(pk=bucket_id)
    except Bucket.DoesNotExist:
        return False, False

    if not bucket.domain_normalized:
        removed_count, _ = BucketLabel.objects.filter(
            bucket=bucket, label=label
        ).delete()
        return False, removed_count > 0

    is_in_source = DomainEntry.objects.filter(
        domain_source__name=source_name,
        domain=bucket.domain_normalized,
    ).exists()

    if is_in_source:
        _, created = BucketLabel.objects.get_or_create(bucket=bucket, label=label)
        return created, False

    removed_count, _ = BucketLabel.objects.filter(bucket=bucket, label=label).delete()
    return False, removed_count > 0


class Command(BaseCommand):
    help = "Apply domain-list-based labels to buckets"

    def add_arguments(self, parser):
        parser.add_argument(
            "--bucket-id",
            type=int,
            default=None,
            help=(
                "If passed, label only this bucket (single-bucket mode). "
                "Otherwise, run in bulk mode."
            ),
        )
        parser.add_argument(
            "--source-name",
            default=None,
            help=(
                "If passed, reconcile only labels mapped to this DomainSource. "
                "Otherwise, reconcile all configured sources."
            ),
        )

    def handle(
        self,
        bucket_id: int | None,
        source_name: str | None,
        **options: object,
    ) -> None:
        source_names = get_label_source_names(source_name)

        if bucket_id is not None:
            for mapped_source_name in source_names:
                created, removed = reconcile_bucket_for_label(
                    bucket_id, mapped_source_name
                )
                if created:
                    LOG.info(
                        "Applied label '%s' to bucket %d",
                        mapped_source_name,
                        bucket_id,
                    )
                if removed:
                    LOG.info(
                        "Removed label '%s' from bucket %d",
                        mapped_source_name,
                        bucket_id,
                    )
            return

        for mapped_source_name in source_names:
            created_count, removed_count = reconcile_all_buckets_for_source(
                mapped_source_name
            )
            LOG.info(
                "Reconciled label '%s': %d added, %d removed",
                mapped_source_name,
                created_count,
                removed_count,
            )
