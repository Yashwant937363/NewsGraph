from fastapi import APIRouter, HTTPException

from app.config.falkordb_client import get_falkordb_graph
from app.agent import run_agent
from app.agent.tools import get_initial_chunks
from app.router.track1.common import _clean_props, _get_color

router = APIRouter()


@router.get("/investigate/{event_id}")
async def investigate(event_id: str, explain: bool = False):
    graph = get_falkordb_graph()
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB graph is not initialized.",
        )

    # 1. Verify center event exists and retrieve its metadata
    center_query = """
    MATCH (center:Event {event_id: $event_id})
    RETURN
        center.event_id AS id,
        labels(center) AS labels,
        coalesce(center.title, center.canonical_name, center.name) AS title,
        properties(center) AS props
    """
    center_res = graph.query(center_query, {"event_id": event_id})
    if not center_res.result_set:
        raise HTTPException(
            status_code=404,
            detail=f"Event '{event_id}' not found.",
        )

    center_row = center_res.result_set[0]
    center_id = str(center_row[0])
    center_labels = list(center_row[1]) if center_row[1] else ["Event"]
    center_title = center_row[2]
    center_props = _clean_props(center_row[3])
    if "title" not in center_props and center_title:
        center_props["title"] = center_title

    nodes_map = {
        center_id: {
            "id": center_id,
            "labels": center_labels,
            "color": _get_color(center_labels),
            "visible": True,
            "data": center_props,
        }
    }
    links = []

    # 2. Multi-hop traversal query using FalkorDB openCypher path binding
    traversal_query = """
    MATCH (center:Event {event_id: $event_id})
    MATCH p = (center)-[*1..2]-(neighbor)
    WHERE NOT neighbor:Chunk
    UNWIND relationships(p) AS rel
    WITH DISTINCT center, startNode(rel) AS sn, endNode(rel) AS en, rel
    WHERE NOT sn:Chunk AND NOT en:Chunk
    RETURN
        coalesce(sn.event_id, sn.story_id, sn.canonical_name, sn.url, sn.name, toString(id(sn))) AS src_id,
        labels(sn) AS src_labels,
        coalesce(sn.title, sn.canonical_name, sn.name, sn.url, sn.story_id, sn.event_id) AS src_title,
        properties(sn) AS src_props,
        coalesce(en.event_id, en.story_id, en.canonical_name, en.url, en.name, toString(id(en))) AS tgt_id,
        labels(en) AS tgt_labels,
        coalesce(en.title, en.canonical_name, en.name, en.url, en.story_id, en.event_id) AS tgt_title,
        properties(en) AS tgt_props,
        type(rel) AS rel_type,
        properties(rel) AS rel_props,
        id(rel) AS rel_id
    LIMIT 120
    """

    res = graph.query(traversal_query, {"event_id": event_id})

    for row in res.result_set:
        (
            src_id,
            src_labels,
            src_title,
            src_props,
            tgt_id,
            tgt_labels,
            tgt_title,
            tgt_props,
            rel_type,
            rel_props,
            rel_id,
        ) = row

        if not src_id or str(src_id) == "None" or not tgt_id or str(tgt_id) == "None":
            continue

        src_id_str = str(src_id)
        tgt_id_str = str(tgt_id)

        # Source node
        if src_id_str not in nodes_map:
            s_props = _clean_props(src_props)
            if "title" not in s_props and src_title:
                s_props["title"] = src_title
            nodes_map[src_id_str] = {
                "id": src_id_str,
                "labels": list(src_labels or []),
                "color": _get_color(src_labels or []),
                "visible": True,
                "data": s_props,
            }

        # Target node
        if tgt_id_str not in nodes_map:
            t_props = _clean_props(tgt_props)
            if "title" not in t_props and tgt_title:
                t_props["title"] = tgt_title
            nodes_map[tgt_id_str] = {
                "id": tgt_id_str,
                "labels": list(tgt_labels or []),
                "color": _get_color(tgt_labels or []),
                "visible": True,
                "data": t_props,
            }

        # Link data
        link_data = _clean_props(rel_props)
        if "status" not in link_data:
            link_data["status"] = "confirmed"
        if "confidence" not in link_data:
            link_data["confidence"] = 1.0
        if "evidence_ids" not in link_data:
            link_data["evidence_ids"] = []

        edge_color = _get_color(tgt_labels or [])
        links.append({
            "id": f"rel_{rel_id}",
            "relationship": rel_type,
            "source": src_id_str,
            "target": tgt_id_str,
            "color": edge_color,
            "visible": True,
            "data": link_data,
        })

    nodes = list(nodes_map.values())

    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(links),
        "countries_count": sum(1 for n in nodes if "Country" in n["labels"]),
        "companies_count": sum(1 for n in nodes if "Company" in n["labels"]),
        "industries_count": sum(1 for n in nodes if "Industry" in n["labels"]),
    }

    explanation = {}
    if explain:
        scoped_article_urls = [
            n["id"] for n in nodes if "Article" in n.get("labels", [])
        ]
        direct_arts = graph.query(
            "MATCH (e:Event)<-[:REPORTS_ON]-(a:Article) WHERE e.event_id = $event_id RETURN a.url",
            {"event_id": event_id},
        )
        for r in direct_arts.result_set:
            if r[0] not in scoped_article_urls:
                scoped_article_urls.append(r[0])

        initial_chunks = get_initial_chunks(scoped_article_urls, limit=3)
        explanation = await run_agent(
            task_type="investigate",
            event_id=event_id,
            event_props=center_props,
            scoped_article_urls=scoped_article_urls,
            initial_chunks=initial_chunks,
        )

    return {
        "event_id": event_id,
        "stats": stats,
        "graph": {
            "nodes": nodes,
            "links": links,
        },
        "explanation": explanation,
    }
