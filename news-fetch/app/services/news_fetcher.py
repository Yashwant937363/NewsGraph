import logging
from datetime import datetime, timedelta
from typing import List, Optional
from newsapi import NewsApiClient
from app.models.schemas.article import Article

logger = logging.getLogger("news_pipeline.fetcher")

class NewsFetcherService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: Optional[NewsApiClient] = None

    @property
    def client(self) -> NewsApiClient:
        if self._client is None:
            if not self.api_key:
                raise ValueError("NEWS_API_KEY is not configured.")
            self._client = NewsApiClient(api_key=self.api_key)
        return self._client

    def fetch_news(
        self,
        date_str: Optional[str] = None,
        query: str = "*",
        language: str = "en",
        page_size: int = 100,
        max_articles: int = 100,
    ) -> List[Article]:
        """
        Fetches news articles for a specific date (defaults to yesterday).
        Handles pagination up to max_articles.
        """
        if not date_str:
            date_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

        logger.info(
            f"[Stage 1: Fetch] Starting news fetch for date={date_str}, query='{query}', "
            f"language='{language}', max_articles={max_articles}"
        )

        all_raw_articles = []
        page = 1
        page_size = min(page_size, 100)

        while len(all_raw_articles) < max_articles:
            logger.info(f"[Stage 1: Fetch] Requesting page {page} from NewsAPI...")
            try:
                response = self.client.get_everything(
                    q=query,
                    from_param=date_str,
                    to=date_str,
                    language=language,
                    sort_by="relevancy",
                    page_size=page_size,
                    page=page,
                )
            except Exception as e:
                logger.error(f"[Stage 1: Fetch] Error fetching page {page} from NewsAPI: {e}")
                raise

            status = response.get("status")
            if status != "ok":
                err_msg = response.get("message", "Unknown error from NewsAPI")
                logger.error(f"[Stage 1: Fetch] NewsAPI returned status '{status}': {err_msg}")
                raise RuntimeError(f"NewsAPI error: {err_msg}")

            articles = response.get("articles", [])
            logger.info(f"[Stage 1: Fetch] Page {page} returned {len(articles)} articles.")

            if not articles:
                break

            all_raw_articles.extend(articles)

            if len(articles) < page_size or len(all_raw_articles) >= max_articles:
                break

            page += 1

        all_raw_articles = all_raw_articles[:max_articles]
        parsed_articles: List[Article] = []
        for raw in all_raw_articles:
            try:
                parsed_articles.append(Article(**raw))
            except Exception as e:
                logger.warning(f"[Stage 1: Fetch] Failed to parse article: {e}")

        logger.info(f"[Stage 1: Fetch] Completed fetch. Total articles collected: {len(parsed_articles)}")
        return parsed_articles
