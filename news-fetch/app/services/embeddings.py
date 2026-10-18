import logging
import time
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from app.models.schemas.article import Article

logger = logging.getLogger("news_pipeline.embeddings")

class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", batch_size: int = 64):
        self.model_name = model_name
        self.batch_size = batch_size
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"[Stage 3: Embeddings] Loading SentenceTransformer model '{self.model_name}'...")
            t0 = time.time()
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"[Stage 3: Embeddings] Model loaded successfully in {time.time() - t0:.2f}s")
        return self._model

    @staticmethod
    def article_to_text(article: Article) -> str:
        """Concatenate title and description for clean semantic representation."""
        parts = [article.title, article.description or ""]
        return " ".join(p.strip() for p in parts if p.strip())

    def encode_texts(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """Encodes arbitrary texts into normalized 384-d embeddings matrix."""
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        bs = batch_size or self.batch_size
        return self.model.encode(
            texts,
            batch_size=bs,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def encode_query(self, query: str) -> List[float]:
        """Encodes a single query string into a 384-d normalized float list."""
        if not query or not query.strip():
            return [0.0] * 384
        vec = self.model.encode(
            query.strip(),
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vec.tolist()

    def generate_embeddings(self, articles: List[Article]) -> np.ndarray:
        """Encodes articles into normalized embeddings matrix."""
        if not articles:
            logger.warning("[Stage 3: Embeddings] No articles provided for embedding generation.")
            return np.empty((0, 384), dtype=np.float32)

        texts = [self.article_to_text(art) for art in articles]
        logger.info(
            f"[Stage 3: Embeddings] Encoding {len(texts)} articles using '{self.model_name}' "
            f"(batch_size={self.batch_size})..."
        )
        t0 = time.time()
        embeddings = self.encode_texts(texts)
        duration = time.time() - t0
        logger.info(
            f"[Stage 3: Embeddings] Generated embeddings of shape {embeddings.shape} in {duration:.2f}s "
            f"({len(texts)/max(duration, 0.001):.1f} articles/s)"
        )
        return embeddings

