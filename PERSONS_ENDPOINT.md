# `/persons` Endpoint Documentation

## Overview

The `/persons` endpoints return persons (SKG-IF Agents with `entity_type: person`) in SKG-IF compliant JSON-LD. Persons are all `foaf:Person` subjects in the triplestore.

## Endpoints

```
GET /api/v1/persons                          # paginated, filterable list
GET /api/v1/persons/{local_identifier}       # single person
```

## List Persons — `GET /api/v1/persons`

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number (1-based, minimum: 1) |
| `page_size` | integer | No | 10 | Number of items per page (range: 1-100) |
| `filter` | string | No | – | Comma-separated `name:value` pairs (see [Filtering](#filtering)) |

Unlike `/products`, there is no `limit` alias.

### Filtering

`filter` is a comma-separated list of `name:value` pairs, combined with AND. The value is everything after the first `:`; values cannot contain commas. Pairs without a `:` are ignored.

| Key | RDF property | Match |
|-----|--------------|-------|
| `name` | `foaf:name` | Exact |
| `given_name` | `foaf:givenName` | Exact |
| `family_name` | `foaf:familyName` | Exact |
| `cf.search.name` | `foaf:name` | Case-insensitive substring |
| `cf.search.given_name` | `foaf:givenName` | Case-insensitive substring |
| `cf.search.family_name` | `foaf:familyName` | Case-insensitive substring |
| `identifiers.id` | `datacite:hasIdentifier/silvio:hasLiteralValue` | Exact |
| `identifiers.scheme` | `datacite:hasIdentifier/datacite:usesIdentifierScheme` | Case-insensitive on the scheme's local name (e.g. `orcid`) |

Any other key returns `422` with the unsupported keys listed.

#### Filter examples

```
/persons?filter=family_name:Smith
/persons?filter=cf.search.family_name:smi,cf.search.given_name:jo
/persons?filter=identifiers.id:0000-0002-1825-0097
/persons?filter=identifiers.scheme:orcid&page=2&page_size=25
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
    "local_identifier": "http://localhost:41012/api/v1/persons?page=1&filter=cf.search.family_name%3Asmi",
    "entity_type": "search_result_page",
    "next_page": {
      "local_identifier": "http://localhost:41012/api/v1/persons?page=2&filter=cf.search.family_name%3Asmi",
      "entity_type": "search_result_page"
    },
    "part_of": {
      "local_identifier": "http://localhost:41012/api/v1/persons?filter=cf.search.family_name%3Asmi",
      "entity_type": "search_result"
    }
  },
  "@graph": [
    {
      "local_identifier": "person-1",
      "entity_type": "person",
      "name": "Jane Smith",
      "given_name": "Jane",
      "family_name": "Smith",
      "identifiers": [
        {
          "value": "0000-0002-1825-0097",
          "scheme": "orcid"
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

## Get Person — `GET /api/v1/persons/{local_identifier}`

`{local_identifier}` is the value returned in `local_identifier` (the `otf:` prefix is restored internally), or a full subject URI. Unlike `/products/{id}`, identifier values such as ORCIDs are **not** resolved here — use `/persons?filter=identifiers.id:...` instead.

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
      "local_identifier": "person-1",
      "entity_type": "person",
      "name": "Jane Smith",
      "given_name": "Jane",
      "family_name": "Smith"
    }
  ]
}
```

## Person Fields

| Field | Type | Required | Source | Description |
|-------|------|----------|--------|-------------|
| `local_identifier` | string | Yes | subject IRI | `otf:` prefix removed |
| `entity_type` | string | Yes | – | Always `person` |
| `name` | string | No | `foaf:name` | Full name |
| `given_name` | string | No | `foaf:givenName` | Given (first) name |
| `family_name` | string | No | `foaf:familyName` | Family (last) name |
| `identifiers` | array | No | `datacite:hasIdentifier` | `{value, scheme}` objects |

If a person has several values for a name property, one of them is returned. Identifier schemes are the lowercased local name of the scheme IRI (e.g. `datacite:orcid` → `orcid`).

## Error Responses

| Status | When | Body |
|--------|------|------|
| `404` | Single person not found | `{"detail": "Person not found"}` |
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
curl http://localhost:41012/api/v1/persons

# Search by family name, 25 per page
curl -G http://localhost:41012/api/v1/persons \
  --data-urlencode "filter=cf.search.family_name:smi" \
  --data-urlencode "page_size=25"

# Single person
curl http://localhost:41012/api/v1/persons/person-1
```

### Python Example
```python
import requests

response = requests.get(
    "http://localhost:41012/api/v1/persons",
    params={"page": 1, "page_size": 20, "filter": "identifiers.scheme:orcid"},
)
data = response.json()

for person in data["@graph"]:
    orcids = [i["value"] for i in person.get("identifiers", []) if i["scheme"] == "orcid"]
    print(person["local_identifier"], person.get("name"), orcids)
```

## Pagination Logic

Offset-based: `OFFSET = (page - 1) * page_size`.

The list template selects one page of **distinct** `foaf:Person` subjects in a subquery (`ORDER BY ?s`), so `LIMIT`/`OFFSET` count persons rather than result rows.

## SPARQL Queries

| Endpoint | Template | Setting |
|----------|----------|---------|
| List | `resources/sparql/persons.txt` | `sparql_persons_path` |
| Single | `resources/sparql/person.txt` | `sparql_person_path` |

```toml
[default]
sparql_person_path = "@format {env[BASE_DIR]}/resources/sparql/person.txt"
sparql_persons_path = "@format {env[BASE_DIR]}/resources/sparql/persons.txt"
```

The list template must contain the `#FILTERS#` and `#PAGINATION#` placeholders. Filter keys are translated to SPARQL by the shared `commons.build_filter_patterns()`, driven by the `PERSON_FILTERS` table in `persons.py`; adding a filter only needs a new entry there.

## Implementation

| File | Contents |
|------|----------|
| `src/ost_clairin_skg/api/v1/persons.py` | `get_persons()`, `get_person()`, `PERSON_FILTERS`, RDF → JSON-LD conversion |
| `src/ost_clairin_skg/infra/commons.py` | `build_persons_sparql()`, `build_person_sparql()`, `build_filter_patterns()` |
| `resources/sparql/persons.txt`, `person.txt` | SPARQL CONSTRUCT templates |
| `tests/test_person_endpoint.py` | Unit tests |

## Known Limitations

- No `total_items` in `part_of`.
- `next_page` is emitted even when the current page is the last one.
- Person contributions/affiliations are not exposed.

## Testing

```bash
uv run pytest tests/test_person_endpoint.py
```

## References

- **SKG-IF Agents**: https://skg-if.github.io/interoperability-framework/docs/agent.html
- **SKG-IF API / Pagination**: https://skg-if.github.io/interoperability-framework/docs/api.html#pagination
- **Related**: `PRODUCTS_ENDPOINT.md`, `ORGANISATIONS_ENDPOINT.md`, `SERVICES_ENDPOINT.md`

---

**Status**: ✅ IMPLEMENTED

**Last Updated**: 2026-09-28

**Version**: 1.0
