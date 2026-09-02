# Clarin OSTrails Interoperability Framework (SKG-IF)
The project is developing a standard interoperability framework called SKG-IF to ensure that different SKG implementations can exchange information.

---

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Documentation Files](#documentation-files)
- [Response Format](#response-format)
- [Configuration Reference](#configuration-reference)
- [Testing Guide](#testing-guide)
- [Deployment Guide](#deployment-guide)
- [Products Endpoint](#products-endpoint)
- [Implementation Details](#implementation-details)
- [Notes](#notes)

<a name="overview"></a>
## Overview

The SKG-IF Product Endpoint is a new API endpoint that retrieves product information from a GraphDB triplestore, transforms it into SKG-IF compliant JSON-LD format, and serves it to clients. This implementation includes:

---

<a name="getting-started"></a>
## 🚀 Getting Started (Start Here!)

### For Quick Overview
1. **Read**: `QUICK_REFERENCE` (2 min) - What changed and why
2. **Review**: `DELIVERABLES` (5 min) - What you're getting
3. **Check**: Key response format below

### For In-Depth Understanding
1. Read: `SKG_IF_IMPLEMENTATION` - Full implementation details
2. Read: `BEFORE_AFTER_COMPARISON` - Understand the changes
3. Read: `CODE_STRUCTURE` - How the code is organized

### For Testing
1. See: `TESTING` - Complete testing guide
2. Run: `pytest tests/test_product_endpoint.py -v`
3. Manual test: `curl http://localhost:41012/api/v1/product/test-id`

### For Deployment
1. See: `DEPLOYMENT` - Deployment procedures
2. Check: Pre-deployment checklist
3. Follow: Deployment steps
4. Verify: Post-deployment verification

---

<a name="documentation-files"></a>
## 📚 Documentation Files

### Primary Documentation

| Document | Purpose | Read Time | Audience |
|----------|---------|-----------|----------|
| **QUICK_REFERENCE** | Quick start guide | 2 min | Everyone |
| **SKG_IF_IMPLEMENTATION** | Complete overview | 5 min | Developers |
| **DELIVERABLES** | What's included | 5 min | Project Managers |
| **TESTING** | How to test | 10 min | QA Engineers |
| **DEPLOYMENT** | How to deploy | 15 min | DevOps/Admins |

### Supplementary Documentation

| Document | Purpose | Read Time | Audience |
|----------|---------|-----------|----------|
| **IMPLEMENTATION_COMPLETE** | Executive summary | 10 min | Decision Makers |
| **CHANGES_SUMMARY** | Detailed changelog | 5 min | Code Reviewers |
| **CODE_STRUCTURE** | Code organization | 10 min | Developers |
| **RESPONSE_FORMAT** | API response examples | 5 min | API Consumers |
| **BEFORE_AFTER_COMPARISON** | Before/after analysis | 5 min | Stakeholders |

### This File
| Document | Purpose |
|----------|---------|
| **INDEX** (this file) | Documentation roadmap |

---

<a name="development"></a>
## Development

This section is intended for contributors. The README focuses on the user- and developer-facing documentation (API usage, configuration, testing, deployment). Detailed change history and file-level diffs are kept in the project's changelogs and version control history rather than in this README.

For contributing and development, consult the source tree under `src/` and the test suite under `tests/`.

---

<a name="response-format"></a>
## 📊 Response Format

### Successful Response (200 OK)

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

| Status | Scenario | Response |
|--------|----------|----------|
| 404 | Product not found | `{"detail": "Product not found"}` |
| 502 | GraphDB query error | `{"detail": "Failed to query triplestore", "error": "..."}` |
| 502 | RDF parsing error | `{"detail": "Failed to convert triplestore response to JSON-LD", "error": "..."}` |

---

<a name="configuration-reference"></a>
## 🔧 Configuration Reference

### Settings File
**Location**: `/conf/settings.toml`

```toml
[default]
sparql_product_path = "@format {env[BASE_DIR]}/resources/sparql/product.txt"
```

### SPARQL Template
**Location**: `/resources/sparql/product.txt`

Contains CONSTRUCT query template that:
- Queries fabio:Work subjects
- Extracts titles and abstracts
- Collects identifiers
- Returns Turtle format

### Environment Variables

```bash
export BASE_DIR=/Users/akmi/dev/work/huc/ost-clarin-skg
export ENDPOINT=http://graphdb:7200/repositories/repo
export USER=graphdb_user
export PASS=graphdb_password
```

---

<a name="testing-guide"></a>
## 🧪 Testing Guide

### Quick Test
```bash
# Run all tests
pytest tests/test_product_endpoint.py -v

# Run specific test class
pytest tests/test_product_endpoint.py::TestRDFToProductTransformation -v

# Run with coverage
pytest tests/test_product_endpoint.py --cov=src/ost_clairin_skg/api/v1/product --cov-report=html
```

### Manual Testing
```bash
# Start service
uvicorn src.ost_clairin_skg.main:app --port 41012

# Test endpoint
curl -H "Accept: application/ld+json" \
  http://localhost:41012/api/v1/product/test-123

# Test with real data
curl "http://localhost:41012/api/v1/product/http://example.com/real-product-id"
```

---

<a name="deployment-guide"></a>
## DEPLOYMENT

<!-- Begin content from DEPLOYMENT -->

# Deployment Guide for SKG-IF Product Endpoint

## Pre-Deployment Checklist

### Code Quality
- [x] All code compiles without errors
- [x] No unused imports or variables
- [x] Type hints are complete
- [x] Documentation strings are present
- [x] Error handling is comprehensive

### Testing
- [ ] Unit tests pass (`pytest tests/test_product_endpoint.py`)
- [ ] Integration tests pass with test data
- [ ] Manual cURL tests successful
- [ ] Performance tests acceptable
- [ ] Error handling validated

### Configuration
- [ ] `sparql_product_path` configured in `settings.toml`
- [ ] SPARQL template file exists at `/resources/sparql/product.txt`
- [ ] GraphDB credentials configured (USER, PASS, ENDPOINT)
- [ ] API prefix configured (`API_PREFIX`)
- [ ] Logging configuration set up

### Dependencies
- [ ] All required packages installed
- [ ] No version conflicts
- [ ] External contexts accessible (w3id.org)
- [ ] GraphDB endpoint accessible

## Deployment Steps

### 1. Environment Preparation

```bash
cd /Users/akmi/dev/work/huc/ost-clarin-skg

# Verify Python version
python3 --version  # Should be 3.8+

# Install/update dependencies
pip install -r requirements.txt  # or uv pip install

# Verify GraphDB connectivity
python3 -c "
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore
try:
	result = query_triplestore('SELECT * WHERE { ?s ?p ?o } LIMIT 1')
	print('✓ GraphDB connection successful')
except Exception as e:
	print(f'✗ GraphDB connection failed: {e}')
"
```

### 2. Configuration Verification

```bash
# Check settings
python3 -c "
from src.ost_clairin_skg.infra.commons import app_settings
print('API Prefix:', app_settings.get('api_prefix'))
print('SPARQL Path:', app_settings.get('sparql_product_path'))
print('Endpoint:', app_settings.get('ENDPOINT'))
"

# Verify SPARQL template exists
test -f ./resources/sparql/product.txt && echo "✓ SPARQL template found" || echo "✗ SPARQL template missing"

# Check template is readable
python3 -c "
from src.ost_clairin_skg.infra.commons import app_settings
path = app_settings.get('sparql_product_path')
print('Template path:', path)
try:
	with open(path) as f:
		content = f.read()
		print(f'✓ Template readable ({len(content)} bytes)')
except Exception as e:
	print(f'✗ Template error: {e}')
"
```

### 3. Application Startup

#### Development Mode
```bash
# Single instance with auto-reload
uvicorn src.ost_clairin_skg.main:app \
  --host 0.0.0.0 \
  --port 41012 \
  --reload
```

#### Production Mode
```bash
# Multiple workers for production
uvicorn src.ost_clairin_skg.main:app \
  --host 0.0.0.0 \
  --port 41012 \
  --workers 4 \
  --loop uvloop
```

#### With Docker
```bash
docker build -t ost-clarin-skg .
docker run -p 41012:41012 \
  -e ENDPOINT=http://graphdb:7200/repositories/your-repo \
  -e USER=admin \
  -e PASS=password \
  ost-clarin-skg
```

### 4. Health Check

```bash
# Test endpoint health
curl -s http://localhost:41012/api/v1 | python3 -m json.tool

# Should return version info and status

# Expected output:
# {
#   "title": "OSTrails Clarin SKG-IF Service",
#   "version": "...",
#   "description": "..."
# }
```

### 5. Functionality Test

```bash
# Test with sample product ID
curl -H "Accept: application/ld+json" \
  http://localhost:41012/api/v1/product/test-product-123

# Should return:
# - Status 200 or 404 (not 500)
# - Content-Type: application/ld+json
# - Valid JSON-LD structure if found
```

### 6. Context Accessibility Test

```bash
# Verify SKG-IF contexts are accessible
curl -s https://w3id.org/skg-if/context/1.1.0/skg-if.json | wc -l
curl -s https://w3id.org/skg-if/context/1.0.0/skg-if-api.json | wc -l

# Both should return data (non-zero byte count)
```

## Monitoring

### Log Files

Monitor application logs:

```bash
# Follow logs
tail -f /path/to/logs/ocs.log

# Search for errors
grep "ERROR" /path/to/logs/ocs.log

# Count by level
grep "WARNING" /path/to/logs/ocs.log | wc -l
```

### Performance Metrics

Monitor key metrics:

```bash
# Response times (from logs)
grep "Get product endpoint" /path/to/logs/ocs.log | \
  awk '{print $1, $2}' | tail -20

# Error rate
(grep "status_code=502" /path/to/logs/ocs.log | wc -l) / \
(grep "Get product endpoint" /path/to/logs/ocs.log | wc -l)
```

### Health Checks

```bash
# Check service is running
curl -s http://localhost:41012/api/v1 > /dev/null && echo "✓ Service healthy" || echo "✗ Service down"

# Check GraphDB connection
curl -s http://localhost:41012/api/v1/product/health 2>&1 | grep -q "200\|404" && echo "✓ GraphDB OK" || echo "✗ GraphDB issue"
```

## Rollback Procedure

If issues occur:

1. **Stop the service**
```bash
# If using systemd
systemctl stop ost-clarin-skg

# If running manually
kill $(lsof -t -i :41012)
```

2. **Revert to previous version**
```bash
git checkout HEAD~1  # or specific commit
```

3. **Restart service**
```bash
uvicorn src.ost_clairin_skg.main:app --port 41012
```

4. **Verify rollback**
```bash
curl -s http://localhost:41012/api/v1 | grep version
```

## Performance Optimization

### Caching

Consider adding response caching:

```python
from fastapi_cache2 import FastAPICache2
from fastapi_cache2.backends.redis import RedisBackend
from redis import asyncio as aioredis

@app.on_event("startup")
async def startup():
	redis = aioredis.from_url("redis://localhost:6379")
	FastAPICache2.init(RedisBackend(redis), prefix="fastapi-cache")

@router.get("/product/{id:path}")
@cached(namespace="products", expire=3600)
def get_product(id: str):
	...
```

### Query Optimization

1. Ensure GraphDB has proper indexes on:
   - `rdf:type fabio:Work`
   - `dc:title`, `dc:abstract`
   - `datacite:hasIdentifier`

2. Monitor query execution time:
```bash
# In GraphDB admin UI
# Queries → Slow Queries
# Set threshold to 1 second
```

### Connection Pooling

Configure GraphDB connection pooling in settings:

```toml
[default]
graphdb_pool_size = 10
graphdb_max_overflow = 20
graphdb_pool_timeout = 30
```

## Scaling

### Horizontal Scaling

For multiple instances:

```bash
# Start 4 instances behind load balancer
for i in {1..4}; do
  PORT=$((41012 + i)) uvicorn src.ost_clairin_skg.main:app \
	--port $PORT &
done
```

Configure load balancer (nginx example):

```nginx
upstream ost_clarin {
	server localhost:41013;
	server localhost:41014;
	server localhost:41015;
	server localhost:41016;
}

server {
	listen 41012;
	location / {
		proxy_pass http://ost_clarin;
	}
}
```

### Database Optimization

1. Enable query result caching in GraphDB
2. Use SPARQL federation for remote data
3. Implement connection pooling
4. Monitor memory usage

## Security

### Environment Variables

Secure sensitive configuration:

```bash
# Don't commit to git
export ENDPOINT="http://graphdb:7200/repositories/repo"
export USER="graphdb_user"
export PASS="secure_password"

# Or use .env file (add to .gitignore)
source .env
```

### CORS Configuration

Configure CORS properly in settings:

```toml
[default]
cors_origins = ["https://trusted.domain.com"]
cors_allow_credentials = true
cors_allow_methods = ["GET"]
cors_allow_headers = ["Accept"]
```

### Rate Limiting

Add rate limiting to prevent abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@router.get("/product/{id:path}")
@limiter.limit("100/minute")
def get_product(id: str, request: Request):
	...
```

## Troubleshooting

### Issue: "Failed to query triplestore"

**Check:**
1. GraphDB endpoint is accessible
2. Credentials are correct
3. Repository exists
4. Network connectivity

**Fix:**
```bash
# Test connectivity
curl -u user:pass http://graphdb:7200/rest/repositories

# Verify credentials in settings
python3 -c "from src.ost_clairin_skg.infra.commons import app_settings; print(app_settings.get('ENDPOINT'))"
```

### Issue: "No fabio:Work found"

**Check:**
1. SPARQL template is correct
2. Data in GraphDB has fabio:Work triples
3. Filter clause is correct

**Fix:**
```bash
# Test SPARQL directly in GraphDB
# Run: DESCRIBE ?s WHERE { ?s a <http://purl.org/spar/fabio/Work> } LIMIT 1
```

### Issue: Slow Response Times

**Check:**
1. GraphDB query performance
2. Network latency
3. SPARQL query complexity
4. Resource utilization

**Fix:**
```bash
# Profile SPARQL execution
# In GraphDB: Explore → Search
# Copy SPARQL query and check execution time
```

---

<a name="products-endpoint"></a>
## PRODUCTS_ENDPOINT

<!-- Begin content from PRODUCTS_ENDPOINT -->

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

<a name="implementation-details"></a>
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

## TESTING

<!-- Begin content from TESTING -->

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

### Load testing with Locust

This project includes a Locust load test at `src/locustfile.py` that exercises the product list and single-product endpoints.

Prerequisites

```bash
# Install locust in your environment
pip install locust
# Optionally create/activate a virtualenv first
```

Configure product ids (optional)

Set the `LOCUST_PRODUCT_IDS` environment variable to a comma-separated list of product identifiers (DOI or URIs) to use for single-product requests. If not provided, the locustfile uses built-in sample ids.

```bash
export LOCUST_PRODUCT_IDS="10.1038/sdata.2016.18,http://example.com/product-1"
```

PowerShell (Windows):

```powershell
$env:LOCUST_PRODUCT_IDS = "10.1038/sdata.2016.18,http://example.com/product-1"
```

Run Locust (web UI)

```bash
# Start the Locust web UI (default at http://localhost:8089)
locust -f src/locustfile.py --host=http://localhost:41012
```

Open http://localhost:8089 in your browser, set the number of users and spawn rate, and start the test.

Run Locust headless (CI / automated)

```bash
# Example: 100 users, spawn 10 users/sec, run for 5 minutes, produce CSV summary
LOCUST_PRODUCT_IDS="10.1038/sdata.2016.18,http://example.com/product-1" \
  locust -f src/locustfile.py --host=http://localhost:41012 \
  --users 100 --spawn-rate 10 --run-time 5m --headless --csv=locust_results
```

Notes

- Adjust `--users`, `--spawn-rate` and `--run-time` based on your environment and goals.
- If your API requires authentication, you can modify `src/locustfile.py` to include headers or a login flow; I can add that if needed.
- Monitor the service (CPU, memory, GraphDB query times) during load tests to identify bottlenecks.


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

### Issue: "Failed to query triplestore"
**Solution**: Check endpoint URL, credentials, and network connectivity

### Issue: Slow response times
**Solution**: Optimize SPARQL query, add database indexes, enable caching

See DEPLOYMENT for more troubleshooting guidance.

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

---
