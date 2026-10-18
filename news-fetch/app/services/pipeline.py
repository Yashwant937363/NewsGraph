from datetime import datetime, timedelta
import logging
import time
from typing import List, Optional

from app.config import Settings, get_settings
from app.models.schemas.article import Article
from app.models.schemas.cluster import EventCluster, PipelineMetrics, PipelineResponse
from app.services.clustering import ClusteringService
from app.services.dedup import DeduplicationService
from app.services.embeddings import EmbeddingService
from app.services.news_fetcher import NewsFetcherService

logger = logging.getLogger("news_pipeline.pipeline")

class NewsPipelineService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        fetcher: Optional[NewsFetcherService] = None,
        dedup_service: Optional[DeduplicationService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        clustering_service: Optional[ClusteringService] = None,
    ):
        self.settings = settings or get_settings()
        self.fetcher = fetcher or NewsFetcherService(api_key=self.settings.news_api_key)
        self.dedup_service = dedup_service or DeduplicationService(
            simhash_distance_threshold=self.settings.simhash_distance_threshold
        )
        self.embedding_service = embedding_service or EmbeddingService(
            model_name=self.settings.embedding_model_name,
            batch_size=self.settings.embedding_batch_size,
        )
        self.clustering_service = clustering_service or ClusteringService(
            eps=self.settings.dbscan_eps,
            min_samples=self.settings.dbscan_min_samples,
        )

    def run_pipeline(
        self,
        articles: Optional[List[Article]] = None,
        date_str: Optional[str] = None,
        query: Optional[str] = None,
        max_articles: int = 100,
        eps: Optional[float] = None,
        min_samples: Optional[int] = None,
    ) -> PipelineResponse:
        """
        Executes stages 1 through 4 (and stage 7 end-to-end evaluation).
        If 'articles' is provided, skips fetching from NewsAPI (useful for testing/fixtures).
        """
        start_time = time.time()
        target_date = date_str or (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        search_query = query or self.settings.default_query

        logger.info("=" * 60)
        logger.info(f"STARTING NEWS PIPELINE EXECUTION FOR DATE: {target_date}")
        logger.info("=" * 60)

        # ----------------- STAGE 1: FETCHING -----------------
        if articles is None:
            fetched_articles = self.fetcher.fetch_news(
                date_str=target_date,
                query=search_query,
                language=self.settings.default_language,
                max_articles=max_articles,
            )
        else:
            logger.info(f"[Stage 1: Input] Using {len(articles)} provided articles directly.")
            fetched_articles = articles

        total_fetched = len(fetched_articles)

        if total_fetched == 0:
            logger.warning("Pipeline completed with 0 articles fetched.")
            metrics = PipelineMetrics(
                total_fetched=0,
                after_url_dedup=0,
                url_duplicates_removed=0,
                after_content_dedup=0,
                content_duplicates_removed=0,
                total_clusters=0,
                noise_count=0,
                noise_ratio=0.0,
                silhouette_score=None,
            )
            return PipelineResponse(date=target_date, metrics=metrics, clusters=[], noise_articles=[])

        # ----------------- STAGE 2: DEDUPLICATION -----------------
        url_deduped, url_duplicates_removed = self.dedup_service.deduplicate_urls(fetched_articles)
        after_url_dedup = len(url_deduped)

        content_deduped, content_duplicates_removed = self.dedup_service.deduplicate_content(url_deduped)
        after_content_dedup = len(content_deduped)

        # ----------------- STAGE 3: EMBEDDINGS -----------------
        embeddings = self.embedding_service.generate_embeddings(content_deduped)

        # ----------------- STAGE 4: CLUSTERING -----------------
        clusters, noise_articles, cluster_metrics = self.clustering_service.cluster_articles(
            articles=content_deduped,
            embeddings=embeddings,
            eps=eps,
            min_samples=min_samples,
        )

        total_duration = time.time() - start_time

        metrics = PipelineMetrics(
            total_fetched=total_fetched,
            after_url_dedup=after_url_dedup,
            url_duplicates_removed=url_duplicates_removed,
            after_content_dedup=after_content_dedup,
            content_duplicates_removed=content_duplicates_removed,
            total_clusters=int(cluster_metrics["total_clusters"]),
            noise_count=int(cluster_metrics["noise_count"]),
            noise_ratio=float(cluster_metrics["noise_ratio"]),
            silhouette_score=cluster_metrics["silhouette_score"],
        )

        logger.info("=" * 60)
        logger.info(f"PIPELINE RUN SUMMARY ({total_duration:.2f}s total)")
        logger.info(f"  • Total fetched:           {metrics.total_fetched}")
        logger.info(f"  • URL duplicates removed:  {metrics.url_duplicates_removed} -> {metrics.after_url_dedup} left")
        logger.info(f"  • Content dupes removed:   {metrics.content_duplicates_removed} -> {metrics.after_content_dedup} left")
        logger.info(f"  • Event clusters formed:   {metrics.total_clusters}")
        logger.info(f"  • Noise articles:          {metrics.noise_count} ({metrics.noise_ratio * 100:.1f}%)")
        if metrics.silhouette_score is not None:
            logger.info(f"  • Silhouette score:        {metrics.silhouette_score:.3f}")
        logger.info("=" * 60)

        return PipelineResponse(
            date=target_date,
            metrics=metrics,
            clusters=clusters,
            noise_articles=noise_articles,
        )
