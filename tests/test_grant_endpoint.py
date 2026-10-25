"""
Test suite for the grant endpoints and SKG-IF JSON-LD response format.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ost_clairin_skg.main import app
from src.ost_clairin_skg.api.v1.grants import rdf_graph_to_grant, rdf_graph_to_grants


client = TestClient(app)

PATCH_TARGET = 'src.ost_clairin_skg.api.v1.grants.query_triplestore'

SAMPLE_TURTLE_DATA = """
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix datacite: <http://purl.org/spar/datacite/> .
@prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .
@prefix frapo: <http://purl.org/cerif/frapo/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix ti: <http://www.ontologydesignpatterns.org/cp/owl/timeinterval.owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<otf:otf___grant___graspos> a frapo:Grant ;
  datacite:hasIdentifier _:id1 ;
  dcterms:title "GraspOS: next Generation Research Assessment to Promote Open Science"@en ;
  dcterms:abstract "GraspOS aims to build and operate a data infrastructure."@en ;
  frapo:hasAcronym "GraspOS" ;
  frapo:hasGrantNumber "101095129" ;
  frapo:hasFundingAgency <otf:otf___org___european_commission> ;
  frapo:hasCallIdentifier "Horizon Europe" ;
  frapo:hasCurrencyCode "EUR" ;
  frapo:hasCurrency "50000"^^xsd:float ;
  foaf:homepage <https://graspos.eu> ;
  frapo:supports <otf:otf___org___clarin_eric>, <otf:otf___org___athena_rc> ;
  dcterms:temporal _:d1 .

_:d1 ti:hasIntervalStartDate "2023-01-01T00:00:00Z"^^xsd:dateTime ;
  ti:hasIntervalEndDate "2025-12-31T23:59:59Z"^^xsd:dateTime .

_:id1 datacite:usesIdentifierScheme datacite:doi ;
  silvio:hasLiteralValue "https://doi.org/10.3030/101095129" .

<otf:otf___grant___minimal> a frapo:Grant ;
  frapo:hasGrantNumber "42" .
"""

# GraphDB returns prefix declarations even when a CONSTRUCT matches nothing
EMPTY_TURTLE_DATA = "@prefix frapo: <http://purl.org/cerif/frapo/> ."


class TestRDFToGrantTransformation:

    def test_rdf_graph_to_grants(self):
        grants = {g["local_identifier"]: g for g in rdf_graph_to_grants(SAMPLE_TURTLE_DATA)}

        assert set(grants) == {"otf___grant___graspos", "otf___grant___minimal"}
        graspos = grants["otf___grant___graspos"]
        assert graspos == {
            "local_identifier": "otf___grant___graspos",
            "entity_type": "grant",
            "identifiers": [{"value": "https://doi.org/10.3030/101095129", "scheme": "doi"}],
            "titles": {"en": ["GraspOS: next Generation Research Assessment to Promote Open Science"]},
            "abstracts": {"en": ["GraspOS aims to build and operate a data infrastructure."]},
            "acronym": "GraspOS",
            "grant_number": "101095129",
            "funding_stream": "Horizon Europe",
            "currency": "EUR",
            "website": "https://graspos.eu",
            "funding_agency": {"local_identifier": "otf___org___european_commission", "entity_type": "organisation"},
            "funded_amount": 50000.0,
            "duration": {"start": "2023-01-01T00:00:00+00:00", "end": "2025-12-31T23:59:59+00:00"},
            "beneficiaries": [
                {"local_identifier": "otf___org___athena_rc", "entity_type": "organisation"},
                {"local_identifier": "otf___org___clarin_eric", "entity_type": "organisation"},
            ],
        }

        assert grants["otf___grant___minimal"] == {
            "local_identifier": "otf___grant___minimal",
            "entity_type": "grant",
            "grant_number": "42",
        }

    def test_rdf_graph_to_grant_uses_requested_id(self):
        grant = rdf_graph_to_grant(SAMPLE_TURTLE_DATA, "some-id")
        assert grant["local_identifier"] == "some-id"

    def test_rdf_graph_to_grant_none_when_empty(self):
        assert rdf_graph_to_grant(EMPTY_TURTLE_DATA, "x") is None


class TestGrantsEndpoint:

    @patch(PATCH_TARGET)
    def test_list_grants(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/grants?page=2&page_size=5")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        data = response.json()
        assert len(data["@graph"]) == 2
        assert data["meta"]["local_identifier"].endswith("/api/v1/grants?page=2&page_size=5")
        assert data["meta"]["next_page"]["local_identifier"].endswith("/api/v1/grants?page=3&page_size=5")
        assert data["meta"]["part_of"]["total_items"] == 42

        sparql = mock_query.call_args[0][0]
        assert "LIMIT 5" in sparql
        assert "OFFSET 5" in sparql

    @patch(PATCH_TARGET)
    def test_list_grants_empty(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/grants")
        assert response.status_code == 200
        assert response.json()["@graph"] == []

    @patch(PATCH_TARGET)
    def test_filters_are_translated_to_sparql(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/grants?filter=cf.search.title:open,grant_number:101095129,identifiers.scheme:doi")

        assert response.status_code == 200
        sparql = mock_query.call_args[0][0]
        assert 'dcterms:title ?fv0 . FILTER(CONTAINS(LCASE(STR(?fv0)), LCASE("open")))' in sparql
        assert 'frapo:hasGrantNumber ?fv1 . FILTER(STR(?fv1) = "101095129")' in sparql
        assert "datacite:usesIdentifierScheme ?fv2" in sparql

    @patch(PATCH_TARGET)
    def test_count_query_uses_filters(self, mock_query, mock_count):
        mock_query.return_value = EMPTY_TURTLE_DATA
        client.get("/api/v1/grants?filter=acronym:GraspOS")

        count_sparql = mock_count["grants"].call_args[0][0]
        assert "COUNT(DISTINCT ?s)" in count_sparql
        assert 'frapo:hasAcronym ?fv0 . FILTER(STR(?fv0) = "GraspOS")' in count_sparql

    @patch(PATCH_TARGET)
    def test_unsupported_filter(self, mock_query):
        response = client.get("/api/v1/grants?filter=beneficiaries.country:NL")
        assert response.status_code == 422
        assert response.json()["unsupported_filters"] == ["beneficiaries.country"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_list_grants_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/grants").status_code == 502


class TestGrantEndpoint:

    @patch(PATCH_TARGET)
    def test_get_grant(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/grants/otf___grant___graspos")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        assert response.json()["@graph"][0]["local_identifier"] == "otf___grant___graspos"
        assert 'FILTER(STR(?s) = "otf:otf___grant___graspos")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_grant_not_found(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        assert client.get("/api/v1/grants/otf:unknown").status_code == 404

    @patch(PATCH_TARGET)
    def test_get_grant_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/grants/otf:x").status_code == 502
