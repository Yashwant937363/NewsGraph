from typing import List, Dict, Any
from app.config.falkordb_client import get_falkordb_graph
from app.agent.tools.similarity_search import search_graph_chunks
from app.agent.tools.neighboring_chunks import get_neighboring_chunks
from app.agent.tools.embedding import get_embedding_service


def get_initial_chunks(scoped_article_urls: List[str], limit: int = 6) -> List[Dict[str, Any]]:
    """
    Fetches initial representative semantic chunks (e.g. chunk 0) for the articles
    in the investigated subgraph to give the agent immediate opening context.
    """
    graph = get_falkordb_graph()
    if graph is None or not scoped_article_urls:
        return []

    cypher = """
    MATCH (a:Article)-[:HAS_CHUNK]->(c:Chunk)
    WHERE a.url IN $scoped_article_urls AND c.chunk_index = 0
    RETURN a.title AS article_title,
           a.url AS article_url,
           c.chunk_id AS chunk_id,
           c.chunk_index AS chunk_index,
           c.text AS chunk_text
    LIMIT $limit
    """
    try:
        res = graph.query(cypher, {"scoped_article_urls": scoped_article_urls, "limit": limit})
        return [
            {
                "article_title": row[0],
                "article_url": row[1],
                "chunk_id": row[2],
                "chunk_index": row[3],
                "chunk_text": row[4],
            }
            for row in res.result_set
        ]
    except Exception:
        return []


# OpenAI/Groq function tool definitions for openai/gpt-oss-120b
AGENT_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_graph_chunks",
            "description": "Performs vector similarity search for specific claims, numbers, casualties, dates, or quotes, STRICTLY scoped to the articles and events within the investigated graph neighborhood.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query focusing on specific entities, numbers, quotes, or causal mechanisms.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of chunks to return (1-10, default: 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_neighboring_chunks",
            "description": "Retrieves the preceding (previous) and following (next) chunks of an article to get complete context around a specific chunk_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_id": {
                        "type": "string",
                        "description": "The exact chunk_id (e.g. 'https://example.com/article#c1') to expand context around.",
                    },
                    "window": {
                        "type": "integer",
                        "description": "Number of neighboring chunks before and after to retrieve (default: 1).",
                        "default": 1,
                    },
                },
                "required": ["chunk_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_final_explanation",
            "description": "Submit your final synthesized assessment and explanation when research is complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "headline": {
                        "type": "string",
                        "description": "Factual headline summarizing the incident or shockwave.",
                    },
                    "incident_overview": {
                        "type": "string",
                        "description": "For UC-01: 1-2 paragraph overview of what happened, location, and date.",
                    },
                    "blast_radius_overview": {
                        "type": "string",
                        "description": "For UC-02: Summary of systemic shockwave and affected regions.",
                    },
                    "key_actors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity": {"type": "string"},
                                "type": {"type": "string"},
                                "role": {"type": "string"},
                            },
                            "required": ["entity", "type", "role"],
                        },
                        "description": "For UC-01: Participating governments, corporations, and figures.",
                    },
                    "causal_drivers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "For UC-01: Direct predecessor incidents and causal catalysts.",
                    },
                    "impacted_sectors": {
                        "type": "object",
                        "description": "For UC-02: Categorized breakdown across Country, Company, Industry, Commodity.",
                    },
                    "critical_chokepoints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "category": {"type": "string"},
                                "name": {"type": "string"},
                                "vulnerability": {"type": "string"},
                            },
                        },
                        "description": "Immediate supply chain vulnerabilities and bottlenecks.",
                    },
                    "verified_quotes_and_metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "quote": {"type": "string"},
                                "publisher": {"type": "string"},
                                "url": {"type": "string"},
                            },
                            "required": ["claim", "quote", "publisher", "url"],
                        },
                        "description": "For UC-01: Verified quotes and metrics extracted from chunks.",
                    },
                    "verified_metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "quote": {"type": "string"},
                                "publisher": {"type": "string"},
                                "url": {"type": "string"},
                            },
                            "required": ["claim", "quote", "publisher", "url"],
                        },
                        "description": "For UC-02: Verified metrics and transmission evidence from chunks.",
                    },
                    "read_more": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                                "publisher": {"type": "string"},
                                "published_at": {"type": "string"},
                            },
                            "required": ["title", "url", "publisher"],
                        },
                        "description": "Source article cards with publisher badges.",
                    },
                    "grounding_score": {
                        "type": "number",
                        "description": "Grounding confidence score between 0.0 and 1.0.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "json",
            "description": "Alias for submitting final JSON explanation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "incident_overview": {"type": "string"},
                    "blast_radius_overview": {"type": "string"},
                    "key_actors": {"type": "array"},
                    "causal_drivers": {"type": "array", "items": {"type": "string"}},
                    "impacted_sectors": {"type": "object"},
                    "critical_chokepoints": {"type": "array"},
                    "verified_quotes_and_metrics": {"type": "array"},
                    "verified_metrics": {"type": "array"},
                    "read_more": {"type": "array"},
                    "grounding_score": {"type": "number"},
                },
            },
        },
    },
]

__all__ = [
    "search_graph_chunks",
    "get_neighboring_chunks",
    "get_initial_chunks",
    "get_embedding_service",
    "AGENT_TOOLS_DEFINITIONS",
]
