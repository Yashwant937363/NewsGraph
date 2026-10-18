import pytest
from app.services.falkordb_chunker import NewsChunker
from app.services.embeddings import EmbeddingService


def test_sentence_splitting():
    chunker = NewsChunker()
    text = "The United States announced new trade curbs on Monday. The restrictions target advanced semiconductors! Will European allies follow suit? Officials declined to comment."
    sentences = chunker.split_into_sentences(text)
    assert len(sentences) == 4
    assert sentences[0] == "The United States announced new trade curbs on Monday."
    assert sentences[1] == "The restrictions target advanced semiconductors!"
    assert sentences[2] == "Will European allies follow suit?"
    assert sentences[3] == "Officials declined to comment."


def test_chunk_article_bounds_and_overlap():
    chunker = NewsChunker(target_words=50, max_words=60, overlap_sentences=1, min_para_words=5)

    title = "Chip Restrictions Shake Global Tech Supply Chains"
    url = "https://example.com/chip-restrictions-2026"

    p1 = "The United States has unveiled aggressive export controls targeting high-end chipmaking gear. Several major tech firms in Asia and Europe expressed concern over supply disruptions. Semiconductor manufacturers are urgently revising their shipment schedules across international markets."
    p2 = "Global markets reacted sharply to the news with tech equities dropping 4 percent. Analysts warn that raw material shortages may worsen if retaliation occurs. European policymakers held emergency meetings in Brussels to assess the economic fallout."
    p3 = "Industry leaders called for clearer guidelines on bilateral technology transfers. Companies have already begun rerouting logistics hubs to mitigate delays. Further announcements are expected following the G7 summit next week."

    full_text = f"{p1}\n\n{p2}\n\n{p3}"

    chunks = chunker.chunk_article(title=title, full_text=full_text, article_url=url)

    assert len(chunks) >= 2
    for i, chk in enumerate(chunks):
        assert chk["chunk_id"] == f"{url}#c{i}"
        assert chk["chunk_index"] == i
        assert chk["word_count"] <= 65
        assert chk["embed_text"].startswith(f"[Article: {title}]")
        assert len(chk["text"]) > 0

    # Test overlap: first sentence of chunk 1 should be last sentence of chunk 0
    if len(chunks) > 1:
        last_sentence_c0 = chunker.split_into_sentences(chunks[0]["text"])[-1]
        first_sentence_c1 = chunker.split_into_sentences(chunks[1]["text"])[0]
        assert last_sentence_c0 == first_sentence_c1


def test_empty_or_minimal_article():
    chunker = NewsChunker()
    assert chunker.chunk_article(title="Test", full_text="", article_url="https://example.com/1") == []
    assert chunker.chunk_article(title="Test", full_text="   ", article_url="https://example.com/1") == []


def test_chunks_with_embeddings():
    chunker = NewsChunker(target_words=40, max_words=60, min_para_words=5)
    embedding_service = EmbeddingService(model_name="all-MiniLM-L6-v2")

    title = "Central Bank Adjusts Benchmark Lending Rate"
    url = "https://example.com/rates-2026"
    full_text = (
        "The Federal Reserve decided to lower interest rates by twenty-five basis points today. "
        "The decision came after months of steady economic indicators and cooling inflation. "
        "Financial markets rallied across Wall Street in immediate response to the policy shift."
    )

    chunks = chunker.process_article_chunks_with_embeddings(
        article_url=url,
        title=title,
        full_text=full_text,
        embedding_service=embedding_service,
    )

    assert len(chunks) >= 1
    for chk in chunks:
        assert "embedding" in chk
        assert len(chk["embedding"]) == 384
        # Assert normalized vector (sum of squares ~ 1.0)
        norm_sq = sum(x * x for x in chk["embedding"])
        assert 0.98 <= norm_sq <= 1.02
