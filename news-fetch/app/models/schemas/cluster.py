from typing import List, Optional
from pydantic import BaseModel
from app.models.schemas.article import Article

class EventCluster(BaseModel):
    cluster_id: int
    article_count: int
    articles: List[Article]

class PipelineMetrics(BaseModel):
    total_fetched: int
    after_url_dedup: int
    url_duplicates_removed: int
    after_content_dedup: int
    content_duplicates_removed: int
    total_clusters: int
    noise_count: int
    noise_ratio: float
    silhouette_score: Optional[float] = None

class PipelineResponse(BaseModel):
    date: str
    metrics: PipelineMetrics
    clusters: List[EventCluster]
    noise_articles: Optional[List[Article]] = None
