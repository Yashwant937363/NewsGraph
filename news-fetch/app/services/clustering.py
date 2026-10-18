from collections import defaultdict
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_distances

from app.models.schemas.article import Article
from app.models.schemas.cluster import EventCluster, PipelineMetrics

logger = logging.getLogger("news_pipeline.clustering")

class ClusteringService:
    def __init__(self, eps: float = 0.35, min_samples: int = 2):
        self.eps = eps
        self.min_samples = min_samples

    def cluster_articles(
        self,
        articles: List[Article],
        embeddings: np.ndarray,
        eps: Optional[float] = None,
        min_samples: Optional[int] = None,
    ) -> Tuple[List[EventCluster], List[Article], Dict[str, float]]:
        """
        Clusters articles based on precomputed cosine distance of embeddings using DBSCAN.
        Returns: (event_clusters, noise_articles, cluster_metrics)
        """
        eps = eps if eps is not None else self.eps
        min_samples = min_samples if min_samples is not None else self.min_samples

        num_articles = len(articles)
        if num_articles == 0:
            logger.warning("[Stage 4: Clustering] No articles to cluster.")
            return [], [], {"total_clusters": 0, "noise_count": 0, "noise_ratio": 0.0, "silhouette_score": None}

        if num_articles < min_samples:
            logger.info(
                f"[Stage 4: Clustering] Number of articles ({num_articles}) < min_samples ({min_samples}). "
                "All marked as noise."
            )
            return [], list(articles), {
                "total_clusters": 0,
                "noise_count": num_articles,
                "noise_ratio": 1.0,
                "silhouette_score": None,
            }

        logger.info(
            f"[Stage 4: Clustering] Running DBSCAN on {num_articles} articles with eps={eps}, min_samples={min_samples}..."
        )
        distance_matrix = cosine_distances(embeddings)

        dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
        labels = dbscan.fit_predict(distance_matrix)

        clusters_map: Dict[int, List[Article]] = defaultdict(list)
        noise_articles: List[Article] = []

        for idx, label in enumerate(labels):
            if label != -1:
                clusters_map[label].append(articles[idx])
            else:
                noise_articles.append(articles[idx])

        # Sort clusters by size descending
        sorted_clusters: List[EventCluster] = []
        for cluster_id, cluster_arts in sorted(clusters_map.items(), key=lambda item: len(item[1]), reverse=True):
            sorted_clusters.append(
                EventCluster(
                    cluster_id=int(cluster_id),
                    article_count=len(cluster_arts),
                    articles=cluster_arts,
                )
            )

        total_clusters = len(sorted_clusters)
        noise_count = len(noise_articles)
        noise_ratio = noise_count / num_articles

        # Compute silhouette score if more than 1 cluster exists among non-noise articles
        silhouette: Optional[float] = None
        non_noise_mask = labels != -1
        unique_labels = set(labels[non_noise_mask])
        if len(unique_labels) > 1:
            try:
                silhouette = float(
                    silhouette_score(distance_matrix[non_noise_mask][:, non_noise_mask], labels[non_noise_mask], metric="precomputed")
                )
            except Exception as e:
                logger.warning(f"[Stage 4: Clustering] Could not compute silhouette score: {e}")

        logger.info(
            f"[Stage 4: Clustering] Results: {total_clusters} event clusters found, "
            f"{noise_count}/{num_articles} noise articles ({noise_ratio * 100:.1f}% noise ratio)"
        )
        if silhouette is not None:
            logger.info(f"[Stage 4: Clustering] Silhouette score (excluding noise): {silhouette:.3f}")

        # Log brief summary of top clusters
        for c in sorted_clusters[:5]:
            lead_title = c.articles[0].title[:80] if c.articles else "Untitled"
            logger.info(f"  • Cluster #{c.cluster_id} ({c.article_count} articles): '{lead_title}...'")

        metrics = {
            "total_clusters": total_clusters,
            "noise_count": noise_count,
            "noise_ratio": round(noise_ratio, 4),
            "silhouette_score": round(silhouette, 4) if silhouette is not None else None,
        }

        return sorted_clusters, noise_articles, metrics
