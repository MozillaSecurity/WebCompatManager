# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from collections.abc import Sequence
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity


class SBERTClusterer:
    """Clusters similar reports using SBERT embeddings."""

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5") -> None:
        self.model: SentenceTransformer = SentenceTransformer(model_name)

    def cluster(
        self, reports: list[Any], distance_threshold: float = 0.38
    ) -> tuple[Any, Any]:
        """Cluster reports using SBERT embeddings."""

        texts = [report.text for report in reports]
        embeddings = self.model.encode(
            texts, show_progress_bar=False, normalize_embeddings=True
        )

        if len(reports) < 2:
            # Single report: assign to cluster 0 with its embedding
            return [0], embeddings

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
        self, reports: list[Any], embeddings: Any
    ) -> int:
        """Find the report closest to the centroid.

        Args:
            reports: List of report objects with an 'id' attribute
            embeddings: Embeddings for the reports
        """

        # Early return for single-report clusters
        if len(reports) == 1:
            return reports[0].id

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

        return reports[closest_idx].id

    def build_embeddings(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(
            texts, show_progress_bar=False, normalize_embeddings=True
        )
        return np.asarray(embeddings, dtype=np.float32)

    def assign_to_cluster_knn(
        self,
        report_text: str,
        cluster_embeddings: dict[int, np.ndarray],
        cluster_sizes: dict[int, int],
        k: int = 5,
        min_votes: int = 2,
        min_similarity: float = 0.5,
    ) -> int | None:
        """Assign a report to a cluster using k-NN voting.

        Args:
            report_text: Text to classify
            cluster_embeddings: Dict mapping cluster IDs to their member embeddings
            cluster_sizes: Dict mapping cluster IDs to number of members
            k: Number of neighbors to consider
            min_votes: Minimum votes required to assign
            min_similarity: Minimum similarity threshold

        Returns:
            Cluster ID if match found, None otherwise
        """
        if not cluster_embeddings:
            return None

        # Encode incoming report
        x = self.model.encode(
            [report_text], show_progress_bar=False, normalize_embeddings=True
        )[0]
        x = np.asarray(x, dtype=np.float32)

        # Collect all neighbors across clusters
        all_neighbors = []
        for cluster_id, embs in cluster_embeddings.items():
            sims = embs @ x

            for sim in sims:
                if sim >= min_similarity:
                    all_neighbors.append((cluster_id, float(sim)))

        if not all_neighbors:
            return None

        # Sort by similarity (descending) and take top-k
        top_k = sorted(all_neighbors, key=lambda x: x[1], reverse=True)[:k]

        # Vote: count clusters
        votes = {}
        for cluster_id, sim in top_k:
            votes[cluster_id] = votes.get(cluster_id, 0) + 1

        # Find winner
        winner_cluster = max(votes, key=votes.get)
        winner_votes = votes[winner_cluster]

        # Adjust min_votes for small clusters
        cluster_size = cluster_sizes.get(winner_cluster, 1)
        min_votes_required = min(min_votes, cluster_size)

        if winner_votes >= min_votes_required:
            return winner_cluster

        return None
