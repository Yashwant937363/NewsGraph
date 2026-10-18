import hashlib
import logging
from typing import List, Set, Tuple
from urllib.parse import urlparse, urlunparse
from simhash import Simhash
from app.models.schemas.article import Article

logger = logging.getLogger("news_pipeline.dedup")

class DeduplicationService:
    def __init__(self, simhash_distance_threshold: int = 1):
        self.simhash_distance_threshold = simhash_distance_threshold

    @staticmethod
    def normalize_url(url: str) -> str:
        """Strip query params, fragments, and tracking parameters."""
        parsed = urlparse(url)
        # Keep scheme + host + path only
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return normalized.lower().rstrip("/")

    @staticmethod
    def url_fingerprint(url: str) -> str:
        """SHA-1 hash of normalized URL for fast lookup."""
        normalized = DeduplicationService.normalize_url(url)
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def content_fingerprint(article: Article) -> Simhash:
        """Combine title + description + content for a robust SimHash fingerprint."""
        text = f"{article.title} {article.description or ''} {article.content or ''}".strip()
        # SimHash over lowercase text
        return Simhash(text.lower())

    def deduplicate_urls(self, articles: List[Article]) -> Tuple[List[Article], int]:
        """Deduplicates articles based on normalized URL SHA-1 fingerprint."""
        logger.info(f"[Stage 2: Dedup (URL)] Starting URL deduplication on {len(articles)} articles...")
        seen_fingerprints: Set[str] = set()
        unique_articles: List[Article] = []
        duplicates_count = 0

        for art in articles:
            fp = self.url_fingerprint(art.url)
            if fp not in seen_fingerprints:
                seen_fingerprints.add(fp)
                unique_articles.append(art)
            else:
                duplicates_count += 1
                logger.debug(f"[Stage 2: Dedup (URL)] Duplicate URL found: {art.url}")

        logger.info(
            f"[Stage 2: Dedup (URL)] Finished URL deduplication. "
            f"Removed: {duplicates_count}, Retained: {len(unique_articles)}"
        )
        return unique_articles, duplicates_count

    def deduplicate_content(self, articles: List[Article]) -> Tuple[List[Article], int]:
        """
        Deduplicates articles based on SimHash locality-sensitive hashing.
        Hamming distance <= threshold implies near-duplicate syndicated content.
        """
        logger.info(
            f"[Stage 2: Dedup (Content)] Starting SimHash deduplication on {len(articles)} articles "
            f"(threshold={self.simhash_distance_threshold})..."
        )
        content_seen: List[Simhash] = []
        final_articles: List[Article] = []
        duplicates_count = 0

        for art in articles:
            fp = self.content_fingerprint(art)
            is_duplicate = False
            for existing_fp in content_seen:
                if fp.distance(existing_fp) <= self.simhash_distance_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                content_seen.append(fp)
                final_articles.append(art)
            else:
                duplicates_count += 1
                logger.debug(f"[Stage 2: Dedup (Content)] Duplicate content detected: '{art.title[:60]}...'")

        logger.info(
            f"[Stage 2: Dedup (Content)] Finished Content deduplication. "
            f"Removed: {duplicates_count}, Retained: {len(final_articles)}"
        )
        return final_articles, duplicates_count

    def deduplicate(self, articles: List[Article]) -> Tuple[List[Article], int, int]:
        """Runs URL dedup followed by SimHash content dedup."""
        logger.info(f"[Stage 2: Dedup] Total incoming articles: {len(articles)}")
        url_deduped, url_dupes = self.deduplicate_urls(articles)
        content_deduped, content_dupes = self.deduplicate_content(url_deduped)
        total_removed = url_dupes + content_dupes
        pct = (total_removed / len(articles) * 100) if articles else 0.0
        logger.info(
            f"[Stage 2: Dedup] Summary: {len(articles)} -> {len(content_deduped)} articles "
            f"(removed {total_removed} duplicates, {pct:.1f}% reduction)"
        )
        return content_deduped, url_dupes, content_dupes
