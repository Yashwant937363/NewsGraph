import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import Settings, get_settings
from app.models.documents.article import ArticleDocument
from app.models.schemas.reasoning import VALID_REASONING_EDGES, VALID_STATUSES
from app.services.falkordb_client import FalkorDBClient

logger = logging.getLogger("news_pipeline.phase3_tools")

PHASE3_TOOLS_SPEC: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_event_context",
            "description": "Get event details, involved entities, and reporting articles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID (e.g. evt_2026-09-08_0)"}
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_candidate_links",
            "description": "Find candidate peer events and entities for causal/narrative links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Source event ID"},
                    "limit": {"type": "integer", "description": "Max candidates (default: 8)", "default": 8},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_entities",
            "description": "List entities connected to event, optionally filtered by type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID"},
                    "entity_type": {"type": "string", "description": "Optional type filter: Country, Company, Person, Organization, Industry, Commodity, Location"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_articles",
            "description": "Search database articles by keyword for evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords"},
                    "limit": {"type": "integer", "description": "Max results (default: 3)", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_text",
            "description": "Get article snippet and metadata by exact URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Article URL"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_edge",
            "description": "Persist validated reasoning edge to graph. Enforces confidence >= 0.55 and evidence URLs for causal edges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "description": "Source event_id or entity name"},
                    "target_id": {"type": "string", "description": "Target event_id or entity name"},
                    "edge_type": {
                        "type": "string",
                        "enum": ["CAUSED", "CONTRIBUTED_TO", "AFFECTS", "IMPACTED", "RELATED_TO"],
                        "description": "Edge type",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["confirmed", "inferred", "related"],
                        "description": "Status (confirmed, inferred, related)",
                        "default": "inferred",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score 0.55 to 1.0",
                    },
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Article URLs citing evidence",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Brief rationale for link",
                    },
                },
                "required": ["source_id", "target_id", "edge_type", "confidence"],
            },
        },
    },
]


