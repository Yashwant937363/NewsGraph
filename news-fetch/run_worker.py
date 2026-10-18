#!/usr/bin/env python3
"""
CLI runner for the NewsFetch Worker.
Can run the fetch worker or inspect current article counts and progress in MongoDB.
"""
import argparse
import asyncio
import json
import logging
import sys
from app.core.db import close_db
from app.core.logging import setup_logging
from app.workers.fetch_worker import NewsFetchWorker


def parse_args():
    parser = argparse.ArgumentParser(
        description="NewsAPI 150-Query Ingestion Worker with MongoDB Deduplication"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Inspect current number of articles and progress in MongoDB without fetching",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of queries to execute (e.g. --limit 5 for testing)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset existing progress state and restart from query 1",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        default="2026-09-08",
        help="Start date (YYYY-MM-DD), default: 2026-09-08",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default="2026-10-07",
        help="End date (YYYY-MM-DD), default: 2026-10-07",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    setup_logging(level=args.log_level)

    worker = NewsFetchWorker(
        date_from=args.from_date,
        date_to=args.to_date,
    )

    try:
        if args.status:
            summary = await worker.get_summary()
            print("\n================== NEWS DB STATUS ==================")
            print(f"Total articles in MongoDB    : {summary['total_articles_in_db']}")
            print(f"Distinct news sources        : {summary['distinct_sources']}")
            print(f"Queries completed            : {summary['queries_completed']} / {summary['total_queries']}")
            print(f"Total NewsAPI requests made  : {summary['total_api_calls']}")
            print(f"Total raw articles fetched   : {summary['total_fetched']}")
            print(f"New articles inserted        : {summary['total_inserted']}")
            print(f"Duplicates skipped           : {summary['total_duplicates_skipped']}")
            print(f"Worker completed all queries : {summary['is_completed']}")
            if summary["sample_articles"]:
                print("\nSample articles currently stored:")
                for i, sample in enumerate(summary["sample_articles"], 1):
                    print(f"  {i}. [{sample['source']}] {sample['title']}")
                    print(f"     URL: {sample['url']}")
                    print(f"     Date: {sample['published_at']}")
            print("====================================================\n")
            return

        print(f"\nStarting ingestion worker for date range: {args.from_date} -> {args.to_date}")
        if args.limit:
            print(f"Limiting to first {args.limit} queries.")

        summary = await worker.run(
            reset_state=args.reset,
            limit_queries=args.limit,
        )

        print("\n================ RUN FINISHED ================")
        print(f"Total articles in MongoDB    : {summary['total_articles_in_db']}")
        print(f"Distinct news sources        : {summary['distinct_sources']}")
        print(f"Queries completed            : {summary['queries_completed']} / {summary['total_queries']}")
        print(f"New articles inserted        : {summary['total_inserted']}")
        print(f"Duplicates skipped           : {summary['total_duplicates_skipped']}")
        print("==============================================\n")

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
