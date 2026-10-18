import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np

from app.config import Settings, get_settings
from app.core.db import init_db
from app.models.documents.article import ArticleDocument
from app.models.documents.phase1_ledger import Phase1LedgerDocument
from app.models.schemas.article import Article, ArticleSource
from app.services.clustering import ClusteringService
from app.services.dedup import DeduplicationService
from app.services.embeddings import EmbeddingService
from app.services.falkordb_client import FalkorDBClient
from app.services.temporal_linker import TemporalLinker

logger = logging.getLogger("news_pipeline.phase1")


class Phase1Pipeline:
    """
    Executes Phase 1 of WorldGraph:
    MongoDB articles -> Group by date -> Dedup (URL + SimHash) ->
    Embed (384-d) -> DBSCAN micro-clusters -> Temporal Linker (T-3 to T-1) ->
    FalkorDB (:Article, :Source, :Event, :Story + structural edges).
    Each date is an atomic unit tracked in Phase1LedgerDocument.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.dedup_service = DeduplicationService(
            simhash_distance_threshold=self.settings.simhash_distance_threshold
        )
        self.embedding_service = EmbeddingService(
            model_name=self.settings.embedding_model_name,
            batch_size=self.settings.embedding_batch_size,
        )
        self.clustering_service = ClusteringService(
            eps=self.settings.dbscan_eps,
            min_samples=self.settings.dbscan_min_samples,
        )
        self.temporal_linker = TemporalLinker(
            similarity_threshold=self.settings.temporal_similarity_threshold
        )
        self.falkordb = FalkorDBClient(self.settings)

    async def get_all_dates(self) -> List[str]:
        """Returns sorted list of distinct publication dates present in MongoDB."""
        await init_db(self.settings)
        # Scan articles to get unique dates
        articles = await ArticleDocument.find_all().to_list()
        dates_set = set()
        for a in articles:
            d = (a.published_at or "")[:10]
            if len(d) == 10 and d.count("-") == 2:
                dates_set.add(d)
        return sorted(list(dates_set))

    async def process_date(
        self,
        date_str: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Processes a single date atomically.
        If already COMPLETED and not force, skips and returns ledger summary.
        """
        await init_db(self.settings)
        self.falkordb.init_schema()

        # Check Ledger
        ledger = await Phase1LedgerDocument.find_one(Phase1LedgerDocument.date == date_str)
        if ledger and ledger.status == "COMPLETED" and not force:
            logger.info(f"⏭️  Date {date_str} already COMPLETED in ledger. Skipping.")
            return {
                "date": date_str,
                "status": "SKIPPED",
                "clusters_count": ledger.clusters_count,
                "stories_created": ledger.stories_created,
                "stories_linked": ledger.stories_linked,
            }

        if ledger is None:
            ledger = Phase1LedgerDocument(date=date_str, status="PROCESSING")
            await ledger.insert()
        else:
            ledger.status = "PROCESSING"
            ledger.updated_at = datetime.utcnow()
            await ledger.save()

        logger.info(f"\n================ Phase 1: Processing {date_str} ================")

        try:
            # 1. Fetch raw articles from MongoDB for date
            query_filter = {"published_at": {"$regex": f"^{date_str}"}}
            docs = await ArticleDocument.find(query_filter).to_list()
            raw_count = len(docs)
            logger.info(f"Loaded {raw_count} articles from MongoDB for date {date_str}.")

            if raw_count == 0:
                ledger.status = "COMPLETED"
                ledger.raw_articles_count = 0
                ledger.completed_at = datetime.utcnow()
                await ledger.save()
                return {"date": date_str, "status": "COMPLETED", "articles": 0}

            # Convert docs to Pydantic Article schemas for dedup service
            articles: List[Article] = []
            doc_lookup: Dict[str, ArticleDocument] = {}
            for doc in docs:
                art = Article(
                    title=doc.title,
                    description=doc.description,
                    url=doc.url,
                    url_to_image=doc.url_to_image,
                    published_at=doc.published_at,
                    content=doc.content,
                    author=doc.author,
                    source=ArticleSource(id=doc.source_id, name=doc.source_name),
                )
                articles.append(art)
                doc_lookup[doc.url] = doc

            # 2. Deduplication (URL + SimHash)
            deduped_articles, _, _ = self.dedup_service.deduplicate(articles)
            dedup_count = len(deduped_articles)
            logger.info(f"Deduplication: {raw_count} raw -> {dedup_count} unique articles.")

            # 3. Generate Embeddings (all-MiniLM-L6-v2)
            embeddings = self.embedding_service.generate_embeddings(deduped_articles)
            logger.info(f"Generated normalized embeddings: shape {embeddings.shape}.")

            # 4. DBSCAN Clustering (eps=0.35, min_samples=2, cosine)
            clusters, noise_articles, cluster_metrics = self.clustering_service.cluster_articles(
                deduped_articles,
                embeddings,
                eps=self.settings.dbscan_eps,
                min_samples=self.settings.dbscan_min_samples,
            )

            logger.info(
                f"DBSCAN results: {len(clusters)} micro-clusters, {len(noise_articles)} noise articles "
                f"(Silhouette: {cluster_metrics.get('silhouette_score')})."
            )

            # Map article URLs to their embeddings for centroid computation
            url_to_vec = {art.url: embeddings[i] for i, art in enumerate(deduped_articles)}

            # 5. Build Event objects & Centroids
            daily_events: List[Dict[str, Any]] = []
            for cluster_idx, cluster in enumerate(clusters):
                cluster_arts = cluster.articles
                if not cluster_arts:
                    continue


                cluster_vecs = [url_to_vec[art.url] for art in cluster_arts if art.url in url_to_vec]
                if not cluster_vecs:
                    continue

                # Compute normalized centroid
                centroid_mean = np.mean(cluster_vecs, axis=0)
                norm = np.linalg.norm(centroid_mean)
                centroid = (centroid_mean / norm if norm > 1e-6 else centroid_mean).tolist()

                # Calculate similarity of each article to centroid
                articles_with_sim = []
                best_sim = -1.0
                rep_article = cluster_arts[0]

                for art in cluster_arts:
                    vec = url_to_vec.get(art.url)
                    if vec is not None:
                        sim = float(np.dot(vec, centroid))
                    else:
                        sim = 1.0

                    articles_with_sim.append({"url": art.url, "similarity": round(sim, 4)})
                    if sim > best_sim:
                        best_sim = sim
                        rep_article = art

                # Dates
                dates = [art.published_at for art in cluster_arts if art.published_at]
                first_seen = min(dates) if dates else f"{date_str}T00:00:00Z"
                last_seen = max(dates) if dates else f"{date_str}T23:59:59Z"

                # Infer category from matched queries if available
                category = "General"
                matched_q = getattr(doc_lookup.get(rep_article.url), "matched_queries", [])
                if matched_q:
                    category = matched_q[0][:30].replace('"', '')

                event_dict = {
                    "event_id": f"evt_{date_str}_{cluster_idx}",
                    "title": rep_article.title or f"Event {date_str} #{cluster_idx}",
                    "summary": rep_article.description or cluster_arts[0].title,
                    "category": category,
                    "sentiment": "neutral",
                    "occurred_at": date_str,
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "centroid": centroid,
                    "articles_with_sim": articles_with_sim,
                }
                daily_events.append(event_dict)

            # 6. Temporal Linker (Look back T-3 to T-1)
            curr_date_dt = datetime.strptime(date_str, "%Y-%m-%d")
            t_minus_3 = (curr_date_dt - timedelta(days=self.settings.temporal_window_days)).strftime("%Y-%m-%d")
            t_minus_1 = (curr_date_dt - timedelta(days=1)).strftime("%Y-%m-%d")

            candidate_events = self.falkordb.get_recent_events(t_minus_3, t_minus_1)
            logger.info(
                f"Temporal Linker: querying past events from {t_minus_3} to {t_minus_1}. "
                f"Found {len(candidate_events)} candidate events."
            )

            linked_results = self.temporal_linker.link_events(
                daily_events,
                candidate_events,
                date_str,
            )

            # 7. Write to FalkorDB (Idempotent MERGE writes)
            # Write all deduplicated articles and sources first
            for art in deduped_articles:
                self.falkordb.write_article_and_source({
                    "url": art.url,
                    "title": art.title,
                    "description": art.description,
                    "author": art.author,
                    "published_at": art.published_at,
                    "url_to_image": art.url_to_image,
                    "source_name": art.source.name if art.source else "Unknown",
                    "source_id": art.source.id if art.source else None,
                })

            stories_created = 0
            stories_linked = 0

            # Write Events, Stories, and Links
            for item in linked_results:
                event_data = item["event"]
                story_id = item["story_id"]
                is_new = item["is_new_story"]
                articles_with_sim = event_data["articles_with_sim"]

                # Write Event + REPORTS_ON edges
                self.falkordb.write_event(event_data, articles_with_sim)

                # Write or update Story
                if is_new:
                    self.falkordb.write_story({
                        "story_id": story_id,
                        "title": event_data["title"],
                        "first_seen": event_data["first_seen"],
                        "last_seen": event_data["last_seen"],
                        "article_count": len(articles_with_sim),
                    })
                    stories_created += 1
                else:
                    self.falkordb.write_story({
                        "story_id": story_id,
                        "last_seen": event_data["last_seen"],
                    }, new_articles_count=len(articles_with_sim))
                    stories_linked += 1

                # Link Event -> Story (PART_OF)
                self.falkordb.link_event_to_story(event_data["event_id"], story_id)

                # Link Event -> Event (PRECEDED / FOLLOWED)
                if item.get("linked_prev_event_id"):
                    self.falkordb.link_events_preceded(
                        prev_event_id=item["linked_prev_event_id"],
                        next_event_id=event_data["event_id"],
                        days_gap=item.get("days_gap") or 1,
                    )

            # 8. Update Ledger Checkpoint
            ledger.status = "COMPLETED"
            ledger.raw_articles_count = raw_count
            ledger.deduped_articles_count = dedup_count
            ledger.clusters_count = len(daily_events)
            ledger.noise_count = len(noise_articles)
            ledger.stories_created = stories_created
            ledger.stories_linked = stories_linked
            ledger.completed_at = datetime.utcnow()
            ledger.updated_at = datetime.utcnow()
            await ledger.save()

            logger.info(
                f"✓ Successfully completed Phase 1 for {date_str}!\n"
                f"  Events: {len(daily_events)} | Stories Created: {stories_created} | "
                f"Stories Linked: {stories_linked}"
            )

            return {
                "date": date_str,
                "status": "COMPLETED",
                "raw_articles": raw_count,
                "deduped_articles": dedup_count,
                "events_created": len(daily_events),
                "stories_created": stories_created,
                "stories_linked": stories_linked,
            }

        except Exception as e:
            logger.error(f"Error processing date {date_str}: {e}", exc_info=True)
            ledger.status = "FAILED"
            ledger.error_message = str(e)
            ledger.updated_at = datetime.utcnow()
            await ledger.save()
            raise

    async def process_all_dates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit_days: Optional[int] = None,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """Processes all dates chronologically from oldest to newest."""
        all_dates = await self.get_all_dates()

        if start_date:
            all_dates = [d for d in all_dates if d >= start_date]
        if end_date:
            all_dates = [d for d in all_dates if d <= end_date]
        if limit_days is not None:
            all_dates = all_dates[:limit_days]

        logger.info(
            f"=== Starting Phase 1 Pipeline for {len(all_dates)} dates "
            f"({all_dates[0] if all_dates else 'none'} to {all_dates[-1] if all_dates else 'none'}) ==="
        )

        results = []
        for date_str in all_dates:
            res = await self.process_date(date_str, force=force)
            results.append(res)

        logger.info("=== Phase 1 Pipeline Finished Across All Selected Dates ===")
        return results

    async def get_summary(self) -> Dict[str, Any]:
        """Returns overview of Phase 1 progress and FalkorDB graph counts."""
        await init_db(self.settings)
        all_dates = await self.get_all_dates()
        ledgers = await Phase1LedgerDocument.find_all().to_list()
        completed = [l for l in ledgers if l.status == "COMPLETED"]
        failed = [l for l in ledgers if l.status == "FAILED"]

        graph_stats = self.falkordb.get_graph_stats()

        return {
            "total_dates_in_mongo": len(all_dates),
            "dates_completed": len(completed),
            "dates_failed": len(failed),
            "dates_pending": len(all_dates) - len(completed),
            "graph_stats": graph_stats,
            "completed_dates": [l.date for l in completed],
        }
