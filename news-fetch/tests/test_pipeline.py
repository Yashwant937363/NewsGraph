import pytest
from app.models.schemas.article import Article, ArticleSource
from app.services.dedup import DeduplicationService
from app.services.embeddings import EmbeddingService
from app.services.clustering import ClusteringService
from app.services.pipeline import NewsPipelineService
from app.config import Settings

@pytest.fixture
def dedup_service():
    return DeduplicationService(simhash_distance_threshold=1)

@pytest.fixture
def sample_articles():
    return [
        Article(
            title="Tech giant unveils quantum computing chip",
            description="A revolutionary 1000-qubit processor was unveiled today by researchers.",
            url="https://example.com/quantum-chip?utm_source=rss&ref=123",
        ),
        Article(
            title="Tech giant unveils quantum computing chip",
            description="A revolutionary 1000-qubit processor was unveiled today by researchers.",
            url="https://example.com/quantum-chip", # Same URL after normalization
        ),
        Article(
            title="Tech giant unveils quantum computing chip",
            description="A revolutionary 1000-qubit processor was unveiled today by researchers.",
            content="Full syndicated copy of the quantum announcement.",
            url="https://syndicate.org/news/quantum-chip-syndicated", # Different URL, same content
        ),
        Article(
            title="New species of deep-sea jellyfish discovered",
            description="Marine biologists have discovered a bioluminescent jellyfish at 4000 meters depth in the Pacific.",
            url="https://oceanlife.org/new-jellyfish",
        ),
    ]

def test_url_normalization(dedup_service):
    raw_url = "https://Example.COM:443/news/article-1?utm_campaign=winter#heading"
    normalized = dedup_service.normalize_url(raw_url)
    assert normalized == "https://example.com:443/news/article-1"

def test_url_deduplication(dedup_service, sample_articles):
    unique, count = dedup_service.deduplicate_urls(sample_articles)
    assert count == 1
    assert len(unique) == 3

def test_content_deduplication(dedup_service):
    art1 = Article(
        title="Breaking: Major breakthrough in fusion energy",
        description="Scientists achieved net energy gain for the second time in history.",
        url="https://source1.com/fusion",
    )
    art2 = Article(
        title="Breaking: Major breakthrough in fusion energy",
        description="Scientists achieved net energy gain for the second time in history.",
        url="https://source2.com/fusion",
    )
    art3 = Article(
        title="Baking tips for beginners in 2026",
        description="How to make delicious sourdough bread at home with minimal equipment.",
        url="https://recipes.com/sourdough",
    )
    unique, count = dedup_service.deduplicate_content([art1, art2, art3])
    assert count == 1
    assert len(unique) == 2
    assert unique[0].title == art1.title
    assert unique[1].title == art3.title

def test_clustering_grouping():
    # Synthetic embeddings: 2 very close vectors, 1 distant vector
    clustering_service = ClusteringService(eps=0.35, min_samples=2)
    import numpy as np
    
    # 2 identical vectors (cos distance 0), 1 orthogonal vector (cos distance 1)
    vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vec2 = np.array([0.99, 0.1, 0.0], dtype=np.float32)
    vec2 /= np.linalg.norm(vec2)
    vec3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    
    embeddings = np.vstack([vec1, vec2, vec3])
    articles = [
        Article(title="Article 1", url="https://a1.com"),
        Article(title="Article 2", url="https://a2.com"),
        Article(title="Article 3", url="https://a3.com"),
    ]

    clusters, noise, metrics = clustering_service.cluster_articles(articles, embeddings)
    assert len(clusters) == 1
    assert clusters[0].article_count == 2
    assert len(noise) == 1
    assert noise[0].title == "Article 3"
    assert metrics["noise_count"] == 1
    assert metrics["total_clusters"] == 1

def test_end_to_end_pipeline():
    settings = Settings(news_api_key="mock_key")
    pipeline = NewsPipelineService(settings=settings)

    articles = [
        Article(title="Mars Rover finds signs of ancient water", description="NASA rover drills into crater rock.", url="https://nasa.gov/1"),
        Article(title="Mars Rover discovers ancient water traces", description="NASA announces rover discovered ancient lake bed minerals.", url="https://bbc.com/1"),
        Article(title="Premier League football match ends in draw", description="Arsenal and Chelsea drew 1-1 yesterday.", url="https://sports.com/1"),
        Article(title="Arsenal vs Chelsea ends in 1-1 stalemate", description="Late goal secures 1-1 draw in London derby.", url="https://espn.com/1"),
        Article(title="Unrelated culinary festival in Lyon", description="Chefs gathered for the annual pastry cup.", url="https://lyon.fr/culinary"),
    ]

    response = pipeline.run_pipeline(articles=articles, date_str="2026-10-06")
    assert response.metrics.total_fetched == 5
    assert response.metrics.total_clusters >= 1
    assert len(response.clusters) >= 1
