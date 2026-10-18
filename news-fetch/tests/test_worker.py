import pytest
from app.services.selected_queries import get_selected_queries
from app.services.key_rotator import KeyRotator
from app.models.documents.article import ArticleDocument
from app.models.documents.fetch_state import FetchStateDocument
from app.core.db import init_db, close_db


def test_selected_queries_count_and_uniqueness():
    queries = get_selected_queries()
    assert len(queries) == 150, "Should have exactly 150 queries"
    
    unique_texts = set(q["query"] for q in queries)
    assert len(unique_texts) == 150, "All 150 queries must be unique"

    for item in queries:
        assert item["id"] > 0
        assert len(item["query"].strip()) > 3


def test_key_rotator():
    test_keys = ["key_alpha_12345", "key_beta_67890"]
    rotator = KeyRotator(keys=test_keys)
    assert rotator.total_keys == 2
    
    first = rotator.get_current_key()
    assert first == "key_alpha_12345"
    
    second = rotator.rotate(reason="unit test")
    assert second == "key_beta_67890"
    assert rotator.get_current_key() == "key_beta_67890"


@pytest.mark.asyncio
async def test_document_models_with_db():
    await init_db()
    try:
        doc = ArticleDocument(
            title="Breaking News Test",
            url="https://example.com/breaking-news-test-unique-12345",
            published_at="2026-10-01T12:00:00Z",
            matched_queries=['"breaking news"'],
        )
        assert doc.url == "https://example.com/breaking-news-test-unique-12345"
        assert len(doc.matched_queries) == 1

        state = FetchStateDocument(
            state_id="test_state_dummy",
            total_queries=150,
            completed_query_ids=[1, 2, 3],
        )
        assert state.total_queries == 150
        assert len(state.completed_query_ids) == 3
    finally:
        await close_db()
