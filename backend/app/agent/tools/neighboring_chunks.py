import logging
from typing import List, Dict, Any
from app.config.falkordb_client import get_falkordb_graph

logger = logging.getLogger("newsgraph.agent.neighboring_chunks")


def get_neighboring_chunks(chunk_id: str, window: int = 1) -> List[Dict[str, Any]]:
    """
    Given a chunk_id, retrieves the preceding and succeeding chunks from the same article
    via FalkorDB graph traversal for context expansion.
    """
    graph = get_falkordb_graph()
    if graph is None:
        logger.error("FalkorDB graph is not initialized.")
        return []

    if not chunk_id or not chunk_id.strip():
        logger.warning("Empty chunk_id provided to get_neighboring_chunks.")
        return []

    cypher = """
    MATCH (a:Article)-[:HAS_CHUNK]->(curr:Chunk {chunk_id: $chunk_id})
    MATCH (a)-[:HAS_CHUNK]->(neighbor:Chunk)
    WHERE neighbor.chunk_index >= curr.chunk_index - $window
      AND neighbor.chunk_index <= curr.chunk_index + $window
      AND neighbor.chunk_id <> $chunk_id
    RETURN neighbor.chunk_id AS chunk_id,
           neighbor.chunk_index AS chunk_index,
           neighbor.text AS chunk_text,
           a.title AS article_title,
           a.url AS article_url,
           CASE WHEN neighbor.chunk_index < curr.chunk_index THEN 'previous' ELSE 'next' END AS position
    ORDER BY neighbor.chunk_index ASC
    """

    try:
        res = graph.query(
            cypher,
            {
                "chunk_id": chunk_id.strip(),
                "window": max(1, window),
            },
        )

        neighbors = []
        for row in res.result_set:
            neighbors.append(
                {
                    "chunk_id": row[0],
                    "chunk_index": row[1],
                    "chunk_text": row[2],
                    "article_title": row[3],
                    "article_url": row[4],
                    "position": row[5],
                }
            )
        return neighbors
    except Exception as e:
        logger.exception(f"Error fetching neighboring chunks for '{chunk_id}': {e}")
        return []
