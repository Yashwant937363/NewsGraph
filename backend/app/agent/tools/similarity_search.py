import logging
from typing import List, Dict, Any
from app.config.falkordb_client import get_falkordb_graph
from app.agent.tools.embedding import get_embedding_service

logger = logging.getLogger("newsgraph.agent.similarity_search")


def search_graph_chunks(
    query: str,
    scoped_article_urls: List[str],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Performs vector similarity search for specific claims, numbers, or quotes,
    STRICTLY scoped to the articles and events within the returned subgraph.
    """
    graph = get_falkordb_graph()
    if graph is None:
        logger.error("FalkorDB graph is not initialized.")
        return []

    if not scoped_article_urls:
        logger.info("No scoped article URLs provided for similarity search.")
        return [
            {
                "info": "No article URLs are scoped to this event in the graph. Ground your assessment on the event metadata and graph topology."
            }
        ]

    embedding_service = get_embedding_service()
    query_vector = embedding_service.encode_query(query)

    cypher = """
    MATCH (a:Article)-[:HAS_CHUNK]->(c:Chunk)
    WHERE a.url IN $scoped_article_urls
      AND c.embedding IS NOT NULL
    WITH a, c, (1.0 - vec.cosineDistance(c.embedding, vecf32($query_vector))) AS similarity
    RETURN a.title AS article_title,
           a.url AS article_url,
           c.chunk_id AS chunk_id,
           c.chunk_index AS chunk_index,
           c.text AS chunk_text,
           similarity
    ORDER BY similarity DESC
    LIMIT $limit
    """

    try:
        res = graph.query(
            cypher,
            {
                "scoped_article_urls": scoped_article_urls,
                "query_vector": query_vector,
                "limit": limit,
            },
        )

        chunks = []
        for row in res.result_set:
            chunks.append(
                {
                    "article_title": row[0],
                    "article_url": row[1],
                    "chunk_id": row[2],
                    "chunk_index": row[3],
                    "chunk_text": row[4],
                    "similarity": round(float(row[5]), 4),
                }
            )
        return chunks
    except Exception as e:
        logger.exception(f"Error during scoped vector search for query '{query}': {e}")
        return []
