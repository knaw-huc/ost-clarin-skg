from fastapi.testclient import TestClient

from src.ost_clairin_skg.main import app


client = TestClient(app)


def test_get_topics_returns_placeholder_payload():
    response = client.get("/api/v1/topics")

    assert response.status_code == 200
    data = response.json()

    assert "@context" in data
    assert "meta" in data
    assert "@graph" in data
    assert len(data["@graph"]) == 3
    assert data["@graph"][0]["entity_type"] == "topic"


def test_get_topics_supports_label_search():
    response = client.get("/api/v1/topics", params={"filter": "cf.search.labels:Solar"})

    assert response.status_code == 200
    data = response.json()

    assert len(data["@graph"]) == 1
    assert data["@graph"][0]["local_identifier"] == "topic-2-solar"


def test_get_topics_supports_language_search():
    response = client.get("/api/v1/topics", params={"filter": "cf.search.language:it"})

    assert response.status_code == 200
    data = response.json()

    assert len(data["@graph"]) == 1
    assert data["@graph"][0]["local_identifier"] == "topic-1-cs"


def test_get_topics_combines_filters_with_and_logic():
    response = client.get(
        "/api/v1/topics",
        params={"filter": "cf.search.labels:Data,cf.search.language:de"},
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["@graph"]) == 1
    assert data["@graph"][0]["local_identifier"] == "topic-3-data"


def test_get_topics_rejects_unsupported_filters():
    response = client.get("/api/v1/topics", params={"filter": "name:Computer Science"})

    assert response.status_code == 422
    assert "Unsupported filter" in response.json()["message"]


def test_get_topic_returns_single_placeholder_topic():
    response = client.get("/api/v1/topics/topic-1-cs")

    assert response.status_code == 200
    data = response.json()

    assert data["meta"]["entity_type"] == "single_entity"
    assert data["@graph"][0]["local_identifier"] == "topic-1-cs"
    assert data["@graph"][0]["labels"]["en"] == "Computer Science"


def test_get_topic_returns_404_for_unknown_identifier():
    response = client.get("/api/v1/topics/unknown-topic")

    assert response.status_code == 404
    assert response.json()["message"] == "Topic 'unknown-topic' not found"
