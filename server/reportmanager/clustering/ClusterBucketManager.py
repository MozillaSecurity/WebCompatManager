# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging import getLogger
from typing import Any
from urllib.parse import urlsplit

import numpy as np
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from reportmanager.clustering.SBERTClusterer import SBERTClusterer
from reportmanager.models import Bucket, BucketHit, Cluster, ReportEntry
from reportmanager.utils import preprocess_text
from webcompat.models import Report

LOG = getLogger("reportmanager.clustering")


@dataclass
class ClusterEmbedding:
    """Cluster representation with embeddings for k-NN assignment."""
    cluster_id: int
    domain: str
    member_ids: list[int]
    member_embeddings: np.ndarray


@dataclass
class ClusterReport:
    """Report data structure used for clustering operations."""
    id: int
    ml_valid_probability: float
    reported_at: datetime
    url: str
    bucket_id: int | None
    text: str = ""
    domain: str = ""
    ok_to_cluster: bool = False


class ClusteringConfig:
    HIGH_VOLUME_WINDOW_DAYS = 30
    HIGH_VOLUME_THRESHOLD = 20  # reports per week
    HIGH_VOLUME_DISTANCE_THRESHOLD = 0.30
    NORMAL_VOLUME_DISTANCE_THRESHOLD = 0.38
    BATCH_SIZE = 500
    CLUSTER_BUCKET_IDENTIFIER = "[Cluster"
    DEFAULT_BUCKET_PRIORITY = 0
    MIN_VALID_PROBABILITY_SINGLE_REPORT = 0.60  # Minimum valid probability for single-report clusters


def batch_update_in_chunks(
    queryset: QuerySet,
    ids: list[int],
    batch_size: int = ClusteringConfig.BATCH_SIZE,
    **update_fields: Any,
) -> int:
    total_updated = 0
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
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
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        count, _ = queryset.filter(id__in=batch_ids).delete()
        total_deleted += count
    return total_deleted

