from datetime import datetime
from itertools import batched
from logging import getLogger

from django.core.management import BaseCommand
from django.utils import timezone

from reportmanager.clustering.ClusterBucketManager import (
    ClusterBucketManager,
    ClusteringConfig,
    ClusterReport,
)
from reportmanager.locking import JobLockError, acquire_job_lock
from reportmanager.models import (
    Bucket,
    BucketHit,
    ClusteringJob,
    ClusteringJobType,
    JobLock,
    ReportEntry,
)

LOG = getLogger("reportmanager.triage")


def complete_job(
    job: ClusteringJob,
    success: bool,
    buckets_created: int = 0,
    error: str | None = None,
) -> None:
    job.completed_at = timezone.now()
    job.is_ok = success
    job.buckets_created = buckets_created
    if error:
        job.error_message = error
    job.save()


def cluster_unmatched_reports(
    manager: ClusterBucketManager,
    unmatched_reports: list[ClusterReport],
) -> tuple[set[int], int]:
    """Cluster unmatched reports to find groups among remaining reports.

    Returns:
        Tuple of (clustered_report_ids, buckets_created)
    """

    if not unmatched_reports:
        return set(), 0

    LOG.info(
        f"Processing {len(unmatched_reports)} unmatched reports for potential clustering..."  # noqa
    )

    unmatched_by_domain = manager.group_reports_by_domain(unmatched_reports)

    clustered_report_ids = set()
    total_buckets = 0

    for domain, domain_reports in unmatched_by_domain.items():
        LOG.info(
            f"Clustering {len(domain_reports)} unmatched reports for domain: {domain}"
        )

        clusters = manager.cluster_domain_reports(domain, domain_reports)

        if not clusters:
            continue

        clusters_with_ids = manager.save_clusters(clusters)
        buckets_count = manager.create_buckets_from_clusters(clusters_with_ids)
        total_buckets += buckets_count

        # Track which reports were successfully clustered
        for cluster_data in clusters_with_ids:
            for report in cluster_data.reports:
                clustered_report_ids.add(report.id)

    return clustered_report_ids, total_buckets


def apply_domain_bucketing_fallback(
    unmatched_reports: list[ClusterReport],
    report_entries: dict[int, ReportEntry],
) -> tuple[int, list[tuple[int, datetime]]]:
    """Add unclustered reports to default domain-based buckets."""
    if not unmatched_reports:
        return 0, []

    LOG.info(
        f"Applying domain-based bucketing to {len(unmatched_reports)} reports that didn't cluster"  # noqa
    )

    # Get all unique domains from unmatched reports
    domains = {report.domain for report in unmatched_reports}

    existing_buckets = {}

    for batch_domains in batched(domains, 500):
        buckets = (
            Bucket.objects.filter(domain__in=batch_domains)
            .exclude(description__contains=ClusteringConfig.CLUSTER_BUCKET_IDENTIFIER)
            .values("domain", "id")
        )
        existing_buckets.update({bucket["domain"]: bucket["id"] for bucket in buckets})

    entries_to_update = []
    bucket_hits = []
    buckets_created = 0

    for report in unmatched_reports:
        bucket_id = existing_buckets.get(report.domain)

        if not bucket_id:
            # Create new domain-based bucket
            report_entry = report_entries[report.id]
            report_obj = report_entry.get_report()

            bucket = Bucket.objects.create(
                description=f"domain is {report.domain}",
                signature=report_obj.create_signature().raw_signature,
            )
            bucket_id = bucket.pk
            buckets_created += 1

            existing_buckets[report.domain] = bucket_id

        entry = report_entries[report.id]
        entry.bucket_id = bucket_id  # type: ignore[attr-defined]
        entries_to_update.append(entry)
        bucket_hits.append((bucket_id, entry.reported_at))

    if entries_to_update:
        ReportEntry.objects.bulk_update(entries_to_update, ["bucket_id"])

    LOG.info(f"Applied domain-based bucketing to {len(entries_to_update)} reports")
    return buckets_created, bucket_hits


