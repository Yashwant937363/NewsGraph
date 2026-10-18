#!/usr/bin/env python3
"""
CLI runner for Phase 2 of WorldGraph:
Event Enrichment -> Groq LLM Entity Extraction -> Normalization ->
FalkorDB Typed Entities (:Entity:Country, :Company, :Person, etc.) +
Mentions & Involves Edges + Rule-Based RELATED_TO & Statements.
"""
import argparse
import asyncio
import sys

from app.core.db import close_db
from app.core.logging import setup_logging
from app.services.phase2_pipeline import Phase2Pipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 2 Pipeline: Event Enrichment -> Entities -> FalkorDB"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display current Phase 2 ledger progress and FalkorDB entity stats",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run Phase 2 enrichment for all events in FalkorDB",
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
        help="Enrich a specific event by event_id",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-enrich events even if already marked COMPLETED in ledger",
    )
    parser.add_argument(
        "--rules-only",
        action="store_true",
        help="Run only the rule-based passes (country RELATED_TO edges)",
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

    pipeline = Phase2Pipeline()

    try:
        if args.status:
            summary = await pipeline.get_summary()
            p2 = summary["phase2_stats"]
            base = summary["base_stats"]
            print("\n================== PHASE 2 STATUS ==================")
            print(f"Total Events in FalkorDB     : {summary['total_events_in_graph']}")
            print(f"Events Completed in Ledger   : {summary['events_completed']}")
            print(f"Events Pending in Ledger     : {summary['events_pending']}")
            print(f"Events Failed in Ledger      : {summary['events_failed']}")
            print("\n--- FalkorDB Phase 2 Entities ---")
            print(f"  :Entity nodes (total)      : {p2.get('entities_total', 0)}")
            print(f"  :Country nodes             : {p2.get('countries', 0)}")
            print(f"  :Company nodes             : {p2.get('companies', 0)}")
            print(f"  :Person nodes              : {p2.get('persons', 0)}")
            print(f"  :Organization nodes        : {p2.get('organizations', 0)}")
            print(f"  :Industry nodes            : {p2.get('industries', 0)}")
            print(f"  :Commodity nodes           : {p2.get('commodities', 0)}")
            print(f"  :Location nodes            : {p2.get('locations', 0)}")
            print(f"  :Statement nodes           : {p2.get('statements', 0)}")
            print("\n--- FalkorDB Phase 2 Edges ---")
            print(f"  -[:INVOLVES]-> edges       : {p2.get('involves_edges', 0)}")
            print(f"  -[:MENTIONS]-> edges       : {p2.get('mentions_edges', 0)}")
            print(f"  -[:RELATED_TO]-> edges     : {p2.get('related_to_edges', 0)}")
            print("====================================================\n")
            return

        if args.rules_only:
            count = await pipeline.run_rule_based_links()
            print(f"\n✓ Rule-based country RELATED_TO pass completed. Edges: {count}\n")
            return

        if args.event_id:
            print(f"\nEnriching single event: {args.event_id}")
            # Fetch event details from FalkorDB
            events = pipeline.falkordb.get_all_events()
            matching = [e for e in events if e["event_id"] == args.event_id]
            if not matching:
                print(f"Error: Event {args.event_id} not found in FalkorDB.")
                sys.exit(1)
            res = await pipeline.enrich_event(matching[0], force=args.force)
            print(f"\nCompleted: {res}\n")
            return

        if args.run_all or args.limit is not None:
            results = await pipeline.process_all_events(
                limit=args.limit,
                force=args.force,
            )
            print("\n================ RUN SUMMARY ================")
            print(f"Processed {len(results)} events.")
            summary = await pipeline.get_summary()
            p2 = summary["phase2_stats"]
            print(f"Total Entities in FalkorDB   : {p2.get('entities_total', 0)}")
            print(f"Countries: {p2.get('countries', 0)} | Companies: {p2.get('companies', 0)} | Persons: {p2.get('persons', 0)}")
            print(f"INVOLVES edges: {p2.get('involves_edges', 0)} | MENTIONS edges: {p2.get('mentions_edges', 0)}")
            print(f"RELATED_TO edges: {p2.get('related_to_edges', 0)}")
            print("=============================================\n")
            return

        # Default notice
        summary = await pipeline.get_summary()
        print("\n[Notice] No action flag specified. Use --run-all or --limit N or --status.")
        print(f"Events Completed: {summary['events_completed']} / {summary['total_events_in_graph']}\n")

    finally:
        await pipeline.groq_client.close()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
