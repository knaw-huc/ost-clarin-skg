# `/services` Endpoint Documentation

## Overview

The `/services` endpoints return services following the [SKG-IF service extension (srv)](https://skg-if.github.io/ext-srv/api/api.html), with `entity_type: srv_service`. Services are all `srv:Service` subjects in the triplestore. Related organisations and venues are embedded as full objects rather than references.

## Endpoints

```
GET /api/v1/services                          # paginated, filterable list
GET /api/v1/services/{local_identifier}       # single service
```

## List Services — `GET /api/v1/services`

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number (1-based, minimum: 1) |
| `page_size` | integer | No | 10 | Number of items per page (range: 1-100) |
| `filter` | string | No | – | Comma-separated `name:value` pairs (see [Filtering](#filtering)) |

### Filtering

`filter` is a comma-separated list of `name:value` pairs, combined with AND. The value is everything after the first `:`, so URIs can be used as values; values cannot contain commas. Pairs without a `:` are ignored.

| Key | Match |
|-----|-------|
| `name` | Exact match on service name (`foaf:name`) |
| `cf.search.name` | Case-insensitive substring match on service name |
| `cf.search.org_name` | Case-insensitive substring match on the name of **any** related organisation |
| `<org>.name` | Exact match on the name of a related organisation of that kind |
| `<org>.identifiers.value` | Exact match on an identifier value of that organisation |
| `<org>.identifiers.scheme` | Identifier scheme of that organisation (e.g. `ror`), case-insensitive |

where `<org>` is one of:

| `<org>` | RDF property |
|---------|--------------|
| `relevant_organisations` | `dc:relation` |
| `srv_has_hosting_organisation` | `srv:hasHostingOrganisation` |
| `srv_has_research_infrastructure` | `srv:isPartOfResearchInfrastructure` |

Any other key returns `422` with the unsupported keys listed.

#### Filter examples

```
/services?filter=cf.search.name:corpus
/services?filter=cf.search.org_name:clarin
/services?filter=srv_has_research_infrastructure.name:CLARIN
/services?filter=srv_has_hosting_organisation.identifiers.value:https://ror.org/04dkp9463
/services?filter=relevant_organisations.identifiers.scheme:ror,cf.search.name:search
```

### Success Response (200 OK)

```json
{
  "@context": [
    "https://w3id.org/skg-if/context/1.1.0/skg-if.json",
    "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json",
    {
      "@base": "http://localhost:41012/"
    },
    "https://w3id.org/skg-if/extension/srv/context/skg-if.json"
  ],
  "meta": {
    "local_identifier": "http://localhost:41012/api/v1/services?page=1",
    "entity_type": "search_result_page",
    "next_page": {
      "local_identifier": "http://localhost:41012/api/v1/services?page=2",
      "entity_type": "search_result_page"
    },
    "part_of": {
      "local_identifier": "http://localhost:41012/api/v1/services",
      "entity_type": "search_result"
    }
  },
  "@graph": [
    {
      "local_identifier": "service-1",
      "entity_type": "srv_service",
      "name": "Example Corpus Search",
      "srv_descriptions": {
        "en": ["Search interface for annotated corpora."]
      },
      "srv_has_hosting_organisation": [
        {
          "local_identifier": "organisation-1",
          "entity_type": "organisation",
          "name": "Example Institute",
          "website": "https://example.org",
          "identifiers": [ { "value": "https://ror.org/000000000", "scheme": "ror" } ],
          "types": ["srv_hosting_organisation"]
        }
      ],
      "srv_has_research_infrastructure": [
        {
          "local_identifier": "organisation-2",
          "entity_type": "organisation",
          "name": "CLARIN ERIC",
          "types": ["srv_research_infrastructure"]
        }
      ],
      "srv_venues": [
        {
          "local_identifier": "venue-1",
          "entity_type": "venue",
          "name": "Example Corpus Search portal",
          "website": "https://search.example.org",
          "types": ["srv_portal"]
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

## Get Service — `GET /api/v1/services/{local_identifier}`

`{local_identifier}` is the value returned in `local_identifier` (the `otf:` prefix is restored internally), or a full subject URI.

The response has the same `@context` (including the srv extension context) and a single `srv_service` object in `@graph`.

## Service Fields

| Field | Type | Required | Source | Description |
|-------|------|----------|--------|-------------|
| `local_identifier` | string | Yes | subject IRI | `otf:` prefix removed |
| `entity_type` | string | Yes | – | Always `srv_service` |
| `name` | string | No | `foaf:name` | Service name |
| `srv_descriptions` | object | No | `dc:description` | Language-keyed descriptions |
| `srv_has_hosting_organisation` | array | No | `srv:hasHostingOrganisation` | Organisation objects |
| `srv_has_research_infrastructure` | array | No | `srv:isPartOfResearchInfrastructure` | Organisation objects |
| `relevant_organisations` | array | No | `dc:relation` | Organisation objects |
| `srv_venues` | array | No | `srv:hasVenue` | Venue objects |

Description language keys are the literal's language tag when it is two letters, otherwise `none` (e.g. harvested `@und` descriptions). A leading `{code:...}` marker is stripped. Linked organisations and venues are sorted by IRI.

### Embedded Organisation

Same fields as on `/organisations` (`local_identifier`, `entity_type: organisation`, `name`, `other_names`, `website`, `identifiers` — see `ORGANISATIONS_ENDPOINT.md`), plus:

| Field | Type | Description |
|-------|------|-------------|
| `types` | array | `srv_hosting_organisation` (`srv:HostingOrganisation`) and/or `srv_research_infrastructure` (`srv:ResearchInfrastructure`) |

### Embedded Venue

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `local_identifier` | string | subject IRI | `otf:` prefix removed |
| `entity_type` | string | – | Always `venue` |
| `name` | string | `foaf:name` | Venue name |
| `website` | string | `foaf:homepage` | Venue URL |
| `types` | array | `rdf:type` | `srv_portal` (`srv:Portal`) |

## Error Responses

| Status | When | Body |
|--------|------|------|
| `404` | Single service not found | `{"detail": "Service not found"}` |
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
curl http://localhost:41012/api/v1/services

# Services of a research infrastructure
curl -G http://localhost:41012/api/v1/services \
  --data-urlencode "filter=srv_has_research_infrastructure.name:CLARIN ERIC"

# Single service
curl http://localhost:41012/api/v1/services/service-1
```

### Python Example
```python
import requests

response = requests.get(
    "http://localhost:41012/api/v1/services",
    params={"page_size": 20, "filter": "cf.search.org_name:clarin"},
)
data = response.json()

for service in data["@graph"]:
    hosts = [o.get("name") for o in service.get("srv_has_hosting_organisation", [])]
    portals = [v.get("website") for v in service.get("srv_venues", [])]
    print(service["local_identifier"], service.get("name"), hosts, portals)
```

## Pagination Logic

Offset-based: `OFFSET = (page - 1) * page_size`.

The list template selects one page of **distinct** `srv:Service` subjects in a subquery (`ORDER BY ?s`), so `LIMIT`/`OFFSET` count services rather than result rows.

## SPARQL Queries

| Endpoint | Template | Setting |
|----------|----------|---------|
| List | `resources/sparql/services.txt` | `sparql_services_path` |
| Single | `resources/sparql/service.txt` | `sparql_service_path` |

```toml
[default]
sparql_service_path = "@format {env[BASE_DIR]}/resources/sparql/service.txt"
sparql_services_path = "@format {env[BASE_DIR]}/resources/sparql/services.txt"
```

The list template must contain the `#FILTERS#` and `#PAGINATION#` placeholders. Both templates fetch each property in its own `UNION` branch so that multi-valued properties (several descriptions, organisations and venues) don't multiply into a cross product of result rows. Filter keys are translated to SPARQL by the shared `commons.build_filter_patterns()`, driven by the `SERVICE_FILTERS` table in `services.py`.

## Implementation

| File | Contents |
|------|----------|
| `src/ost_clairin_skg/api/v1/services.py` | `get_services()`, `get_service()`, `SERVICE_FILTERS`, service / venue / linked-organisation extraction |
| `src/ost_clairin_skg/api/v1/organizations.py` | `_extract_organisation()`, reused for embedded organisations |
| `src/ost_clairin_skg/infra/commons.py` | `build_services_sparql()`, `build_service_sparql()`, `build_filter_patterns()` |
| `resources/sparql/services.txt`, `service.txt` | SPARQL CONSTRUCT templates |
| `tests/test_service_endpoint.py` | Unit tests |

## Known Limitations

- No `total_items` in `part_of`.
- `next_page` is emitted even when the current page is the last one.
- There are no filters on venues or descriptions.

## Testing

```bash
uv run pytest tests/test_service_endpoint.py
```

## References

- **SKG-IF Service Extension**: https://skg-if.github.io/ext-srv/
- **SKG-IF Service Extension API**: https://skg-if.github.io/ext-srv/api/api.html
- **SKG-IF API / Pagination**: https://skg-if.github.io/interoperability-framework/docs/api.html#pagination
- **Related**: `PRODUCTS_ENDPOINT.md`, `PERSONS_ENDPOINT.md`, `ORGANISATIONS_ENDPOINT.md`

---

**Status**: ✅ IMPLEMENTED

**Last Updated**: 2026-09-28

**Version**: 1.0
