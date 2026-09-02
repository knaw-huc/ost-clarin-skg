# `/products` Endpoint Documentation

## Overview

The `/products` endpoint returns a paginated list of products in SKG-IF compliant JSON-LD format with proper pagination metadata.

## Endpoint

```
GET /api/v1/products
```

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number (1-based, minimum: 1) |
| `limit` | integer | No | 10 | Number of items per page (range: 1-100) |

## Response Format

### Success (200 OK)

```json
{
  "@context": [
    "https://w3id.org/skg-if/context/1.1.0/skg-if.json",
    "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json",
    {
      "@base": "http://localhost:41012/"
    }
  ],
  "meta": {
    "local_identifier": "http://localhost:41012/api/v1/products?page=1",
    "entity_type": "search_result_page",
    "next_page": {
      "local_identifier": "http://localhost:41012/api/v1/products?page=2",
      "entity_type": "search_result_page"
    },
    "part_of": {
      "local_identifier": "http://localhost:41012/api/v1/products",
      "entity_type": "search_result"
    }
  },
  "@graph": [
    {
      "local_identifier": "http://example.com/product-1",
      "entity_type": "product",
      "product_type": "literature",
      "titles": {
        "en": ["Product Title"]
      },
      "abstracts": {
        "en": ["Product abstract"]
      },
      "identifiers": [
        {
          "value": "10.1038/example",
          "scheme": "doi"
        }
      ]
    },
    {
      "local_identifier": "http://example.com/product-2",
      "entity_type": "product",
      "product_type": "literature"
    }
  ]
}
```

### Error Responses

#### 502 Bad Gateway (Triplestore Query Failed)
```json
{
  "detail": "Failed to query triplestore",
  "error": "..."
}
```

#### 502 Bad Gateway (Transformation Failed)
```json
{
  "detail": "Failed to convert triplestore response to JSON-LD",
  "error": "..."
}
```

## Response Headers

```
Content-Type: application/ld+json
```

## SKG-IF Compliance

The response follows the SKG-IF specification for search results:

### Multi-Context Structure
- **SKG-IF Ontology** (1.1.0): `https://w3id.org/skg-if/context/1.1.0/skg-if.json`
- **SKG-IF API** (1.0.0): `https://w3id.org/skg-if/context/1.0.0/skg-if-api.json`
- **Custom Base**: Derived from request base URL

### Metadata Object
The `meta` object provides pagination information:

| Field | Type | Description |
|-------|------|-------------|
| `local_identifier` | string | Current page URL |
| `entity_type` | string | Always "search_result_page" |
| `next_page` | object | Reference to next page |
| `part_of` | object | Reference to the entire search result |

### Graph Array
The `@graph` array contains the list of products. Each product includes:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `local_identifier` | string | Yes | Product URI |
| `entity_type` | string | Yes | Always "product" |
| `product_type` | string | Yes | Type of product (e.g., "literature") |
| `titles` | object | No | Language-keyed titles |
| `abstracts` | object | No | Language-keyed abstracts |
| `identifiers` | array | No | Array of identifier objects |

## Usage Examples

### Basic Request (Default Pagination)
```bash
curl -H "Accept: application/ld+json" \
  http://localhost:41012/api/v1/products
```

Returns first 10 products (page 1, limit 10).

### Custom Page Size
```bash
curl -H "Accept: application/ld+json" \
  "http://localhost:41012/api/v1/products?limit=20"
```

Returns first 20 products.

### Navigate to Specific Page
```bash
curl -H "Accept: application/ld+json" \
  "http://localhost:41012/api/v1/products?page=3&limit=15"
```

Returns products 31-45 (page 3 with 15 items per page).

### Python Example
```python
import requests

response = requests.get(
    "http://localhost:41012/api/v1/products",
    params={"page": 1, "limit": 20},
    headers={"Accept": "application/ld+json"}
)

data = response.json()

# Access metadata
current_page = data["meta"]["local_identifier"]
next_page = data["meta"]["next_page"]["local_identifier"]

# Access products
products = data["@graph"]
for product in products:
    print(f"Product: {product['local_identifier']}")
    if "titles" in product:
        print(f"  Title: {product['titles']['en'][0]}")
```

## Query parameter syntax examples

Below are some example query parameter usages for the `/products` endpoint. These demonstrate how to combine filters, use paging and override the page size.

```
/products?filter=product_type:literature,identifiers.id:10.1038/sdata.2016.18
/products?filter=cf.search.title:ocean
/products?filter=cf.contributions_orcid:0000-0002-1825-0097
/products?filter=cf.search.title:ocean&page=1&page_size=5
```

Notes:
- `filter` is a comma-separated list of `name:value` pairs. Server-side operator is AND between pairs.
- `page` is 1-based. `page_size` is an alias for `limit`; when provided it overrides `limit`.
- If an unsupported filter key is supplied the endpoint will return HTTP 422 with the unsupported keys listed.

## Pagination Logic

The pagination uses offset-based pagination:

- **Page 1**: OFFSET 0, LIMIT 10 (items 1-10)
- **Page 2**: OFFSET 10, LIMIT 10 (items 11-20)
- **Page 3**: OFFSET 20, LIMIT 10 (items 21-30)
- etc.

Formula: `OFFSET = (page - 1) * limit`

