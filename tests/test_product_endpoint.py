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
        assert product["product_type"] == "literature"

        # Check titles
        assert "titles" in product
        assert "en" in product["titles"]
        assert len(product["titles"]["en"]) > 0
        assert "FAIR" in product["titles"]["en"][0]

        # Check abstracts
        assert "abstracts" in product
        assert "en" in product["abstracts"]
        assert len(product["abstracts"]["en"]) > 0

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
    """Tests for the /api/v1/product/{id} endpoint."""

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_product_endpoint_success(self, mock_query):
        """Test successful product retrieval."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/product/test-123")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/ld+json"

        data = response.json()
        assert "@context" in data
        assert "@graph" in data
        assert len(data["@graph"]) > 0

        product = data["@graph"][0]
        assert product["local_identifier"] == "test-123"
        assert product["entity_type"] == "product"

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_product_endpoint_not_found(self, mock_query):
        """Test product not found response."""
        mock_query.return_value = ""

        response = client.get("/api/v1/product/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_product_endpoint_query_error(self, mock_query):
        """Test handling of triplestore query errors."""
        mock_query.side_effect = RuntimeError("Connection failed")

        response = client.get("/api/v1/product/test-123")

        assert response.status_code == 502
        data = response.json()
        assert "detail" in data
        assert "Failed to query triplestore" in data["detail"]

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_product_endpoint_content_type(self, mock_query):
        """Test that response has correct content type."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/product/test-123")

        assert response.headers["content-type"] == "application/ld+json"

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_product_endpoint_with_uri_id(self, mock_query):
        """Test endpoint with URI-style product ID."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        uri_id = "http://example.com/product-123"
        response = client.get(f"/api/v1/product/{uri_id}")

        assert response.status_code == 200
        data = response.json()
        product = data["@graph"][0]
        assert product["local_identifier"] == uri_id


class TestJSONLDCompliance:
    """Tests for JSON-LD format compliance."""

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_valid_json_ld_structure(self, mock_query):
        """Test that response is valid JSON-LD."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/product/test-123")
        data = response.json()

        # Must have @context
        assert "@context" in data

        # @context can be string, object, or array
        assert isinstance(data["@context"], list)

        # Array elements must be strings or objects
        for context in data["@context"]:
            assert isinstance(context, (str, dict))

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_graph_structure(self, mock_query):
        """Test @graph array structure."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/product/test-123")
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

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_required_skg_if_fields(self, mock_query):
        """Test that response includes required SKG-IF fields."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/product/test-123")
        data = response.json()
        product = data["@graph"][0]

        # Required fields
        assert "local_identifier" in product
        assert "entity_type" in product
        assert product["entity_type"] == "product"

    @patch('src.ost_clairin_skg.api.v1.product.query_triplestore')
    def test_language_tags(self, mock_query):
        """Test that text fields have proper language tags."""
        mock_query.return_value = SAMPLE_TURTLE_DATA

        response = client.get("/api/v1/product/test-123")
        data = response.json()
        product = data["@graph"][0]

        # Titles and abstracts should be language-tagged
        if "titles" in product:
            assert isinstance(product["titles"], dict)
            assert "en" in product["titles"]
            assert isinstance(product["titles"]["en"], list)

        if "abstracts" in product:
            assert isinstance(product["abstracts"], dict)
            assert "en" in product["abstracts"]
            assert isinstance(product["abstracts"]["en"], list)


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

