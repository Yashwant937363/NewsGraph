from typing import List, Literal, Optional
from pydantic import BaseModel, Field

VALID_ENTITY_TYPES = {
    "Country",
    "Company",
    "Person",
    "Organization",
    "Industry",
    "Commodity",
    "Location",
}

VALID_ROLES = {"actor", "location", "object"}


class ExtractedEntity(BaseModel):
    name: str
    type: Literal[
        "Country",
        "Company",
        "Person",
        "Organization",
        "Industry",
        "Commodity",
        "Location",
    ]
    role: Literal["actor", "location", "object"] = "actor"
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    canonical_name: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)


class EntityMention(BaseModel):
    article_url: str
    canonical_name: str
    entity_type: str
    count: int = 1
    salience: float = 0.5


class EventEnrichmentResult(BaseModel):
    event_id: str
    entities: List[ExtractedEntity] = Field(default_factory=list)
    mentions_count: int = 0
    statements_count: int = 0
