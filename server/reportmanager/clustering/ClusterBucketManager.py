# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import batched
from typing import Any

import numpy as np
from django.db import transaction
from django.db.models import Count, QuerySet
from django.utils import timezone

from reportmanager.clustering.SBERTClusterer import SBERTClusterer
from reportmanager.models import Bucket, BucketHit, Cluster, ReportEntry


@dataclass
class DomainClusterData:
    """Domain-specific clustering data including distance threshold and embeddings."""

    domain: str
    distance_threshold: float
    embeddings: dict[int, np.ndarray]  # cluster_id -> embeddings


@dataclass
class ClusterReport:
    id: int
    ml_valid_probability: float
    reported_at: datetime
    url: str
    bucket_id: int | None
    text: str = ""
    domain: str = ""

    @property
    def ok_to_cluster(self) -> bool:
        return ClusterBucketManager.ok_to_cluster(self.text, self.ml_valid_probability)


@dataclass
class ClusterData:
    centroid_id: int
    reports: list[ClusterReport]
    domain: str
    id: int | None = None


@dataclass
class ClusterGroup:
    """Intermediate structure for grouping reports and embeddings by cluster label."""

    reports: list[ClusterReport]
    embeddings: list[np.ndarray]


class ClusteringConfig:
    """Configuration parameters for similarity-based report clustering.

    This class defines thresholds and parameters for both:
    1. Initial clustering: Grouping similar reports into clusters using
       agglomerative clustering with average linkage (see SBERTClusterer.cluster)
    2. Assignment: Adding new incoming reports to existing clusters using
       top-N average similarity

    Distance threshold strategy:

    The distance threshold for agglomerative clustering is calculated dynamically
    per domain using a volume-based strategy (see dynamic_threshold method):

    - High-volume domains: Stricter thresholds (MIN_DISTANCE_THRESHOLD) to avoid
      over-clustering, using only recent reports
    - Low-volume domains: Permissive thresholds (MAX_DISTANCE_THRESHOLD) to ensure
      enough grouping, using all historical reports
    - Mid-volume domains: Sigmoid transition between the min and max

    Threshold interpretation:
    - Lower threshold = stricter clustering = only very similar reports group together
    - Higher threshold = more permissive clustering = somewhat similar reports
      can group together

    Example:
    - Distance 0.30 means reports must be 70% similar to cluster together
    - Distance 0.38 means reports must be 62% similar to cluster together

    Assignment buffer:
    - ASSIGNMENT_SIMILARITY_BUFFER compensates for top-N avg being more permissive
      than average linkage clustering, preventing false positive assignments to
      existing clusters
    """

    # Reports per week to classify domain as high-volume
    HIGH_VOLUME_THRESHOLD = 20
    # For high-volume domains, only cluster reports from last N days
    HIGH_VOLUME_WINDOW_DAYS = 14

    # Threshold for high-volume domains (70% similarity required)
    MIN_DISTANCE_THRESHOLD = 0.30
    # Threshold for normal-volume domains (62% similarity required)
    MAX_DISTANCE_THRESHOLD = 0.38

    # This arbitrary buffer added to similarity threshold when assigning
    # incoming reports to clusters. This compensates for the fact that
    # top-N avg produces higher similarity scores than agglomerative
    # clustering with average linkage.
    #
    # Why: Top-N avg picks the best N matches from a cluster, while average
    # linkage (used in initial clustering) averages over all members. This means
    # top-N avg will assign reports to clusters more aggressively.
    #
    # The buffer provides margin to prevent borderline false positives
    # where top-N avg accepts reports based on a few high matches despite
    # overall weak cluster fit.
    ASSIGNMENT_SIMILARITY_BUFFER = 0.05

    # Minimum ML confidence for single-report clusters
    MIN_VALID_PROBABILITY_SINGLE_REPORT = 0.60
    # Number of records to process per batch to avoid SQL variable limits
    BATCH_SIZE = 500
    # Identifier in bucket description for cluster-based buckets
    CLUSTER_BUCKET_IDENTIFIER = "[Cluster"
    DEFAULT_BUCKET_PRIORITY = 0


def batch_update_in_chunks(
    queryset: QuerySet,
    ids: list[int],
    batch_size: int = ClusteringConfig.BATCH_SIZE,
    **update_fields: Any,
) -> int:
    total_updated = 0
    for batch_ids in batched(ids, batch_size):
        count = queryset.filter(id__in=batch_ids).update(**update_fields)
        total_updated += count
    return total_updated


def batch_delete_in_chunks(
    queryset: QuerySet,
    ids: list[int],
    batch_size: int = ClusteringConfig.BATCH_SIZE,
) -> int:
    """Delete objects in batches to avoid 'too many SQL variables' error."""
    total_deleted = 0
    for batch_ids in batched(ids, batch_size):
        count, _ = queryset.filter(id__in=batch_ids).delete()
        total_deleted += count
    return total_deleted


