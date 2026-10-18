#!/usr/bin/env python3
"""
CLI Runner to slice full-text news articles into semantic chunks,
generate 384-d vector embeddings using all-MiniLM-L6-v2, and persist them
directly into FalkorDB as (:Article)-[:HAS_CHUNK]->(:Chunk) nodes.
"""

import argparse
import asyncio
import logging
import sys
import time
from typing import List, Dict, Any, Set

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings
from app.services.falkordb_client import FalkorDBClient
from app.services.embeddings import EmbeddingService
from app.services.falkordb_chunker import NewsChunker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("falkordb_chunks")


async def get_stats(falkordb: FalkorDBClient, mongo_db) -> Dict[str, Any]:
    """Retrieves current chunk and article stats across FalkorDB and MongoDB."""
    chunk_stats = falkordb.get_chunk_stats()

    # Event articles in FalkorDB
    res_event_arts = falkordb.graph.query(
        "MATCH (e:Event)<-[:REPORTS_ON]-(a:Article) RETURN count(DISTINCT a.url)"
    )
    event_article_count = res_event_arts.result_set[0][0] if res_event_arts.result_set else 0

    # Articles with chunks in FalkorDB
    res_chunked = falkordb.graph.query(
        "MATCH (a:Article)-[:HAS_CHUNK]->(c:Chunk) RETURN count(DISTINCT a.url)"
    )
    articles_with_chunks = res_chunked.result_set[0][0] if res_chunked.result_set else 0

    # Articles with full text in MongoDB
    mongo_with_text = await mongo_db.articles.count_documents({"content_extracted": True})
    mongo_total = await mongo_db.articles.count_documents({})

    return {
        "chunk_nodes": chunk_stats["chunk_nodes"],
        "has_chunk_edges": chunk_stats["has_chunk_edges"],
        "event_articles_in_falkordb": event_article_count,
        "articles_with_chunks_in_falkordb": articles_with_chunks,
        "mongo_extracted_articles": mongo_with_text,
        "mongo_total_articles": mongo_total,
    }


