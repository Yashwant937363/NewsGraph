import os
import logging

from falkordb import FalkorDB, Graph

logger = logging.getLogger(__name__)

client: FalkorDB | None = None
graph: Graph | None = None


def init_falkordb() -> bool:
    """Initialize FalkorDB and verify connectivity."""
    global client, graph

    try:
        client = FalkorDB(
            host=os.getenv("FALKORDB_HOST", "localhost"),
            port=int(os.getenv("FALKORDB_PORT", "6379")),
            password=os.getenv("FALKORDB_PASSWORD") or None,
            socket_timeout=3,
            socket_connect_timeout=3,
        )

        # Verify that the database is reachable.
        client.connection.ping()

        graph = client.select_graph(
            os.getenv("FALKORDB_GRAPH", "worldgraph")
        )
        if graph is None:
            raise RuntimeError("Failed to select FalkorDB graph")

        logger.info("FalkorDB connection established")
        return True

    except Exception:
        logger.exception("Failed to connect to FalkorDB")
        close_falkordb()
        return False

def get_falkordb_client() -> FalkorDB | None:
    return client
    
def get_falkordb_graph() -> Graph | None:
    return graph


def is_falkordb_healthy() -> bool:
    """Return whether FalkorDB is reachable."""
    try:
        return client is not None and client.connection.ping()
    except Exception:
        logger.exception("FalkorDB health check failed")
        return False


def close_falkordb() -> None:
    """Close the FalkorDB client."""
    global client, graph

    if client is not None:
        try:
            client.close()
        except Exception:
            logger.exception("Error closing FalkorDB client")
        finally:
            client = None
            graph = None