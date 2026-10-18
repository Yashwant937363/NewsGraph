from datetime import datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field


class Phase3LedgerDocument(Document):
    """
    Tracks reasoning & causal linking progress per Event for Phase 3.
    Event-by-event granularity ensures crash-resilient and resumable runs.
    """
    event_id: Indexed(str, unique=True)
    status: str = "PENDING"  # PENDING, PROCESSING, COMPLETED, FAILED, SKIPPED
    tool_calls_count: int = 0
    edges_written: int = 0
    caused_edges: int = 0
    contributed_edges: int = 0
    affects_edges: int = 0
    impacted_edges: int = 0
    related_edges: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "phase3_ledger"
        indexes = [
            "event_id",
            "status",
        ]
