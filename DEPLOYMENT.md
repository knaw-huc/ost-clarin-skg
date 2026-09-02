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

### Issue: Memory Usage High

**Check:**
1. Number of concurrent connections
2. RDF graph size
3. Response caching

**Fix:**
```bash
# Implement pagination
# Limit SPARQL results
# Enable response caching
# Increase worker memory limit
```

## Post-Deployment Verification

```bash
#!/bin/bash

echo "=== Deployment Verification ==="

# 1. Service running
echo -n "Service running: "
curl -s http://localhost:41012/api/v1 > /dev/null && echo "✓" || echo "✗"

# 2. GraphDB accessible
echo -n "GraphDB connected: "
# Check logs for connection success
grep -q "GraphDB" /path/to/logs/ocs.log && echo "✓" || echo "✗"

# 3. Contexts accessible
echo -n "SKG-IF contexts accessible: "
curl -s https://w3id.org/skg-if/context/1.1.0/skg-if.json > /dev/null && echo "✓" || echo "✗"

# 4. Sample query works
echo -n "Sample query works: "
curl -s -H "Accept: application/ld+json" \
  http://localhost:41012/api/v1/product/test | grep -q "@context" && echo "✓" || echo "✗"

# 5. Response format correct
echo -n "Response format correct: "
RESPONSE=$(curl -s -H "Accept: application/ld+json" http://localhost:41012/api/v1/product/test)
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert '@context' in data and '@graph' in data
print('✓')
" 2>/dev/null || echo "✗"

echo "=== Verification Complete ==="
```

## Support and Escalation

### Log Analysis

Critical logs to monitor:

1. **Connection Errors**
```bash
grep "RuntimeError\|ConnectionError" /path/to/logs/ocs.log
```

2. **Parse Errors**
```bash
grep "ValueError\|ParseError" /path/to/logs/ocs.log
```

3. **Performance Issues**
```bash
grep "timeout\|took.*seconds" /path/to/logs/ocs.log
```

### Contact Information

For issues, contact:
- DevOps team
- GraphDB administrator
- System architect

## Documentation

- Product API: `/RESPONSE_FORMAT.md`
- Implementation: `/IMPLEMENTATION_COMPLETE.md`
- Code Changes: `/CHANGES_SUMMARY.md`
- Testing: `/TESTING.md`

