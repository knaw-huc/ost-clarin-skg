"""
Test suite for the venue endpoints and SKG-IF JSON-LD response format.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ost_clairin_skg.main import app
from src.ost_clairin_skg.api.v1.venues import rdf_graph_to_venue, rdf_graph_to_venues


client = TestClient(app)

PATCH_TARGET = 'src.ost_clairin_skg.api.v1.venues.query_triplestore'

SAMPLE_TURTLE_DATA = """
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix datacite: <http://purl.org/spar/datacite/> .
@prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .
@prefix fabio: <http://purl.org/spar/fabio/> .
@prefix frapo: <http://purl.org/cerif/frapo/> .

<otf:otf___venue_journal___puhe_ja_kieli> a fabio:ExpressionCollection, fabio:Journal ;
  foaf:name "Puhe ja kieli" ;
  frapo:hasAcronym "PjK" ;
  datacite:hasIdentifier _:id1 .

_:id1 datacite:usesIdentifierScheme datacite:issn ;
  silvio:hasLiteralValue "2341-5967" .

<otf:otf___venue___untyped> a fabio:ExpressionCollection ;
  foaf:name "Untyped venue" .
"""

# GraphDB returns prefix declarations even when a CONSTRUCT matches nothing
EMPTY_TURTLE_DATA = "@prefix fabio: <http://purl.org/spar/fabio/> ."


class TestRDFToVenueTransformation:

    def test_rdf_graph_to_venues(self):
        venues = {v["local_identifier"]: v for v in rdf_graph_to_venues(SAMPLE_TURTLE_DATA)}

        assert venues["otf___venue_journal___puhe_ja_kieli"] == {
            "local_identifier": "otf___venue_journal___puhe_ja_kieli",
            "entity_type": "venue",
            "identifiers": [{"value": "2341-5967", "scheme": "issn"}],
            "name": "Puhe ja kieli",
            "type": "journal",
            "acronym": "PjK",
        }
        assert venues["otf___venue___untyped"] == {
            "local_identifier": "otf___venue___untyped",
            "entity_type": "venue",
            "name": "Untyped venue",
            "type": "unknown",
        }

    def test_rdf_graph_to_venue_uses_requested_id(self):
        venue = rdf_graph_to_venue(SAMPLE_TURTLE_DATA, "some-id")
        assert venue["local_identifier"] == "some-id"


class TestVenuesEndpoint:

    @patch(PATCH_TARGET)
    def test_list_venues(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/venues?page=2&page_size=5")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        data = response.json()
        assert len(data["@graph"]) == 2
        assert data["meta"]["local_identifier"].endswith("/api/v1/venues?page=2&page_size=5")
        assert data["meta"]["next_page"]["local_identifier"].endswith("/api/v1/venues?page=3&page_size=5")
        assert data["meta"]["part_of"]["total_items"] == 42

        sparql = mock_query.call_args[0][0]
        assert "LIMIT 5" in sparql
        assert "OFFSET 5" in sparql

    @patch(PATCH_TARGET)
    def test_list_venues_empty(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/venues")
        assert response.status_code == 200
        assert response.json()["@graph"] == []

    @patch(PATCH_TARGET)
    def test_filters_are_translated_to_sparql(self, mock_query, mock_count):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/venues?filter=cf.search.name:puhe,type:journal,identifiers.scheme:issn")

        assert response.status_code == 200
        for sparql in (mock_query.call_args[0][0], mock_count["venues"].call_args[0][0]):
            assert 'foaf:name ?fv0 . FILTER(CONTAINS(LCASE(STR(?fv0)), LCASE("puhe")))' in sparql
            assert "datacite:usesIdentifierScheme ?fv1" in sparql
            assert "?s a <http://purl.org/spar/fabio/Journal> ." in sparql

    @patch(PATCH_TARGET)
    def test_unknown_type_filter(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        client.get("/api/v1/venues?filter=type:unknown")
        assert "FILTER NOT EXISTS { ?s a ?ft . VALUES ?ft {" in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_invalid_type_filter(self, mock_query):
        response = client.get("/api/v1/venues?filter=type:magazine")
        assert response.status_code == 422
        assert "journal" in response.json()["supported_types"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_unsupported_filter(self, mock_query):
        response = client.get("/api/v1/venues?filter=series:X")
        assert response.status_code == 422
        assert response.json()["unsupported_filters"] == ["series"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_list_venues_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/venues").status_code == 502


class TestVenueEndpoint:

    @patch(PATCH_TARGET)
    def test_get_venue(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/venues/otf___venue_journal___puhe_ja_kieli")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        assert response.json()["@graph"][0]["local_identifier"] == "otf___venue_journal___puhe_ja_kieli"
        assert 'FILTER(STR(?s) = "otf:otf___venue_journal___puhe_ja_kieli")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_venue_not_found(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        assert client.get("/api/v1/venues/otf:unknown").status_code == 404

    @patch(PATCH_TARGET)
    def test_get_venue_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/venues/otf:x").status_code == 502
