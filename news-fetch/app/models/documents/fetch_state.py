from datetime import datetime
from typing import Any, Dict, List, Optional
from beanie import Document, Indexed
from pydantic import Field


class FetchStateDocument(Document):
    state_id: Indexed(str, unique=True) = "global_fetch_state"
    current_query_index: int = 0
    completed_query_ids: List[int] = Field(default_factory=list)
    failed_queries: List[Dict[str, Any]] = Field(default_factory=list)
    active_key_index: int = 0
    total_queries: int = 150
    total_api_calls: int = 0
    total_articles_fetched: int = 0
    total_articles_inserted: int = 0
    total_duplicates_skipped: int = 0
    is_completed: bool = False
    last_error: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "fetch_state"
