# `/topics` Endpoint Documentation

## Overview

The `/topics` endpoints return topics following the [SKG-IF topic entity](https://skg-if.github.io/interoperability-framework/docs/topic.html), with `entity_type: topic`. Topics are all `fabio:SubjectTerm` subjects in the triplestore. The same topic shape is embedded in products (see `PRODUCTS_ENDPOINT.md`, [Topics](PRODUCTS_ENDPOINT.md#topics)).

## Endpoints

```
GET /api/v1/topics                          # paginated, filterable list
GET /api/v1/topics/{local_identifier}       # single topic
```

## List Topics — `GET /api/v1/topics`

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
| `identifiers.scheme` | Identifier scheme (e.g. `wikidata`), case-insensitive match on the local name of the scheme IRI |
| `identifiers.value` | Exact match on any identifier value |
| `cf.search.labels` | Case-insensitive substring match on any label (`skos:prefLabel`) |
| `cf.search.language` | Topic has a label with this language tag (e.g. `en`), case-insensitive |

Any other key returns `422` with the unsupported keys listed.

Each pair is matched independently, so `cf.search.labels:Solar,cf.search.language:en` returns topics that have *some* label containing "solar" and *some* English label — not necessarily the same label.

#### Filter examples

```
/topics?filter=cf.search.labels:solar
/topics?filter=cf.search.labels:Solar,cf.search.language:en
/topics?filter=identifiers.scheme:wikidata
/topics?filter=identifiers.value:Q12705
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
    "local_identifier": "http://localhost:41012/api/v1/topics?page=1",
    "entity_type": "search_result_page",
    "next_page": {
      "local_identifier": "http://localhost:41012/api/v1/topics?page=2",
      "entity_type": "search_result_page"
    },
    "part_of": {
      "local_identifier": "http://localhost:41012/api/v1/topics",
      "entity_type": "search_result"
    }
  },
  "@graph": [
    {
      "local_identifier": "otf___topic___solar",
      "entity_type": "topic",
      "labels": {
        "en": "Solar energy",
        "fr": "Energie solaire"
      },
      "identifiers": [
        { "value": "Q12705", "scheme": "wikidata" }
      ]
    },
    {
      "local_identifier": "otf___topic___tcof",
      "entity_type": "topic",
      "labels": {
        "none": "tcof"
      }
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

## Get Topic — `GET /api/v1/topics/{local_identifier}`

`{local_identifier}` is the value returned in `local_identifier` (the `otf:` prefix is restored internally), or a full subject URI. It is compared against the subject IRI only; unlike `/products/{id}`, identifier values (e.g. a Wikidata QID) are not accepted here — use the `identifiers.value` filter on the list endpoint instead.

The response has the same `@context` and a single `topic` object in `@graph`. There is no `meta` block.

## Topic Fields

| Field | Type | Required | Source | Description |
|-------|------|----------|--------|-------------|
| `local_identifier` | string | Yes | subject IRI | `otf:` prefix removed |
| `entity_type` | string | Yes | – | Always `topic` |
| `labels` | object | No | `skos:prefLabel` | Language-keyed labels, one per language |
| `identifiers` | array | No | `datacite:hasIdentifier` | `{value, scheme}` objects |

Label language keys are the literal's language tag when it is two letters, otherwise `none` (untagged or e.g. `@und` labels). When several labels share a language key, the alphabetically first one is kept, so the choice is stable across requests.

### Identifiers

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `value` | string | `silvio:hasLiteralValue` | Identifier value |
| `scheme` | string | `datacite:usesIdentifierScheme` | Local name of the scheme IRI, lowercased (e.g. `datacite:wikidata` → `wikidata`) |

Identifiers without a value are omitted.

## Error Responses

| Status | When | Body |
|--------|------|------|
| `404` | Single topic not found | `{"detail": "Topic not found"}` |
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
curl http://localhost:41012/api/v1/topics

# English topics with "energy" in a label
curl -G http://localhost:41012/api/v1/topics \
  --data-urlencode "filter=cf.search.labels:energy,cf.search.language:en"

# Single topic
curl http://localhost:41012/api/v1/topics/otf___topic___tcof
```

### Python Example
```python
import requests

response = requests.get(
    "http://localhost:41012/api/v1/topics",
    params={"page_size": 20, "filter": "identifiers.scheme:wikidata"},
)
data = response.json()

for topic in data["@graph"]:
    label = topic.get("labels", {}).get("en") or next(iter(topic.get("labels", {}).values()), None)
    ids = [i["value"] for i in topic.get("identifiers", [])]
    print(topic["local_identifier"], label, ids)
```

## Pagination Logic

Offset-based: `OFFSET = (page - 1) * page_size`.

The list template selects one page of **distinct** `fabio:SubjectTerm` subjects in a subquery (`ORDER BY ?s`), so `LIMIT`/`OFFSET` count topics rather than result rows (a topic with several labels or identifiers still counts once).

## SPARQL Queries

| Endpoint | Template | Setting |
|----------|----------|---------|
| List | `resources/sparql/topics.txt` | `sparql_topics_path` |
| Single | `resources/sparql/topic.txt` | `sparql_topic_path` |

```toml
[default]
sparql_topic_path = "@format {env[BASE_DIR]}/resources/sparql/topic.txt"
sparql_topics_path = "@format {env[BASE_DIR]}/resources/sparql/topics.txt"
```

The list template must contain the `#FILTERS#` and `#PAGINATION#` placeholders. The single-topic template has no placeholder: the `FILTER(STR(?s) = "...")` clause is inserted before the final closing brace of its `WHERE` block. Filter keys are translated to SPARQL by the shared `commons.build_filter_patterns()`, driven by the `TOPIC_FILTERS` table in `topics.py`.

## Implementation

| File | Contents |
|------|----------|
| `src/ost_clairin_skg/api/v1/topics.py` | `get_topics()`, `get_topic()`, `TOPIC_FILTERS`, `extract_topic()` |
| `src/ost_clairin_skg/api/v1/products.py` | Reuses `extract_topic()` for product topics |
| `src/ost_clairin_skg/infra/commons.py` | `build_topics_sparql()`, `build_topic_sparql()`, `build_filter_patterns()`, namespaces and context URLs |
| `resources/sparql/topics.txt`, `topic.txt` | SPARQL CONSTRUCT templates |
| `tests/test_topics_endpoint.py` | Unit tests |

## Known Limitations

- No `total_items` in `part_of`.
- `next_page` is emitted even when the current page is the last one.
- Only one label per language is returned; additional labels in the same language are dropped.
- The single-topic endpoint does not resolve identifier values.

## Testing

```bash
uv run pytest tests/test_topics_endpoint.py
```

## References

- **SKG-IF Topic**: https://skg-if.github.io/interoperability-framework/docs/topic.html
- **SKG-IF API / Pagination**: https://skg-if.github.io/interoperability-framework/docs/api.html#pagination
- **Related**: `PRODUCTS_ENDPOINT.md`, `PERSONS_ENDPOINT.md`, `ORGANISATIONS_ENDPOINT.md`, `SERVICES_ENDPOINT.md`

---

**Status**: ✅ IMPLEMENTED

**Last Updated**: 2026-10-01

**Version**: 1.0
