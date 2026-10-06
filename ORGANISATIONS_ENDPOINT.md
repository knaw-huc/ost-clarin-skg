# `/organisations` Endpoint Documentation

## Overview

The `/organisations` endpoints return organisations (SKG-IF Agents with `entity_type: organisation`) in SKG-IF compliant JSON-LD. Organisations are all `foaf:Organization` subjects in the triplestore.

Note the British spelling in the URL path (`/organisations`); the Python module is `organizations.py`.

## Endpoints

```
GET /api/v1/organisations                          # paginated, filterable list
GET /api/v1/organisations/{local_identifier}       # single organisation
```

## List Organisations — `GET /api/v1/organisations`

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number (1-based, minimum: 1) |
| `page_size` | integer | No | 10 | Number of items per page (range: 1-100) |
| `filter` | string | No | – | Comma-separated `name:value` pairs (see [Filtering](#filtering)) |

### Filtering

`filter` is a comma-separated list of `name:value` pairs, combined with AND. The value is everything after the first `:`, so URIs can be used as values; values cannot contain commas. Pairs without a `:` are ignored.

| Key | RDF property | Match |
|-----|--------------|-------|
| `name` | `foaf:name` | Exact, on any of the organisation's names |
| `cf.search.name` | `foaf:name` | Case-insensitive substring, on any name |
| `identifiers.id` | `datacite:hasIdentifier/silvio:hasLiteralValue` | Exact |
| `identifiers.scheme` | `datacite:hasIdentifier/datacite:usesIdentifierScheme` | Case-insensitive on the scheme's local name (e.g. `ror`) |

Any other key returns `422` with the unsupported keys listed.

#### Filter examples

```
/organisations?filter=cf.search.name:university
/organisations?filter=identifiers.scheme:ror
/organisations?filter=identifiers.id:https://ror.org/04dkp9463
/organisations?filter=cf.search.name:institute&page=2&page_size=50
```

### Success Response (200 OK)

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
    "local_identifier": "http://localhost:41012/api/v1/organisations?page=1",
    "entity_type": "search_result_page",
    "next_page": {
      "local_identifier": "http://localhost:41012/api/v1/organisations?page=2",
      "entity_type": "search_result_page"
    },
    "part_of": {
      "local_identifier": "http://localhost:41012/api/v1/organisations",
      "entity_type": "search_result"
    }
  },
  "@graph": [
    {
      "local_identifier": "organisation-1",
      "entity_type": "organisation",
      "name": "Universiteit van Amsterdam",
      "other_names": ["University of Amsterdam"],
      "website": "https://www.uva.nl",
      "identifiers": [
        {
          "value": "https://ror.org/04dkp9463",
          "scheme": "ror"
        }
      ]
    }
  ]
}
```

An empty result returns the same structure with `"@graph": []`.

### Pagination Metadata

| Field | Type | Description |
|-------|------|-------------|
| `local_identifier` | string | Current page URL |
| `entity_type` | string | Always `search_result_page` |
| `next_page` | object | Reference to the next page |
| `part_of` | object | Reference to the whole search result (URL without `page`) |

Notes:
- `page_size` is included in the URLs only when it differs from 10; `filter` is included (URL-encoded) whenever given.
- `next_page` is always present, even on the last page; there is no `total_items`.

## Get Organisation — `GET /api/v1/organisations/{local_identifier}`

`{local_identifier}` is the value returned in `local_identifier` (the `otf:` prefix is restored internally), or a full subject URI. Identifier values such as ROR IDs are **not** resolved here — use `/organisations?filter=identifiers.id:...` instead.

### Success Response (200 OK)

```json
{
  "@context": [
    "https://w3id.org/skg-if/context/1.1.0/skg-if.json",
    "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json",
    {
      "@base": "http://localhost:41012/"
    }
  ],
  "@graph": [
    {
      "local_identifier": "organisation-1",
      "entity_type": "organisation",
      "name": "Universiteit van Amsterdam",
      "website": "https://www.uva.nl"
    }
  ]
}
```

## Organisation Fields

| Field | Type | Required | Source | Description |
|-------|------|----------|--------|-------------|
| `local_identifier` | string | Yes | subject IRI | `otf:` prefix removed |
| `entity_type` | string | Yes | – | Always `organisation` |
| `name` | string | No | `foaf:name` | Primary name |
| `other_names` | array | No | `foaf:name` | Remaining names, when there are several |
| `website` | string | No | `foaf:homepage` | Homepage URL |
| `identifiers` | array | No | `datacite:hasIdentifier` | `{value, scheme}` objects |

When an organisation has several `foaf:name` values, they are sorted alphabetically: the first becomes `name` and the rest `other_names`, so the output is stable between requests. Identifier schemes are the lowercased local name of the scheme IRI (e.g. `datacite:ror` → `ror`).

The same organisation object is embedded in `/services` responses (see `SERVICES_ENDPOINT.md`), where it may additionally carry `types`.

## Error Responses

| Status | When | Body |
|--------|------|------|
| `404` | Single organisation not found | `{"detail": "Organisation not found"}` |
| `422` | Unsupported filter key | `{"detail": "Unsupported filter(s) requested", "unsupported_filters": [...]}` |
| `422` | Invalid `page`/`page_size` | FastAPI validation error |
| `502` | Triplestore query failed | `{"detail": "Failed to query triplestore", "error": "..."}` |
| `502` | RDF → JSON-LD conversion failed | `{"detail": "Failed to convert triplestore response to JSON-LD", "error": "..."}` |

## Response Headers

```
Content-Type: application/ld+json
```

## Usage Examples

```bash
# First page
curl http://localhost:41012/api/v1/organisations

