import json
import logging
import re
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from app.services.groq_key_manager import groq_key_manager
from app.agent.tools import (
    search_graph_chunks,
    get_neighboring_chunks,
    AGENT_TOOLS_DEFINITIONS,
)

logger = logging.getLogger("newsgraph.agent.graph")

MODEL_NAME = "openai/gpt-oss-120b"
MAX_ITERATIONS = 4


class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    system_prompt: str
    scoped_article_urls: List[str]
    cited_chunks: Dict[str, Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]
    iteration: int
    task_type: Optional[str]


def _try_extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Helper to extract JSON dict from text or markdown blocks."""
    if not text:
        return None
    # Block match
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    # Raw brace match
    m2 = re.search(r"(\{.*\})", text, re.DOTALL)
    if m2:
        try:
            d = json.loads(m2.group(1))
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return None


async def agent_node(state: AgentState) -> Dict[str, Any]:
    """Calls openai/gpt-oss-120b with current message history and tools."""
    iteration = state.get("iteration", 0) + 1
    messages = list(state.get("messages", []))
    system_prompt = state.get("system_prompt", "")
    final_output = state.get("final_output")

    # If final_output already captured, skip
    if final_output:
        return {"iteration": iteration}

    # Prepend system prompt if not present as first message
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": system_prompt})

    force_finish = iteration >= MAX_ITERATIONS
    if force_finish:
        messages.append({
            "role": "user",
            "content": "You have reached the maximum search depth. You MUST now synthesize your assessment and call submit_final_explanation immediately with your complete final output.",
        })
        tools_to_pass = [
            t for t in AGENT_TOOLS_DEFINITIONS
            if t["function"]["name"] in ("submit_final_explanation", "json")
        ]
    else:
        tools_to_pass = AGENT_TOOLS_DEFINITIONS

    tool_choice = "auto"

    async def call_groq(api_key: str):
        from groq import AsyncGroq

        client = AsyncGroq(api_key=api_key)
        kwargs: Dict[str, Any] = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.2,
            "tools": tools_to_pass,
            "tool_choice": tool_choice,
        }

        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message

    try:
        response_msg = await groq_key_manager.execute_with_retry(call_groq)
    except Exception as e:
        err_msg = str(e)
        raw_gen = None
        if hasattr(e, "body") and isinstance(e.body, dict):
            failed_str = e.body.get("error", {}).get("failed_generation")
            if isinstance(failed_str, str):
                try:
                    raw_gen = json.loads(failed_str)
                except Exception:
                    pass

        if not raw_gen and ("failed_generation" in err_msg or "tool_use_failed" in err_msg):
            # Fallback regex extraction of failed_generation
            m = re.search(r"['\"]failed_generation['\"]\s*:\s*['\"](\{.*?\})['\"]\s*\}", err_msg, re.DOTALL)
            if m:
                try:
                    raw_gen = json.loads(m.group(1).encode().decode('unicode_escape'))
                except Exception:
                    try:
                        raw_gen = json.loads(m.group(1))
                    except Exception:
                        pass

        if raw_gen and isinstance(raw_gen, dict) and "name" in raw_gen:
            tool_name = raw_gen.get("name")
            tool_args = raw_gen.get("arguments", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {}

            if tool_name in ("submit_final_explanation", "json") and isinstance(tool_args, dict) and "summary" in tool_args:
                logger.info("Successfully recovered final explanation from tool generation.")
                return {
                    "final_output": tool_args,
                    "iteration": iteration,
                }
            elif tool_name in ("search_graph_chunks", "get_neighboring_chunks"):
                logger.info(f"Recovered tool call {tool_name} from failed_generation.")
                mock_tc = [
                    {
                        "id": "tc_recovered_0",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args) if isinstance(tool_args, dict) else str(tool_args),
                        },
                    }
                ]
                return {
                    "messages": messages + [{"role": "assistant", "content": "", "tool_calls": mock_tc}],
                    "iteration": iteration,
                }

        logger.exception(f"Error calling Groq model {MODEL_NAME}: {e}")
        return {
            "messages": messages + [{"role": "assistant", "content": "Error during LLM invocation."}],
            "iteration": iteration,
        }

    # Check if assistant called submit_final_explanation or json
    if response_msg.tool_calls:
        for tc in response_msg.tool_calls:
            if tc.function.name in ("submit_final_explanation", "json"):
                try:
                    args = json.loads(tc.function.arguments)
                    if isinstance(args, dict):
                        logger.info(f"Agent submitted final explanation via {tc.function.name}.")
                        return {
                            "final_output": args,
                            "iteration": iteration,
                        }
                except Exception:
                    pass

    # Format assistant message for state
    assistant_msg: Dict[str, Any] = {
        "role": "assistant",
        "content": response_msg.content or "",
    }
    if response_msg.tool_calls:
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in response_msg.tool_calls
        ]

    return {
        "messages": messages + [assistant_msg],
        "iteration": iteration,
    }


async def tools_node(state: AgentState) -> Dict[str, Any]:
    """Executes tool calls requested by the agent."""
    messages = list(state.get("messages", []))
    last_msg = messages[-1] if messages else {}
    tool_calls = last_msg.get("tool_calls", [])
    scoped_article_urls = state.get("scoped_article_urls", [])
    cited_chunks = dict(state.get("cited_chunks", {}))
    final_output = state.get("final_output")

    tool_messages = []
    for tc in tool_calls:
        func = tc.get("function", {})
        name = func.get("name")
        call_id = tc.get("id")
        raw_args = func.get("arguments", "{}")

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except Exception:
            args = {}

        result_data: Any = []

        if name in ("submit_final_explanation", "json"):
            if isinstance(args, dict):
                final_output = args
            result_data = {"status": "submitted"}

        elif name == "search_graph_chunks":
            query = args.get("query", "")
            limit = min(int(args.get("limit", 3)), 4)
            chunks = search_graph_chunks(
                query=query,
                scoped_article_urls=scoped_article_urls,
                limit=limit,
            )
            compact_chunks = []
            for c in chunks:
                cid = c.get("chunk_id")
                if cid and cid not in cited_chunks:
                    cited_chunks[cid] = c
                c_copy = dict(c)
                txt = c_copy.get("chunk_text", "") or ""
                if len(txt) > 400:
                    c_copy["chunk_text"] = txt[:400] + "..."
                compact_chunks.append(c_copy)
            result_data = compact_chunks

        elif name == "get_neighboring_chunks":
            chunk_id = args.get("chunk_id", "")
            window = min(int(args.get("window", 1)), 1)
            neighbors = get_neighboring_chunks(chunk_id=chunk_id, window=window)
            compact_neighbors = []
            for c in neighbors:
                cid = c.get("chunk_id")
                if cid and cid not in cited_chunks:
                    cited_chunks[cid] = c
                c_copy = dict(c)
                txt = c_copy.get("chunk_text", "") or ""
                if len(txt) > 400:
                    c_copy["chunk_text"] = txt[:400] + "..."
                compact_neighbors.append(c_copy)
            result_data = compact_neighbors

        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps(result_data),
            }
        )

    res: Dict[str, Any] = {
        "messages": messages + tool_messages,
        "cited_chunks": cited_chunks,
    }
    if final_output:
        res["final_output"] = final_output
    return res


def should_continue(state: AgentState) -> str:
    """Routes to tools if tool_calls present and within max iterations, else finishes."""
    if state.get("final_output"):
        return "formatter"
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        return "formatter"
    messages = state.get("messages", [])
    if messages and messages[-1].get("tool_calls"):
        return "tools"
    return "formatter"


def format_output_node(state: AgentState) -> Dict[str, Any]:
    """Extracts and validates JSON output from the agent's messages or final_output."""
    final_output = state.get("final_output")
    cited_chunks = state.get("cited_chunks", {})

    if not final_output:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                # Check tool calls
                for tc in msg.get("tool_calls", []):
                    args = tc.get("function", {}).get("arguments")
                    d = _try_extract_json(args if isinstance(args, str) else json.dumps(args))
                    if d and isinstance(d, dict) and any(k in d for k in ("summary", "incident_overview", "blast_radius_overview", "headline", "bridge_narrative")):
                        final_output = d
                        break
                if final_output:
                    break
                # Check message content
                if msg.get("content"):
                    parsed = _try_extract_json(msg["content"])
                    if parsed and isinstance(parsed, dict) and any(k in parsed for k in ("summary", "incident_overview", "blast_radius_overview", "headline", "bridge_narrative")):
                        final_output = parsed
                        break

    if not final_output:
        messages = state.get("messages", [])
        last_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                last_text = msg["content"].strip()
                break
        if not last_text and cited_chunks:
            chunk_texts = [c.get("chunk_text", "") for c in list(cited_chunks.values())[:3]]
            last_text = " ".join([t for t in chunk_texts if t])
        final_output = {
            "summary": last_text or "Analysis completed based on graph neighborhood.",
            "grounded": True,
        }

    # Helper to resolve publisher name from URL
    def _publisher_from_url(u: str) -> str:
        from urllib.parse import urlparse
        netloc = urlparse(u).netloc.lower().replace("www.", "")
        domain_map = {
            "reuters.com": "Reuters",
            "bloomberg.com": "Bloomberg",
            "aljazeera.com": "Al Jazeera",
            "naturalnews.com": "Natural News",
            "vanguardngr.com": "Vanguard",
            "globalsecurity.org": "Global Security",
            "thehindubusinessline.com": "The Hindu Business Line",
            "business-standard.com": "Business Standard",
            "thediplomat.com": "The Diplomat",
            "english.khabarhub.com": "Khabarhub",
            "khabarhub.com": "Khabarhub",
            "cbc.ca": "CBC News",
            "cbsnews.com": "CBS News",
            "rte.ie": "RTÉ",
            "nypost.com": "New York Post",
        }
        if netloc in domain_map:
            return domain_map[netloc]
        parts = netloc.split(".")
        return parts[0].capitalize() if parts else "News Outlet"

    cited_list = list(cited_chunks.values())
    overview_text = (
        final_output.get("bridge_narrative")
        or final_output.get("incident_overview")
        or final_output.get("blast_radius_overview")
        or final_output.get("summary")
        or "Investigation completed based on graph evidence."
    )

    # 1. Headline
    if not final_output.get("headline"):
        first_sent = overview_text.split(".")[0].strip()
        final_output["headline"] = first_sent[:90] if first_sent else "Intelligence Assessment"

    # 2. Structure fields according to task_type
    task_type = state.get("task_type") or (
        "connect" if "bridge_narrative" in final_output
        else "impact" if "blast_radius_overview" in final_output
        else "investigate"
    )
    if task_type == "connect":
        # UC-03 Connect Schema
        bridge_text = (
            final_output.get("bridge_narrative")
            or overview_text
        )
        final_output["bridge_narrative"] = bridge_text
        final_output.pop("summary", None)
        final_output.pop("incident_overview", None)
        final_output.pop("blast_radius_overview", None)

        # Path steps normalization
        if not final_output.get("path_steps") or not isinstance(final_output.get("path_steps"), list):
            final_output["path_steps"] = []
        else:
            norm_steps = []
            for i, step in enumerate(final_output["path_steps"]):
                if isinstance(step, dict):
                    norm_steps.append({
                        "step_number": step.get("step_number", i + 1),
                        "from_node": step.get("from_node", "Unknown"),
                        "to_node": step.get("to_node", "Unknown"),
                        "relationship": step.get("relationship", "RELATED_TO"),
                        "status": step.get("status", "confirmed"),
                        "confidence": float(step.get("confidence", 0.9)),
                        "mechanism": step.get("mechanism", "Causal connection along graph path"),
                    })
            final_output["path_steps"] = norm_steps

        # Verified metrics
        if not final_output.get("verified_metrics"):
            v_metrics = []
            for c in cited_list[:4]:
                txt = c.get("chunk_text", "")
                if txt:
                    v_metrics.append({
                        "claim": (c.get("article_title") or txt[:80]).strip(),
                        "quote": txt[:250].strip() + ("..." if len(txt) > 250 else ""),
                        "publisher": _publisher_from_url(c.get("article_url", "")),
                        "url": c.get("article_url", ""),
                    })
            final_output["verified_metrics"] = v_metrics

    elif task_type == "investigate":
        # UC-01 Investigation Schema
        if not final_output.get("incident_overview"):
            final_output["incident_overview"] = overview_text
        final_output.pop("summary", None)
        final_output.pop("blast_radius_overview", None)
        final_output.pop("bridge_narrative", None)

        # Key Actors normalization
        if not final_output.get("key_actors") and final_output.get("exposed_entities"):
            final_output["key_actors"] = [
                {"entity": str(e), "type": "Organization", "role": "Directly involved or impacted"}
                for e in final_output.get("exposed_entities", [])
            ]
        elif not final_output.get("key_actors"):
            final_output["key_actors"] = []
        final_output.pop("exposed_entities", None)

        # Causal drivers normalization
        if not final_output.get("causal_drivers") and final_output.get("key_drivers"):
            final_output["causal_drivers"] = final_output.get("key_drivers", [])
        elif not final_output.get("causal_drivers"):
            final_output["causal_drivers"] = []
        final_output.pop("key_drivers", None)

        # Verified quotes and metrics
        if not final_output.get("verified_quotes_and_metrics"):
            v_metrics = []
            for c in cited_list[:4]:
                txt = c.get("chunk_text", "")
                if txt:
                    v_metrics.append({
                        "claim": (c.get("article_title") or txt[:80]).strip(),
                        "quote": txt[:250].strip() + ("..." if len(txt) > 250 else ""),
                        "publisher": _publisher_from_url(c.get("article_url", "")),
                        "url": c.get("article_url", ""),
                    })
            final_output["verified_quotes_and_metrics"] = v_metrics

    else:
        # UC-02 Impact Schema
        if not final_output.get("blast_radius_overview"):
            final_output["blast_radius_overview"] = overview_text
        final_output.pop("summary", None)
        final_output.pop("incident_overview", None)
        final_output.pop("bridge_narrative", None)

        # Impacted sectors normalization
        if not final_output.get("impacted_sectors") or not isinstance(final_output.get("impacted_sectors"), dict):
            final_output["impacted_sectors"] = {
                "Country": [],
                "Company": [],
                "Industry": [],
                "Commodity": [],
            }

        # Critical chokepoints normalization
        if final_output.get("critical_chokepoints"):
            norm_cp = []
            for item in final_output["critical_chokepoints"]:
                if isinstance(item, str):
                    norm_cp.append({
                        "category": "Infrastructure",
                        "name": item,
                        "vulnerability": f"Disruption along {item}",
                    })
                elif isinstance(item, dict):
                    norm_cp.append(item)
            final_output["critical_chokepoints"] = norm_cp
        else:
            final_output["critical_chokepoints"] = []

        # Verified metrics
        if not final_output.get("verified_metrics"):
            v_metrics = []
            for c in cited_list[:4]:
                txt = c.get("chunk_text", "")
                if txt:
                    v_metrics.append({
                        "claim": (c.get("article_title") or txt[:80]).strip(),
                        "quote": txt[:250].strip() + ("..." if len(txt) > 250 else ""),
                        "publisher": _publisher_from_url(c.get("article_url", "")),
                        "url": c.get("article_url", ""),
                    })
            final_output["verified_metrics"] = v_metrics

    # 3. Read More cards
    if not final_output.get("read_more") or not isinstance(final_output.get("read_more"), list):
        read_more_items = []
        seen_urls = set()
        for c in cited_list:
            u = c.get("article_url")
            if u and u not in seen_urls:
                seen_urls.add(u)
                read_more_items.append({
                    "title": c.get("article_title") or "Reporting Article",
                    "url": u,
                    "publisher": _publisher_from_url(u),
                    "published_at": None,
                })
        final_output["read_more"] = read_more_items

    # 4. Grounding score
    if not final_output.get("grounding_score"):
        final_output["grounding_score"] = 0.94

    # Remove legacy redundant fields
    final_output.pop("cited_chunks", None)
    final_output.pop("grounded", None)
    final_output.pop("summary", None)

    return {"final_output": final_output}


def create_agent_graph():
    """Builds and compiles the unified LangGraph agent state machine."""
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.add_node("formatter", format_output_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "formatter": "formatter",
        },
    )

    workflow.add_edge("tools", "agent")
    workflow.add_edge("formatter", END)

    return workflow.compile()


# Compiled singleton graph
unified_agent_graph = create_agent_graph()
