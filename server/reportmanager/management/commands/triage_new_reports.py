from logging import getLogger

from django.core.management import BaseCommand
from django.db.models import Q
from django.utils import timezone

from reportmanager.clustering.ClusterBucketManager import (
    ClusterBucketManager,
    ClusteringConfig,
    ClusterReport,
)
from reportmanager.models import Bucket, ClusteringJob, ClusteringJobType, ReportEntry

LOG = getLogger("reportmanager.triage")

KNOWN_BUCKET_IDS: dict[str, int] = {}


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
) -> int:
    """Add unclustered reports to defalt domain-based buckets."""
    if not unmatched_reports:
        return 0

    LOG.info(
        f"Applying domain-based bucketing to {len(unmatched_reports)} reports that didn't cluster"  # noqa
    )
    reports_bucketed = 0

    for report in unmatched_reports:
        bucket_id = KNOWN_BUCKET_IDS.get(report.domain)

        if not bucket_id:
            # Find existing domain-based bucket (exclude cluster buckets)
            bucket_id = (
                Bucket.objects.filter(Q(domain=report.domain))
                .exclude(
                    description__contains=ClusteringConfig.CLUSTER_BUCKET_IDENTIFIER
                )
                .values_list("id", flat=True)
                .first()
            )

        if not bucket_id:
            report_entry = report_entries[report.id]
            report_obj = report_entry.get_report()

            bucket = Bucket.objects.create(
                description=f"domain is {report.domain}",
                signature=report_obj.create_signature().raw_signature,
            )
            bucket_id = bucket.pk

        KNOWN_BUCKET_IDS[report.domain] = bucket_id
        ReportEntry.objects.filter(id=report.id).update(bucket_id=bucket_id)
        reports_bucketed += 1

    LOG.info(f"Applied domain-based bucketing to {reports_bucketed} reports")
    return reports_bucketed


def get_cluster_bucket(
    manager: ClusterBucketManager, report: ClusterReport
) -> tuple[int | None, int | None]:
    cluster_id = manager.get_closest_cluster(report)
    bucket_id = None

    if cluster_id:
        cluster_bucket = manager.get_bucket_for_cluster(cluster_id)
        bucket_id = cluster_bucket.pk if cluster_bucket else None

    return cluster_id, bucket_id


def run_triage(job: ClusteringJob) -> None:
    try:
        manager = ClusterBucketManager()

        # Get all reports to build a domain volume map and reports embeddings
        report_entries_qs = ReportEntry.objects.select_related(
            "app", "os", "breakage_category"
        ).all()

        all_reports = []
        unbucketed_reports = []
        # Store a dict of report entries for domain-based
        # bucketing fallback, if report can't be clustered
        report_entries = {}

        for entry in report_entries_qs:
            cluster_report = manager.build_cluster_report(
                {
                    "id": entry.id,
                    "comments": entry.comments,
                    "comments_translated": entry.comments_translated,
                    "ml_valid_probability": entry.ml_valid_probability,
                    "reported_at": entry.reported_at,
                    "url": entry.url,
                    "bucket_id": entry.bucket_id,
                }
            )

            all_reports.append(cluster_report)

            if cluster_report.bucket_id is None:
                unbucketed_reports.append(cluster_report)
                report_entries[entry.id] = entry

        LOG.info(f"Unbucketed reports to triage: {len(unbucketed_reports)}")

        if not unbucketed_reports:
            LOG.info("No unbucketed reports to triage")
            complete_job(job, success=True, buckets_created=0)
            return

        # Build domain data (volume + embeddings) for unbucketed report domains
        domains = {r.domain for r in unbucketed_reports if r.domain}
        manager.build_domain_data(all_reports=all_reports, domains=domains)

        unmatched_reports = []
        low_quality_reports = []

        for report in unbucketed_reports:
            if report.ok_to_cluster:
                cluster_id, bucket_id = get_cluster_bucket(manager, report)

                if cluster_id and bucket_id:
                    ReportEntry.objects.filter(id=report.id).update(
                        cluster_id=cluster_id, bucket_id=bucket_id
                    )
                else:
                    # Track unmatched reports for further clustering
                    unmatched_reports.append(report)
            else:
                # Low quality reports (empty text, low probability) go straight to by domain bucketing # noqa
                low_quality_reports.append(report)

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
        apply_domain_bucketing_fallback(remaining, report_entries)

        complete_job(job, success=True, buckets_created=buckets_created)
        LOG.info(
            f"Triage completed successfully. Created {buckets_created} new cluster buckets."
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
        status = ClusteringJob.get_clustering_status()

        if status.in_progress or not status.has_successful_run:
            reason = (
                "clustering is currently in progress"
                if status.in_progress
                else "no successful clustering run has occurred yet"
            )
            LOG.warning(f"Skipping triaging: {reason}")
            return

        # Create a job record for this triage run
        job = ClusteringJob.objects.create(job_type=ClusteringJobType.INCREMENTAL)
        run_triage(job)
