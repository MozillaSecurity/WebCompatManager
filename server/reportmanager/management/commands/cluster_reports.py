# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from logging import getLogger

from django.core.management import BaseCommand
from django.utils import timezone

from reportmanager.clustering.ClusterBucketManager import ClusterBucketManager
from reportmanager.models import ClusteringJob, ClusteringJobType

LOG = getLogger("reportmanager.cluster")


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


def run_clustering(domain_filter: str | None, job: ClusteringJob) -> None:
    try:
        manager = ClusterBucketManager()

        # Clean up in case there was a previous run
        deleted_clusters_count = manager.delete_existing_clusters(domain_filter)
        deleted_buckets_count = manager.delete_cluster_buckets(domain_filter)

        LOG.info(f"Deleted {deleted_clusters_count} existing clusters.")
        LOG.info(f"Deleted {deleted_buckets_count} cluster-based buckets...")

        all_reports = manager.fetch_reports(domain_filter)
        reports_by_domain = manager.group_reports_by_domain(all_reports)

        if domain_filter:
            if domain_filter in reports_by_domain:
                LOG.info(f"Filtering to domain: {domain_filter}")
            else:
                LOG.info(f"No reports found for domain: {domain_filter}")
                complete_job(job, success=True, buckets_created=0)
                return

        LOG.info(f"Clustering {len(all_reports)} reports...")
        all_clusters = []
        for domain, reports in reports_by_domain.items():
            domain_clusters = manager.cluster_domain_reports(domain, reports)
            all_clusters.extend(domain_clusters)

        if not all_clusters:
            LOG.warning("No clusters created.")
            complete_job(job, success=True, buckets_created=0)
            return

        LOG.info(f"Saving {len(all_clusters)} clusters to db.")

        all_clusters = manager.save_clusters(all_clusters)
        buckets_count = manager.create_buckets_from_clusters(all_clusters)

        LOG.info(f"Created {buckets_count} cluster-based buckets.")

        complete_job(job, success=True, buckets_created=buckets_count)

    except Exception as e:
        complete_job(job, success=False, error=str(e))
        raise


class Command(BaseCommand):
    help = "Cluster similar reports within domains and create buckets for each cluster"

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            type=str,
            help="Cluster reports for a specific domain only",
        )

    def handle(self, domain: str | None = None, **options) -> None:
        status = ClusteringJob.get_clustering_status()

        if status.in_progress:
            LOG.warning("Clustering is already in progress. Skipping this run.")
            return

        job = ClusteringJob.objects.create(
            domain=domain, job_type=ClusteringJobType.FULL
        )
        run_clustering(domain, job)
