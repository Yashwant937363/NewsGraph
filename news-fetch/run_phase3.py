#!/usr/bin/env python3
"""
CLI runner for Phase 3 of WorldGraph:
Autonomous LLM Agent Reasoning -> Tool Calling Loop -> Guarded Edge Writes
Produces: :CAUSED, :CONTRIBUTED_TO, :AFFECTS, :IMPACTED, :RELATED_TO edges
with complete Trust Property Contract and audit trail.
"""
import argparse
import asyncio
import sys

from app.core.db import close_db
from app.core.logging import setup_logging
from app.services.phase3_pipeline import Phase3Pipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 3 Pipeline: Autonomous Reasoning Agent & Causal Graph"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display current Phase 3 ledger progress and FalkorDB reasoning edge statistics",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run Phase 3 reasoning for all events in FalkorDB",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N events (useful for testing or batch runs)",
    )
    parser.add_argument(
        "--event-id",
        type=str,
        default=None,
        help="Reason about a specific event by event_id",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process events even if already marked COMPLETED in ledger",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Groq model to use (e.g. 'openai/gpt-oss-120b' or 'openai/gpt-oss-20b')",
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=None,
        help="Groq requests per minute rate pacing limit (default: 8)",
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

    pipeline = Phase3Pipeline()
    if args.model:
        pipeline.groq_client.active_model = args.model
        pipeline.settings.groq_model = args.model
    if args.rpm is not None:
        pipeline.groq_client.requests_per_minute = args.rpm
        pipeline.settings.groq_requests_per_minute = args.rpm

    try:
        if args.status:
            summary = await pipeline.get_summary()
            rs = summary["reasoning_stats"]
            print("\n================== PHASE 3 STATUS ==================")
            print(f"Total Events in FalkorDB     : {summary['total_events_in_graph']}")
            print(f"Events Completed in Ledger   : {summary['events_completed']}")
            print(f"Events Pending in Ledger     : {summary['events_pending']}")
            print(f"Events Failed in Ledger      : {summary['events_failed']}")
            print("\n--- FalkorDB Reasoning Edges ---")
            print(f"  -[:CAUSED]-> edges         : {rs.get('caused_edges', 0)}")
            print(f"  -[:CONTRIBUTED_TO]-> edges : {rs.get('contributed_edges', 0)}")
            print(f"  -[:AFFECTS]-> edges        : {rs.get('affects_edges', 0)}")
            print(f"  -[:IMPACTED]-> edges       : {rs.get('impacted_edges', 0)}")
            print(f"  -[:RELATED_TO]-> edges     : {rs.get('related_to_edges', 0)}")
            print("\n--- Trust Property Contract Statuses ---")
            print(f"  status='confirmed'         : {rs.get('confirmed_edges', 0)}")
            print(f"  status='inferred'          : {rs.get('inferred_edges', 0)}")
            print(f"  status='related'           : {rs.get('related_edges', 0)}")
            print("====================================================\n")
            return

        if args.event_id:
            events = pipeline.falkordb.get_all_events()
            target = next((e for e in events if e["event_id"] == args.event_id), None)
            if not target:
                print(f"Error: Event '{args.event_id}' not found in FalkorDB.")
                sys.exit(1)

            print(f"\n🚀 Running Phase 3 reasoning for event {args.event_id}...")
            res = await pipeline.reason_about_event(target, force=args.force)
            print(f"Result: {res}\n")
            return

        if args.run_all or args.limit is not None:
            limit_str = f" (limit={args.limit})" if args.limit else " (ALL)"
            print(f"\n🚀 Launching Phase 3 Reasoning across events{limit_str}...")
            res = await pipeline.run_all(limit=args.limit, force=args.force)
            print(f"\n✓ Completed: {res}\n")
            return

        print("No action specified. Run with --status, --run-all, --limit N, or --event-id <id>.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