def get_cluster_bucket(
    manager: ClusterBucketManager,
    report: ClusterReport,
    domain_data: dict,
) -> tuple[int | None, int | None]:
    cluster_id = manager.get_closest_cluster(report, domain_data)
    bucket_id = None

    if cluster_id:
        cluster_bucket = manager.get_bucket_for_cluster(cluster_id)
        bucket_id = cluster_bucket.pk if cluster_bucket else None

    return cluster_id, bucket_id


def run_triage(job: ClusteringJob) -> None:
    try:
        manager = ClusterBucketManager()

        # Query all unbucketed reports
        report_entries_qs = ReportEntry.objects.select_related(
            "app", "os", "breakage_category"
        ).filter(bucket_id__isnull=True)

        unbucketed_reports = []
        report_entries = {}

        for entry in report_entries_qs:
            cluster_report = manager.build_cluster_report(
                {
                    "id": entry.id,
                    "comments_preprocessed": entry.comments_preprocessed,
                    "ml_valid_probability": entry.ml_valid_probability,
                    "reported_at": entry.reported_at,
                    "url": entry.url,
                    "bucket_id": entry.bucket_id,
                    "domain": entry.domain,
                }
            )

            unbucketed_reports.append(cluster_report)
            report_entries[entry.id] = entry

        LOG.info(f"Unbucketed reports to triage: {len(unbucketed_reports)}")

        if not unbucketed_reports:
            LOG.info("No unbucketed reports to triage")
            complete_job(job, success=True, buckets_created=0)
            return

        domains = {r.domain for r in unbucketed_reports if r.domain}
        domain_data = manager.build_domain_data(domains=domains)

        unmatched_reports = []
        low_quality_reports = []
        entries_to_update = []
        bucket_hits = []

        for report in unbucketed_reports:
            if report.ok_to_cluster:
                cluster_id, bucket_id = get_cluster_bucket(manager, report, domain_data)

                if cluster_id and bucket_id:
                    entry = report_entries[report.id]
                    entry.cluster_id = cluster_id
                    entry.bucket_id = bucket_id
                    entries_to_update.append(entry)
                    bucket_hits.append((bucket_id, entry.reported_at))
                else:
                    # Track unmatched reports for further clustering
                    unmatched_reports.append(report)
            else:
                # Low quality reports (empty text, low probability) go straight to by domain bucketing # noqa
                low_quality_reports.append(report)

        if entries_to_update:
            ReportEntry.objects.bulk_update(
                entries_to_update, ["cluster_id", "bucket_id"]
            )

        # Cluster unmatched reports that might form clusters among themselves
        clustered_report_ids, buckets_created = cluster_unmatched_reports(
            manager, unmatched_reports
        )

        # Filter out reports that were successfully clustered
        still_unmatched = [
            r for r in unmatched_reports if r.id not in clustered_report_ids
        ]

        # Fall back to domain-based bucketing for reports that still don't have clusters
        # and low-quality reports
        remaining = still_unmatched + low_quality_reports
        fallback_buckets, fallback_bucket_hits = apply_domain_bucketing_fallback(
            remaining, report_entries
        )

        all_bucket_hits = bucket_hits + fallback_bucket_hits
        if all_bucket_hits:
            BucketHit.bulk_increment_counts(all_bucket_hits)

        total_buckets = buckets_created + fallback_buckets
        complete_job(job, success=True, buckets_created=total_buckets)
        LOG.info(
            f"Triage completed successfully. Created {buckets_created} cluster buckets and {fallback_buckets} domain buckets."  # noqa
        )

    except Exception as e:
        complete_job(job, success=False, error=str(e))
        raise


class Command(BaseCommand):
    help = (
        "Iterates over all unbucketed report entries that have never been triaged "
        "before to assign them into the existing buckets."
    )

    def handle(self, *args: object, **options: object) -> None:
        try:
            with acquire_job_lock(JobLock.CLUSTERING):
                status = ClusteringJob.get_clustering_status()

                if not status.has_successful_run:
                    LOG.warning("Skipping triaging: full clustering has not run yet")
                    return

                # Create a job record for this triage run
                job = ClusteringJob.objects.create(
                    job_type=ClusteringJobType.INCREMENTAL
                )
                run_triage(job)

        except JobLockError as e:
            LOG.warning(f"Cannot start triage: {e}.")
            return
