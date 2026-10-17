import logging
import time
from typing import List, Optional

logger = logging.getLogger("newsgraph.agent.embedding")

_embedding_instance: Optional["EmbeddingService"] = None


class EmbeddingService:
    """Generates 384-dimensional dense vectors using all-MiniLM-L6-v2 for FalkorDB vecf32 similarity search."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model '{self.model_name}'...")
            t0 = time.time()
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            logger.info(f"SentenceTransformer loaded in {time.time() - t0:.2f}s")
        return self._model

    def encode_query(self, query: str) -> List[float]:
        """Encodes query into a 384-d normalized float list."""
        if not query or not query.strip():
            return [0.0] * 384
        vec = self.model.encode(
            query.strip(),
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vec.tolist()


def get_embedding_service() -> EmbeddingService:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = EmbeddingService()
    return _embedding_instance
