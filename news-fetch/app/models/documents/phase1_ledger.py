from datetime import datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field


class Phase1LedgerDocument(Document):
    """
    Tracks daily batch progress for Phase 1 (articles -> events -> stories -> FalkorDB).
    Each date is an atomic unit. Completed dates are skipped on re-runs.
    """
    date: Indexed(str, unique=True)
    status: str = "PENDING"  # PENDING, PROCESSING, COMPLETED, FAILED
    raw_articles_count: int = 0
    deduped_articles_count: int = 0
    clusters_count: int = 0
    noise_count: int = 0
    stories_linked: int = 0
    stories_created: int = 0
    nodes_written: int = 0
    edges_written: int = 0
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "phase1_ledger"
        indexes = [
            "date",
            "status",
        ]
