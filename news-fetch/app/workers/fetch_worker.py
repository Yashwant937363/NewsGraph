import asyncio
import logging
import math
import os
import signal
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from pymongo.errors import DuplicateKeyError

from app.config import Settings, get_settings
from app.core.db import close_db, init_db
from app.models.documents.article import ArticleDocument
from app.models.documents.fetch_state import FetchStateDocument
from app.services.key_rotator import KeyRotator
from app.services.selected_queries import get_selected_queries

logger = logging.getLogger("news_pipeline.worker")


class NewsFetchWorker:
    """
    Worker that executes the 150 unique queries from Queries.md against
    NewsAPI /everything, handling pagination (e.g. 500 articles -> 5 pages),
    multi-key rotation, deduplication in MongoDB, and resumable state persistence.
    """

    NEWS_API_BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(
        self,
        settings: Optional[Settings] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_pages_per_query: int = 10,
    ):
        self.settings = settings or get_settings()
        self.date_from = date_from or self.settings.date_from
        self.date_to = date_to or self.settings.date_to
        self.max_pages_per_query = max_pages_per_query
        self.rotator = KeyRotator()
        self.queries = get_selected_queries()
        self.state: Optional[FetchStateDocument] = None
        self._shutdown_requested = False
        self._client: Optional[httpx.AsyncClient] = None

    def request_shutdown(self, signum=None, frame=None) -> None:
        """Flags worker for graceful termination after current operation."""
        logger.warning("Shutdown signal received! Finishing current batch and saving state...")
        self._shutdown_requested = True

    async def get_or_create_state(self, reset: bool = False) -> FetchStateDocument:
        """Retrieves or initializes the fetch progress state in MongoDB."""
        state = await FetchStateDocument.find_one(FetchStateDocument.state_id == "global_fetch_state")
        if reset and state:
            logger.info("Resetting existing fetch state as requested.")
            await state.delete()
            state = None

        if state is None:
            state = FetchStateDocument(
                state_id="global_fetch_state",
                total_queries=len(self.queries),
                current_query_index=0,
                completed_query_ids=[],
                failed_queries=[],
                active_key_index=self.rotator.current_index,
            )
            await state.insert()
            logger.info("Created new FetchStateDocument in MongoDB.")
        else:
            logger.info(
                f"Resumed existing fetch state: {len(state.completed_query_ids)}/{state.total_queries} "
                f"queries completed. Current query index: {state.current_query_index}."
            )
            self.rotator.set_current_index(state.active_key_index)

        self.state = state
        return state

    async def _fetch_page_with_retry(
        self,
        query_str: str,
        page: int,
        page_size: int = 100,
        max_key_retries: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches a single page of results for a query from NewsAPI.
        Handles key rotation on 429 / 401, plan limit detection on 426,
        and backoff retries.
        """
        retries = 0
        while retries < max_key_retries and not self._shutdown_requested:
            api_key = self.rotator.get_current_key()
            params = {
                "q": query_str,
                "from": self.date_from,
                "to": self.date_to,
                "language": self.settings.default_language,
                "sortBy": "relevancy",
                "pageSize": page_size,
                "page": page,
                "apiKey": api_key,
            }

            try:
                if self.state:
                    self.state.total_api_calls += 1

                response = await self._client.get(
                    self.NEWS_API_BASE_URL,
                    params=params,
                    timeout=25.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        return data
                    else:
                        msg = data.get("message", "Unknown error")
                        logger.warning(f"NewsAPI error in body: {msg}")

                elif response.status_code == 426:
                    # Developer accounts limit: 100 max results across pages
                    logger.info(
                        f"NewsAPI plan limitation (HTTP 426) on page {page} for query. "
                        f"Developer plan max results reached."
                    )
                    return {"status": "plan_limit", "articles": [], "totalResults": 0}

                elif response.status_code == 429:
                    logger.warning(
                        f"HTTP 429 Rate Limited on key [{api_key[:8]}...]. Rotating key..."
                    )
                    self.rotator.rotate("rate limit (HTTP 429)")
                    if self.state:
                        self.state.active_key_index = self.rotator.current_index
                    await asyncio.sleep(1.0)
                    retries += 1
                    continue

                elif response.status_code in (401, 403):
                    logger.warning(
                        f"HTTP {response.status_code} on key [{api_key[:8]}...]. Rotating key..."
                    )
                    self.rotator.rotate(f"unauthorized/quota (HTTP {response.status_code})")
                    if self.state:
                        self.state.active_key_index = self.rotator.current_index
                    await asyncio.sleep(1.0)
                    retries += 1
                    continue

                else:
                    logger.error(
                        f"HTTP {response.status_code} from NewsAPI: {response.text[:200]}"
                    )
                    await asyncio.sleep(2.0)
                    retries += 1

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning(f"Network error querying NewsAPI: {exc}. Retrying...")
                await asyncio.sleep(2.0)
                retries += 1

        return None

    async def _process_article(self, raw_article: Dict[str, Any], query_str: str) -> bool:
        """
        Inserts article into MongoDB if not present.
        If already present, appends query to matched_queries and avoids duplication.
        Returns True if newly inserted, False if duplicate or skipped.
        """
        url = (raw_article.get("url") or "").strip()
        if not url or url == "https://removed.com" or "[Removed]" in (raw_article.get("title") or ""):
            return False

        # Check if already in MongoDB
        existing = await ArticleDocument.find_one(ArticleDocument.url == url)
        if existing:
            if query_str not in existing.matched_queries:
                existing.matched_queries.append(query_str)
                await existing.save()
            if self.state:
                self.state.total_duplicates_skipped += 1
            return False

        # Create new document
        source_data = raw_article.get("source") or {}
        article_doc = ArticleDocument(
            title=raw_article.get("title") or "",
            description=raw_article.get("description"),
            url=url,
            url_to_image=raw_article.get("urlToImage"),
            published_at=raw_article.get("publishedAt"),
            content=raw_article.get("content"),
            author=raw_article.get("author"),
            source_id=source_data.get("id"),
            source_name=source_data.get("name"),
            matched_queries=[query_str],
            created_at=datetime.utcnow(),
        )

        try:
            await article_doc.insert()
            if self.state:
                self.state.total_articles_inserted += 1
            return True
        except DuplicateKeyError:
            if self.state:
                self.state.total_duplicates_skipped += 1
            return False

    async def run(
        self,
        reset_state: bool = False,
        limit_queries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Runs the full fetch pipeline across all 150 queries.
        """
        await init_db(self.settings)
        await self.get_or_create_state(reset=reset_state)

        # Set up signal handling for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.request_shutdown)
            except NotImplementedError:
                pass  # e.g., on Windows

        headers = {"User-Agent": "NewsFetchPipeline/1.0 (+https://github.com)"}
        self._client = httpx.AsyncClient(headers=headers)

        queries_to_run = self.queries
        if limit_queries is not None:
            queries_to_run = queries_to_run[:limit_queries]

        logger.info(
            f"=== Starting NewsFetch Worker ===\n"
            f"Total Queries: {len(queries_to_run)}\n"
            f"Date Range: {self.date_from} to {self.date_to}\n"
            f"API Keys Available: {self.rotator.total_keys}\n"
            f"Previously Completed: {len(self.state.completed_query_ids)}\n"
        )

        try:
            for idx, item in enumerate(queries_to_run):
                if self._shutdown_requested:
                    logger.warning("Halting query loop due to shutdown request.")
                    break

                qid = item["id"]
                query_str = item["query"]

                if qid in self.state.completed_query_ids:
                    continue

                self.state.current_query_index = idx
                self.state.active_key_index = self.rotator.current_index
                await self.state.save()

                logger.info(
                    f"[{idx + 1}/{len(queries_to_run)}] Query ID {qid}: {query_str[:70]}..."
                )

                # Fetch Page 1
                first_page = await self._fetch_page_with_retry(query_str, page=1)
                if not first_page or first_page.get("status") not in ("ok", "plan_limit"):
                    logger.error(f"Failed to fetch page 1 for query ID {qid}.")
                    self.state.failed_queries.append({
                        "query_id": qid,
                        "query": query_str,
                        "error": "Failed to fetch page 1",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    await self.state.save()
                    continue

                total_results = first_page.get("totalResults", 0)
                articles_p1 = first_page.get("articles", [])
                total_pages = math.ceil(total_results / 100) if total_results > 0 else 1
                pages_to_fetch = min(total_pages, self.max_pages_per_query)

                logger.info(
                    f"  -> totalResults: {total_results} | Pages to fetch: {pages_to_fetch} "
                    f"| Page 1 articles: {len(articles_p1)}"
                )

                query_new_inserted = 0
                query_duplicates = 0

                # Process Page 1 articles
                for art in articles_p1:
                    inserted = await self._process_article(art, query_str)
                    if inserted:
                        query_new_inserted += 1
                    else:
                        query_duplicates += 1

                self.state.total_articles_fetched += len(articles_p1)

                # Fetch remaining pages if any
                for page in range(2, pages_to_fetch + 1):
                    if self._shutdown_requested:
                        break

                    await asyncio.sleep(0.3)  # Gentle delay between requests
                    page_data = await self._fetch_page_with_retry(query_str, page=page)
                    if not page_data or page_data.get("status") == "plan_limit":
                        break

                    page_articles = page_data.get("articles", [])
                    if not page_articles:
                        break

                    self.state.total_articles_fetched += len(page_articles)
                    for art in page_articles:
                        inserted = await self._process_article(art, query_str)
                        if inserted:
                            query_new_inserted += 1
                        else:
                            query_duplicates += 1

                    if len(page_articles) < 100:
                        break

                # Mark query as completed
                self.state.completed_query_ids.append(qid)
                self.state.updated_at = datetime.utcnow()
                await self.state.save()

                total_in_db = await ArticleDocument.count()
                logger.info(
                    f"  ✓ Finished Query {qid} | New Inserted: {query_new_inserted} | "
                    f"Dups Skipped: {query_duplicates} | Total in DB: {total_in_db}"
                )

                await asyncio.sleep(0.2)

            if len(self.state.completed_query_ids) >= len(self.queries):
                self.state.is_completed = True
                await self.state.save()
                logger.info("🎉 All 150 queries have been successfully executed!")

        finally:
            if self._client:
                await self._client.aclose()
            if self.state:
                self.state.updated_at = datetime.utcnow()
                await self.state.save()

        summary = await self.get_summary()
        return summary

    async def get_summary(self) -> Dict[str, Any]:
        """Returns statistics of the current database and progress."""
        await init_db(self.settings)
        state = await FetchStateDocument.find_one(FetchStateDocument.state_id == "global_fetch_state")
        total_articles = await ArticleDocument.count()

        distinct_sources = len(await ArticleDocument.distinct("source_name"))
        sample_articles = await ArticleDocument.find().limit(3).to_list()

        return {
            "total_articles_in_db": total_articles,
            "distinct_sources": distinct_sources,
            "queries_completed": len(state.completed_query_ids) if state else 0,
            "total_queries": len(self.queries),
            "total_api_calls": state.total_api_calls if state else 0,
            "total_fetched": state.total_articles_fetched if state else 0,
            "total_inserted": state.total_articles_inserted if state else 0,
            "total_duplicates_skipped": state.total_duplicates_skipped if state else 0,
            "is_completed": state.is_completed if state else False,
            "active_key_index": state.active_key_index if state else 0,
            "sample_articles": [
                {
                    "title": a.title,
                    "url": a.url,
                    "published_at": a.published_at,
                    "source": a.source_name,
                    "matched_queries": a.matched_queries,
                }
                for a in sample_articles
            ],
        }