class ClusterBucketManager:
    def __init__(self) -> None:
        self.clusterer = SBERTClusterer()

    def build_cluster_report(self, report_data: dict) -> ClusterReport:
        report = ClusterReport(
            id=report_data["id"],
            ml_valid_probability=report_data["ml_valid_probability"],
            reported_at=report_data["reported_at"],
            url=report_data["url"],
            bucket_id=report_data["bucket_id"],
            text=report_data["comments_preprocessed"],
            domain=report_data["domain"],
        )

        return report

    def fetch_reports(self, domain: str | None = None) -> list[ClusterReport]:
        reports_qs = ReportEntry.objects.exclude(comments_preprocessed="").filter(
            ml_valid_probability__gt=0.03
        )

        reports = [
            self.build_cluster_report(report_data)
            for report_data in reports_qs.values(
                "id",
                "comments_preprocessed",
                "ml_valid_probability",
                "reported_at",
                "url",
                "bucket_id",
                "domain",
            )
        ]

        if domain:
            reports = [r for r in reports if r.domain == domain]

        return reports

    @staticmethod
    def ok_to_cluster(text: str, ml_valid_probability: float | None) -> bool:
        """Check if a report meets quality thresholds for clustering."""
        if not text or not text.strip():
            return False

        return ml_valid_probability is not None and ml_valid_probability > 0.03

    def group_reports_by_domain(
        self, reports: list[ClusterReport], domains: set[str] | None = None
    ) -> dict[str, list[ClusterReport]]:
        """Group reports by domain, optionally filtering to specific domains."""

        reports_by_domain = defaultdict(list)

        for report in reports:
            if not report.ok_to_cluster:
                continue

            if domains and report.domain not in domains:
                continue

            reports_by_domain[report.domain].append(report)

        return reports_by_domain

    def is_high_volume_domain(self, reports: list[ClusterReport]) -> bool:
        """Determine if a domain is high-volume based on average weekly reports."""

        report_count = len(reports)
        dates = [r.reported_at for r in reports]
        min_date = min(dates)
        max_date = max(dates)
        days_span = (max_date - min_date).days + 1
        avg_weekly_reports = (report_count / days_span) * 7
        return avg_weekly_reports > ClusteringConfig.HIGH_VOLUME_THRESHOLD

    def filter_recent_reports(
        self, reports: list[ClusterReport], days: int
    ) -> list[ClusterReport]:
        cutoff_date = timezone.now() - timedelta(days=days)
        return [r for r in reports if r.reported_at >= cutoff_date]

    def group_reports_by_label(
        self, reports: list[ClusterReport], labels: np.ndarray, embeddings: np.ndarray
    ) -> list[ClusterGroup]:
        """Group reports and their embeddings by cluster label."""

        assert len(reports) == len(labels) == len(embeddings), (
            f"Length mismatch detected: reports={len(reports)}, "
            f"labels={len(labels)}, embeddings={len(embeddings)}"
        )

        grouped: dict[Any, ClusterGroup] = defaultdict(lambda: ClusterGroup([], []))

        for label, report, embedding in zip(labels, reports, embeddings):
            group = grouped[label]
            group.reports.append(report)
            group.embeddings.append(embedding)

        return list(grouped.values())

    def build_clusters(
        self,
        cluster_groups: list[ClusterGroup],
        domain: str,
    ) -> list[ClusterData]:
        """Create cluster objects with centroids and reports."""

        clusters = []
        for cluster_group in cluster_groups:
            reports = cluster_group.reports

            # Skip creating single-report clusters if report has
            # low validity probability
            if (
                len(reports) == 1
                and reports[0].ml_valid_probability
                < ClusteringConfig.MIN_VALID_PROBABILITY_SINGLE_REPORT
            ):
                continue

            centroid_idx = self.clusterer.find_centroid_index(
                np.array(cluster_group.embeddings)
            )
            centroid_id = reports[centroid_idx].id
            clusters.append(
                ClusterData(
                    centroid_id=centroid_id,
                    reports=reports,
                    domain=domain,
                )
            )
        return clusters

    @staticmethod
    def dynamic_threshold(report_count, min, max, center=100, steepness=0.05):
        """Calculate dynamic clustering threshold using sigmoid transition.

        Args:
            report_count: Number of reports for the domain
            min: Minimum threshold for high-volume domains (strict clustering)
            max: Maximum threshold for low-volume domains (lenient clustering)
            center: Report count where threshold is halfway between min and max.
                Based on a 60-day window analysis: 98% of domains have 1-10 reports,
                ~1.8% have 10-100 reports, and only 0.2% have >100 reports. Default 100
                keeps most domains lenient (98% well below center), gradually tightens
                for the ~300 mid-volume domains, and reaches strict clustering for the
                top 0.2%.
            steepness: Controls transition speed. Default 0.05 creates gradual
                ~100-report transition (at 50: ≈0.37, at 100: ≈0.34, at 150: ≈0.31).

        Returns:
            float: Clustering distance threshold

        Note that these parameters are initial estimates and may need tuning. There is
        some uncertainty about the best value and volume-based approach might not be ideal
        and may require some experimentation with calculating threshold based on how diverse
        reports are within each domain instead.
        """
        # Sigmoid from high → low as volume increases
        blend = 1.0 / (1.0 + np.exp(-steepness * (report_count - center)))
        return max * (1 - blend) + min * blend

    def cluster_domain_reports(
        self,
        domain: str,
        reports: list[ClusterReport],
    ) -> list[ClusterData]:
        """Cluster reports for a single domain."""

        if len(reports) == 0:
            return []

        # Calculate if this is a high-volume domain
        # and if so, only use reports in the last N days
        is_high_volume = self.is_high_volume_domain(reports)

        if is_high_volume:
            reports = self.filter_recent_reports(
                reports, ClusteringConfig.HIGH_VOLUME_WINDOW_DAYS
            )

        if len(reports) == 0:
            return []

        # Use different thresholds for high vs normal volume
        threshold = self.dynamic_threshold(
            report_count=len(reports),
            min=ClusteringConfig.MIN_DISTANCE_THRESHOLD,
            max=ClusteringConfig.MAX_DISTANCE_THRESHOLD,
        )

        texts = [report.text for report in reports]
        labels, embeddings = self.clusterer.cluster(texts, threshold)

        clustered_groups = self.group_reports_by_label(reports, labels, embeddings)
        clusters = self.build_clusters(clustered_groups, domain)

        return clusters

    def save_clusters(self, clusters: list[ClusterData]) -> list[ClusterData]:
        with transaction.atomic():
            for cluster in clusters:
                cluster_obj = Cluster.objects.create(
                    domain=cluster.domain,
                    centroid_id=cluster.centroid_id,
                )

                cluster.id = cluster_obj.pk

                report_ids_in_cluster = [r.id for r in cluster.reports]
                batch_update_in_chunks(
                    ReportEntry.objects.all(),
                    report_ids_in_cluster,
                    cluster=cluster_obj,
                )

        return clusters

    def delete_existing_clusters(self, domain: str | None = None) -> int:
        clusters_qs = Cluster.objects.all()

        if domain:
            clusters_qs = clusters_qs.filter(domain=domain)

        cluster_count = clusters_qs.count()

        if cluster_count == 0:
            return 0

        # Unassign reports from these clusters
        ReportEntry.objects.filter(cluster__in=clusters_qs).update(cluster=None)

        cluster_ids = list(clusters_qs.values_list("id", flat=True))
        batch_delete_in_chunks(Cluster.objects.all(), cluster_ids)

        return cluster_count

    def delete_cluster_buckets(self, domain: str | None = None) -> int:
        old_cluster_buckets = Bucket.objects.filter(
            description__contains=ClusteringConfig.CLUSTER_BUCKET_IDENTIFIER
        )

        if domain:
            old_cluster_buckets = old_cluster_buckets.filter(domain=domain)

        bucket_count = old_cluster_buckets.count()

        if bucket_count == 0:
            return 0

        # Unassign reports from these buckets (to avoid CASCADE delete)
        ReportEntry.objects.filter(bucket__in=old_cluster_buckets).update(bucket=None)

        # Delete buckets in batches to avoid SQL variable limit
        # This also deletes related BucketHit and BucketWatch records via CASCADE
        bucket_ids = list(old_cluster_buckets.values_list("id", flat=True))
        batch_delete_in_chunks(Bucket.objects.all(), bucket_ids)

        return bucket_count

    def build_cluster_bucket_signature(self, domain: str, cluster_id: int) -> str:
        """Build a signature JSON for a cluster bucket."""

        signature = {
            "symptoms": [
                {"type": "url", "part": "hostname", "value": domain},
                {"type": "cluster_id", "value": str(cluster_id)},
            ]
        }
        return json.dumps(signature, sort_keys=True)

    def update_bucket_hits(self, reports_to_move: QuerySet, new_bucket_id: int) -> None:
        """Update BucketHit counts when moving reports to a new bucket."""

        for report in reports_to_move.values("reported_at", "bucket_id"):
            if report["bucket_id"]:
                BucketHit.decrement_count(report["bucket_id"], report["reported_at"])
            BucketHit.increment_count(new_bucket_id, report["reported_at"])

    def create_bucket_for_cluster(
        self, domain: str, cluster_id: int, report_ids: list[int]
    ) -> None:
        """Create a new bucket for a cluster and reassign reports."""

        signature = self.build_cluster_bucket_signature(domain, cluster_id)

        with transaction.atomic():
            new_bucket = Bucket.objects.create(
                description=f"{domain} {ClusteringConfig.CLUSTER_BUCKET_IDENTIFIER} {cluster_id}]",  # noqa
                signature=signature,
                priority=ClusteringConfig.DEFAULT_BUCKET_PRIORITY,
                color=None,
                bug=None,
                domain=domain,
                cluster_id=cluster_id,
            )

            # Reassign reports to new bucket
            reports_to_move = ReportEntry.objects.filter(id__in=report_ids)
            self.update_bucket_hits(reports_to_move, new_bucket.id)
            reports_to_move.update(bucket=new_bucket)

    def create_buckets_from_clusters(self, all_clusters: list[ClusterData]) -> int:
        buckets_created = 0
        for cluster_data in all_clusters:
            report_ids = [r.id for r in cluster_data.reports]

            if not report_ids:
                continue

            if cluster_data.id is None:
                print(
                    f"Attempted to create a bucket for cluster without id for domain {cluster_data.domain}"  # noqa
                )
                continue

            self.create_bucket_for_cluster(
                cluster_data.domain, cluster_data.id, report_ids
            )
            buckets_created += 1

        return buckets_created

    def get_bucket_for_cluster(self, cluster_id: int) -> Bucket | None:
        cluster = Cluster.objects.filter(id=cluster_id).first()
        if not cluster:
            return None

        signature = self.build_cluster_bucket_signature(cluster.domain, cluster_id)
        bucket = Bucket.objects.filter(signature=signature).first()
        return bucket

    def calculate_domain_thresholds(self, domains: set[str]) -> dict[str, float]:
        """Calculate dynamic distance thresholds for domains based on report volume."""
        domain_thresholds = {}

        for batch_domains in batched(domains, 500):
            domain_stats = (
                ReportEntry.objects.filter(domain__in=batch_domains)
                .filter(ml_valid_probability__gt=0.03)
                .exclude(comments_preprocessed="")
                .values("domain")
                .annotate(report_count=Count("id"))
            )

            for stats in domain_stats:
                domain = stats["domain"]
                report_count = stats["report_count"]

                threshold = self.dynamic_threshold(
                    report_count=report_count,
                    min=ClusteringConfig.MIN_DISTANCE_THRESHOLD,
                    max=ClusteringConfig.MAX_DISTANCE_THRESHOLD,
                )
                domain_thresholds[domain] = threshold

        return domain_thresholds

    def build_domain_data(
        self,
        domains: set[str] | None = None,
    ) -> dict[str, DomainClusterData]:
        """Build domain data: threshold based on volume and cluster embeddings."""

        domain_data: dict[str, DomainClusterData] = {}

        if not domains:
            return domain_data

        domain_thresholds = self.calculate_domain_thresholds(domains=domains)

        texts_by_domain: dict[str, dict[int, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for batch_domains in batched(domains, 500):
            clustered_reports = (
                Cluster.objects.filter(domain__in=batch_domains)
                .values(
                    "id",
                    "domain",
                    "reportentry__id",
                    "reportentry__comments_preprocessed",
                )
                .exclude(reportentry__comments_preprocessed="")
            )

            for row in clustered_reports:
                if row["reportentry__id"] is None:
                    continue

                preprocessed = row["reportentry__comments_preprocessed"]

                if preprocessed:
                    texts_by_domain[row["domain"]][row["id"]].append(preprocessed)

        for domain, clusters in texts_by_domain.items():
            distance_threshold = domain_thresholds.get(
                domain, ClusteringConfig.MAX_DISTANCE_THRESHOLD
            )

            cluster_embeddings = {
                cluster_id: self.clusterer.build_embeddings(texts)
                for cluster_id, texts in clusters.items()
                if texts
            }

            if cluster_embeddings:
                domain_data[domain] = DomainClusterData(
                    domain=domain,
                    distance_threshold=distance_threshold,
                    embeddings=cluster_embeddings,
                )

        return domain_data

    def get_closest_cluster(
        self,
        report: ClusterReport,
        domain_data: dict[str, DomainClusterData],
    ) -> int | None:
        """Find the closest cluster for a report."""

        data = domain_data.get(report.domain)

        if not data or not data.embeddings:
            return None

        domain_threshold = 1.0 - data.distance_threshold
        min_similarity = (
            domain_threshold + ClusteringConfig.ASSIGNMENT_SIMILARITY_BUFFER
        )

        cluster_id = self.clusterer.assign_to_cluster_top_n_avg(
            report.text,
            data.embeddings,
            n=5,
            min_similarity=min_similarity,
        )

        return cluster_id
