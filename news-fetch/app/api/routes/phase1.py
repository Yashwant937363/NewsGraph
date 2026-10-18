import os
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse

from app.services.phase1_service import Phase1Service

router = APIRouter(prefix="/phase1", tags=["phase1"])
phase1_ui_router = APIRouter(tags=["ui"])

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "templates",
    "phase1_explorer.html",
)


@phase1_ui_router.get("/phase1", response_class=HTMLResponse, summary="Phase 1 Graph Visualization UI")
@phase1_ui_router.get("/phase2", response_class=HTMLResponse, summary="Phase 2 Knowledge Graph & Entity Explorer UI")
@phase1_ui_router.get("/graph", response_class=HTMLResponse, include_in_schema=False)
async def phase1_explorer_page():
    """Serves the interactive graph and story timeline visualization page."""
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    return HTMLResponse(
        content="<h1>Phase 1/2 Explorer template not found</h1>",
        status_code=500,
    )


@router.get("/stats", summary="Get Phase 1 & Phase 2 graph counts and statistics")
async def get_phase1_stats():
    service = Phase1Service()
    return service.get_overview_stats()


@router.get("/dates", summary="Get list of dates with event and article counts")
async def get_phase1_dates():
    service = Phase1Service()
    return service.get_dates_summary()


@router.get("/stories", summary="Get stories with event counts and date ranges")
async def get_phase1_stories(
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search term in story title"),
    min_events: int = Query(1, ge=1, description="Minimum events in story"),
    date: Optional[str] = Query(None, description="Filter by event date YYYY-MM-DD"),
):
    service = Phase1Service()
    return service.get_stories(
        skip=skip,
        limit=limit,
        search=search,
        min_events=min_events,
        date=date,
    )


@router.get("/story/{story_id}/graph", summary="Get force-directed graph for a story")
async def get_story_graph(
    story_id: str,
    include_articles: bool = Query(True, description="Include articles and sources in graph"),
    include_entities: bool = Query(True, description="Include Phase 2 entities (Country, Company, Person, etc.)"),
    include_related: bool = Query(True, description="Include Phase 2 RELATED_TO edges"),
    max_articles_per_event: int = Query(4, ge=1, le=10),
    max_entities_per_event: int = Query(6, ge=1, le=15),
):
    service = Phase1Service()
    graph_data = service.get_story_graph(
        story_id=story_id,
        include_articles=include_articles,
        include_entities=include_entities,
        include_related=include_related,
        max_articles_per_event=max_articles_per_event,
        max_entities_per_event=max_entities_per_event,
    )
    if not graph_data.get("story"):
        raise HTTPException(status_code=404, detail="Story not found in FalkorDB")
    return graph_data


@router.get("/event/{event_id}", summary="Get detailed event view with reporting articles and Phase 2 entities")
async def get_event_detail(event_id: str):
    service = Phase1Service()
    detail = service.get_event_detail(event_id)
    if "error" in detail:
        raise HTTPException(status_code=404, detail=detail["error"])
    return detail


@router.get("/entities", summary="Get paginated list of Phase 2 entities")
async def get_phase2_entities(
    entity_type: Optional[str] = Query(None, description="Filter by type (Country, Company, Person, Organization, Industry, Commodity, Location)"),
    search: Optional[str] = Query(None, description="Search term in entity canonical name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = Phase1Service()
    return service.get_entities(
        entity_type=entity_type,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get("/entity/{canonical_name}/graph", summary="Get ego-network graph for a Phase 2 entity")
async def get_entity_graph(
    canonical_name: str,
    max_events: int = Query(12, ge=1, le=30),
):
    service = Phase1Service()
    graph_data = service.get_entity_graph(canonical_name, max_events=max_events)
    if "error" in graph_data:
        raise HTTPException(status_code=404, detail=graph_data["error"])
    return graph_data