## SPARQL Query

The endpoint uses the SPARQL template from `/resources/sparql/products.txt` with dynamically added `LIMIT` and `OFFSET` clauses.

### Template Location
```
/resources/sparql/products.txt
```

### Configuration
```toml
[default]
sparql_products_path = "@format {env[BASE_DIR]}/resources/sparql/products.txt"
```

## Data Flow

```
1. Request with page and limit parameters
   ↓
2. Calculate offset: (page - 1) * limit
   ↓
3. Load SPARQL template from configuration
   ↓
4. Add LIMIT and OFFSET to SPARQL
   ↓
5. Query GraphDB triplestore
   ↓
6. Parse RDF Turtle response
   ↓
7. Extract all fabio:Work subjects
   ↓
8. For each product, extract:
   - Title (dc:title)
   - Abstract (dc:abstract)
   - Identifiers (datacite:hasIdentifier)
   ↓
9. Build pagination metadata:
   - Current page URL
   - Next page URL
   - Search result base URL
   ↓
10. Build SKG-IF response with contexts
    ↓
11. Return JSON-LD
```

## Implementation Details

### Files Modified

1. **`/src/ost_clairin_skg/api/v1/product.py`**
   - Added `_rdf_graph_to_products()` function
   - Added `get_products()` endpoint
   - Imports updated to include `List`, `Query`

2. **`/src/ost_clairin_skg/infra/commons.py`**
   - Added `build_products_sparql()` function
   - Loads template and adds pagination

3. **`/conf/settings.toml`**
   - Added `sparql_products_path` configuration

### Files Created

4. **`/resources/sparql/products.txt`**
   - SPARQL CONSTRUCT template for multiple products
   - Queries all fabio:Work subjects
   - Extracts titles, abstracts, identifiers

## Performance Considerations

### Pagination Limits
- Minimum page: 1
- Maximum items per page: 100
- Default items per page: 10

### Query Optimization
- The SPARQL query uses LIMIT to avoid loading too many results
- OFFSET pagination may be slow for large datasets
- Consider adding filters or using cursor-based pagination for production

### Caching
For production, consider caching responses:
```python
from fastapi_cache import cached

@router.get("/products")
@cached(namespace="products", expire=3600)
def get_products(...):
    ...
```

## Extending the Endpoint

### Adding Total Count
To include `total_items` in the response, add a COUNT query:

```python
def _count_total_products() -> int:
    count_sparql = """
    PREFIX fabio: <http://purl.org/spar/fabio/>
    SELECT (COUNT(DISTINCT ?s) as ?count)
    WHERE {
        ?s a fabio:Work .
    }
    """
    # Execute and parse result
    ...
```

Then update the metadata:
```python
"part_of": {
    "local_identifier": search_url,
    "entity_type": "search_result",
    "total_items": _count_total_products()
}
```

### Adding Filters
Add filter parameters to the endpoint:

```python
def get_products(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    product_type: Optional[str] = Query(None, description="Filter by product type")
):
    # Build filter clause
    filter_clause = ""
    if product_type:
        filter_clause = f'FILTER(?productType = "{product_type}")'
    
    # Pass to SPARQL builder
    sparql = commons.build_products_sparql(limit, offset, filter_clause)
    ...
```

### Adding Sorting
Add sort parameter:

```python
def get_products(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort: str = Query("title", description="Sort field")
):
    # Modify SPARQL to include ORDER BY
    ...
```

## Testing

### Manual Testing
```bash
# Test basic endpoint
curl http://localhost:41012/api/v1/products | python3 -m json.tool

# Test pagination
curl "http://localhost:41012/api/v1/products?page=2" | python3 -m json.tool

# Test custom limit
curl "http://localhost:41012/api/v1/products?limit=5" | python3 -m json.tool

# Test combined parameters
curl "http://localhost:41012/api/v1/products?page=2&limit=20" | python3 -m json.tool
```

### Validation Checklist
- [ ] Response has `@context` array with 3 elements
- [ ] Response has `meta` object with pagination info
- [ ] Response has `@graph` array with products
- [ ] Each product has required fields (local_identifier, entity_type, product_type)
- [ ] Content-Type is `application/ld+json`
- [ ] Pagination URLs are correctly formatted
- [ ] Empty result set returns valid response structure

## Troubleshooting

### Issue: Empty @graph array
**Cause**: No products in triplestore or SPARQL query issue
**Solution**: Check GraphDB has data, verify SPARQL template

### Issue: Incorrect pagination URLs
**Cause**: Request base URL misconfigured
**Solution**: Check FastAPI configuration and proxy settings

### Issue: 502 error
**Cause**: GraphDB connection or SPARQL syntax error
**Solution**: Check logs, verify GraphDB connection, test SPARQL directly

## References

- **SKG-IF Research Products**: https://skg-if.github.io/interoperability-framework/docs/research-product.html
- **SKG-IF Pagination**: https://skg-if.github.io/interoperability-framework/docs/api.html#pagination
- **JSON-LD Specification**: https://www.w3.org/TR/json-ld11/
- **Single Product Endpoint**: See `/product/{id}` documentation

---

**Status**: ✅ IMPLEMENTED

**Last Updated**: 2026-03-05

**Version**: 1.0

