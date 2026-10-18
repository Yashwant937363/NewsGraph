import logging
import re
from typing import Any, Dict, List, Optional
from app.services.embeddings import EmbeddingService

logger = logging.getLogger("news_pipeline.chunker")


class NewsChunker:
    """
    Paragraph-aware semantic chunker optimized for news articles and
    all-MiniLM-L6-v2 256-token (~150-190 words) input limit.
    """

    def __init__(
        self,
        target_words: int = 150,
        max_words: int = 185,
        min_para_words: int = 15,
        overlap_sentences: int = 1,
    ):
        self.target_words = target_words
        self.max_words = max_words
        self.min_para_words = min_para_words
        self.overlap_sentences = overlap_sentences

    @staticmethod
    def split_into_sentences(text: str) -> List[str]:
        """
        Splits text into sentences safely using punctuation regex,
        avoiding splits on common abbreviations like U.S., etc.
        """
        # Protect common abbreviations before splitting
        text = text.strip()
        if not text:
            return []

        # Simple sentence splitter on .!? followed by whitespace and capital letter / quote
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'‘“])", text)
        cleaned = [s.strip() for s in sentences if s.strip()]
        if not cleaned:
            return [text]
        return cleaned

    def chunk_article(
        self,
        title: str,
        full_text: str,
        article_url: str,
    ) -> List[Dict[str, Any]]:
        """
        Splits full_text into semantic paragraph-aggregated chunks.
        Prepends '[Article: <title>]' as context anchor in embed_text.
        """
        if not full_text or not full_text.strip():
            return []

        # 1. Clean paragraphs
        raw_paras = full_text.split("\n\n")
        # If no \n\n found, try single \n
        if len(raw_paras) <= 1 and "\n" in full_text:
            raw_paras = full_text.split("\n")

        clean_paras = [
            p.strip() for p in raw_paras
            if len(p.strip().split()) >= self.min_para_words
        ]

        if not clean_paras:
            # Fallback if paragraphs are short or dense
            if len(full_text.strip().split()) >= 10:
                clean_paras = [full_text.strip()]
            else:
                return []

        chunks: List[Dict[str, Any]] = []
        current_chunk_sentences: List[str] = []
        current_word_count = 0

        clean_title = (title or "").strip()
        prefix = f"[Article: {clean_title}]\n" if clean_title else ""

        for para in clean_paras:
            sentences = self.split_into_sentences(para)
            for sentence in sentences:
                s_words = len(sentence.split())

                # If adding this sentence exceeds max_words and we already have sentences
                if current_word_count + s_words > self.max_words and current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences)
                    embed_text = f"{prefix}{chunk_text}" if prefix else chunk_text
                    chunks.append({
                        "chunk_index": len(chunks),
                        "text": chunk_text,
                        "embed_text": embed_text,
                        "word_count": current_word_count,
                    })

                    # Carry over overlap sentence(s)
                    if self.overlap_sentences > 0:
                        overlap = current_chunk_sentences[-self.overlap_sentences:]
                    else:
                        overlap = []
                    current_chunk_sentences = list(overlap)
                    current_word_count = sum(len(s.split()) for s in current_chunk_sentences)

                current_chunk_sentences.append(sentence)
                current_word_count += s_words

        # Final trailing chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            embed_text = f"{prefix}{chunk_text}" if prefix else chunk_text
            chunks.append({
                "chunk_index": len(chunks),
                "text": chunk_text,
                "embed_text": embed_text,
                "word_count": current_word_count,
            })

        # Assign deterministic chunk IDs
        for chk in chunks:
            chk["chunk_id"] = f"{article_url}#c{chk['chunk_index']}"

        return chunks

    def process_article_chunks_with_embeddings(
        self,
        article_url: str,
        title: str,
        full_text: str,
        embedding_service: EmbeddingService,
    ) -> List[Dict[str, Any]]:
        """
        Chunks the article text and generates 384-d normalized embeddings
        for each chunk using all-MiniLM-L6-v2.
        """
        chunks = self.chunk_article(title=title, full_text=full_text, article_url=article_url)
        if not chunks:
            return []

        embed_texts = [c["embed_text"] for c in chunks]
        embeddings = embedding_service.encode_texts(embed_texts)

        for i, chk in enumerate(chunks):
            chk["embedding"] = embeddings[i].tolist()

        return chunks
