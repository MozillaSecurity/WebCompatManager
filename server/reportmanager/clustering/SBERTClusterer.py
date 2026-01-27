# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from collections.abc import Sequence
from typing import Any

from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity


class SBERTClusterer:
    """Clusters similar reports using SBERT embeddings."""

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5") -> None:
        self.model: SentenceTransformer = SentenceTransformer(model_name)

    def cluster(
        self, reports: list[dict[str, Any]], distance_threshold: float = 0.38
    ) -> tuple[Any, Any]:
        """Cluster reports using SBERT embeddings."""

        if len(reports) < 2:
            return [0], []

        texts = [report["text"] for report in reports]
        embeddings = self.model.encode(
            texts, show_progress_bar=False, normalize_embeddings=True
        )

        similarities = cosine_similarity(embeddings)
        distances = 1 - similarities

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric="precomputed",
            linkage="average",
        )

        labels = clustering.fit_predict(distances)

        return labels, embeddings

    def euclidean_distance(self, emb1: Sequence[float], emb2: Sequence[float]) -> float:
        """Calculate Euclidean distance between two embeddings."""
        return sum((a - b) ** 2 for a, b in zip(emb1, emb2)) ** 0.5

    def find_centroid_for_cluster(
        self, reports: list[dict[str, Any]], embeddings: Any
    ) -> int:
        """Find the report closest to the centroid."""

        # Early return for single-report clusters
        if len(reports) == 1:
            return reports[0]["id"]

        report_embeddings = list(embeddings)
        embedding_dim = len(report_embeddings[0])
        centroid = [
            sum(emb[j] for emb in report_embeddings) / len(report_embeddings)
            for j in range(embedding_dim)
        ]

        # Find report closest to centroid
        distances = [
            self.euclidean_distance(emb, centroid) for emb in report_embeddings
        ]
        closest_idx = distances.index(min(distances))

        return reports[closest_idx]["id"]