# Name search
curl -G http://localhost:41012/api/v1/organisations \
  --data-urlencode "filter=cf.search.name:university"

# Lookup by ROR
curl -G http://localhost:41012/api/v1/organisations \
  --data-urlencode "filter=identifiers.id:https://ror.org/04dkp9463"

# Single organisation
curl http://localhost:41012/api/v1/organisations/organisation-1
```

### Python Example
```python
import requests

response = requests.get(
    "http://localhost:41012/api/v1/organisations",
    params={"page_size": 50, "filter": "identifiers.scheme:ror"},
)
data = response.json()

for org in data["@graph"]:
    print(org["local_identifier"], org.get("name"), org.get("website"))
```

## Pagination Logic

Offset-based: `OFFSET = (page - 1) * page_size`.

The list template selects one page of **distinct** `foaf:Organization` subjects in a subquery (`ORDER BY ?s`), so `LIMIT`/`OFFSET` count organisations rather than result rows.

## SPARQL Queries

| Endpoint | Template | Setting |
|----------|----------|---------|
| List | `resources/sparql/organisations.txt` | `sparql_organisations_path` |
| Single | `resources/sparql/organisation.txt` | `sparql_organisation_path` |

```toml
[default]
sparql_organisation_path = "@format {env[BASE_DIR]}/resources/sparql/organisation.txt"
sparql_organisations_path = "@format {env[BASE_DIR]}/resources/sparql/organisations.txt"
```

The list template must contain the `#FILTERS#` and `#PAGINATION#` placeholders. Filter keys are translated to SPARQL by the shared `commons.build_filter_patterns()`, driven by the `ORGANISATION_FILTERS` table in `organizations.py`.

## Implementation

| File | Contents |
|------|----------|
| `src/ost_clairin_skg/api/v1/organizations.py` | `get_organisations()`, `get_organisation()`, `ORGANISATION_FILTERS`, `_extract_organisation()` (also used by services) |
| `src/ost_clairin_skg/infra/commons.py` | `build_organisations_sparql()`, `build_organisation_sparql()`, `build_filter_patterns()` |
| `resources/sparql/organisations.txt`, `organisation.txt` | SPARQL CONSTRUCT templates |
| `tests/test_organisation_endpoint.py` | Unit tests |

## Known Limitations

- No `total_items` in `part_of`.
- `next_page` is emitted even when the current page is the last one.
- Organisation `types`, country and parent/child relations are not exposed on this endpoint.

## Testing

```bash
uv run pytest tests/test_organisation_endpoint.py
```

## References

- **SKG-IF Agents**: https://skg-if.github.io/interoperability-framework/docs/agent.html
- **SKG-IF API / Pagination**: https://skg-if.github.io/interoperability-framework/docs/api.html#pagination
- **Related**: `PRODUCTS_ENDPOINT.md`, `PERSONS_ENDPOINT.md`, `SERVICES_ENDPOINT.md`

---

**Status**: ✅ IMPLEMENTED

**Last Updated**: 2026-09-28

**Version**: 1.0
