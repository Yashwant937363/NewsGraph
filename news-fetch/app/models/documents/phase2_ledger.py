from datetime import datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field


class Phase2LedgerDocument(Document):
    """
    Tracks enrichment progress per Event for Phase 2.
    Event-by-event granularity ensures crash-resilient and resumable runs.
    """
    event_id: Indexed(str, unique=True)
    status: str = "PENDING"  # PENDING, PROCESSING, COMPLETED, FAILED
    entities_count: int = 0
    mentions_count: int = 0
    statements_count: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "phase2_ledger"
        indexes = [
            "event_id",
            "status",
        ]
