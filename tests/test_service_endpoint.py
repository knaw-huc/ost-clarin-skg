"""
Test suite for the service endpoints (SKG-IF service extension).
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ost_clairin_skg.main import app
from src.ost_clairin_skg.api.v1.services import _rdf_graph_to_service, _rdf_graph_to_services


client = TestClient(app)

PATCH_TARGET = 'src.ost_clairin_skg.api.v1.services.query_triplestore'

SAMPLE_TURTLE_DATA = """
@prefix srv: <https://w3id.org/skg-if/extension/srv/ontology/> .
@prefix dc: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix fabio: <http://purl.org/spar/fabio/> .

<otf:service___tei2tcf> a srv:Service ;
  foaf:name "Converter TEI2TCF" ;
  dc:description "{code:und}Converts TEI files to TCF"@und ;
  srv:hasHostingOrganisation <otf:otf___org___ims> ;
  srv:isPartOfResearchInfrastructure <otf:otf___org___clarin_eric> ;
  dc:relation <otf:otf___org___ims>, <otf:otf___org___clarin_eric> ;
  srv:hasVenue <otf:otf___venue___vlo> .

<otf:otf___org___ims> a foaf:Organization, srv:HostingOrganisation ;
  foaf:name "IMS, University of Stuttgart" .

<otf:otf___org___clarin_eric> a foaf:Organization, srv:ResearchInfrastructure ;
  foaf:name "CLARIN ERIC" .

<otf:otf___venue___vlo> a fabio:ExpressionCollection, srv:Portal ;
  foaf:name "Virtual Language Observatory" ;
  foaf:homepage <https://vlo.clarin.eu/> .

<otf:service___bare> a srv:Service .
"""

# GraphDB returns prefix declarations even when a CONSTRUCT matches nothing
EMPTY_TURTLE_DATA = "@prefix srv: <https://w3id.org/skg-if/extension/srv/ontology/> ."


class TestRDFToServiceTransformation:

    def test_rdf_graph_to_services(self):
        services = {s["local_identifier"]: s for s in _rdf_graph_to_services(SAMPLE_TURTLE_DATA)}

        assert set(services) == {"service___tei2tcf", "service___bare"}
        tei = services["service___tei2tcf"]
        assert tei["entity_type"] == "srv_service"
        assert tei["name"] == "Converter TEI2TCF"
        assert tei["srv_descriptions"] == {"none": ["Converts TEI files to TCF"]}
        assert tei["srv_has_hosting_organisation"] == [{
            "local_identifier": "otf___org___ims",
            "entity_type": "organisation",
            "name": "IMS, University of Stuttgart",
            "types": ["srv_hosting_organisation"],
        }]
        assert [o["name"] for o in tei["srv_has_research_infrastructure"]] == ["CLARIN ERIC"]
        assert tei["srv_has_research_infrastructure"][0]["types"] == ["srv_research_infrastructure"]
        assert {o["local_identifier"] for o in tei["relevant_organisations"]} == {"otf___org___ims", "otf___org___clarin_eric"}
        assert tei["srv_venues"] == [{
            "local_identifier": "otf___venue___vlo",
            "entity_type": "venue",
            "name": "Virtual Language Observatory",
            "website": "https://vlo.clarin.eu/",
            "types": ["srv_portal"],
        }]

        assert services["service___bare"] == {"local_identifier": "service___bare", "entity_type": "srv_service"}

    def test_two_letter_language_tag_is_kept(self):
        turtle = """
        @prefix srv: <https://w3id.org/skg-if/extension/srv/ontology/> .
        @prefix dc: <http://purl.org/dc/terms/> .
        <otf:service___x> a srv:Service ; dc:description "{code:en}A parser"@en .
        """
        assert _rdf_graph_to_service(turtle, "x")["srv_descriptions"] == {"en": ["A parser"]}


class TestServicesEndpoint:

    @patch(PATCH_TARGET)
    def test_list_services(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/services?page=2&page_size=5")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        data = response.json()
        assert data["@context"][3] == "https://w3id.org/skg-if/extension/srv/context/skg-if.json"
        assert len(data["@graph"]) == 2
        assert data["meta"]["local_identifier"].endswith("/api/v1/services?page=2&page_size=5")

        sparql = mock_query.call_args[0][0]
        subquery = sparql[sparql.index("SELECT DISTINCT ?s"):sparql.index("UNION")]
        assert "LIMIT 5" in subquery and "OFFSET 5" in subquery

    @patch(PATCH_TARGET)
    def test_list_services_empty(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/services")
        assert response.status_code == 200
        assert response.json()["@graph"] == []

    @patch(PATCH_TARGET)
    def test_filters_are_translated_to_sparql(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get(
            "/api/v1/services?filter=cf.search.org_name:stuttgart,"
            "srv_has_research_infrastructure.name:CLARIN ERIC,relevant_organisations.identifiers.scheme:ror"
        )

        assert response.status_code == 200
        sparql = mock_query.call_args[0][0]
        assert ('?s (dc:relation|srv:hasHostingOrganisation|srv:isPartOfResearchInfrastructure)/foaf:name ?fv0 . '
                'FILTER(CONTAINS(LCASE(STR(?fv0)), LCASE("stuttgart")))') in sparql
        assert '?s srv:isPartOfResearchInfrastructure/foaf:name ?fv1 . FILTER(STR(?fv1) = "CLARIN ERIC")' in sparql
        assert "?s dc:relation/datacite:hasIdentifier/datacite:usesIdentifierScheme ?fv2" in sparql

    @patch(PATCH_TARGET)
    def test_unsupported_filter(self, mock_query):
        response = client.get("/api/v1/services?filter=country:CZ")
        assert response.status_code == 422
        assert response.json()["unsupported_filters"] == ["country"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_list_services_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/services").status_code == 502


class TestServiceEndpoint:

    @patch(PATCH_TARGET)
    def test_get_service(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/services/service___tei2tcf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        assert response.json()["@graph"][0]["local_identifier"] == "service___tei2tcf"
        assert 'FILTER(STR(?s) = "otf:service___tei2tcf")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_service_not_found(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        assert client.get("/api/v1/services/service___unknown").status_code == 404

    @patch(PATCH_TARGET)
    def test_get_service_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/services/service___x").status_code == 502