class ClusterBucketManager:
    def __init__(self, clusterer: SBERTClusterer | None = None) -> None:
        self.clusterer = clusterer or SBERTClusterer()
        self.cluster_embeddings: dict[int, ClusterEmbedding] = {}

    def build_cluster_report(self, report_data: dict) -> ClusterReport:
        comments = report_data["comments_translated"] or report_data["comments"]
        preprocessed_text = preprocess_text(comments)

        try:
            parsed_url = urlsplit(report_data["url"])
            domain = parsed_url.hostname or "unknown"
        except Exception:
            domain = "unknown"

        report = ClusterReport(
            id=report_data["id"],
            ml_valid_probability=report_data["ml_valid_probability"],
            reported_at=report_data["reported_at"],
            url=report_data["url"],
            bucket_id=report_data["bucket_id"],
            text=preprocessed_text,
            domain=domain,
        )

        report.ok_to_cluster = ClusterBucketManager.ok_to_cluster(
            report.text, report.ml_valid_probability
        )

        return report

    def fetch_reports(self) -> list[ClusterReport]:
        reports_qs = ReportEntry.objects.exclude(comments="").filter(
            ml_valid_probability__gt=0.03
        )

        return [
            self.build_cluster_report(report_data)
            for report_data in reports_qs.values(
                "id",
                "comments",
                "comments_translated",
                "ml_valid_probability",
                "reported_at",
                "url",
                "bucket_id",
            )
        ]

    @staticmethod
    def ok_to_cluster(text: str, ml_valid_probability: float | None) -> bool:
        """Check if a report meets quality thresholds for clustering."""
        if not text or not text.strip():
            return False

        return ml_valid_probability is not None and ml_valid_probability > 0.03

    def group_reports_by_domain(
        self, reports: list[ClusterReport], domains: list[str] | None = None
    ) -> dict[str, list[ClusterReport]]:
        """Group reports by domain, optionally filtering to specific domains."""

        reports_by_domain = defaultdict(list)

        for report in reports:
            if not report.ok_to_cluster:
                continue

            # Filter by domains if specified
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

    def filter_recent_reports(self, reports: list[ClusterReport], days: int) -> list[ClusterReport]:
        cutoff_date = timezone.now() - timedelta(days=days)
        return [r for r in reports if r.reported_at >= cutoff_date]

    def build_domain_volume_map(
        self, reports_by_domain: dict[str, list[ClusterReport]]
    ) -> dict[str, str]:
        """Build a map of domain to volume level ('high' or 'normal')."""
        domain_volume_map = {}
        for domain, reports in reports_by_domain.items():
            is_high_volume = self.is_high_volume_domain(reports)
            domain_volume_map[domain] = "high" if is_high_volume else "normal"
        return domain_volume_map

    def group_reports_by_label(
        self, reports: list[ClusterReport], labels: list[int], embeddings: list
    ) -> dict[int, dict[str, list]]:
        clusters_dict: dict[int, dict[str, list]] = defaultdict(
            lambda: {"reports": [], "embeddings": []}
        )
        for label, report, embedding in zip(labels, reports, embeddings):
            clusters_dict[label]["reports"].append(report)
            clusters_dict[label]["embeddings"].append(embedding)
        return clusters_dict

    def build_clusters(
        self,
        clusters_dict: dict[int, dict[str, list]],
        domain: str,
    ) -> list[dict]:
        """Create cluster objects with centroids and reports."""

        clusters = []
        for cluster_data in clusters_dict.values():
            reports = cluster_data["reports"]

            # Skip creating single-report clusters if report has low validity probability
            if len(reports) == 1:
                report = reports[0]
                valid_prob = report.ml_valid_probability
                if valid_prob < ClusteringConfig.MIN_VALID_PROBABILITY_SINGLE_REPORT:
                    continue

            centroid_id = self.clusterer.find_centroid_for_cluster(
                reports, cluster_data["embeddings"]
            )
            clusters.append(
                {
                    "centroid_id": centroid_id,
                    "reports": reports,
                    "domain": domain,
                }
            )
        return clusters

    def cluster_domain_reports(
        self,
        domain: str,
        reports: list[ClusterReport],
    ) -> list[dict]:
        """Cluster reports for a single domain."""

        if len(reports) == 0:
            return []

        # Calculate if this is a high-volume domain
        # and if so, only use reports in the last 14 days
        is_high_volume = self.is_high_volume_domain(reports)

        if is_high_volume:
            reports = self.filter_recent_reports(
                reports, ClusteringConfig.HIGH_VOLUME_WINDOW_DAYS
            )

        if len(reports) == 0:
            return []

        # Use different thresholds for high vs normal volume
        threshold = (
            ClusteringConfig.HIGH_VOLUME_DISTANCE_THRESHOLD
            if is_high_volume
            else ClusteringConfig.NORMAL_VOLUME_DISTANCE_THRESHOLD
        )

        labels, embeddings = self.clusterer.cluster(reports, threshold)

        clusters_dict = self.group_reports_by_label(reports, labels, embeddings)
        clusters = self.build_clusters(clusters_dict, domain)

        return clusters

    def save_clusters(self, clusters: list[dict]) -> list[dict]:
        """Save clusters to db and add cluster DB IDs to cluster dicts."""

        with transaction.atomic():
            for cluster in clusters:
                cluster_obj = Cluster.objects.create(
                    domain=cluster["domain"],
                    centroid_id=cluster["centroid_id"],
                )

                cluster["cluster_id"] = cluster_obj.pk

                report_ids_in_cluster = [r.id for r in cluster["reports"]]
                batch_update_in_chunks(
                    ReportEntry.objects.all(),
                    report_ids_in_cluster,
                    cluster=cluster_obj,
                )

        return clusters

    def delete_existing_clusters(self) -> int:
        cluster_count = Cluster.objects.count()

        if cluster_count == 0:
            return 0

        ReportEntry.objects.filter(cluster__isnull=False).update(cluster=None)

        cluster_ids = list(Cluster.objects.values_list("id", flat=True))
        batch_delete_in_chunks(Cluster.objects.all(), cluster_ids)

        return cluster_count

    def delete_cluster_buckets(self) -> int:
        old_cluster_buckets = Bucket.objects.filter(
            description__contains=ClusteringConfig.CLUSTER_BUCKET_IDENTIFIER
        )

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

    def update_bucket_hits(self, reports_to_move, new_bucket_id: int):
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
            )

            # Reassign reports to new bucket
            reports_to_move = ReportEntry.objects.filter(id__in=report_ids)
            self.update_bucket_hits(reports_to_move, new_bucket.id)
            reports_to_move.update(bucket=new_bucket)

    def create_buckets_from_clusters(self, all_clusters: list[dict]) -> int:
        buckets_created = 0
        for cluster_data in all_clusters:
            report_ids = [r.id for r in cluster_data["reports"]]

            if not report_ids:
                continue

            self.create_bucket_for_cluster(
                cluster_data["domain"], cluster_data["cluster_id"], report_ids
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

    def load_cluster_embeddings(self, domains: list[str] | None = None) -> None:
        """Load cluster embeddings from existing clusters in the database."""

        clusters_qs = Cluster.objects.prefetch_related("reportentry_set")
        if domains:
            clusters_qs = clusters_qs.filter(domain__in=domains)
        clusters = clusters_qs.all()

        for cluster in clusters:
            reports = list(
                cluster.reportentry_set.exclude(comments="").values(
                    "id", "comments", "comments_translated"
                )
            )

            if not reports:
                continue

            processed_reports = []
            texts = []
            for r in reports:
                text = r["comments_translated"] or r["comments"]
                preprocessed = preprocess_text(text)
                if preprocessed:
                    texts.append(preprocessed)
                    processed_reports.append({"id": r["id"], "text": preprocessed})

            if not processed_reports:
                continue

            embeddings = self.clusterer.build_embeddings(texts)
            member_ids = [r["id"] for r in processed_reports]

            cluster_emb = ClusterEmbedding(
                cluster_id=cluster.id,
                domain=cluster.domain,
                member_ids=member_ids,
                member_embeddings=embeddings,
            )
            self.cluster_embeddings[cluster.id] = cluster_emb

    def get_closest_cluster(
        self,
        report: ClusterReport,
        is_high_volume: bool = False,
        k: int = 5,
        min_votes: int = 2,
    ) -> int | None:
        domain_embeddings = {
            cid: emb
            for cid, emb in self.cluster_embeddings.items()
            if emb.domain == report.domain
        }

        if not domain_embeddings:
            return None

        embeddings = {cid: emb.member_embeddings for cid, emb in domain_embeddings.items()}
        size = {cid: len(emb.member_ids) for cid, emb in domain_embeddings.items()}

        distance_threshold = (
            ClusteringConfig.HIGH_VOLUME_DISTANCE_THRESHOLD
            if is_high_volume
            else ClusteringConfig.NORMAL_VOLUME_DISTANCE_THRESHOLD
        )

        min_similarity = 1.0 - distance_threshold

        cluster_id = self.clusterer.assign_to_cluster_knn(
            report.text,
            embeddings,
            size,
            k=k,
            min_votes=min_votes,
            min_similarity=min_similarity,
        )

        return cluster_id
