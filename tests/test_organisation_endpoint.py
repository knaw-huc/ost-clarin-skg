"""
Test suite for the organisation endpoints and SKG-IF JSON-LD response format.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ost_clairin_skg.main import app
from src.ost_clairin_skg.api.v1.organizations import _rdf_graph_to_organisation, _rdf_graph_to_organisations


client = TestClient(app)

PATCH_TARGET = 'src.ost_clairin_skg.api.v1.organizations.query_triplestore'

SAMPLE_TURTLE_DATA = """
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix datacite: <http://purl.org/spar/datacite/> .
@prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .

<otf:otf___org___clarin_eric> a foaf:Organization ;
  foaf:name "CLARIN ERIC" ;
  foaf:homepage <https://www.clarin.eu/> ;
  datacite:hasIdentifier _:id1 .

_:id1 datacite:usesIdentifierScheme datacite:ror ;
  silvio:hasLiteralValue "https://ror.org/05k4x2q18" .

<otf:otf___org___vytautas_magnus_university> a foaf:Organization ;
  foaf:name "Vytautas Magnus university", "Vytautas Magnus University" .
"""

# GraphDB returns prefix declarations even when a CONSTRUCT matches nothing
EMPTY_TURTLE_DATA = "@prefix foaf: <http://xmlns.com/foaf/0.1/> ."


class TestRDFToOrganisationTransformation:

    def test_rdf_graph_to_organisations(self):
        orgs = {o["local_identifier"]: o for o in _rdf_graph_to_organisations(SAMPLE_TURTLE_DATA)}

        assert set(orgs) == {"otf___org___clarin_eric", "otf___org___vytautas_magnus_university"}
        clarin = orgs["otf___org___clarin_eric"]
        assert clarin["entity_type"] == "organisation"
        assert clarin["name"] == "CLARIN ERIC"
        assert clarin["website"] == "https://www.clarin.eu/"
        assert clarin["identifiers"] == [{"value": "https://ror.org/05k4x2q18", "scheme": "ror"}]
        assert "other_names" not in clarin

        vmu = orgs["otf___org___vytautas_magnus_university"]
        assert vmu["name"] == "Vytautas Magnus University"
        assert vmu["other_names"] == ["Vytautas Magnus university"]
        assert "website" not in vmu
        assert "identifiers" not in vmu

    def test_rdf_graph_to_organisation_uses_requested_id(self):
        org = _rdf_graph_to_organisation(SAMPLE_TURTLE_DATA, "some-id")
        assert org["local_identifier"] == "some-id"


class TestOrganisationsEndpoint:

    @patch(PATCH_TARGET)
    def test_list_organisations(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/organisations?page=2&page_size=5")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        data = response.json()
        assert len(data["@graph"]) == 2
        assert data["meta"]["local_identifier"].endswith("/api/v1/organisations?page=2&page_size=5")
        assert data["meta"]["next_page"]["local_identifier"].endswith("/api/v1/organisations?page=3&page_size=5")
        assert data["meta"]["part_of"]["total_items"] == 42

        sparql = mock_query.call_args[0][0]
        assert "LIMIT 5" in sparql
        assert "OFFSET 5" in sparql

    @patch(PATCH_TARGET)
    def test_list_organisations_empty(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/organisations")
        assert response.status_code == 200
        assert response.json()["@graph"] == []

    @patch(PATCH_TARGET)
    def test_filters_are_translated_to_sparql(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/organisations?filter=cf.search.name:clarin,name:CLARIN ERIC,identifiers.scheme:ror")

        assert response.status_code == 200
        sparql = mock_query.call_args[0][0]
        assert 'foaf:name ?fv0 . FILTER(CONTAINS(LCASE(STR(?fv0)), LCASE("clarin")))' in sparql
        assert 'foaf:name ?fv1 . FILTER(STR(?fv1) = "CLARIN ERIC")' in sparql
        assert "datacite:usesIdentifierScheme ?fv2" in sparql

    @patch(PATCH_TARGET)
    def test_filter_value_is_escaped(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        client.get('/api/v1/organisations?filter=name:a"b')
        assert 'FILTER(STR(?fv0) = "a\\"b")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_unsupported_filter(self, mock_query):
        response = client.get("/api/v1/organisations?filter=country:NL")
        assert response.status_code == 422
        assert response.json()["unsupported_filters"] == ["country"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_list_organisations_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/organisations").status_code == 502


class TestOrganisationEndpoint:

    @patch(PATCH_TARGET)
    def test_get_organisation(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/organisations/otf___org___clarin_eric")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        assert response.json()["@graph"][0]["local_identifier"] == "otf___org___clarin_eric"
        assert 'FILTER(STR(?s) = "otf:otf___org___clarin_eric")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_organisation_with_prefixed_id(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/organisations/otf:otf___org___clarin_eric")

        assert response.json()["@graph"][0]["local_identifier"] == "otf___org___clarin_eric"
        assert 'FILTER(STR(?s) = "otf:otf___org___clarin_eric")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_organisation_not_found(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        assert client.get("/api/v1/organisations/otf:unknown").status_code == 404

    @patch(PATCH_TARGET)
    def test_get_organisation_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/organisations/otf:x").status_code == 502
