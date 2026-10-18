import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import Settings, get_settings
from app.core.db import init_db
from app.models.documents.phase3_ledger import Phase3LedgerDocument
from app.services.falkordb_client import FalkorDBClient
from app.services.groq_client import GroqClient
from app.services.phase3_tools import Phase3Tools, PHASE3_TOOLS_SPEC

logger = logging.getLogger("news_pipeline.phase3")

SYSTEM_PROMPT = """You are WorldGraph Reasoning Agent (graph_agent_v1).
Analyze the event and establish validated causal/impact edges to real events/entities using `write_edge`.
Allowed edge types:
- CAUSED: Direct cause (Event -> Event). Requires >=1 article URL in evidence_ids.
- CONTRIBUTED_TO: Partial cause (Event -> Event). Requires >=1 article URL in evidence_ids.
- AFFECTS: Impact on actor/sector (Event -> Entity).
- IMPACTED: Entity impact on event (Entity -> Event).
- RELATED_TO: Thematic/geopolitical link (Event -> Event).
Rules: Confidence >= 0.55. No self-loops. Cite real IDs and URLs provided in context. Be decisive: call `write_edge` immediately for verified links and finish in 1-2 turns.
"""


class Phase3Pipeline:
    """
    Executes Phase 3 of WorldGraph: Reasoning (Autonomous LLM Causal Linking via Tools).
    - Event-by-event processing with crash resilience via Phase3LedgerDocument.
    - Autonomous agent loop with max 25 tool calls per event.
    - Python-guarded tool execution enforcing Trust Property Contract and confidence floor.
    - Real-time persistence of reasoning edges (:CAUSED, :CONTRIBUTED_TO, :AFFECTS, :IMPACTED, :RELATED_TO).
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.falkordb = FalkorDBClient(self.settings)
        self.groq_client = GroqClient(self.settings)
        self.tools_engine = Phase3Tools(self.falkordb, self.settings)

    async def reason_about_event(
        self,
        event: Dict[str, Any],
        force: bool = False,
        max_turns: int = 4,
    ) -> Dict[str, Any]:
        """
        Runs the reasoning agent loop for a single Event:
        Loads event context and candidates, launches Groq tool-calling loop,
        executes guarded tool calls, and records progress in Phase3LedgerDocument.
        """
        event_id = event["event_id"]
        await init_db(self.settings)

        # 1. Check Ledger
        ledger = await Phase3LedgerDocument.find_one(Phase3LedgerDocument.event_id == event_id)
        if ledger and ledger.status == "COMPLETED" and not force:
            logger.info(f"⏭️  Event {event_id} already COMPLETED in Phase 3 ledger. Skipping.")
            return {
                "event_id": event_id,
                "status": "SKIPPED",
                "edges_written": ledger.edges_written,
                "caused_edges": ledger.caused_edges,
                "contributed_edges": ledger.contributed_edges,
                "affects_edges": ledger.affects_edges,
                "impacted_edges": ledger.impacted_edges,
                "related_edges": ledger.related_edges,
            }

        if ledger is None:
            ledger = Phase3LedgerDocument(event_id=event_id, status="PROCESSING")
            await ledger.insert()
        else:
            ledger.status = "PROCESSING"
            ledger.updated_at = datetime.utcnow()
            await ledger.save()

        started_at = datetime.utcnow()
        tool_calls_total = 0
        edges_created = {
            "CAUSED": 0,
            "CONTRIBUTED_TO": 0,
            "AFFECTS": 0,
            "IMPACTED": 0,
            "RELATED_TO": 0,
        }

        try:
            # 2. Gather Initial Event Context & Candidates
            context = await self.tools_engine.get_event_context(event_id)
            candidates = await self.tools_engine.find_candidate_links(event_id, limit=6)

            # Compact entities list: name, type, role
            ents_list = [
                f"{e.get('canonical_name')} ({e.get('type')}, role: {e.get('role')})"
                for e in context.get('entities', [])[:8]
            ]
            ents_str = ", ".join(ents_list) if ents_list else "None identified"

            # Compact articles list: title, snippet, URL
            arts_lines = []
            for a in context.get('articles', [])[:3]:
                snippet = (a.get('description') or '')[:120].replace('\n', ' ')
                arts_lines.append(f"- {a.get('title')} | URL: {a.get('url')} | Snippet: {snippet}")
            arts_str = "\n".join(arts_lines) if arts_lines else "No reporting articles available."

            # Compact candidate links list: id, label, title, reason
            cands_lines = []
            for c in candidates.get('candidates', [])[:5]:
                cands_lines.append(f"- [{c.get('id')}] ({c.get('label')}) {c.get('title')}: {c.get('reason')}")
            cands_str = "\n".join(cands_lines) if cands_lines else "No candidate events or entities pre-discovered."

            initial_prompt = (
                f"TARGET EVENT TO ANALYZE:\n"
                f"- Event ID: {event_id}\n"
                f"- Title: {context.get('title', '')}\n"
                f"- Summary: {context.get('summary', '')}\n"
                f"- Category: {context.get('category', 'General')} | Date: {context.get('occurred_at', '')}\n\n"
                f"Directly Involved Entities:\n{ents_str}\n\n"
                f"Key Reporting Articles:\n{arts_str}\n\n"
                f"Pre-discovered Candidate Connections:\n{cands_str}\n\n"
                "Please analyze this event. Use tools to investigate further if needed, "
                "and call `write_edge` to establish justified causal or impact links."
            )

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": initial_prompt},
            ]

            turn = 0
            agent_done = False

            # 3. Agent Tool Calling Loop (max 25 tool calls or max_turns)
            while turn < max_turns and not agent_done and tool_calls_total < 25:
                turn += 1
                assistant_msg = await self.groq_client.chat_completion_with_tools(
                    messages=messages,
                    tools=PHASE3_TOOLS_SPEC,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=1024,
                    max_retries=6,
                )

                tool_calls = assistant_msg.get("tool_calls")
                content = assistant_msg.get("content") or ""

                if not tool_calls:
                    # Model provided text response without additional tool calls -> finished
                    logger.debug(f"Agent finished reasoning for {event_id}: {content[:100]}...")
                    messages.append({"role": "assistant", "content": content})
                    agent_done = True
                    break

                # Append assistant message with its tool calls
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                })

                # Execute each tool call
                for tc in tool_calls:
                    tool_calls_total += 1
                    tc_id = tc.get("id") or f"call_{tool_calls_total}"
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args_raw = fn.get("arguments", "{}")

                    try:
                        if isinstance(fn_args_raw, dict):
                            fn_args = fn_args_raw
                        else:
                            fn_args = json.loads(fn_args_raw)
                    except Exception:
                        fn_args = {}

                    logger.info(f"🤖 Agent [{event_id}] Tool Call #{tool_calls_total}: {fn_name}({list(fn_args.keys())})")
                    tool_result = await self.tools_engine.execute_tool(fn_name, fn_args)

                    # Track edge creations
                    if fn_name == "write_edge" and tool_result.get("success"):
                        edge_type = tool_result.get("edge_type")
                        if edge_type in edges_created:
                            edges_created[edge_type] += 1
                            logger.info(
                                f"✓ Reasoning edge created: ({tool_result.get('source_id')})"
                                f"-[:{edge_type}]->({tool_result.get('target_id')})"
                            )

                    # Compact tool result message content to preserve token budget
                    if fn_name == "write_edge":
                        compact_res = {
                            "success": tool_result.get("success"),
                            "edge": f"({tool_result.get('source_id')})-[:{tool_result.get('edge_type')}]->({tool_result.get('target_id')})",
                            "message": tool_result.get("message", "ok"),
                        }
                    else:
                        compact_res = tool_result

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": json.dumps(compact_res),
                    })

                    if tool_calls_total >= 25:
                        logger.info(f"Event {event_id} reached 25 tool calls limit.")
                        break

            # 4. Update Ledger on Success
            total_edges = sum(edges_created.values())
            ledger.status = "COMPLETED"
            ledger.tool_calls_count = tool_calls_total
            ledger.edges_written = total_edges
            ledger.caused_edges = edges_created["CAUSED"]
            ledger.contributed_edges = edges_created["CONTRIBUTED_TO"]
            ledger.affects_edges = edges_created["AFFECTS"]
            ledger.impacted_edges = edges_created["IMPACTED"]
            ledger.related_edges = edges_created["RELATED_TO"]
            ledger.error_message = None
            ledger.started_at = started_at
            ledger.completed_at = datetime.utcnow()
            ledger.updated_at = datetime.utcnow()
            await ledger.save()

            logger.info(
                f"✅ Phase 3 Reasoning COMPLETED for {event_id}: {total_edges} edge(s) "
                f"(CAUSED={edges_created['CAUSED']}, AFFECTS={edges_created['AFFECTS']}, "
                f"CONTRIBUTED={edges_created['CONTRIBUTED_TO']}, IMPACTED={edges_created['IMPACTED']}, "
                f"RELATED={edges_created['RELATED_TO']}) in {tool_calls_total} tool call(s)."
            )

            return {
                "event_id": event_id,
                "status": "COMPLETED",
                "tool_calls_count": tool_calls_total,
                "edges_written": total_edges,
                "edges_breakdown": edges_created,
            }

        except Exception as e:
            logger.error(f"❌ Phase 3 Reasoning FAILED for event {event_id}: {e}", exc_info=True)
            ledger.status = "FAILED"
            ledger.error_message = str(e)
            ledger.updated_at = datetime.utcnow()
            await ledger.save()
            return {
                "event_id": event_id,
                "status": "FAILED",
                "error": str(e),
            }

    async def run_all(
        self,
        limit: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Runs Phase 3 reasoning across all events in FalkorDB sequentially.
        Event-by-event checkpoints allow pausing and resuming at any time.
        """
        await init_db(self.settings)
        all_events = self.falkordb.get_all_events()
        logger.info(f"Total events found in FalkorDB: {len(all_events)}")

        target_events = all_events[:limit] if limit else all_events
        completed_count = 0
        skipped_count = 0
        failed_count = 0
        total_edges_new = 0

        for i, ev in enumerate(target_events, 1):
            eid = ev["event_id"]
            logger.info(f"\n--- [{i}/{len(target_events)}] Processing Event {eid} ---")
            res = await self.reason_about_event(ev, force=force)

            if res.get("status") == "COMPLETED":
                completed_count += 1
                total_edges_new += res.get("edges_written", 0)
            elif res.get("status") == "SKIPPED":
                skipped_count += 1
            else:
                failed_count += 1

            # Brief pause between events to manage rate limits cleanly
            await asyncio.sleep(0.5)

        return {
            "total_targeted": len(target_events),
            "completed": completed_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "new_edges_written": total_edges_new,
        }

    async def get_summary(self) -> Dict[str, Any]:
        """Provides full progress and statistics for Phase 3."""
        await init_db(self.settings)

        total_events = len(self.falkordb.get_all_events())
        ledger_completed = await Phase3LedgerDocument.find(
            Phase3LedgerDocument.status == "COMPLETED"
        ).count()
        ledger_pending = await Phase3LedgerDocument.find(
            Phase3LedgerDocument.status == "PENDING"
        ).count()
        ledger_failed = await Phase3LedgerDocument.find(
            Phase3LedgerDocument.status == "FAILED"
        ).count()

        reasoning_stats = self.falkordb.get_reasoning_stats()

        return {
            "total_events_in_graph": total_events,
            "events_completed": ledger_completed,
            "events_pending": ledger_pending,
            "events_failed": ledger_failed,
            "reasoning_stats": reasoning_stats,
        }
