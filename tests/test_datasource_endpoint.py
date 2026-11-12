"""
Test suite for the datasource endpoints and SKG-IF JSON-LD response format.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ost_clairin_skg.main import app
from src.ost_clairin_skg.api.v1.datasources import rdf_graph_to_datasource, rdf_graph_to_datasources


client = TestClient(app)

PATCH_TARGET = 'src.ost_clairin_skg.api.v1.datasources.query_triplestore'

SAMPLE_TURTLE_DATA = """
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix fabio: <http://purl.org/spar/fabio/> .
@prefix frapo: <http://purl.org/cerif/frapo/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .

<otf:otf___ds___cedifor> a dcat:DataService, frapo:Repository ;
  foaf:name "CEDIFOR" ;
  dcat:servesDataset <otf:otf___product___1>, <otf:otf___product___2> .

<otf:otf___product___1> a fabio:Dataset .
<otf:otf___product___2> a fabio:Software .

<otf:otf___ds___unclassified> a dcat:DataService ;
  foaf:name "Unclassified" .
"""

# GraphDB returns prefix declarations even when a CONSTRUCT matches nothing
EMPTY_TURTLE_DATA = "@prefix dcat: <http://www.w3.org/ns/dcat#> ."


class TestRDFToDatasourceTransformation:

    def test_rdf_graph_to_datasources(self):
        datasources = {d["local_identifier"]: d for d in rdf_graph_to_datasources(SAMPLE_TURTLE_DATA)}

        assert datasources["otf___ds___cedifor"] == {
            "local_identifier": "otf___ds___cedifor",
            "entity_type": "datasource",
            "name": "CEDIFOR",
            "data_source_classification": "repository",
            "research_product_types": ["research data", "software"],
        }
        assert datasources["otf___ds___unclassified"] == {
            "local_identifier": "otf___ds___unclassified",
            "entity_type": "datasource",
            "name": "Unclassified",
        }

    def test_rdf_graph_to_datasource_uses_requested_id(self):
        datasource = rdf_graph_to_datasource(SAMPLE_TURTLE_DATA, "some-id")
        assert datasource["local_identifier"] == "some-id"


class TestDatasourcesEndpoint:

    @patch(PATCH_TARGET)
    def test_list_datasources(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/datasources?page=2&page_size=5")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        data = response.json()
        assert len(data["@context"]) == 3
        assert len(data["@graph"]) == 2
        assert data["meta"]["local_identifier"].endswith("/api/v1/datasources?page=2&page_size=5")
        assert data["meta"]["next_page"]["local_identifier"].endswith("/api/v1/datasources?page=3&page_size=5")
        assert data["meta"]["part_of"]["total_items"] == 42

        sparql = mock_query.call_args[0][0]
        assert "LIMIT 5" in sparql
        assert "OFFSET 5" in sparql

    @patch(PATCH_TARGET)
    def test_list_datasources_empty(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/datasources")
        assert response.status_code == 200
        assert response.json()["@graph"] == []

    @patch(PATCH_TARGET)
    def test_filters_are_translated_to_sparql(self, mock_query, mock_count):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get(
            "/api/v1/datasources?filter=cf.search.name:cedi,data_source_classification:repository,"
            "research_product_type:software"
        )

        assert response.status_code == 200
        for sparql in (mock_query.call_args[0][0], mock_count["datasources"].call_args[0][0]):
            assert 'foaf:name ?fv0 . FILTER(CONTAINS(LCASE(STR(?fv0)), LCASE("cedi")))' in sparql
            assert "?s a <http://purl.org/cerif/frapo/Repository> ." in sparql
            assert "FILTER(?fwt IN (<http://purl.org/spar/fabio/Software>))" in sparql

    @patch(PATCH_TARGET)
    def test_invalid_classification_filter(self, mock_query):
        response = client.get("/api/v1/datasources?filter=data_source_classification:magazine")
        assert response.status_code == 422
        assert response.json()["supported_values"] == ["repository"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_unsupported_filter(self, mock_query):
        response = client.get("/api/v1/datasources?filter=acronym:X")
        assert response.status_code == 422
        assert response.json()["unsupported_filters"] == ["acronym"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_list_datasources_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/datasources").status_code == 502


class TestDatasourceEndpoint:

    @patch(PATCH_TARGET)
    def test_get_datasource(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/datasources/otf___ds___cedifor")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        assert response.json()["@graph"][0]["local_identifier"] == "otf___ds___cedifor"
        assert 'FILTER(STR(?s) = "otf:otf___ds___cedifor")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_datasource_not_found(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        assert client.get("/api/v1/datasources/otf:unknown").status_code == 404

    @patch(PATCH_TARGET)
    def test_get_datasource_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/datasources/otf:x").status_code == 502
