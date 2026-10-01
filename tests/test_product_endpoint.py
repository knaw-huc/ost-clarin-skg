"""
Test suite for the product endpoint and SKG-IF JSON-LD response format.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import json

from src.ost_clairin_skg.main import app
from src.ost_clairin_skg.api.v1.products import _rdf_graph_to_product, _build_skg_if_response


client = TestClient(app)


# Sample Turtle RDF data for testing
SAMPLE_TURTLE_DATA = """
@prefix datacite: <http://purl.org/spar/datacite/> .
@prefix dc: <http://purl.org/dc/terms/> .
@prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .
@prefix fabio: <http://purl.org/spar/fabio/> .

<http://localhost:8080/cmd2rdf/graph/test-product-123>
  a fabio:Work ;
  dc:title "The FAIR Guiding Principles for scientific data management and stewardship" ;
  dc:abstract "There is an urgent need to improve the infrastructure supporting the reuse of scholarly data." ;
  datacite:hasIdentifier _:id1, _:id2 .

_:id1
  datacite:usesIdentifierScheme datacite:doi ;
  silvio:hasLiteralValue "10.1038/sdata.2016.18" .

_:id2
  datacite:usesIdentifierScheme datacite:pmid ;
  silvio:hasLiteralValue "26978244" .
"""


class TestRDFToProductTransformation:
    """Tests for RDF to SKG-IF product transformation."""

    def test_rdf_graph_to_product_basic(self):
        """Test basic transformation from RDF to product dictionary."""
        product = _rdf_graph_to_product(SAMPLE_TURTLE_DATA, "test-product-123")

        # Check basic fields
        assert product["local_identifier"] == "test-product-123"
        assert product["entity_type"] == "product"
        # Only fabio:Work, no more specific class
        assert product["product_type"] == "other"

        # Check titles
        assert "titles" in product
        assert "none" in product["titles"]
        assert len(product["titles"]["none"]) > 0
        assert "FAIR" in product["titles"]["none"][0]

        # Check abstracts
        assert "abstracts" in product
        assert "none" in product["abstracts"]
        assert len(product["abstracts"]["none"]) > 0

        # Check identifiers
        assert "identifiers" in product
        assert len(product["identifiers"]) == 2

    def test_identifiers_extraction(self):
        """Test proper extraction and formatting of identifiers."""
        product = _rdf_graph_to_product(SAMPLE_TURTLE_DATA, "test-id")

        identifiers = product["identifiers"]

        # Should have both DOI and PMID
        schemes = [id_obj["scheme"] for id_obj in identifiers]
        assert "doi" in schemes
        assert "pmid" in schemes

        # Check DOI identifier
        doi_id = next((id_obj for id_obj in identifiers if id_obj["scheme"] == "doi"), None)
        assert doi_id is not None
        assert doi_id["value"] == "10.1038/sdata.2016.18"

        # Check PMID identifier
        pmid_id = next((id_obj for id_obj in identifiers if id_obj["scheme"] == "pmid"), None)
        assert pmid_id is not None
        assert pmid_id["value"] == "26978244"

    def test_missing_optional_fields(self):
        """Test handling of missing optional fields."""
        minimal_turtle = """
        @prefix fabio: <http://purl.org/spar/fabio/> .
        <http://example.com/product>
          a fabio:Work .
        """

        product = _rdf_graph_to_product(minimal_turtle, "minimal-product")

        # Required fields should be present
        assert product["local_identifier"] == "minimal-product"
        assert product["entity_type"] == "product"

        # Optional fields should not be present
        assert "titles" not in product
        assert "abstracts" not in product
        assert "identifiers" not in product

    @pytest.mark.parametrize("fabio_class, expected", [
        ("Dataset", "research data"),
        ("Software", "research software"),
        ("JournalArticle", "literature"),
    ])
    def test_product_type_from_fabio_class(self, fabio_class, expected):
        turtle = f"""
        @prefix fabio: <http://purl.org/spar/fabio/> .
        <http://example.com/product> a fabio:Work, fabio:{fabio_class} .
        """
        assert _rdf_graph_to_product(turtle, "p")["product_type"] == expected

    def test_topics_extraction(self):
        """Topics are terms reached via bido:holdsBibliometricDataInTime/bido:withBibliometricData."""
        turtle = """
        @prefix fabio: <http://purl.org/spar/fabio/> .
        @prefix bido: <http://purl.org/spar/bido/> .
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        <http://example.com/product> a fabio:Work ;
          bido:holdsBibliometricDataInTime _:bd1, _:bd2 .
        _:bd1 a bido:BibliometricDataInTime ; bido:withBibliometricData <otf:otf___topic___tcof> .
        _:bd2 a bido:BibliometricDataInTime ; bido:withBibliometricData <http://example.com/not-a-term> .
        <otf:otf___topic___tcof> a fabio:SubjectTerm ; skos:prefLabel "tcof" .
        """
        product = _rdf_graph_to_product(turtle, "p")

        assert product["topics"] == [{"term": {
            "local_identifier": "otf___topic___tcof",
            "entity_type": "topic",
            "labels": {"none": "tcof"},
        }}]
        assert "topics" not in _rdf_graph_to_product(SAMPLE_TURTLE_DATA, "p")

    def test_no_fabio_work_raises_error(self):
        """Test that missing fabio:Work raises appropriate error."""
        invalid_turtle = """
        @prefix dc: <http://purl.org/dc/terms/> .
        <http://example.com/product>
          dc:title "Test" .
        """

        with pytest.raises(ValueError, match="No fabio:Work found"):
            _rdf_graph_to_product(invalid_turtle, "invalid-product")


class TestSKGIFResponseBuilder:
    """Tests for SKG-IF JSON-LD response building."""

    def test_build_skg_if_response_structure(self):
        """Test that response has correct JSON-LD structure."""
        product_data = {
            "local_identifier": "test-123",
            "entity_type": "product",
            "product_type": "literature"
        }

        response = _build_skg_if_response(product_data)

        # Check top-level structure
        assert "@context" in response
        assert "@graph" in response

        # Check @context is array with 3 elements
        assert isinstance(response["@context"], list)
        assert len(response["@context"]) == 3

        # Check @context elements
        assert response["@context"][0] == "https://w3id.org/skg-if/context/1.1.0/skg-if.json"
        assert response["@context"][1] == "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json"
        assert isinstance(response["@context"][2], dict)
        assert "@base" in response["@context"][2]

        # Check @graph contains product
        assert isinstance(response["@graph"], list)
        assert len(response["@graph"]) == 1
        assert response["@graph"][0] == product_data

    def test_build_skg_if_response_custom_base_url(self):
        """Test custom base URL in context."""
        product_data = {"local_identifier": "test"}
        custom_base = "https://custom.example.com/"

        response = _build_skg_if_response(product_data, base_url=custom_base)

        assert response["@context"][2]["@base"] == custom_base

    def test_build_skg_if_response_default_base_url(self):
        """Test default base URL."""
        product_data = {"local_identifier": "test"}

        response = _build_skg_if_response(product_data)

        assert response["@context"][2]["@base"] == "https://w3id.org/skg-if/sandbox/api/"


class TestProductEndpoint:
    """Tests for the /api/v1/products/{id} endpoint."""

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_endpoint_success(self, mock_query):
        """Test successful product retrieval."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/products/test-123")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"

        data = response.json()
        assert "@context" in data
        assert "@graph" in data
        assert len(data["@graph"]) > 0

        product = data["@graph"][0]
        assert product["local_identifier"] == "test-123"
        assert product["entity_type"] == "product"

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_endpoint_not_found(self, mock_query):
        """Test product not found response."""
        mock_query.return_value = ""

        response = client.get("/api/v1/products/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_endpoint_query_error(self, mock_query):
        """Test handling of triplestore query errors."""
        mock_query.side_effect = RuntimeError("Connection failed")

        response = client.get("/api/v1/products/test-123")

        assert response.status_code == 502
        data = response.json()
        assert "detail" in data
        assert "Failed to query triplestore" in data["detail"]

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_endpoint_content_type(self, mock_query):
        """Test that response has correct content type."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/products/test-123")

        assert response.headers["content-type"] == "application/ld+json"

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_endpoint_with_uri_id(self, mock_query):
        """Test endpoint with URI-style product ID."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        uri_id = "http://example.com/product-123"
        response = client.get(f"/api/v1/products/{uri_id}")

        assert response.status_code == 200
        data = response.json()
        product = data["@graph"][0]
        assert product["local_identifier"] == uri_id
        assert f"VALUES ?s {{ <{uri_id}> }}" in mock_query.call_args[0][0]

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_endpoint_with_invalid_uri_id(self, mock_query):
        """A URI id with characters not allowed in an IRI is compared as a string instead of injected as <...>."""
        from rdflib.plugins.sparql import parser
        mock_query.return_value = ""

        response = client.get("/api/v1/products/http%3A%2F%2Fx%3E%20%7D%20%23")

        assert response.status_code == 404
        sparql = mock_query.call_args[0][0]
        assert "VALUES ?s" not in sparql
        assert 'FILTER(STR(?s) = "http://x> } #"' in sparql
        parser.parseQuery(sparql)

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_endpoint_no_match_returns_404(self, mock_query):
        """GraphDB returns only prefix declarations when nothing matches."""
        mock_query.return_value = "@prefix fabio: <http://purl.org/spar/fabio/> ."

        response = client.get("/api/v1/products/otf:unknown")

        assert response.status_code == 404

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_endpoint_matches_local_id_or_identifier(self, mock_query):
        """A non-URI id matches the subject IRI or an identifier value, with no leftover template filter."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        client.get("/api/v1/products/10.1038/sdata.2016.18")

        sparql = mock_query.call_args[0][0]
        assert 'FILTER(STR(?s) = "otf:10.1038/sdata.2016.18" || EXISTS' in sparql
        assert 'FILTER(STR(?fpid) = "10.1038/sdata.2016.18")' in sparql
        assert "Robin1_Lem" not in sparql

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_product_type_filter(self, mock_query):
        mock_query.return_value = ""

        client.get("/api/v1/products?filter=product_type:research software")
        assert "FILTER EXISTS { ?s a ?ftype . FILTER(?ftype IN (<http://purl.org/spar/fabio/Software>)) }" in mock_query.call_args[0][0]

        client.get("/api/v1/products?filter=product_type:other")
        sparql = mock_query.call_args[0][0]
        assert "FILTER NOT EXISTS { ?s a ?ftype . FILTER(?ftype IN (<http://purl.org/spar/fabio/Dataset>" in sparql
        assert "<http://purl.org/spar/fabio/Software>" in sparql

    @pytest.mark.parametrize("key", ["cf.search.title_abstract", "cf.cites"])
    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_filter_value_is_escaped(self, mock_query, key):
        """Quotes and backslashes in a filter value end up inside a valid SPARQL string literal."""
        from rdflib.plugins.sparql import parser
        mock_query.return_value = ""

        response = client.get("/api/v1/products", params={"filter": f'{key}:a"b\\c'})

        assert response.status_code == 200
        sparql = mock_query.call_args[0][0]
        assert '"a\\"b\\\\c"' in sparql
        parser.parseQuery(sparql)

    @pytest.mark.parametrize("key", ["product_type", "cf.contributions_aff_ror", "cf.cites", "cf.cited_by"])
    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_filter_invalid_iri_rejected(self, mock_query, key):
        """A URI filter value with characters not allowed in an IRI is rejected before querying."""
        response = client.get("/api/v1/products", params={"filter": f"{key}:http://x> }} #"})

        assert response.status_code == 422
        assert response.json()["invalid_iris"] == ["http://x> } #"]
        mock_query.assert_not_called()

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_products_list_strips_otf_prefix(self, mock_query):
        """The otf: scheme prefix of subject IRIs is not exposed in local identifiers."""
        mock_query.return_value = """
        @prefix fabio: <http://purl.org/spar/fabio/> .
        <otf:otf___product___x> a fabio:Work .
        """

        response = client.get("/api/v1/products")

        assert response.json()["@graph"][0]["local_identifier"] == "otf___product___x"


class TestJSONLDCompliance:
    """Tests for JSON-LD format compliance."""

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_valid_json_ld_structure(self, mock_query):
        """Test that response is valid JSON-LD."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/products/test-123")
        data = response.json()

        # Must have @context
        assert "@context" in data

        # @context can be string, object, or array
        assert isinstance(data["@context"], list)

        # Array elements must be strings or objects
        for context in data["@context"]:
            assert isinstance(context, (str, dict))

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_graph_structure(self, mock_query):
        """Test @graph array structure."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/products/test-123")
        data = response.json()

        # Should have @graph as array
        assert "@graph" in data
        assert isinstance(data["@graph"], list)
        assert len(data["@graph"]) > 0

        # Each element should be object with @id or local_identifier
        for item in data["@graph"]:
            assert isinstance(item, dict)
            # Should have either @id or local_identifier
            assert "local_identifier" in item or "@id" in item

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_required_skg_if_fields(self, mock_query):
        """Test that response includes required SKG-IF fields."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/products/test-123")
        data = response.json()
        product = data["@graph"][0]

        # Required fields
        assert "local_identifier" in product
        assert "entity_type" in product
        assert product["entity_type"] == "product"

    @patch('src.ost_clairin_skg.api.v1.products.query_triplestore')
    def test_language_tags(self, mock_query):
        """Test that text fields have proper language tags."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/products/test-123")
        data = response.json()
        product = data["@graph"][0]

        # Titles and abstracts should be language-tagged
        if "titles" in product:
            assert isinstance(product["titles"], dict)
            assert "none" in product["titles"]
            assert isinstance(product["titles"]["none"], list)

        if "abstracts" in product:
            assert isinstance(product["abstracts"], dict)
            assert "none" in product["abstracts"]
            assert isinstance(product["abstracts"]["none"], list)


class TestIdentifierHandling:
    """Tests for identifier extraction and formatting."""

    def test_identifier_scheme_normalization(self):
        """Test that identifier schemes are properly normalized."""
        turtle = """
        @prefix datacite: <http://purl.org/spar/datacite/> .
        @prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .
        @prefix fabio: <http://purl.org/spar/fabio/> .
        
        <http://example.com/p1> a fabio:Work ;
          datacite:hasIdentifier _:id1, _:id2, _:id3 .
        
        _:id1 datacite:usesIdentifierScheme datacite:doi ;
             silvio:hasLiteralValue "10.1234/test" .
        _:id2 datacite:usesIdentifierScheme datacite:handle ;
             silvio:hasLiteralValue "11403/test" .
        _:id3 datacite:usesIdentifierScheme datacite:pmid ;
             silvio:hasLiteralValue "12345678" .
        """

        product = _rdf_graph_to_product(turtle, "test")
        identifiers = product["identifiers"]

        # All schemes should be lowercase short names
        schemes = [id_obj["scheme"] for id_obj in identifiers]
        assert all(isinstance(s, str) and s.islower() for s in schemes)

        # Should have expected schemes
        assert "doi" in schemes
        assert "handle" in schemes
        assert "pmid" in schemes

    def test_missing_identifier_value(self):
        """Test handling of identifiers without values."""
        turtle = """
        @prefix datacite: <http://purl.org/spar/datacite/> .
        @prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .
        @prefix fabio: <http://purl.org/spar/fabio/> .
        
        <http://example.com/p1> a fabio:Work ;
          datacite:hasIdentifier _:id1, _:id2 .
        
        _:id1 datacite:usesIdentifierScheme datacite:doi ;
             silvio:hasLiteralValue "10.1234/valid" .
        _:id2 datacite:usesIdentifierScheme datacite:doi .
        """

        product = _rdf_graph_to_product(turtle, "test")
        identifiers = product["identifiers"]

        # Should only include identifiers with values
        assert len(identifiers) == 1
        assert identifiers[0]["value"] == "10.1234/valid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

