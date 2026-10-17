from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException

from app.config.falkordb_client import get_falkordb_graph

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search_graph(q: Optional[str] = None, limit: int = 20):
    """
    Unified search endpoint for FalkorDB.
    - If q is empty/omitted: returns recent events ordered by occurred_at DESC.
    - If q is provided: searches both :Event (title, summary, event_id) and
      :Entity (canonical_name) with event count ranking.
    """
    graph = get_falkordb_graph()
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB graph is not initialized.",
        )

    clean_q = (q or "").strip()

    # 1. Empty query -> Return recent events
    if not clean_q:
        recent_query = """
        MATCH (e:Event)
        RETURN
            e.event_id AS event_id,
            coalesce(e.title, e.summary, e.name) AS title,
            e.occurred_at AS occurred_at,
            coalesce(e.category, '') AS category,
            coalesce(e.summary, '') AS summary
        ORDER BY e.occurred_at DESC
        LIMIT $limit
        """
        res = graph.query(recent_query, {"limit": limit})
        events = [
            {
                "id": row[0],
                "event_id": row[0],
                "title": row[1],
                "occurred_at": row[2],
                "category": row[3],
                "summary": row[4],
                "type": "event",
            }
            for row in res.result_set
        ]
        return {
            "query": "",
            "events": events,
            "entities": [],
        }

    # 2. Query with search term -> Search both Events and Entities
    event_query = """
    MATCH (e:Event)
    WHERE toLower(e.title) CONTAINS toLower($term)
       OR toLower(e.summary) CONTAINS toLower($term)
       OR toLower(e.event_id) CONTAINS toLower($term)
    RETURN
        e.event_id AS event_id,
        coalesce(e.title, e.summary, e.name) AS title,
        e.occurred_at AS occurred_at,
        coalesce(e.category, '') AS category,
        coalesce(e.summary, '') AS summary
    ORDER BY e.occurred_at DESC
    LIMIT $limit
    """
    ev_res = graph.query(event_query, {"term": clean_q, "limit": limit})
    events = [
        {
            "id": row[0],
            "event_id": row[0],
            "title": row[1],
            "occurred_at": row[2],
            "category": row[3],
            "summary": row[4],
            "type": "event",
        }
        for row in ev_res.result_set
    ]

    entity_query = """
    MATCH (ent:Entity)
    WHERE toLower(ent.canonical_name) CONTAINS toLower($term)
    OPTIONAL MATCH (ent)-[r]-(ev:Event)
    WITH ent, labels(ent) AS ent_labels, count(DISTINCT ev) AS event_count
    RETURN
        ent.canonical_name AS canonical_name,
        ent_labels,
        event_count,
        reduce(s = '', x IN ent_labels | CASE WHEN x <> 'Entity' THEN x ELSE s END) AS primary_category
    ORDER BY event_count DESC
    LIMIT $limit
    """
    ent_res = graph.query(entity_query, {"term": clean_q, "limit": limit})
    entities = [
        {
            "id": row[0],
            "canonical_name": row[0],
            "title": row[0],
            "labels": list(row[1]) if row[1] else ["Entity"],
            "event_count": row[2],
            "category": row[3] or "Entity",
            "type": "entity",
        }
        for row in ent_res.result_set
    ]

    return {
        "query": clean_q,
        "events": events,
        "entities": entities,
    }


@router.get("/entity/{entity_name}/events")
async def get_entity_connected_events(entity_name: str, limit: int = 15):
    """
    Returns events connected to a specific entity, ordered by date.
    """
    graph = get_falkordb_graph()
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB graph is not initialized.",
        )

    query = """
    MATCH (ent:Entity)-[r]-(ev:Event)
    WHERE ent.canonical_name = $name
    RETURN DISTINCT
        ev.event_id AS event_id,
        coalesce(ev.title, ev.summary, ev.name) AS title,
        ev.occurred_at AS occurred_at,
        type(r) AS relationship
    ORDER BY ev.occurred_at DESC
    LIMIT $limit
    """
    res = graph.query(query, {"name": entity_name, "limit": limit})
    return [
        {
            "event_id": row[0],
            "title": row[1],
            "occurred_at": row[2],
            "relationship": row[3],
        }
        for row in res.result_set
    ]
