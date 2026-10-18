from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ArticleSource(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

class Article(BaseModel):
    title: str = ""
    description: Optional[str] = None
    url: str
    url_to_image: Optional[str] = Field(default=None, alias="urlToImage")
    published_at: Optional[str] = Field(default=None, alias="publishedAt")
    content: Optional[str] = None
    author: Optional[str] = None
    source: Optional[ArticleSource] = None

    model_config = ConfigDict(populate_by_name=True)

class ArticleDetail(BaseModel):
    id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    url: str
    url_to_image: Optional[str] = None
    published_at: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    matched_queries: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None

class ArticleListResponse(BaseModel):
    items: List[ArticleDetail]
    total: int
    skip: int
    limit: int
    has_more: bool
    sources: List[str] = Field(default_factory=list)

