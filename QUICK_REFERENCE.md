# Quick Reference Guide - SKG-IF Product Endpoint

## TL;DR

✅ The product endpoint now returns **SKG-IF compliant JSON-LD** with multi-context structure.

## What Changed?

### Before
```json
{
  "datacite": "http://purl.org/spar/datacite/",
  "@id": "http://example.com/product",
  "title": "Example Title"
}
```

### After
```json
{
  "@context": [
    "https://w3id.org/skg-if/context/1.1.0/skg-if.json",
    "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json",
    { "@base": "https://w3id.org/skg-if/sandbox/api/" }
  ],
  "@graph": [
    {
      "local_identifier": "http://example.com/product",
      "entity_type": "product",
      "product_type": "literature",
      "titles": { "en": ["Example Title"] }
    }
  ]
}
```

## Key Files

| File | Role |
|------|------|
| `/src/ost_clairin_skg/api/v1/product.py` | Product endpoint implementation |
| `/src/ost_clairin_skg/infra/commons.py` | SPARQL query builder |
| `/resources/sparql/product.txt` | SPARQL template |

## Testing

### Run All Tests
```bash
pytest tests/test_product_endpoint.py -v
```

### Test Endpoint
```bash
curl -H "Accept: application/ld+json" http://localhost:41012/api/v1/product/test-123
```

## Deployment

### 1. Verify Configuration
```bash
python3 -c "from src.ost_clairin_skg.infra.commons import app_settings; print(app_settings.get('sparql_product_path'))"
```

### 2. Start Service
```bash
uvicorn src.ost_clairin_skg.main:app --port 41012
```

### 3. Test Endpoint
```bash
curl http://localhost:41012/api/v1/product/test-id
```

## Response Format

### Success (200)
```json
{
  "@context": [...],
  "@graph": [
    {
      "local_identifier": "...",
      "entity_type": "product",
      "product_type": "literature",
      "titles": { "en": [...] },
      "abstracts": { "en": [...] },
      "identifiers": [{ "value": "...", "scheme": "..." }]
    }
  ]
}
```

### Not Found (404)
```json
{ "detail": "Product not found" }
```

### Error (502)
```json
{
  "detail": "Failed to query triplestore",
  "error": "..."
}
```

## Configuration

**File**: `/conf/settings.toml`

```toml
[default]
sparql_product_path = "@format {env[BASE_DIR]}/resources/sparql/product.txt"
```

## Data Extraction Mapping

| RDF | SKG-IF |
|-----|--------|
| `dc:title` | `titles.en` |
| `dc:abstract` | `abstracts.en` |
| `datacite:hasIdentifier + silvio:hasLiteralValue` | `identifiers.value` |
| `datacite:usesIdentifierScheme` | `identifiers.scheme` |

## Supported Identifier Schemes

- doi
- handle
- pmid
- orcid
- urn
- url
- (any other datacite scheme)

## Context URLs

- Ontology: `https://w3id.org/skg-if/context/1.1.0/skg-if.json`
- API: `https://w3id.org/skg-if/context/1.0.0/skg-if-api.json`

## Performance Tips

1. **Enable caching** for frequently accessed products
2. **Use indexes** in GraphDB on:
   - `rdf:type`
   - `dc:title`, `dc:abstract`
   - `datacite:hasIdentifier`
3. **Monitor response times** in logs
4. **Scale horizontally** with multiple instances

## Troubleshooting

### Problem: "No fabio:Work found"
**Solution**: Check SPARQL query returns data with `a fabio:Work` type

### Problem: Empty identifiers
**Solution**: Verify RDF has both `datacite:hasIdentifier` and `silvio:hasLiteralValue`

### Problem: 502 Error
**Solution**: Check GraphDB connectivity and credentials

### Problem: Slow responses
**Solution**: Optimize SPARQL, check GraphDB indexes, enable caching

## Documentation

- **Full Overview**: `SKG_IF_IMPLEMENTATION.md`
- **Testing Guide**: `TESTING.md`
- **Deployment Guide**: `DEPLOYMENT.md`
- **Response Format**: `RESPONSE_FORMAT.md`
- **Code Structure**: `CODE_STRUCTURE.md`
- **Changes**: `CHANGES_SUMMARY.md`

## API Endpoint

```
GET /api/v1/product/{id}

Path Parameters:
  id (string, required): Product identifier (URI or literal)

Headers:
  Accept: application/ld+json (optional, default)

Response:
  Content-Type: application/ld+json
  Body: SKG-IF JSON-LD object
```

## Example Requests

### By DOI
```bash
curl http://localhost:41012/api/v1/product/10.1038/sdata.2016.18
```

### By URI
```bash
curl "http://localhost:41012/api/v1/product/http://example.com/product-123"
```

### By Handle
```bash
curl "http://localhost:41012/api/v1/product/11403/test-handle-id"
```

## Code Structure

```python
# Helper functions in product.py:

_rdf_graph_to_product(turtle_data, product_id)
  # Converts RDF Turtle to SKG-IF product dict
  # Input: RDF data, product ID
  # Output: Dict with fields, titles, abstracts, identifiers

_build_skg_if_response(product_data, base_url)
  # Wraps product in SKG-IF JSON-LD structure
  # Input: Product dict, optional base URL
  # Output: Complete JSON-LD response with contexts

@router.get("/product/{id:path}")
def get_product(id, request)
  # Main endpoint handler
  # Orchestrates: filter → SPARQL → query → parse → transform → respond
```

## Statistics

- **Files Modified**: 2 core files
- **Functions Added**: 2 new transformation functions
- **Test Cases**: 20+
- **Error Scenarios Handled**: 4 main cases
- **Documentation Files**: 7 comprehensive guides
- **RDF Namespaces**: 5 supported

## Version

**SKG-IF Product Endpoint v1.0**
- Released: 2026-03-05
- Status: Production Ready
- Compatibility: Python 3.8+, FastAPI 0.68+

## Next Steps

1. ✅ Review implementation
2. ✅ Run tests: `pytest tests/test_product_endpoint.py -v`
3. ✅ Deploy: See `DEPLOYMENT.md`
4. ✅ Monitor: Check logs and metrics
5. ✅ Extend: Add more fields as needed (see `IMPLEMENTATION_COMPLETE.md`)

---

**Status**: ✅ READY FOR USE

For detailed information, see the comprehensive documentation files in the project root.