class Phase3Tools:
    """
    Executes and validates agent tool calls in Python.
    Strictly prevents arbitrary Cypher injection and enforces the Trust Property Contract.
    """

    def __init__(
        self,
        falkordb_client: Optional[FalkorDBClient] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.falkordb = falkordb_client or FalkorDBClient(self.settings)

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Routes and executes a tool call by name with validated arguments."""
        if tool_name == "get_event_context":
            return await self.get_event_context(arguments.get("event_id", ""))
        elif tool_name == "find_candidate_links":
            return await self.find_candidate_links(
                arguments.get("event_id", ""),
                limit=int(arguments.get("limit", 10)),
            )
        elif tool_name == "list_entities":
            return await self.list_entities(
                arguments.get("event_id", ""),
                entity_type=arguments.get("entity_type"),
            )
        elif tool_name == "search_articles":
            return await self.search_articles(
                arguments.get("query", ""),
                limit=int(arguments.get("limit", 5)),
            )
        elif tool_name == "get_article_text":
            return await self.get_article_text(arguments.get("url", ""))
        elif tool_name == "write_edge":
            return await self.write_edge(
                source_id=arguments.get("source_id", ""),
                target_id=arguments.get("target_id", ""),
                edge_type=arguments.get("edge_type", ""),
                status=arguments.get("status", "inferred"),
                confidence=float(arguments.get("confidence", 0.7)),
                evidence_ids=arguments.get("evidence_ids") or [],
                rationale=arguments.get("rationale"),
            )
        else:
            return {"error": f"Unknown tool name: {tool_name}"}

    async def get_event_context(self, event_id: str) -> Dict[str, Any]:
        """Tool 1: get_event_context"""
        if not event_id:
            return {"error": "Missing event_id"}

        exists, node_type = self.falkordb.node_exists(event_id)
        if not exists or node_type != "Event":
            return {"error": f"Event '{event_id}' not found in FalkorDB"}

        # Get Event node properties
        res = self.falkordb.graph.query(
            "MATCH (e:Event) WHERE e.event_id = $eid RETURN e.event_id, e.title, e.summary, e.category, e.occurred_at",
            {"eid": event_id},
        )
        if not res.result_set:
            return {"error": f"Event '{event_id}' not found"}

        row = res.result_set[0]
        event_dict = {
            "event_id": row[0],
            "title": row[1] or "",
            "summary": row[2] or "",
            "category": row[3] or "General",
            "occurred_at": row[4] or "",
        }

        # Entities
        event_dict["entities"] = self.falkordb.get_event_entities(event_id)

        # Articles
        event_dict["articles"] = self.falkordb.get_event_top_articles(event_id, limit=5)

        return event_dict

    async def find_candidate_links(self, event_id: str, limit: int = 10) -> Dict[str, Any]:
        """Tool 2: find_candidate_links"""
        if not event_id:
            return {"error": "Missing event_id"}

        candidates = self.falkordb.get_candidate_links(event_id, limit=limit)
        return {
            "event_id": event_id,
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

    async def list_entities(self, event_id: str, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Tool 3: list_entities"""
        if not event_id:
            return {"error": "Missing event_id"}

        entities = self.falkordb.get_event_entities(event_id, entity_type=entity_type)
        return {
            "event_id": event_id,
            "filter_type": entity_type or "ALL",
            "count": len(entities),
            "entities": entities,
        }

    async def search_articles(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Tool 4: search_articles in MongoDB"""
        if not query:
            return {"error": "Missing search query"}

        clean_query = query.strip()
        tokens = re.findall(r"\w+", clean_query)
        if not tokens:
            return {"results": []}

        # Regex search in title or description
        pattern = "|".join(tokens[:5])
        rgx = {"$regex": pattern, "$options": "i"}
        docs = await ArticleDocument.find(
            {"$or": [{"title": rgx}, {"description": rgx}]}
        ).limit(limit).to_list()

        results = []
        for d in docs:
            pub = str(d.published_at) if d.published_at else ""
            src_name = getattr(d, "source_name", None) or (d.source.name if hasattr(d, "source") and d.source else "Unknown")
            results.append({
                "url": d.url,
                "title": d.title,
                "description": d.description or "",
                "published_at": pub,
                "source_name": src_name,
            })

        return {"query": query, "count": len(results), "articles": results}

    async def get_article_text(self, url: str) -> Dict[str, Any]:
        """Tool 5: get_article_text from MongoDB"""
        if not url:
            return {"error": "Missing article url"}

        doc = await ArticleDocument.find_one(ArticleDocument.url == url)
        if not doc:
            return {"error": f"Article with URL '{url}' not found in database"}

        pub = str(doc.published_at) if doc.published_at else ""
        src_name = getattr(doc, "source_name", None) or (doc.source.name if hasattr(doc, "source") and doc.source else "Unknown")

        body = (doc.full_text or doc.content or doc.description or "")[:800]

        return {
            "url": doc.url,
            "title": doc.title,
            "description": doc.description or "",
            "content": body,
            "has_full_text": bool(doc.full_text),
            "author": doc.author or "",
            "published_at": pub,
            "source_name": src_name,
        }

    async def write_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        status: str = "inferred",
        confidence: float = 0.7,
        evidence_ids: Optional[List[str]] = None,
        rationale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tool 6: write_edge with strict guardrail validations:
        - Allowed edge type check
        - Self-loop prevention
        - Node existence check in FalkorDB
        - Label compatibility check
        - Confidence floor (>= 0.55)
        - Evidence enforcement (fallback to RELATED_TO if missing)
        - Rationale enforcement for inferred edges
        - Protection of editor curated edges
        """
        evidence_list = evidence_ids or []

        # 1. Edge type validation
        if edge_type not in VALID_REASONING_EDGES:
            return {
                "rejected": True,
                "reason": f"Invalid edge_type '{edge_type}'. Allowed types: {sorted(list(VALID_REASONING_EDGES))}",
            }

        # 2. Self-loop check
        if source_id == target_id:
            return {
                "rejected": True,
                "reason": f"Self-loops are not allowed (source_id == target_id == '{source_id}').",
            }

        # 3. Confidence floor check
        if confidence < 0.55 or confidence > 1.0:
            return {
                "rejected": True,
                "reason": f"Confidence {confidence} is outside valid bounds [0.55, 1.0]. Low confidence edges are rejected to avoid graph pollution.",
            }

        # 4. Status validation
        if status not in VALID_STATUSES:
            status = "inferred"

        # 5. Node existence checks in FalkorDB
        src_exists, src_type = self.falkordb.node_exists(source_id)
        if not src_exists:
            return {
                "rejected": True,
                "reason": f"Source node '{source_id}' does not exist in FalkorDB knowledge graph.",
            }

        tgt_exists, tgt_type = self.falkordb.node_exists(target_id)
        if not tgt_exists:
            return {
                "rejected": True,
                "reason": f"Target node '{target_id}' does not exist in FalkorDB knowledge graph.",
            }

        # 6. Label compatibility check
        # CAUSED, CONTRIBUTED_TO, RELATED_TO must be Event -> Event
        if edge_type in ("CAUSED", "CONTRIBUTED_TO", "RELATED_TO"):
            if src_type != "Event":
                return {
                    "rejected": True,
                    "reason": f"{edge_type} requires source to be an Event node, but got '{src_type}'.",
                }
            if tgt_type != "Event":
                return {
                    "rejected": True,
                    "reason": f"{edge_type} requires target to be an Event node, but got '{tgt_type}'.",
                }

        # AFFECTS must be Event -> Entity
        elif edge_type == "AFFECTS":
            if src_type != "Event":
                return {
                    "rejected": True,
                    "reason": f"AFFECTS requires source to be an Event node, but got '{src_type}'.",
                }
            if tgt_type == "Event":
                return {
                    "rejected": True,
                    "reason": "AFFECTS requires target to be an Entity node (Country, Company, Industry, etc.), not another Event.",
                }

        # IMPACTED must be Entity -> Event
        elif edge_type == "IMPACTED":
            if src_type == "Event":
                return {
                    "rejected": True,
                    "reason": "IMPACTED requires source to be an Entity node (Country, Company, Industry, etc.), not an Event.",
                }
            if tgt_type != "Event":
                return {
                    "rejected": True,
                    "reason": f"IMPACTED requires target to be an Event node, but got '{tgt_type}'.",
                }

        # 7. Evidence enforcement rule
        # Rule: No evidence, no causal claim. If LLM claims CAUSED/CONTRIBUTED_TO without evidence, downgrade to RELATED_TO.
        final_edge_type = edge_type
        final_status = status

        if final_edge_type in ("CAUSED", "CONTRIBUTED_TO") and not evidence_list:
            logger.warning(
                f"Downgrading {final_edge_type} to RELATED_TO between {source_id} and {target_id} due to missing evidence URLs."
            )
            final_edge_type = "RELATED_TO"
            final_status = "related"

        if final_status in ("confirmed", "inferred") and not evidence_list:
            final_status = "related"

        # 8. Rationale fallback
        final_rationale = rationale or f"{final_edge_type} relationship identified by reasoning agent"

        # 9. Write edge to FalkorDB
        success = self.falkordb.write_reasoning_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=final_edge_type,
            status=final_status,
            confidence=confidence,
            evidence_ids=evidence_list,
            rationale=final_rationale,
            agent="graph_agent_v1",
        )

        if not success:
            return {
                "rejected": True,
                "reason": "Failed to persist relationship to FalkorDB due to database execution error.",
            }

        return {
            "success": True,
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": final_edge_type,
            "status": final_status,
            "confidence": confidence,
            "evidence_count": len(evidence_list),
            "downgraded": final_edge_type != edge_type,
            "message": f"Edge ({source_id})-[:{final_edge_type}]->({target_id}) committed successfully to FalkorDB.",
        }
