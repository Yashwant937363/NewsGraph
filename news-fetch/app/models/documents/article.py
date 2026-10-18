from datetime import datetime
from typing import List, Optional
from beanie import Document, Indexed
from pydantic import Field


class ArticleDocument(Document):
    title: str = ""
    description: Optional[str] = None
    url: Indexed(str, unique=True)
    url_to_image: Optional[str] = None
    published_at: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    matched_queries: List[str] = Field(default_factory=list)
    full_text: Optional[str] = None
    content_extracted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "articles"
        indexes = [
            "url",
            "published_at",
            "matched_queries",
            "content_extracted",
        ]
