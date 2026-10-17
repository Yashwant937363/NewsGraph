from fastapi import APIRouter, HTTPException

from app.config.falkordb_client import get_falkordb_graph
from app.agent import run_agent
from app.agent.tools import get_initial_chunks
from app.router.track1.common import _clean_props, _get_color

router = APIRouter()


@router.get("/impact/{event_id}")
async def finding_impact(event_id: str, explain: bool = False):
    graph = get_falkordb_graph()
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB graph is not initialized.",
        )

    # 1. Verify center event exists
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
    grouped_impacts = {
        "Country": [],
        "Company": [],
        "Industry": [],
        "Commodity": [],
        "Organization": [],
        "Location": [],
        "Person": [],
    }

    # 2. Impact traversal query for blast radius graph
    impact_query = """
    MATCH (center:Event {event_id: $event_id})
    MATCH p = (center)-[:AFFECTS|CONTRIBUTED_TO|IMPACTED|INVOLVES|CAUSED*1..2]-(target)
    WHERE target:Entity OR target:Event
    UNWIND relationships(p) AS rel
    WITH DISTINCT center, startNode(rel) AS sn, endNode(rel) AS en, rel
    RETURN
        coalesce(sn.event_id, sn.canonical_name, sn.url) AS src_id,
        labels(sn) AS src_labels,
        coalesce(sn.title, sn.canonical_name, sn.name, sn.url) AS src_title,
        properties(sn) AS src_props,
        coalesce(en.event_id, en.canonical_name, en.url) AS tgt_id,
        labels(en) AS tgt_labels,
        coalesce(en.title, en.canonical_name, en.name, en.url) AS tgt_title,
        properties(en) AS tgt_props,
        type(rel) AS rel_type,
        properties(rel) AS rel_props,
        id(rel) AS rel_id
    LIMIT 100
    """
    res = graph.query(impact_query, {"event_id": event_id})

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

        src_id_str = str(src_id)
        tgt_id_str = str(tgt_id)

        # Register source node
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

        # Register target node
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

        # Group entities into impact categories
        for n_id, n_labels, n_title in [
            (src_id_str, src_labels, src_title),
            (tgt_id_str, tgt_labels, tgt_title),
        ]:
            if "Entity" in n_labels:
                name = n_title or n_id
                for cat in grouped_impacts.keys():
                    if cat in n_labels and name not in grouped_impacts[cat]:
                        grouped_impacts[cat].append(name)

        # Build link data
        link_data = _clean_props(rel_props)
        if "status" not in link_data:
            link_data["status"] = "inferred"
        if "confidence" not in link_data:
            link_data["confidence"] = 1.0

        edge_color = (
            "#F59E0B"
            if rel_type in ("AFFECTS", "IMPACTED")
            else _get_color(tgt_labels or [])
        )
        links.append({
            "id": f"rel_impact_{rel_id}",
            "relationship": rel_type,
            "source": src_id_str,
            "target": tgt_id_str,
            "color": edge_color,
            "visible": True,
            "data": link_data,
        })

    # 3. Query downstream impacted events
    downstream_query = """
    MATCH (center:Event {event_id: $event_id})
    MATCH (center)-[:CAUSED|CONTRIBUTED_TO|FOLLOWED*1..2]->(downstream:Event)
    WHERE downstream.event_id <> $event_id
    RETURN DISTINCT
        downstream.event_id AS event_id,
        coalesce(downstream.title, downstream.name) AS title,
        downstream.occurred_at AS occurred_at
    LIMIT 30
    """
    downstream_res = graph.query(downstream_query, {"event_id": event_id})
    events_impacted = [
        {
            "event_id": row[0],
            "title": row[1],
            "occurred_at": row[2],
        }
        for row in downstream_res.result_set
    ]

    explanation = {}
    if explain:
        scoped_article_urls = [
            n["id"] for n in nodes_map.values() if "Article" in n.get("labels", [])
        ]
        for link in links:
            ev_ids = link.get("data", {}).get("evidence_ids", [])
            for u in ev_ids:
                if isinstance(u, str) and u.startswith("http") and u not in scoped_article_urls:
                    scoped_article_urls.append(u)

        # Collect reporting articles for center event + any downstream events
        event_ids_in_scope = [event_id] + [e["event_id"] for e in events_impacted if e.get("event_id")]
        art_res = graph.query(
            "MATCH (e:Event)<-[:REPORTS_ON]-(a:Article) WHERE e.event_id IN $event_ids RETURN DISTINCT a.url",
            {"event_ids": event_ids_in_scope},
        )
        for r in art_res.result_set:
            if r[0] and r[0] not in scoped_article_urls:
                scoped_article_urls.append(r[0])

        initial_chunks = get_initial_chunks(scoped_article_urls, limit=3)
        explanation = await run_agent(
            task_type="impact",
            event_id=event_id,
            event_props=center_props,
            scoped_article_urls=scoped_article_urls,
            initial_chunks=initial_chunks,
        )

    return {
        "event_id": event_id,
        "grouped_impacts": {k: v for k, v in grouped_impacts.items() if v},
        "events_impacted": events_impacted,
        "graph": {
            "nodes": list(nodes_map.values()),
            "links": links,
        },
        "explanation": explanation,
    }
