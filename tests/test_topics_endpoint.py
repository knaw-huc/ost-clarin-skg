"""
Test suite for the topic endpoints and SKG-IF JSON-LD response format.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ost_clairin_skg.main import app
from src.ost_clairin_skg.api.v1.topics import _rdf_graph_to_topic, _rdf_graph_to_topics


client = TestClient(app)

PATCH_TARGET = 'src.ost_clairin_skg.api.v1.topics.query_triplestore'

SAMPLE_TURTLE_DATA = """
@prefix fabio: <http://purl.org/spar/fabio/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix datacite: <http://purl.org/spar/datacite/> .
@prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .

<otf:otf___topic___tcof> a fabio:SubjectTerm ;
  skos:prefLabel "tcof" .

<otf:otf___topic___solar> a fabio:SubjectTerm ;
  skos:prefLabel "Solar energy"@en, "Energie solaire"@fr ;
  datacite:hasIdentifier _:id1 .

_:id1 datacite:usesIdentifierScheme <http://purl.org/spar/datacite/wikidata> ;
  silvio:hasLiteralValue "Q12705" .
"""

# GraphDB returns prefix declarations even when a CONSTRUCT matches nothing
EMPTY_TURTLE_DATA = "@prefix fabio: <http://purl.org/spar/fabio/> ."


class TestRDFToTopicTransformation:

    def test_rdf_graph_to_topics(self):
        topics = {t["local_identifier"]: t for t in _rdf_graph_to_topics(SAMPLE_TURTLE_DATA)}

        assert set(topics) == {"otf___topic___tcof", "otf___topic___solar"}
        tcof = topics["otf___topic___tcof"]
        assert tcof["entity_type"] == "topic"
        assert tcof["labels"] == {"none": "tcof"}
        assert "identifiers" not in tcof

        solar = topics["otf___topic___solar"]
        assert solar["labels"] == {"en": "Solar energy", "fr": "Energie solaire"}
        assert solar["identifiers"] == [{"value": "Q12705", "scheme": "wikidata"}]

    def test_rdf_graph_to_topic_uses_requested_id(self):
        topic = _rdf_graph_to_topic(SAMPLE_TURTLE_DATA, "some-id")
        assert topic["local_identifier"] == "some-id"


class TestTopicsEndpoint:

    @patch(PATCH_TARGET)
    def test_list_topics(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/topics?page=2&page_size=5")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        data = response.json()
        assert len(data["@graph"]) == 2
        assert data["meta"]["local_identifier"].endswith("/api/v1/topics?page=2&page_size=5")
        assert data["meta"]["next_page"]["local_identifier"].endswith("/api/v1/topics?page=3&page_size=5")

        sparql = mock_query.call_args[0][0]
        assert "LIMIT 5" in sparql
        assert "OFFSET 5" in sparql

    @patch(PATCH_TARGET)
    def test_list_topics_empty(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/topics")
        assert response.status_code == 200
        assert response.json()["@graph"] == []

    @patch(PATCH_TARGET)
    def test_filters_are_translated_to_sparql(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/topics?filter=cf.search.labels:Solar,cf.search.language:en,identifiers.scheme:wikidata")

        assert response.status_code == 200
        sparql = mock_query.call_args[0][0]
        assert 'skos:prefLabel ?fv0 . FILTER(CONTAINS(LCASE(STR(?fv0)), LCASE("Solar")))' in sparql
        assert 'skos:prefLabel ?fv1 . FILTER(LCASE(LANG(?fv1)) = LCASE("en"))' in sparql
        assert "datacite:usesIdentifierScheme ?fv2" in sparql

    @patch(PATCH_TARGET)
    def test_unsupported_filter(self, mock_query):
        response = client.get("/api/v1/topics?filter=name:Computer Science")
        assert response.status_code == 422
        assert response.json()["unsupported_filters"] == ["name"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_list_topics_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/topics").status_code == 502


class TestTopicEndpoint:

    @patch(PATCH_TARGET)
    def test_get_topic(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/topics/otf___topic___tcof")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        assert response.json()["@graph"][0]["local_identifier"] == "otf___topic___tcof"
        assert 'FILTER(STR(?s) = "otf:otf___topic___tcof")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_topic_not_found(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        assert client.get("/api/v1/topics/otf:unknown").status_code == 404

    @patch(PATCH_TARGET)
    def test_get_topic_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/topics/otf:x").status_code == 502
