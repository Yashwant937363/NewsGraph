#!/usr/bin/env python3
"""
CLI runner for Phase 1 of WorldGraph:
Articles -> Events -> Stories -> FalkorDB + Temporal Linking.
"""
import argparse
import asyncio
import logging
import sys

from app.core.db import close_db
from app.core.logging import setup_logging
from app.services.phase1_pipeline import Phase1Pipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 1 Pipeline: MongoDB -> Events -> Stories -> FalkorDB"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display current Phase 1 ledger progress and FalkorDB graph stats",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run Phase 1 for all available dates in MongoDB chronologically",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Run Phase 1 for a specific date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit-days",
        type=int,
        default=None,
        help="Process only first N dates (useful for fast verification)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process dates even if already marked COMPLETED in ledger",
    )
    parser.add_argument(
        "--clear-graph",
        action="store_true",
        help="Delete all nodes and edges in FalkorDB before running",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    setup_logging(level=args.log_level)

    pipeline = Phase1Pipeline()

    try:
        if args.clear_graph:
            pipeline.falkordb.clear_graph()
            print("✓ FalkorDB graph reset complete.")

        if args.status:
            summary = await pipeline.get_summary()
            stats = summary["graph_stats"]
            print("\n================== PHASE 1 STATUS ==================")
            print(f"Total Dates in MongoDB       : {summary['total_dates_in_mongo']}")
            print(f"Dates Completed in Ledger    : {summary['dates_completed']}")
            print(f"Dates Pending                : {summary['dates_pending']}")
            print(f"Dates Failed                 : {summary['dates_failed']}")
            print("\n--- FalkorDB Graph Elements ---")
            print(f"  :Article nodes             : {stats.get('articles', 0)}")
            print(f"  :Source nodes              : {stats.get('sources', 0)}")
            print(f"  :Event nodes               : {stats.get('events', 0)}")
            print(f"  :Story nodes               : {stats.get('stories', 0)}")
            print(f"  -[:REPORTS_ON]-> edges     : {stats.get('reports_on_edges', 0)}")
            print(f"  -[:PUBLISHED_BY]-> edges   : {stats.get('published_by_edges', 0)}")
            print(f"  -[:PART_OF]-> edges        : {stats.get('part_of_edges', 0)}")
            print(f"  -[:PRECEDED]-> edges       : {stats.get('preceded_edges', 0)}")
            print("====================================================\n")
            return

        if args.date:
            print(f"\nRunning Phase 1 for date: {args.date}")
            res = await pipeline.process_date(args.date, force=args.force)
            print(f"\nCompleted {args.date}: {res}\n")
            return

        if args.run_all or args.limit_days is not None:
            results = await pipeline.process_all_dates(
                limit_days=args.limit_days,
                force=args.force,
            )
            print("\n================ RUN SUMMARY ================")
            print(f"Processed {len(results)} dates.")
            summary = await pipeline.get_summary()
            stats = summary["graph_stats"]
            print(f"Total Events in FalkorDB   : {stats.get('events', 0)}")
            print(f"Total Stories in FalkorDB  : {stats.get('stories', 0)}")
            print(f"Total Articles in FalkorDB : {stats.get('articles', 0)}")
            print(f"Preceded/Followed Edges    : {stats.get('preceded_edges', 0)}")
            print("=============================================\n")
            return

        # If no action specified, show status
        summary = await pipeline.get_summary()
        stats = summary["graph_stats"]
        print("\n[Notice] No run flag specified. Showing current status. Use --run-all or --limit-days N to run.")
        print(f"Dates Completed: {summary['dates_completed']} / {summary['total_dates_in_mongo']}")
        print(f"FalkorDB Events: {stats.get('events', 0)} | Stories: {stats.get('stories', 0)}\n")

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
