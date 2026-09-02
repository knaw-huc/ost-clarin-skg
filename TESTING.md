# Testing Guide for SKG-IF Product Endpoint

## Overview

This document provides guidance on testing the SKG-IF JSON-LD product endpoint implementation.

## Test Suite

The test suite is located at: `/tests/test_product_endpoint.py`

### Test Categories

#### 1. RDF to Product Transformation Tests
- **`test_rdf_graph_to_product_basic`** - Validates basic transformation from RDF to product dictionary
- **`test_identifiers_extraction`** - Ensures identifiers are properly extracted and formatted
- **`test_missing_optional_fields`** - Tests handling of products with missing optional fields
- **`test_no_fabio_work_raises_error`** - Verifies error handling when RDF lacks fabio:Work

#### 2. SKG-IF Response Builder Tests
- **`test_build_skg_if_response_structure`** - Validates @context and @graph structure
- **`test_build_skg_if_response_custom_base_url`** - Tests custom base URL configuration
- **`test_build_skg_if_response_default_base_url`** - Tests default base URL

#### 3. Product Endpoint Tests
- **`test_product_endpoint_success`** - Tests successful product retrieval
- **`test_product_endpoint_not_found`** - Tests 404 response
- **`test_product_endpoint_query_error`** - Tests 502 error handling
- **`test_product_endpoint_content_type`** - Verifies application/ld+json content type
- **`test_product_endpoint_with_uri_id`** - Tests endpoint with URI-style product IDs

#### 4. JSON-LD Compliance Tests
- **`test_valid_json_ld_structure`** - Validates JSON-LD structure compliance
- **`test_graph_structure`** - Tests @graph array structure
- **`test_required_skg_if_fields`** - Ensures required SKG-IF fields are present
- **`test_language_tags`** - Verifies proper language tagging

#### 5. Identifier Handling Tests
- **`test_identifier_scheme_normalization`** - Tests scheme name normalization
- **`test_missing_identifier_value`** - Tests handling of incomplete identifiers

## Running the Tests

### Prerequisites

Install test dependencies:

```bash
pip install pytest pytest-cov
```

Or using uv:

```bash
uv pip install pytest pytest-cov
```

### Run All Tests

```bash
cd /Users/akmi/dev/work/huc/ost-clarin-skg
pytest tests/test_product_endpoint.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_product_endpoint.py::TestRDFToProductTransformation -v
```

### Run Specific Test

```bash
pytest tests/test_product_endpoint.py::TestRDFToProductTransformation::test_identifiers_extraction -v
```

### Run with Coverage Report

```bash
pytest tests/test_product_endpoint.py --cov=src/ost_clairin_skg/api/v1/product --cov-report=html
```

### Run with Output

```bash
pytest tests/test_product_endpoint.py -v -s
```

## Manual Testing

### Using cURL

#### Test with DOI identifier

```bash
curl -H "Accept: application/ld+json" \
  http://localhost:41012/api/v1/product/10.1038/sdata.2016.18 | python3 -m json.tool
```

#### Test with URI identifier

```bash
curl -H "Accept: application/ld+json" \
  "http://localhost:41012/api/v1/product/http://example.com/product-123" | python3 -m json.tool
```

#### Test error handling (nonexistent product)

```bash
curl -H "Accept: application/ld+json" \
  http://localhost:41012/api/v1/product/nonexistent-product-id
```

### Using Python

```python
import requests
import json

# Test successful retrieval
response = requests.get(
    "http://localhost:41012/api/v1/product/test-123",
    headers={"Accept": "application/ld+json"}
)

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('content-type')}")
print(json.dumps(response.json(), indent=2))

# Validate response structure
data = response.json()
assert "@context" in data
assert "@graph" in data
assert len(data["@graph"]) > 0

product = data["@graph"][0]
assert product["entity_type"] == "product"
assert "local_identifier" in product

print("✓ Response validation passed!")
```

## Integration Testing

### Test with Real Triplestore

