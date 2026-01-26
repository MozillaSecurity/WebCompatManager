# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import json
from collections import defaultdict
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from reportmanager.Clustering.SBERTClusterer import SBERTClusterer
from reportmanager.models import Bucket, BucketHit, Cluster, ReportEntry
from reportmanager.utils import preprocess_text


class ClusteringConfig:
    HIGH_VOLUME_WINDOW_DAYS = 14
    HIGH_VOLUME_THRESHOLD = 20  # reports per week
    HIGH_VOLUME_DISTANCE_THRESHOLD = 0.30
    NORMAL_VOLUME_DISTANCE_THRESHOLD = 0.38
    BATCH_SIZE = 500
    CLUSTER_BUCKET_IDENTIFIER = "[Cluster"
    DEFAULT_BUCKET_PRIORITY = 0


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


def deduplicate_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove exact word-for-word duplicates within each cluster."""

    deduped = []

    seen_texts = set()
    for report in reports:
        if report["text"] not in seen_texts:
            seen_texts.add(report["text"])
            deduped.append(report)

    return deduped


class ClusterBucketManager:
    def __init__(self, clusterer: SBERTClusterer | None = None) -> None:
        self.clusterer = clusterer or SBERTClusterer()

    def fetch_reports(self) -> list[dict[str, Any]]:
        reports_qs = ReportEntry.objects.exclude(comments="").filter(
            ml_valid_probability__gt=0.03
        )

        all_reports = list(
            reports_qs.values(
                "id",
                "comments",
                "comments_translated",
                "ml_valid_probability",
                "reported_at",
                "url",
            )
        )

        return all_reports

    def group_reports_by_domain(self, reports: list[dict]) -> dict[str, list[dict]]:
        reports_by_domain = defaultdict(list)

        for report in reports:
            text = report["comments_translated"] or report["comments"]

            if text and text.strip():
                try:
                    parsed_url = urlsplit(report["url"])
                    domain = parsed_url.hostname or "unknown"
                except Exception:
                    domain = "unknown"

                report["text"] = preprocess_text(text)
                report["domain"] = domain
                reports_by_domain[domain].append(report)

        return reports_by_domain

    def is_high_volume_domain(self, reports: list[dict]) -> bool:
        """Determine if a domain is high-volume based on average weekly reports."""

        report_count = len(reports)
        dates = [r["reported_at"] for r in reports]
        min_date = min(dates)
        max_date = max(dates)
        days_span = (max_date - min_date).days + 1
        avg_weekly_reports = (report_count / days_span) * 7
        return avg_weekly_reports > ClusteringConfig.HIGH_VOLUME_THRESHOLD

    def filter_recent_reports(self, reports: list[dict], days: int) -> list[dict]:
        cutoff_date = timezone.now() - timedelta(days=days)
        return [r for r in reports if r["reported_at"] >= cutoff_date]

    def group_reports_by_label(
        self, reports: list[dict], labels: list[int], embeddings: list
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
        """Create cluster objects with centroids and deduplicated reports."""

        clusters = []
        for cluster_data in clusters_dict.values():
            centroid_id = self.clusterer.find_centroid_for_cluster(
                cluster_data["reports"], cluster_data["embeddings"]
            )
            clusters.append(
                {
                    "centroid_id": centroid_id,
                    "reports": deduplicate_reports(cluster_data["reports"]),
                    "domain": domain,
                }
            )
        return clusters

    def cluster_domain_reports(
        self,
        domain: str,
        reports: list[dict],
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

                report_ids_in_cluster = [r["id"] for r in cluster["reports"]]
                batch_update_in_chunks(
                    ReportEntry.objects.all(),
                    report_ids_in_cluster,
                    cluster=cluster_obj,
                )

        return clusters

    def delete_existing_clusters(self) -> int:
        cluster_count = Cluster.objects.count()
        Cluster.objects.all().delete()
        return cluster_count

    def delete_cluster_buckets(self) -> int:
        old_cluster_buckets = Bucket.objects.filter(
            description__contains=ClusteringConfig.CLUSTER_BUCKET_IDENTIFIER
        )

        bucket_count = old_cluster_buckets.count()

        # Unassign reports from these buckets (to avoid CASCADE delete)
        ReportEntry.objects.filter(bucket__in=old_cluster_buckets).update(bucket=None)

        # Besides clusters this would delete related BucketHit and BucketWatch records
        old_cluster_buckets.delete()

        return bucket_count

    def create_cluster_bucket_signature(self, domain: str, cluster_id: int) -> str:
        """Create a signature JSON for a cluster bucket."""

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

        signature = self.create_cluster_bucket_signature(domain, cluster_id)

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
            report_ids = [r["id"] for r in cluster_data["reports"]]

            if not report_ids:
                continue

            self.create_bucket_for_cluster(
                cluster_data["domain"], cluster_data["cluster_id"], report_ids
            )
            buckets_created += 1

        return buckets_created
