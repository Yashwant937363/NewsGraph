#!/usr/bin/env python3
"""
CLI runner to fetch clean, substantive article content from URLs and save into MongoDB.
Strips boilerplate, navigation, ads, headers, and footers using ArticleExtractor.
Falls back to NewsAPI metadata for WAF/paywalled articles to ensure 100% coverage.
"""
import argparse
import asyncio
import logging
import sys
import time
from typing import List

from app.config import get_settings
from app.core.db import close_db, init_db
from app.models.documents.article import ArticleDocument
from app.services.article_extractor import ArticleExtractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("extract_content")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch exact clean article content from URLs and update MongoDB"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Inspect extraction stats in MongoDB without fetching",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract content for ALL pending articles in the database",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Limit number of articles to process (default: 50, ignored if --all is set)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Fetch and extract content for a single specific article URL",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent worker tasks (default: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP request timeout per article in seconds (default: 15.0)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if article was already marked as extracted",
    )
    return parser.parse_args()


async def print_status():
    total = await ArticleDocument.count()
    extracted = await ArticleDocument.find(ArticleDocument.full_text != None).count()
    attempted = await ArticleDocument.find(ArticleDocument.content_extracted == True).count()
    pending = total - attempted

    print("\n" + "=" * 50)
    print(" 📰 Article Content Extraction Status in MongoDB")
    print("=" * 50)
    print(f"Total articles in DB:        {total:,}")
    print(f"Clean full_text in DB:       {extracted:,} ({(extracted / total * 100) if total else 0:.1f}%)")
    print(f"Extraction attempted:        {attempted:,}")
    print(f"Pending extraction:          {pending:,}")
    print("=" * 50 + "\n")


async def extract_single_url(url: str, extractor: ArticleExtractor):
    print(f"\n🔍 Fetching and extracting clean text from:\n   {url}\n")
    text, words = await extractor.extract_from_url(url)

    if not text:
        print("❌ Failed to extract web content (page unreachable, paywalled, or blocked).")
        return

    print(f"✅ Successfully extracted {words} words!\n")
    print("-" * 50)
    preview = text[:600] + ("..." if len(text) > 600 else "")
    print(preview)
    print("-" * 50)

    # Update in DB if article exists
    doc = await ArticleDocument.find_one(ArticleDocument.url == url)
    if doc:
        doc.full_text = text
        doc.content_extracted = True
        await doc.save()
        print(f"💾 Saved to MongoDB article record: '{doc.title[:60]}'")
    else:
        print("ℹ️ URL is not present in MongoDB articles collection (preview only).")


async def batch_worker(
    queue: asyncio.Queue,
    extractor: ArticleExtractor,
    stats: dict,
):
    while not queue.empty():
        doc = await queue.get()
        try:
            text, words = await extractor.extract_from_url(doc.url)
            if text and words >= 30:
                doc.full_text = text
                doc.content_extracted = True
                await doc.save()
                stats["web_extracted"] += 1
                stats["words"] += words
                logger.info(f"✓ [{stats['processed'] + 1}] Web Extracted {words} words: {doc.title[:50]}")
            else:
                # Fallback to NewsAPI metadata so article is never blank for AI/RAG
                fallback_parts = [p for p in [doc.title, doc.description, doc.content] if p]
                doc.content_extracted = True
                await doc.save()
                fb_words = len(doc.full_text.split())
                stats["fallback_extracted"] += 1
                stats["words"] += fb_words
                logger.info(f"⚠️ [{stats['processed'] + 1}] Webpage blocked/paywalled, used NewsAPI text ({fb_words}w): {doc.title[:45]}")
        except Exception as e:
            fallback_parts = [p for p in [doc.title, doc.description, doc.content] if p]
            doc.full_text = "\n\n".join(fallback_parts) if fallback_parts else doc.title
            doc.content_extracted = True
            await doc.save()
            stats["fallback_extracted"] += 1
            logger.debug(f"Error on {doc.url}: {e}")
        finally:
            stats["processed"] += 1
            queue.task_done()


async def run_batch(
    limit: int,
    concurrency: int,
    timeout: float,
    force: bool,
    extract_all: bool = False,
):
    extractor = ArticleExtractor(timeout=timeout)

    total_pending = await ArticleDocument.find(
        {"$or": [
            {"content_extracted": False},
            {"content_extracted": None},
            {"content_extracted": {"$exists": False}},
        ]}
    ).count()

    if total_pending == 0 and not force:
        print("🎉 No pending articles to extract! All articles have been processed.")
        return

    target_total = total_pending if extract_all else min(limit, total_pending)
    print(f"\n🚀 Starting extraction for {target_total:,} articles (concurrency={concurrency}, timeout={timeout}s)...")
    start_time = time.time()
    stats = {"processed": 0, "web_extracted": 0, "fallback_extracted": 0, "words": 0}

    chunk_size = 100
    chunk_num = 0

    while True:
        remaining = target_total - stats["processed"]
        if remaining <= 0:
            break

        current_limit = min(chunk_size, remaining)
        if force:
            docs = await ArticleDocument.find().skip(stats["processed"]).limit(current_limit).to_list()
        else:
            docs = await ArticleDocument.find(
                {"$or": [
                    {"content_extracted": False},
                    {"content_extracted": None},
                    {"content_extracted": {"$exists": False}},
                ]}
            ).limit(current_limit).to_list()

        if not docs:
            break

        chunk_num += 1
        queue = asyncio.Queue()
        for doc in docs:
            queue.put_nowait(doc)

        workers = [
            asyncio.create_task(batch_worker(queue, extractor, stats))
            for _ in range(concurrency)
        ]
        await queue.join()
        for w in workers:
            w.cancel()

        elapsed = time.time() - start_time
        rate = stats["processed"] / elapsed if elapsed > 0 else 0
        pct = (stats["processed"] / target_total) * 100
        print(
            f"📊 Progress: {stats['processed']:,}/{target_total:,} ({pct:.1f}%) | "
            f"Web: {stats['web_extracted']:,} | Fallback: {stats['fallback_extracted']:,} | Rate: {rate:.1f} art/sec"
        )

    elapsed = time.time() - start_time
    total_successful = stats["web_extracted"] + stats["fallback_extracted"]
    avg_words = (stats["words"] // total_successful) if total_successful > 0 else 0
    print("\n" + "=" * 50)
    print(" ✅ Extraction Run Complete")
    print("=" * 50)
    print(f"Processed:            {stats['processed']:,} articles in {elapsed:.1f}s ({(stats['processed'] / elapsed) if elapsed else 0:.1f} art/sec)")
    print(f"Web Page Extracted:   {stats['web_extracted']:,} articles ({stats['web_extracted'] / max(1, stats['processed']) * 100:.1f}%)")
    print(f"Fallback NewsAPI:     {stats['fallback_extracted']:,} articles (WAF blocked/paywalled/video)")
    print(f"Total Words Stored:   {stats['words']:,} words (avg {avg_words:,} words/article)")
    print("=" * 50 + "\n")


async def main():
    args = parse_args()
    settings = get_settings()
    await init_db(settings)

    try:
        if args.status:
            await print_status()
        elif args.url:
            extractor = ArticleExtractor(timeout=args.timeout)
            await extract_single_url(args.url, extractor)
        else:
            await run_batch(
                limit=args.limit,
                concurrency=args.concurrency,
                timeout=args.timeout,
                force=args.force,
                extract_all=args.all,
            )
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
