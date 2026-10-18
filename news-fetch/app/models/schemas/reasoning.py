from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

# Allowed reasoning edge types in Phase 3
VALID_REASONING_EDGES = {
    "CAUSED",
    "CONTRIBUTED_TO",
    "AFFECTS",
    "IMPACTED",
    "RELATED_TO",
}

VALID_STATUSES = {"confirmed", "inferred", "related"}


class ReasoningEdgeInput(BaseModel):
    source_id: str
    target_id: str
    edge_type: Literal[
        "CAUSED",
        "CONTRIBUTED_TO",
        "AFFECTS",
        "IMPACTED",
        "RELATED_TO",
    ]
    status: Literal["confirmed", "inferred", "related"] = "inferred"
    confidence: float = Field(ge=0.55, le=1.0)
    evidence_ids: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    agent: str = "graph_agent_v1"


class TrustProperties(BaseModel):
    status: str
    confidence: float
    evidence_ids: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    agent: str = "graph_agent_v1"
    created_at: str
    valid_from: str
    valid_to: Optional[str] = None


class CandidateLink(BaseModel):
    id: str
    label: str
    title: str
    summary: Optional[str] = None
    occurred_at: Optional[str] = None
    category: Optional[str] = None
    similarity_score: Optional[float] = None
    reason: str


class EventContext(BaseModel):
    event_id: str
    title: str
    summary: str
    category: str
    occurred_at: str
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    articles: List[Dict[str, Any]] = Field(default_factory=list)


class EdgeEvidenceResponse(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    status: str
    confidence: float
    rationale: Optional[str] = None
    agent: str
    evidence_ids: List[str] = Field(default_factory=list)
    articles: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    valid_from: Optional[str] = None