1. Start the application:
```bash
uvicorn src.ost_clairin_skg.main:app --port 41012 --reload
```

2. Query an actual product from the triplestore:
```bash
curl -H "Accept: application/ld+json" \
  "http://localhost:41012/api/v1/product/oai:ortolang:832add7d-1789-4bbb-813f-da4ec98f8d2d"
```

3. Validate the response contains:
- Valid JSON-LD structure
- SKG-IF contexts
- Product data fields
- Proper content type

### Validate Context URLs

Ensure external context URLs are accessible:

```bash
# SKG-IF Ontology Context
curl -s https://w3id.org/skg-if/context/1.1.0/skg-if.json | python3 -m json.tool | head -30

# SKG-IF API Context
curl -s https://w3id.org/skg-if/context/1.0.0/skg-if-api.json | python3 -m json.tool | head -30
```

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Print SPARQL Query

The endpoint logs the SPARQL query at DEBUG level:

```bash
# Run with debug logging
LOGLEVEL=DEBUG uvicorn src.ost_clairin_skg.main:app --port 41012
```

### Inspect RDF Data

Check the intermediate Turtle RDF data:

```python
from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore

filter_clause = commons.build_filter_clause("test-product")
sparql = commons.build_product_sparql(filter_clause)

# Query and print raw Turtle
turtle_data = query_triplestore(sparql)
print(turtle_data)
```

### Parse RDF Manually

```python
import rdflib

turtle = """
@prefix fabio: <http://purl.org/spar/fabio/> .
<http://example.com/product> a fabio:Work .
"""

g = rdflib.Graph()
g.parse(data=turtle, format="turtle")

# List all triples
for s, p, o in g:
    print(f"{s} -> {p} -> {o}")
```

## Performance Testing

### Load Testing

Use Apache Bench or similar:

```bash
# 1000 requests with 10 concurrent
ab -n 1000 -c 10 http://localhost:41012/api/v1/product/test-123

# With custom headers
ab -n 1000 -c 10 -H "Accept: application/ld+json" \
  http://localhost:41012/api/v1/product/test-123
```

### Response Time Measurement

```python
import time
import requests

start = time.time()
response = requests.get("http://localhost:41012/api/v1/product/test-123")
duration = time.time() - start

print(f"Response time: {duration:.3f}s")
print(f"Status: {response.status_code}")
```

## Validation Checklist

Before deployment, ensure:

- [ ] All unit tests pass
- [ ] Integration tests pass with real triplestore
- [ ] Response has correct content type (application/ld+json)
- [ ] @context array has 3 elements
- [ ] @graph array contains products
- [ ] All products have required fields
- [ ] Identifiers are properly formatted
- [ ] Language tags are present and correct
- [ ] Error responses have appropriate status codes
- [ ] Logging works correctly
- [ ] Performance is acceptable
- [ ] External contexts are accessible

## Common Issues and Solutions

### Issue: "No fabio:Work found in RDF data"
**Solution**: Ensure the SPARQL query returns data with `a fabio:Work` type

### Issue: Empty identifiers
**Solution**: Check that RDF has both `datacite:hasIdentifier` and `silvio:hasLiteralValue`

### Issue: Missing titles/abstracts
**Solution**: Verify RDF includes `dc:title` and `dc:abstract` properties

### Issue: Wrong content type
**Solution**: Ensure `media_type="application/ld+json"` in JSONResponse

### Issue: Invalid JSON-LD context URLs
**Solution**: Verify external context URLs are accessible from your network

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
test:
  script:
    - pytest tests/test_product_endpoint.py -v --cov
    - pytest tests/test_product_endpoint.py --cov-report=term-missing
```

## References

- JSON-LD Specification: https://www.w3.org/TR/json-ld11/
- SKG-IF Specification: https://w3id.org/skg-if/
- pytest Documentation: https://docs.pytest.org/
- RDFLib Documentation: https://rdflib.readthedocs.io/

