from django.core.management import BaseCommand, call_command
from logging import getLogger

from django.db.models import Q
from reportmanager.models import Bucket, ReportEntry

from reportmanager.clustering.ClusterBucketManager import (
    ClusterBucketManager,
    ClusteringConfig,
    ClusterReport,
)

LOG = getLogger("reportmanager.triage")

class Command(BaseCommand):
    help = (
        "Iterates over all unbucketed report entries that have never been triaged "
        "before to assign them into the existing buckets."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = ClusterBucketManager()
        # Memoize bucket lookups by domain
        self.known_bucket_ids: dict[str, int] = {}

    def cluster_unmatched_reports(
        self,
        unmatched_reports: list[ClusterReport],
    ) -> set:
        """Cluster unmatched reports to find groups among remaining reports."""

        if not unmatched_reports:
            return set()

        LOG.info(f"Processing {len(unmatched_reports)} unmatched reports for potential clustering...")

        unmatched_by_domain = self.manager.group_reports_by_domain(unmatched_reports)

        clustered_report_ids = set()

        for domain, domain_reports in unmatched_by_domain.items():
            LOG.info(f"Clustering {len(domain_reports)} unmatched reports for domain: {domain}")

            clusters = self.manager.cluster_domain_reports(domain, domain_reports)

            if not clusters:
                continue

            clusters_with_ids = self.manager.save_clusters(clusters)
            self.manager.create_buckets_from_clusters(clusters_with_ids)

            # Track which reports were successfully clustered
            for cluster_data in clusters_with_ids:
                for report in cluster_data["reports"]:
                    clustered_report_ids.add(report.id)

        return clustered_report_ids

    def apply_domain_bucketing_fallback(
        self,
        unmatched_reports: list[ClusterReport],
        report_entries: dict[int, ReportEntry],
    ) -> int:
        """Add unclustered reports to defalt domain-based buckets."""
        if not unmatched_reports:
            return 0

        LOG.info(f"Applying domain-based bucketing to {len(unmatched_reports)} reports that didn't cluster")
        reports_bucketed = 0

        for report in unmatched_reports:
            # Check memoized buckets
            bucket_id = self.known_bucket_ids.get(report.domain)

            if not bucket_id:
                # Find existing domain-based bucket (exclude cluster buckets)
                bucket_id = Bucket.objects.filter(
                    Q(domain=report.domain)
                ).exclude(
                    description__contains=ClusteringConfig.CLUSTER_BUCKET_IDENTIFIER
                ).values_list("id", flat=True).first()

            if not bucket_id:
                report_entry = report_entries[report.id]
                report_obj = report_entry.get_report()

                bucket = Bucket.objects.create(
                    description=f"domain is {report.domain}",
                    signature=report_obj.create_signature().raw_signature,
                )
                bucket_id = bucket.pk

            self.known_bucket_ids[report.domain] = bucket_id
            ReportEntry.objects.filter(id=report.id).update(bucket_id=bucket_id)
            reports_bucketed += 1

        LOG.info(f"Applied domain-based bucketing to {reports_bucketed} reports")
        return reports_bucketed

    def handle(self, *args, **options):
        report_entries_qs = ReportEntry.objects.select_related('app', 'os', 'breakage_category').all()
        report_entries = {entry.id: entry for entry in report_entries_qs}

        all_reports = [
            self.manager.build_cluster_report({
                "id": entry.id,
                "comments": entry.comments,
                "comments_translated": entry.comments_translated,
                "ml_valid_probability": entry.ml_valid_probability,
                "reported_at": entry.reported_at,
                "url": entry.url,
                "bucket_id": entry.bucket_id,
            })
            for entry in report_entries_qs
        ]

        unbucketed_reports = [r for r in all_reports if r.bucket_id is None]

        LOG.info(f"Unbucketed reports to triage: {len(unbucketed_reports)}")

        if not unbucketed_reports:
            LOG.info("No unbucketed reports to triage")
            return

        # Build domain volume map containing only domains of reports that need bucketing
        domains = list(set(r.domain for r in unbucketed_reports if r.domain))
        reports_by_domain = self.manager.group_reports_by_domain(all_reports, domains)
        domain_volume_map = self.manager.build_domain_volume_map(reports_by_domain)

        # Load cluster embeddings only for domains with unbucketed reports
        self.manager.load_cluster_embeddings(domains=domains)

        unmatched_reports = []
        low_quality_reports = []

        for report in unbucketed_reports:
            if report.ok_to_cluster:
                is_high_volume = domain_volume_map.get(report.domain, "normal") == "high"

                cluster_id = self.manager.get_closest_cluster(
                    report,
                    is_high_volume=is_high_volume,
                    k=5,
                    min_votes=5,
                )

                if cluster_id:
                    cluster_bucket = self.manager.get_bucket_for_cluster(cluster_id)
                    bucket_id = cluster_bucket.pk if cluster_bucket else None

                    ReportEntry.objects.filter(id=report.id).update(
                        cluster_id=cluster_id,
                        bucket_id=bucket_id
                    )
                else:
                    # Track unmatched reports for further clustering
                    unmatched_reports.append(report)
            else:
                # Low quality reports (empty text, low probability) go straight to domain bucketing
                low_quality_reports.append(report)

        # Cluster unmatched reports that might form clusters among themselves
        clustered_report_ids = self.cluster_unmatched_reports(unmatched_reports)

        # Filter out reports that were successfully clustered
        still_unmatched = [r for r in unmatched_reports if r.id not in clustered_report_ids]

        # Fall back to domain-based bucketing for reports that still don't have clusters
        # and low-quality reports
        reports_for_fallback = still_unmatched + low_quality_reports
        self.apply_domain_bucketing_fallback(reports_for_fallback, report_entries)
