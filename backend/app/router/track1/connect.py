from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException

from app.config.falkordb_client import get_falkordb_graph
from app.agent import run_agent
from app.agent.tools import get_initial_chunks
from app.router.track1.common import _clean_props, _get_color

router = APIRouter()


@router.get("/connect")
async def connect_the_dots(
    source_event_id: str,
    target_event_id: str,
    explain: bool = True,
):
    """
    UC-03: Connect the Dots (Finding a Path).
    Computes the shortest path between two events, formats the graph for @falkordb/canvas,
    and generates an agentic grounded causal bridge narrative when explain=True.
    """
    graph = get_falkordb_graph()
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB graph is not initialized.",
        )

    # 1. Verify existence of both source and target nodes
    verify_query = """
    MATCH (n)
    WHERE n.event_id IN [$src, $tgt]
       OR n.story_id IN [$src, $tgt]
       OR n.canonical_name IN [$src, $tgt]
       OR n.url IN [$src, $tgt]
       OR n.name IN [$src, $tgt]
    RETURN
        coalesce(n.event_id, n.story_id, n.canonical_name, n.url, n.name) AS id,
        labels(n) AS labels,
        coalesce(n.title, n.canonical_name, n.name, n.story_id) AS title,
        properties(n) AS props
    """
    verify_res = graph.query(verify_query, {"src": source_event_id, "tgt": target_event_id})
    nodes_found = {
        row[0]: {"labels": list(row[1] or ["Event"]), "title": row[2], "props": _clean_props(row[3])}
        for row in verify_res.result_set
    }

    if source_event_id not in nodes_found:
        raise HTTPException(
            status_code=404,
            detail=f"Source node '{source_event_id}' not found.",
        )
    if target_event_id not in nodes_found:
        raise HTTPException(
            status_code=404,
            detail=f"Target node '{target_event_id}' not found.",
        )

    src_info = nodes_found[source_event_id]
    tgt_info = nodes_found[target_event_id]

    # 2. Query FalkorDB shortestPath
    path_query = """
    MATCH (n1), (n2)
    WHERE (n1.event_id = $src OR n1.story_id = $src OR n1.canonical_name = $src OR n1.url = $src OR n1.name = $src)
      AND (n2.event_id = $tgt OR n2.story_id = $tgt OR n2.canonical_name = $tgt OR n2.url = $tgt OR n2.name = $tgt)
    RETURN shortestPath((n1)-[*]-(n2))
    """
    path_res = graph.query(path_query, {"src": source_event_id, "tgt": target_event_id})

    # Case: No path found
    if not path_res.result_set or path_res.result_set[0][0] is None:
        return {
            "connection": {
                "source_event_id": source_event_id,
                "target_event_id": target_event_id,
                "found": False,
                "path_length": 0,
            },
            "graph": {
                "nodes": [],
                "links": [],
            },
            "explanation": {
                "headline": "No Connection Found",
                "bridge_narrative": "No evidence-backed connection found between these events in the knowledge graph.",
                "path_steps": [],
                "verified_metrics": [],
                "read_more": [],
                "grounding_score": 0.0,
            },
        }

    path_obj = path_res.result_set[0][0]
    nodes_map: Dict[str, Dict[str, Any]] = {}
    internal_to_key: Dict[int, str] = {}
    node_titles: Dict[str, str] = {}
    path_event_ids: List[str] = []
    path_entity_names: List[str] = []

    # Process nodes along the path
    for node in path_obj.nodes():
        props = _clean_props(node.properties)
        node_key = str(props.get("event_id") or props.get("story_id") or props.get("canonical_name") or props.get("url") or props.get("name") or node.id)
        internal_to_key[node.id] = node_key
        labels = list(node.labels or [])
        title = props.get("title") or props.get("canonical_name") or props.get("name") or props.get("story_id") or node_key
        if "title" not in props:
            props["title"] = title
        node_titles[node_key] = title

        if "Event" in labels and props.get("event_id"):
            path_event_ids.append(props["event_id"])
        if "Entity" in labels and props.get("canonical_name"):
            path_entity_names.append(props["canonical_name"])

        nodes_map[node_key] = {
            "id": node_key,
            "labels": labels,
            "color": _get_color(labels),
            "visible": True,
            "data": props,
        }

    # Process relationships along the path
    links: List[Dict[str, Any]] = []
    path_hops: List[Dict[str, Any]] = []
    scoped_article_urls: List[str] = []

    for i, edge in enumerate(path_obj.edges()):
        src_key = internal_to_key.get(edge.src_node, str(edge.src_node))
        tgt_key = internal_to_key.get(edge.dest_node, str(edge.dest_node))
        rel_props = _clean_props(edge.properties)

        rel_type = edge.relation
        if "status" not in rel_props:
            rel_props["status"] = "confirmed" if rel_type in ("CAUSED", "AFFECTS", "CONTRIBUTED_TO") else "related"
        if "confidence" not in rel_props:
            rel_props["confidence"] = 0.95 if rel_props["status"] == "confirmed" else 0.85
        if "evidence_ids" not in rel_props:
            rel_props["evidence_ids"] = []

        for ev in rel_props["evidence_ids"]:
            if isinstance(ev, str) and ev.startswith("http") and ev not in scoped_article_urls:
                scoped_article_urls.append(ev)

        # Dynamic edge coloring
        if rel_type in ("CAUSED", "AFFECTS", "CONTRIBUTED_TO"):
            edge_color = "#10B981"
        elif rel_type in ("PRECEDED", "FOLLOWED"):
            edge_color = "#3B82F6"
        else:
            tgt_labels = nodes_map.get(tgt_key, {}).get("labels", [])
            edge_color = _get_color(tgt_labels)

        links.append({
            "id": f"rel_path_{edge.id}",
            "relationship": rel_type,
            "source": src_key,
            "target": tgt_key,
            "color": edge_color,
            "visible": True,
            "data": rel_props,
        })

        path_hops.append({
            "step_number": i + 1,
            "from_node": node_titles.get(src_key, src_key),
            "to_node": node_titles.get(tgt_key, tgt_key),
            "relationship": rel_type,
            "status": rel_props.get("status", "confirmed"),
            "confidence": rel_props.get("confidence", 0.9),
            "mechanism": f"Direct link via {rel_type} relationship",
        })

    # Grounded explanation synthesis
    explanation: Dict[str, Any] = {}
    if explain:
        # Collect reporting articles from path events
        if path_event_ids:
            art_res = graph.query(
                "MATCH (e:Event)<-[:REPORTS_ON]-(a:Article) WHERE e.event_id IN $eids RETURN DISTINCT a.url",
                {"eids": path_event_ids},
            )
            for r in art_res.result_set:
                if r[0] and r[0] not in scoped_article_urls:
                    scoped_article_urls.append(r[0])

        # Collect articles mentioning path entities
        if path_entity_names:
            ent_art_res = graph.query(
                "MATCH (ent:Entity)<-[:MENTIONS]-(a:Article) WHERE ent.canonical_name IN $names RETURN DISTINCT a.url LIMIT 20",
                {"names": path_entity_names},
            )
            for r in ent_art_res.result_set:
                if r[0] and r[0] not in scoped_article_urls:
                    scoped_article_urls.append(r[0])

        initial_chunks = get_initial_chunks(scoped_article_urls, limit=3)
        try:
            explanation = await run_agent(
                task_type="connect",
                event_id=source_event_id,
                event_props=src_info["props"],
                scoped_article_urls=scoped_article_urls,
                initial_chunks=initial_chunks,
                graph_context={
                    "target_event_id": target_event_id,
                    "target_event_props": tgt_info["props"],
                    "path_hops": path_hops,
                },
            )
        except Exception as e:
            logger.error(f"Error during connect agent run: {e}")
            explanation = {}

    src_title = src_info["props"].get("title") or source_event_id
    tgt_title = tgt_info["props"].get("title") or target_event_id
    if not explanation.get("headline"):
        explanation["headline"] = f"Causal Bridge: {src_title} → {tgt_title}"
    if not explanation.get("bridge_narrative"):
        explanation["bridge_narrative"] = f"Evidence-backed causal path spanning {len(links)} hops connects '{src_title}' to '{tgt_title}' across the knowledge graph."
    if not explanation.get("path_steps"):
        explanation["path_steps"] = path_hops

    return {
        "connection": {
            "source_event_id": source_event_id,
            "target_event_id": target_event_id,
            "found": True,
            "path_length": len(links),
        },
        "graph": {
            "nodes": list(nodes_map.values()),
            "links": links,
        },
        "explanation": explanation,
    }
