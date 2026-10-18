import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "News Event Clustering Pipeline API is running" in data["message"]

def test_health_endpoint(client):
    response = client.get("/api/v1/pipeline/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_articles_html_page(client):
    response = client.get("/articles")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "NewsFetch" in response.text
    assert "searchInput" in response.text

def test_articles_api_endpoint(client):
    response = client.get("/api/v1/articles?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "has_more" in data
    assert isinstance(data["items"], list)

def test_articles_stats_endpoint(client):
    response = client.get("/api/v1/articles/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_articles" in data
    assert "total_queries" in data


def test_phase1_html_page(client):
    response = client.get("/phase1")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "WorldGraph" in response.text
    assert "Phase 1 Output" in response.text
    assert "vis-network" in response.text


def test_phase1_stats_endpoint(client):
    response = client.get("/api/v1/phase1/stats")
    assert response.status_code == 200
    data = response.json()
    assert "graph_stats" in data
    assert data["graph_stats"]["events"] > 0


def test_phase1_stories_endpoint(client):
    response = client.get("/api/v1/phase1/stories?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "stories" in data
    assert len(data["stories"]) > 0
    story_id = data["stories"][0]["story_id"]

    # Test story graph endpoint
    g_res = client.get(f"/api/v1/phase1/story/{story_id}/graph")
    assert g_res.status_code == 200
    g_data = g_res.json()
    assert "nodes" in g_data
    assert "edges" in g_data
    assert len(g_data["nodes"]) > 0

