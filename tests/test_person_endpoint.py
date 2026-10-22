"""
Test suite for the person endpoints and SKG-IF JSON-LD response format.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ost_clairin_skg.main import app
from src.ost_clairin_skg.api.v1.persons import _rdf_graph_to_person, _rdf_graph_to_persons


client = TestClient(app)

PATCH_TARGET = 'src.ost_clairin_skg.api.v1.persons.query_triplestore'

SAMPLE_TURTLE_DATA = """
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix datacite: <http://purl.org/spar/datacite/> .
@prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .

<otf:otf___person___josiah_carberry> a foaf:Person ;
  foaf:name "Josiah Carberry" ;
  foaf:givenName "Josiah" ;
  foaf:familyName "Carberry" ;
  datacite:hasIdentifier _:id1 .

_:id1 datacite:usesIdentifierScheme datacite:orcid ;
  silvio:hasLiteralValue "0000-0002-1825-0097" .

<otf:otf___person___alice_brown> a foaf:Person ;
  foaf:name "Alice Brown" .
"""

# GraphDB returns prefix declarations even when a CONSTRUCT matches nothing
EMPTY_TURTLE_DATA = "@prefix foaf: <http://xmlns.com/foaf/0.1/> ."


class TestRDFToPersonTransformation:

    def test_rdf_graph_to_persons(self):
        persons = {p["local_identifier"]: p for p in _rdf_graph_to_persons(SAMPLE_TURTLE_DATA)}

        assert set(persons) == {"otf___person___josiah_carberry", "otf___person___alice_brown"}
        josiah = persons["otf___person___josiah_carberry"]
        assert josiah["entity_type"] == "person"
        assert josiah["name"] == "Josiah Carberry"
        assert josiah["given_name"] == "Josiah"
        assert josiah["family_name"] == "Carberry"
        assert josiah["identifiers"] == [{"value": "0000-0002-1825-0097", "scheme": "orcid"}]

        alice = persons["otf___person___alice_brown"]
        assert alice["name"] == "Alice Brown"
        assert "given_name" not in alice
        assert "identifiers" not in alice

    def test_rdf_graph_to_person_uses_requested_id(self):
        person = _rdf_graph_to_person(SAMPLE_TURTLE_DATA, "some-id")
        assert person["local_identifier"] == "some-id"


class TestPersonsEndpoint:

    @patch(PATCH_TARGET)
    def test_list_persons(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/persons?page=2&page_size=5")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        data = response.json()
        assert len(data["@graph"]) == 2
        assert data["meta"]["local_identifier"].endswith("/api/v1/persons?page=2&page_size=5")
        assert data["meta"]["next_page"]["local_identifier"].endswith("/api/v1/persons?page=3&page_size=5")

        sparql = mock_query.call_args[0][0]
        assert "LIMIT 5" in sparql
        assert "OFFSET 5" in sparql

    @patch(PATCH_TARGET)
    def test_list_persons_empty(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/persons")
        assert response.status_code == 200
        assert response.json()["@graph"] == []

    @patch(PATCH_TARGET)
    def test_filters_are_translated_to_sparql(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/persons?filter=cf.search.name:carb,given_name:Josiah,identifiers.scheme:orcid")

        assert response.status_code == 200
        sparql = mock_query.call_args[0][0]
        assert 'foaf:name ?fv0 . FILTER(CONTAINS(LCASE(STR(?fv0)), LCASE("carb")))' in sparql
        assert 'foaf:givenName ?fv1 . FILTER(STR(?fv1) = "Josiah")' in sparql
        assert "datacite:usesIdentifierScheme ?fv2" in sparql

    @patch(PATCH_TARGET)
    def test_filters_and_paging_apply_to_distinct_persons(self, mock_query):
        """Filters and LIMIT/OFFSET sit in the subquery selecting distinct persons, not on the result rows."""
        mock_query.return_value = EMPTY_TURTLE_DATA
        client.get("/api/v1/persons?filter=name:x&page=3&page_size=5")

        sparql = mock_query.call_args[0][0]
        subquery = sparql[sparql.index("SELECT DISTINCT ?s"):sparql.index("OPTIONAL")]
        assert 'FILTER(STR(?fv0) = "x")' in subquery
        assert "ORDER BY ?s" in subquery
        assert "LIMIT 5" in subquery and "OFFSET 10" in subquery
        assert "#FILTERS#" not in sparql and "#PAGINATION#" not in sparql

    def test_total_items_counts_filtered_persons(self, mock_count):
        with patch(PATCH_TARGET, return_value=EMPTY_TURTLE_DATA):
            response = client.get("/api/v1/persons?filter=name:x&page=3&page_size=5")

        assert response.json()["meta"]["part_of"]["total_items"] == 42
        count_sparql = mock_count["persons"].call_args[0][0]
        assert "SELECT (COUNT(DISTINCT ?s) AS ?total)" in count_sparql
        assert "?s a foaf:Person" in count_sparql
        assert 'FILTER(STR(?fv0) = "x")' in count_sparql
        assert "LIMIT" not in count_sparql and "OFFSET" not in count_sparql
        assert "PREFIX foaf:" in count_sparql

    def test_next_page_only_when_more_items(self, mock_count):
        mock_count["persons"].return_value = 10
        with patch(PATCH_TARGET, return_value=EMPTY_TURTLE_DATA):
            assert "next_page" in client.get("/api/v1/persons?page=1&page_size=5").json()["meta"]
            assert "next_page" not in client.get("/api/v1/persons?page=2&page_size=5").json()["meta"]
            assert "next_page" not in client.get("/api/v1/persons?page=3&page_size=5").json()["meta"]

    def test_count_query_error(self, mock_count):
        mock_count["persons"].side_effect = RuntimeError("boom")
        with patch(PATCH_TARGET, return_value=EMPTY_TURTLE_DATA):
            assert client.get("/api/v1/persons").status_code == 502

    @patch(PATCH_TARGET)
    def test_filter_value_is_escaped(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        client.get('/api/v1/persons?filter=name:a"b')
        assert 'FILTER(STR(?fv0) = "a\\"b")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_unsupported_filter(self, mock_query):
        response = client.get("/api/v1/persons?filter=affiliations.role:x")
        assert response.status_code == 422
        assert response.json()["unsupported_filters"] == ["affiliations.role"]
        mock_query.assert_not_called()

    @patch(PATCH_TARGET)
    def test_list_persons_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/persons").status_code == 502


class TestPersonEndpoint:

    @patch(PATCH_TARGET)
    def test_get_person(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/persons/otf___person___josiah_carberry")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"
        graph = response.json()["@graph"]
        assert graph[0]["local_identifier"] == "otf___person___josiah_carberry"
        assert 'FILTER(STR(?s) = "otf:otf___person___josiah_carberry")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_person_with_prefixed_id(self, mock_query):
        mock_query.return_value = SAMPLE_TURTLE_DATA
        response = client.get("/api/v1/persons/otf:otf___person___josiah_carberry")

        assert response.json()["@graph"][0]["local_identifier"] == "otf___person___josiah_carberry"
        assert 'FILTER(STR(?s) = "otf:otf___person___josiah_carberry")' in mock_query.call_args[0][0]

    @patch(PATCH_TARGET)
    def test_get_person_not_found(self, mock_query):
        mock_query.return_value = EMPTY_TURTLE_DATA
        response = client.get("/api/v1/persons/otf:unknown")
        assert response.status_code == 404

    @patch(PATCH_TARGET)
    def test_get_person_query_error(self, mock_query):
        mock_query.side_effect = RuntimeError("boom")
        assert client.get("/api/v1/persons/otf:x").status_code == 502