def print_status(stats: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("           FalkorDB Chunks & Native Vector RAG Status")
    print("=" * 60)
    print(f"  FalkorDB :Chunk nodes:               {stats['chunk_nodes']}")
    print(f"  FalkorDB :HAS_CHUNK edges:           {stats['has_chunk_edges']}")
    print(f"  FalkorDB Articles with Chunks:       {stats['articles_with_chunks_in_falkordb']}")
    print(f"  FalkorDB Articles linked to Events:  {stats['event_articles_in_falkordb']}")
    print(f"  MongoDB Extracted Full-Text Docs:    {stats['mongo_extracted_articles']}")
    print(f"  MongoDB Total Article Docs:          {stats['mongo_total_articles']}")
    if stats['event_articles_in_falkordb'] > 0:
        cov = (stats['articles_with_chunks_in_falkordb'] / stats['event_articles_in_falkordb']) * 100
        print(f"  Event Articles Coverage:             {cov:.1f}%")
    print("=" * 60 + "\n")


async def run_chunking(
    limit: int = 0,
    batch_size: int = 64,
    all_articles: bool = False,
    force: bool = False,
    clear_first: bool = False,
) -> None:
    settings = get_settings()
    falkordb = FalkorDBClient(settings)
    falkordb.init_schema()

    if clear_first:
        logger.warning("Clearing existing :Chunk nodes from FalkorDB...")
        falkordb.graph.query("MATCH (c:Chunk) DETACH DELETE c")
        logger.info("Cleared all :Chunk nodes.")

    mongo_client = AsyncIOMotorClient(settings.mongodb_url)
    mongo_db = mongo_client[settings.mongodb_db_name]

    # 1. Determine target URLs
    if all_articles:
        logger.info("Targeting all articles with extracted content in MongoDB...")
        cursor = mongo_db.articles.find(
            {"content_extracted": True},
            {"url": 1}
        )
        target_urls = [doc["url"] async for doc in cursor if doc.get("url")]
    else:
        logger.info("Targeting articles linked to Events in FalkorDB (UC-01, UC-02, UC-03)...")
        res = falkordb.graph.query(
            "MATCH (e:Event)<-[:REPORTS_ON]-(a:Article) RETURN DISTINCT a.url"
        )
        target_urls = [row[0] for row in res.result_set if row[0]]

    logger.info(f"Identified {len(target_urls)} candidate articles.")

    # 2. Filter out already-chunked articles if not force
    if not force:
        res_existing = falkordb.graph.query(
            "MATCH (a:Article)-[:HAS_CHUNK]->(c:Chunk) RETURN DISTINCT a.url"
        )
        existing_urls: Set[str] = {row[0] for row in res_existing.result_set}
        target_urls = [u for u in target_urls if u not in existing_urls]
        logger.info(
            f"Filtered out {len(existing_urls)} already-chunked articles. "
            f"{len(target_urls)} articles remaining to process."
        )

    if limit > 0:
        target_urls = target_urls[:limit]
        logger.info(f"Applied limit: processing {len(target_urls)} articles.")

    if not target_urls:
        logger.info("No articles to process. Everything is up to date!")
        stats = await get_stats(falkordb, mongo_db)
        print_status(stats)
        return

    # 3. Initialize chunker and embedding service
    chunker = NewsChunker(target_words=150, max_words=185, min_para_words=15, overlap_sentences=1)
    embedding_service = EmbeddingService(model_name=settings.embedding_model_name, batch_size=batch_size)
    # Warm up model
    _ = embedding_service.model

    total_articles = len(target_urls)
    total_chunks_written = 0
    t_start = time.time()

    # Process in article batches (e.g., 50 articles at a time)
    article_batch_size = 50
    for i in range(0, total_articles, article_batch_size):
        batch_urls = target_urls[i:i + article_batch_size]

        # Fetch full text from MongoDB
        docs_cursor = mongo_db.articles.find(
            {"url": {"$in": batch_urls}, "content_extracted": True},
            {"url": 1, "title": 1, "full_text": 1}
        )
        docs = [d async for d in docs_cursor if d.get("full_text")]

        if not docs:
            continue

        # Chunk all docs in this batch
        batch_chunks_flat: List[Dict[str, Any]] = []
        doc_chunk_map: Dict[str, List[Dict[str, Any]]] = {}

        for doc in docs:
            url = doc["url"]
            title = doc.get("title") or ""
            full_text = doc["full_text"]
            chunks = chunker.chunk_article(title=title, full_text=full_text, article_url=url)
            if chunks:
                doc_chunk_map[url] = chunks
                batch_chunks_flat.extend(chunks)

        if not batch_chunks_flat:
            continue

        # Batch encode all chunk embed_texts
        embed_texts = [c["embed_text"] for c in batch_chunks_flat]
        embeddings = embedding_service.encode_texts(embed_texts, batch_size=batch_size)

        for idx, chk in enumerate(batch_chunks_flat):
            chk["embedding"] = embeddings[idx].tolist()

        # Write to FalkorDB per article
        for url, chunks in doc_chunk_map.items():
            written = falkordb.write_article_chunks(url, chunks)
            total_chunks_written += written

        elapsed = time.time() - t_start
        processed_count = min(i + article_batch_size, total_articles)
        speed_art = processed_count / max(elapsed, 0.001)
        speed_chk = total_chunks_written / max(elapsed, 0.001)

        logger.info(
            f"Progress: [{processed_count}/{total_articles}] articles ({processed_count/total_articles*100:.1f}%) | "
            f"{total_chunks_written} chunks created | "
            f"{speed_art:.1f} art/s | {speed_chk:.1f} chk/s | Elapsed: {elapsed:.1f}s"
        )

    t_total = time.time() - t_start
    logger.info(
        f"Completed chunking in {t_total:.2f}s: "
        f"{total_chunks_written} chunks across {total_articles} articles."
    )

    stats = await get_stats(falkordb, mongo_db)
    print_status(stats)


def main():
    parser = argparse.ArgumentParser(
        description="Extract semantic chunks and generate 384-d vector embeddings in FalkorDB."
    )
    parser.add_argument(
        "--status", action="store_true", help="Print current chunking and vector index status."
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Maximum number of articles to process (0 = all)."
    )
    parser.add_argument(
        "--batch-size", type=int, default=64, help="Batch size for SentenceTransformer encoding (default: 64)."
    )
    parser.add_argument(
        "--all-articles", action="store_true", help="Process all articles in MongoDB instead of only event articles."
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-process articles even if chunks already exist."
    )
    parser.add_argument(
        "--clear", action="store_true", help="Clear all existing :Chunk nodes before processing."
    )

    args = parser.parse_args()

    if args.status:
        settings = get_settings()
        falkordb = FalkorDBClient(settings)
        mongo_client = AsyncIOMotorClient(settings.mongodb_url)
        mongo_db = mongo_client[settings.mongodb_db_name]
        stats = asyncio.run(get_stats(falkordb, mongo_db))
        print_status(stats)
        return

    asyncio.run(
        run_chunking(
            limit=args.limit,
            batch_size=args.batch_size,
            all_articles=args.all_articles,
            force=args.force,
            clear_first=args.clear,
        )
    )


if __name__ == "__main__":
    main()
