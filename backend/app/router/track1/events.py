from fastapi import APIRouter, HTTPException
from app.config.falkordb_client import get_falkordb_graph

router = APIRouter()


@router.get("/events")
async def get_events(limit: int = 25):
    """Retrieves recent events from FalkorDB ordered by occurred_at."""
    graph = get_falkordb_graph()
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB graph is not initialized.",
        )
    query = """
    MATCH (e:Event)
    RETURN e.event_id, coalesce(e.title, e.summary, e.name) AS title, e.occurred_at
    ORDER BY e.occurred_at DESC
    LIMIT $limit
    """
    res = graph.query(query, {"limit": limit})
    return [
        {"event_id": row[0], "title": row[1], "occurred_at": row[2]}
        for row in res.result_set
    ]
