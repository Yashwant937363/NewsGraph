from datetime import datetime
from typing import List
from beanie import Document, Indexed
from pydantic import Field


class EntityAliasDocument(Document):
    """
    Stores resolved entity alias mappings in MongoDB.
    Ensures an alias (e.g. 'US' -> 'United States') is cached and never resolved twice.
    """
    raw_name: Indexed(str, unique=True)
    canonical_name: str
    entity_type: str
    aliases: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "entity_alias_cache"
        indexes = [
            "raw_name",
            "canonical_name",
            "entity_type",
        ]
