import logging
from typing import List, Dict, Any, Optional
from app.agent.graph import unified_agent_graph
from app.agent.prompts import (
    INVESTIGATE_SYSTEM_PROMPT,
    IMPACT_SYSTEM_PROMPT,
    CONNECT_SYSTEM_PROMPT,
)

logger = logging.getLogger("newsgraph.agent.runner")


async def run_agent(
    task_type: str,
    event_id: str,
    event_props: Dict[str, Any],
    scoped_article_urls: List[str],
    initial_chunks: List[Dict[str, Any]],
    graph_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes the single unified LangGraph agent for a given task ('investigate' or 'impact').
    Dynamically applies the task prompt, initializes state, runs the graph, and returns the grounded explanation.
    """
    # 1. Select prompt based on task_type
    if task_type == "connect":
        system_prompt = CONNECT_SYSTEM_PROMPT
        target_eid = (graph_context or {}).get("target_event_id", "")
        task_instruction = (
            f"Analyze the causal bridge connecting source event '{event_id}' to target event '{target_eid}'."
        )
    elif task_type == "impact":
        system_prompt = IMPACT_SYSTEM_PROMPT
        task_instruction = (
            f"Analyze the blast radius and downstream impact for event '{event_id}'."
        )
    else:
        system_prompt = INVESTIGATE_SYSTEM_PROMPT
        task_instruction = (
            f"Investigate the incident, causes, and exposed entities for event '{event_id}'."
        )

    # 2. Build initial user message with context
    title = event_props.get("title", "")
    category = event_props.get("category", "")
    occurred_at = event_props.get("occurred_at", "")
    summary = event_props.get("summary", "")

    initial_evidence_text = ""
    cited_map = {}
    if initial_chunks:
        initial_evidence_text = "\n### Initial Reporting Chunks:\n"
        for i, c in enumerate(initial_chunks[:3]):
            cid = c.get("chunk_id", f"chunk_{i}")
            cited_map[cid] = c
            txt = c.get("chunk_text", "") or ""
            if len(txt) > 400:
                txt = txt[:400] + "..."
            initial_evidence_text += (
                f"- [Chunk ID: {cid}]\n"
                f"  Title: {c.get('article_title')}\n"
                f"  Text: {txt}\n\n"
            )

    if task_type == "connect":
        target_props = (graph_context or {}).get("target_event_props", {})
        path_hops_text = ""
        path_hops = (graph_context or {}).get("path_hops", [])
        if path_hops:
            path_hops_text = "\n### Identified Graph Path Hops:\n"
            for hop in path_hops:
                path_hops_text += f"- Step {hop.get('step_number')}: {hop.get('from_node')} --[{hop.get('relationship')}]--> {hop.get('to_node')}\n"

        user_content = f"""{task_instruction}

### Source Event:
- Event ID: {event_id}
- Title: {title}
- Occurred At: {occurred_at}
- Category: {category}
- Overview: {summary}

### Target Event:
- Event ID: {graph_context.get('target_event_id', '') if graph_context else ''}
- Title: {target_props.get('title', '')}
- Occurred At: {target_props.get('occurred_at', '')}
- Category: {target_props.get('category', '')}
- Overview: {target_props.get('summary', '')}
{path_hops_text}
{initial_evidence_text}
Please conduct your analysis using the available tools (`search_graph_chunks`, `get_neighboring_chunks`) to gather specific evidence, numbers, and quotes from the scoped articles along the path, then return your causal bridge assessment in the requested JSON format.
"""
    else:
        user_content = f"""{task_instruction}

### Event Metadata:
- Event ID: {event_id}
- Title: {title}
- Occurred At: {occurred_at}
- Category: {category}
- Initial Overview: {summary}
{initial_evidence_text}
Please conduct your analysis using the available tools (`search_graph_chunks`, `get_neighboring_chunks`) to gather specific evidence, numbers, and quotes from the scoped articles, then return your final assessment in the requested JSON format.
"""

    initial_state = {
        "messages": [{"role": "user", "content": user_content}],
        "system_prompt": system_prompt,
        "scoped_article_urls": scoped_article_urls,
        "cited_chunks": cited_map,
        "final_output": None,
        "iteration": 0,
        "task_type": task_type,
    }

    logger.info(f"Invoking LangGraph agent for event '{event_id}' (task={task_type})...")
    try:
        final_state = await unified_agent_graph.ainvoke(initial_state)
        output = final_state.get("final_output") or {}
        return output
    except Exception as e:
        logger.exception(f"Error in LangGraph agent runner for {event_id}: {e}")
        return {
            "summary": summary or f"Analysis of event {event_id}.",
            "grounded": False,
            "error": str(e),
            "cited_chunks": list(cited_map.values()),
        }
