# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from logging import getLogger

from django.core.management import BaseCommand

from reportmanager.clustering.ClusterBucketManager import ClusterBucketManager

LOG = getLogger("reportmanager.cluster")


class Command(BaseCommand):
    help = "Cluster similar reports within domains and create buckets for each cluster"

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            type=str,
            help="Cluster reports for a specific domain only",
        )

    def handle(self, domain: str | None = None, **options) -> None:
        domain_filter = domain
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
                return

        LOG.info(f"Clustering {len(all_reports)} reports...")
        all_clusters = []
        for domain, reports in reports_by_domain.items():
            domain_clusters = manager.cluster_domain_reports(domain, reports)
            all_clusters.extend(domain_clusters)

        if not all_clusters:
            LOG.warning("No clusters created.")
            return

        LOG.info(f"Saving {len(all_clusters)} clusters to db.")

        all_clusters = manager.save_clusters(all_clusters)
        buckets_count = manager.create_buckets_from_clusters(all_clusters)

        LOG.info(f"Created {buckets_count} cluster-based buckets.")
