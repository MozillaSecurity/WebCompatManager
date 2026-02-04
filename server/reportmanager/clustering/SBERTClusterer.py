# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity


class SBERTClusterer:
    """Clusters similar reports using SBERT embeddings."""

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5") -> None:
        self.model: SentenceTransformer = SentenceTransformer(model_name)

    def cluster(
        self, texts: list[str], distance_threshold: float
    ) -> tuple[np.ndarray, np.ndarray]:
        """Cluster text documents using SBERT embeddings and agglomerative clustering.

        Returns:
            Tuple of (labels, embeddings) where both are numpy arrays.
            labels: Array of cluster IDs (integers) for each text.
                   Example: [0, 1, 0, 2, 1] means texts 0 and 2 are in cluster 0,
                   texts 1 and 4 are in cluster 1, and text 3 is in cluster 2.
            embeddings: Array of SBERT embeddings for each text
        """
        embeddings = self.model.encode(
            texts, show_progress_bar=False, normalize_embeddings=True
        )

        if len(texts) < 2:
            # Single text: assign to cluster 0 with its embedding
            return np.array([0]), embeddings

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

    def find_centroid_index(self, embeddings: np.ndarray) -> int:
        """Find the index of the embedding closest to the centroid."""
        # Early return for single-item clusters
        if len(embeddings) == 1:
            return 0

        centroid = np.mean(embeddings, axis=0)
        squared_distances = np.sum((embeddings - centroid) ** 2, axis=1)
        closest_idx = int(np.argmin(squared_distances))

        return closest_idx

    def build_embeddings(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(
            texts, show_progress_bar=False, normalize_embeddings=True
        )
        return np.asarray(embeddings, dtype=np.float32)

    def assign_to_cluster_top_n_avg(
        self,
        report_text: str,
        cluster_embeddings: dict[int, np.ndarray],
        n: int,
        min_similarity: float,
    ) -> int | None:
        """Assign report to cluster based on average similarity to top-N members.

        This approach averages the similarity scores of the N most similar members
        from each cluster, then assigns to the cluster with the highest average.

        Args:
            report_text: Text to classify
            cluster_embeddings: Dict mapping cluster IDs to their member embeddings
            n: Number of top similar members to average (default: 3)
            min_similarity: Minimum average similarity threshold (default: 0.5)

        Returns:
            Cluster ID if match found, None otherwise
        """
        if not cluster_embeddings:
            return None

        x = self.model.encode(
            [report_text], show_progress_bar=False, normalize_embeddings=True
        )[0]
        x = np.asarray(x, dtype=np.float32)

        best_cluster = None
        best_avg_similarity = min_similarity

        for cluster_id, embs in cluster_embeddings.items():
            # Calculate similarities to all members
            sims = embs @ x

            # Take average of top-N most similar members
            # For small clusters, use all members
            top_n = min(n, len(sims))

            if top_n == 0:
                continue

            # Use partition to get top-N
            if len(sims) > top_n:
                top_sims = np.partition(sims, -top_n)[-top_n:]
            else:
                top_sims = sims

            avg_similarity = float(np.mean(top_sims))

            # Update best cluster if this one has higher average similarity
            if avg_similarity > best_avg_similarity:
                best_avg_similarity = avg_similarity
                best_cluster = cluster_id

        return best_cluster
