import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.falkordb_client import FalkorDBClient
from app.services.phase3_pipeline import Phase3Pipeline

logger = logging.getLogger("news_pipeline.api.phase3")

router = APIRouter(
    prefix="/phase3",
    tags=["Phase 3 Reasoning & Causal Intelligence"],
)

falkordb = FalkorDBClient()
pipeline = Phase3Pipeline()


class CurateEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    status: str = Field(..., description="'confirmed', 'inferred', or 'related'")
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: Optional[str] = None
    notes: Optional[str] = None


@router.get("/stats")
async def get_phase3_stats() -> Dict[str, Any]:
    """Returns Phase 3 ledger summary and FalkorDB reasoning edge counts."""
    return await pipeline.get_summary()


@router.get("/edges")
async def list_reasoning_edges(
    edge_type: Optional[str] = Query(None, description="Filter by edge type (CAUSED, CONTRIBUTED_TO, AFFECTS, IMPACTED)"),
    status: Optional[str] = Query(None, description="Filter by status (confirmed, inferred, related)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Returns list of Phase 3 reasoning edges for UI display and drill-down."""
    edges = falkordb.get_reasoning_edges(edge_type=edge_type, status=status, skip=skip, limit=limit)
    return {
        "edges": edges,
        "count": len(edges),
        "skip": skip,
        "limit": limit,
    }


@router.post("/reason/{event_id}")
async def reason_about_event_endpoint(
    event_id: str,
    force: bool = Query(default=False, description="Re-run reasoning even if already COMPLETED"),
) -> Dict[str, Any]:
    """Triggers the autonomous reasoning agent loop for a specific event."""
    events = falkordb.get_all_events()
    target = next((e for e in events if e["event_id"] == event_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found in FalkorDB")

    res = await pipeline.reason_about_event(target, force=force)
    return res


@router.get("/investigate/{event_id}")
async def investigate_event(
    event_id: str,
    hops: int = Query(default=2, ge=1, le=3, description="Number of hops to traverse (1-3)"),
) -> Dict[str, Any]:
    """
    UC-01: Investigate Event (Multi-Hop Link Analysis)
    Executes a multi-hop traversal in FalkorDB returning all connected actors,
    downstream impacts, and causal links with full trust properties.
    """
    exists, _ = falkordb.node_exists(event_id)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")

    return falkordb.investigate_event_multihop(event_id, hops=hops)


@router.get("/impact/{event_id}")
async def impact_radius(
    event_id: str,
    hops: int = Query(default=2, ge=1, le=3, description="Bounded BFS hops (1-3)"),
) -> Dict[str, Any]:
    """
    UC-02: Impact Radius (Tracing an Impact)
    Bounded BFS from the event over AFFECTS, CONTRIBUTED_TO, and IMPACTED edges.
    Returns impacted entities grouped by Countries, Companies, Industries, Commodities.
    """
    exists, _ = falkordb.node_exists(event_id)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")

    return falkordb.get_impact_radius(event_id, hops=hops)


@router.get("/connect")
async def connect_the_dots(
    source_event_id: str = Query(..., description="First event ID, e.g. evt_2026-09-08_0"),
    target_event_id: str = Query(..., description="Second event ID, e.g. evt_2026-09-15_4"),
) -> Dict[str, Any]:
    """
    UC-03: Connect the Dots (Finding a Path)
    Finds the shortest and strongest path between two events in FalkorDB.
    """
    if source_event_id == target_event_id:
        raise HTTPException(status_code=400, detail="source_event_id and target_event_id cannot be the same")

    res = falkordb.get_shortest_path(source_event_id, target_event_id)
    if not res:
        return {
            "source_event_id": source_event_id,
            "target_event_id": target_event_id,
            "found": False,
            "message": "No evidence-backed connection found between these events.",
        }

    return {
        "found": True,
        **res,
    }


@router.get("/evidence")
async def view_evidence_trail(
    source_id: str = Query(..., description="Source node ID (event_id or canonical_name)"),
    target_id: str = Query(..., description="Target node ID (event_id or canonical_name)"),
    edge_type: str = Query(..., description="Edge relation type (CAUSED, AFFECTS, etc.)"),
) -> Dict[str, Any]:
    """
    UC-04: View Evidence Trail (Evidence & Case Mapping)
    Inspects an edge's trust properties and resolves all supporting article URLs
    together with source reliability scores and publication timestamps.
    """
    evidence = falkordb.get_edge_evidence(source_id, target_id, edge_type)
    if not evidence:
        raise HTTPException(
            status_code=404,
            detail=f"Edge ({source_id})-[:{edge_type}]->({target_id}) not found in graph",
        )
    return evidence


@router.post("/curate")
async def curate_edge(request: CurateEdgeRequest) -> Dict[str, Any]:
    """
    UC-08: Curate AI Connections (Human-in-the-Loop)
    Allows human editors to verify, modify confidence, or annotate reasoning edges.
    Sets agent='editor' which permanently protects the edge from being overwritten by AI agents.
    """
    success = falkordb.write_reasoning_edge(
        source_id=request.source_id,
        target_id=request.target_id,
        edge_type=request.edge_type,
        status=request.status,
        confidence=request.confidence,
        evidence_ids=[],
        rationale=request.rationale or request.notes,
        agent="editor",
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to persist curation update to FalkorDB")

    return {
        "success": True,
        "message": f"Edge successfully curated with agent='editor'.",
        "curated_edge": request.model_dump(),
    }
