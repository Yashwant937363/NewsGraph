from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies import get_pipeline_service
from app.models.schemas.cluster import PipelineResponse
from app.services.pipeline import NewsPipelineService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

class PipelineRunRequest(BaseModel):
    date: Optional[str] = Field(default=None, description="ISO Date YYYY-MM-DD")
    query: Optional[str] = Field(default="*", description="Search query")
    max_articles: int = Field(default=100, ge=1, le=500, description="Max articles to fetch")
    eps: Optional[float] = Field(default=None, ge=0.05, le=1.0, description="DBSCAN eps threshold")
    min_samples: Optional[int] = Field(default=None, ge=2, le=20, description="DBSCAN min_samples")

@router.post("/run", response_model=PipelineResponse)
async def run_pipeline_endpoint(
    req: PipelineRunRequest,
    pipeline_service: NewsPipelineService = Depends(get_pipeline_service),
):
    """
    Triggers the news processing pipeline up to Event Clustering (Stage 1 to 4).
    """
    try:
        response = pipeline_service.run_pipeline(
            date_str=req.date,
            query=req.query,
            max_articles=req.max_articles,
            eps=req.eps,
            min_samples=req.min_samples,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "news_pipeline"}
