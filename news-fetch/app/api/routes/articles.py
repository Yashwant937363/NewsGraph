import os
import re
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.models.documents.article import ArticleDocument
from app.models.documents.fetch_state import FetchStateDocument
from app.models.schemas.article import ArticleDetail, ArticleListResponse

router = APIRouter(prefix="/articles", tags=["articles"])
ui_router = APIRouter(tags=["ui"])

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "templates",
    "articles.html",
)


@ui_router.get("/articles", response_class=HTMLResponse, summary="Browse articles UI")
@ui_router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def articles_page():
    """Serves the interactive lazy-loaded HTML page for browsing articles."""
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    return HTMLResponse(
        content="<h1>Articles template not found</h1>",
        status_code=500,
    )


@router.get(
    "",
    response_model=ArticleListResponse,
    summary="Get paginated articles with optional search and filters",
)
async def get_articles(
    skip: int = Query(0, ge=0, description="Offset for lazy loading"),
    limit: int = Query(24, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Keyword search in title/description"),
    source: Optional[str] = Query(None, description="Filter by news source name"),
    query_tag: Optional[str] = Query(None, description="Filter by matched query tag"),
):
    """
    Returns paginated articles from MongoDB for lazy loading,
    supporting search, source filtering, and query tag filtering.
    """
    conditions = []

    if search and search.strip():
        term = re.escape(search.strip())
        conditions.append({
            "$or": [
                {"title": {"$regex": term, "$options": "i"}},
                {"description": {"$regex": term, "$options": "i"}},
            ]
        })

    if source and source.strip():
        conditions.append({"source_name": source.strip()})

    if query_tag and query_tag.strip():
        conditions.append({"matched_queries": query_tag.strip()})

    if conditions:
        if len(conditions) == 1:
            mongo_query = conditions[0]
        else:
            mongo_query = {"$and": conditions}
        query = ArticleDocument.find(mongo_query)
    else:
        query = ArticleDocument.find()

    total = await query.count()
    items_docs = (
        await query.sort("-published_at", "-created_at")
        .skip(skip)
        .limit(limit)
        .to_list()
    )

    items = [
        ArticleDetail(
            id=str(doc.id),
            title=doc.title,
            description=doc.description,
            url=doc.url,
            url_to_image=doc.url_to_image,
            published_at=doc.published_at,
            content=doc.content,
            author=doc.author,
            source_id=doc.source_id,
            source_name=doc.source_name,
            matched_queries=doc.matched_queries,
            created_at=doc.created_at.isoformat() if doc.created_at else None,
        )
        for doc in items_docs
    ]

    has_more = (skip + len(items)) < total

    # Fetch unique source names (only non-empty, sorted)
    distinct_sources = await ArticleDocument.distinct("source_name")
    cleaned_sources = sorted([s for s in distinct_sources if s])

    return ArticleListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
        sources=cleaned_sources,
    )


@router.get("/stats", summary="Get DB and fetch progress summary")
async def get_articles_stats():
    """Returns database article metrics and worker state."""
    total_articles = await ArticleDocument.count()
    distinct_sources = len(await ArticleDocument.distinct("source_name"))
    state = await FetchStateDocument.find_one(FetchStateDocument.state_id == "global_fetch_state")

    return {
        "total_articles": total_articles,
        "distinct_sources": distinct_sources,
        "queries_completed": len(state.completed_query_ids) if state else 0,
        "total_queries": state.total_queries if state else 150,
        "total_api_calls": state.total_api_calls if state else 0,
        "total_fetched": state.total_articles_fetched if state else 0,
        "total_inserted": state.total_articles_inserted if state else 0,
        "total_duplicates_skipped": state.total_duplicates_skipped if state else 0,
        "is_completed": state.is_completed if state else False,
    }
