# `/products` Endpoint Documentation

## Overview

The `/products` endpoints return research products (SKG-IF `entity_type: product`) in SKG-IF compliant JSON-LD. Products are all `fabio:Work` subjects in the triplestore.

## Endpoints

```
GET /api/v1/products                 # paginated, filterable list
GET /api/v1/products/{id}            # single product
```

## List Products — `GET /api/v1/products`

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number (1-based, minimum: 1) |
| `limit` | integer | No | 10 | Number of items per page (range: 1-100) |
| `page_size` | integer | No | – | Alias for `limit` (range: 1-100); overrides `limit` when provided |
| `filter` | string | No | – | Comma-separated `name:value` pairs (see [Filtering](#filtering)) |

### Filtering

`filter` is a comma-separated list of `name:value` pairs, combined with AND. The value is everything after the first `:`, so URIs can be used as values; values cannot contain commas.

| Key | Description |
|-----|-------------|
| `product_type` / `type` | `literature`, `research data`, `research software`, `other`, or an RDF type URI (see [Product Types](#product-types)) |
| `cf.search.title` / `title` | Case-insensitive substring match on title |
| `cf.search.title_abstract` | Case-insensitive substring match on title **or** abstract |
| `cf.contributions_orcid` | ORCID of a contributor |
| `cf.contributions_aff_ror` | ROR URI (exact) or ROR value (substring) of a contributor affiliation |
| `cf.contributions_aff_country` | Country code of a contributor affiliation (case-insensitive) |
| `cf.cites` | URI or identifier value of a cited product |
| `cf.cited_by` | URI or identifier value of a citing product |
| `cf.cites_doi` | DOI of a cited product |
| `cf.cited_by_doi` | DOI of a citing product |

For backward compatibility, keys starting with `contributions.person.identifiers.id` or `contributions.person.identifiers.scheme`, and any key ending in `.scheme`, are also accepted. They match against the **product's own** identifiers.

Any other key returns `422` with the unsupported keys listed.

#### Filter examples

```
/products?filter=product_type:literature
/products?filter=product_type:research data,cf.search.title:corpus
/products?filter=cf.search.title:ocean&page=1&page_size=5
/products?filter=cf.search.title_abstract:speech
/products?filter=cf.contributions_orcid:0000-0002-1825-0097
/products?filter=cf.cites_doi:10.1038/sdata.2016.18
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
      "local_identifier": "product-1",
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
      "local_identifier": "product-2",
      "entity_type": "product",
      "product_type": "other"
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
- The page size is added to the URLs (as `limit` or `page_size`, whichever the client used) only when it differs from 10.
- `next_page` is always present, even on the last page; there is no `total_items`.
- The `filter` parameter is **not** carried over into the `meta` URLs (unlike `/persons`, `/organisations` and `/services`).

## Get Product — `GET /api/v1/products/{id}`

`{id}` may be:
- a local identifier as returned in `local_identifier` (e.g. `product-1`),
- a full subject URI (URL-encoded slashes are supported), or
- the value of one of the product's identifiers, e.g. a DOI (`/products/10.1038/sdata.2016.18`).

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
      "local_identifier": "product-1",
      "entity_type": "product",
      "product_type": "research data",
      "titles": { "en": ["Product Title"] },
      "identifiers": [ { "value": "10.1038/example", "scheme": "doi" } ]
    }
  ]
}
```

The `local_identifier` echoes the requested `{id}` (without the `otf:` prefix).

## Product Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `local_identifier` | string | Yes | Subject IRI with the internal `otf:` prefix removed |
| `entity_type` | string | Yes | Always `product` |
| `product_type` | string | Yes | See [Product Types](#product-types) |
| `titles` | object | No | Language-keyed titles (`dc:title`) |
| `abstracts` | object | No | Language-keyed abstracts (`dc:abstract`) |
| `identifiers` | array | No | `{value, scheme}` objects (`datacite:hasIdentifier`) |
| `topics` | array | No | `{term: topic}` objects; see [Topics](#topics) |
| `manifestations` | array | No | See [Manifestations](#manifestations) |

Language keys are the literal's language tag when it is two letters, otherwise `none`. A leading `{code:...}` marker in harvested text is stripped. Identifier schemes are the lowercased local name of the scheme IRI (e.g. `datacite:doi` → `doi`).

### Topics

A topic is a `fabio:SubjectTerm` reached via `bido:holdsBibliometricDataInTime/bido:withBibliometricData` (the SKG-IF RDF mapping of product topics). Each `term` has the same shape as a `/topics` item: `local_identifier` (without `otf:`), `entity_type: topic`, `labels` (one `skos:prefLabel` per language key, same language-key rule as titles) and optional `identifiers`.

```json
"topics": [
  { "term": { "local_identifier": "otf___topic___tcof", "entity_type": "topic", "labels": { "none": "tcof" } } }
]
```

### Manifestations

SKG-IF maps manifestations to the `fabio:Expression`s a work links to via `frbr:realization`. In this triplestore the manifestation's fields sit on the Expression's `frbr:embodiment` (a `fabio:Manifestation`), so they are read from there:

| Field | Source | Notes |
|-------|--------|-------|
| `access_rights.status` | `pso:holdsStatusInTime/pso:withStatus` | `pso:open-access` → `open`, `closed-access` → `closed`, `restricted-access` → `restricted`, `embargoed` → `embargoed`, `unpublished` → `unavailable`; other statuses are ignored |
| `access_rights.description` | `rdfs:comment` on the status | |
| `license` | `dcterms:license` | IRIs only. Local codes such as `PUB`, `RES` and `UNSPECIFIED` are skipped. If there are several licences, the first in sort order is used |
| `biblio.hosting_data_source` | `dcat:accessService` | `{local_identifier, entity_type: datasource, name}`, where `name` comes from `foaf:name`. If there are several, the first in sort order is used |

`license` and `hosting_data_source` (nested in `biblio`) follow the names in the SKG-IF 1.1.0 JSON-LD context. A manifestation with none of these fields is left out. `type`, `dates`, `identifiers`, `peer_review` and `version` are not in the data, so they are not output.

```json
"manifestations": [
  {
    "access_rights": { "status": "open" },
    "license": "http://www.apache.org/licenses/LICENSE-2.0",
    "biblio": {
      "hosting_data_source": {
        "local_identifier": "otf___ds___ims_clarin_d_centre_university_of_stuttgart",
        "entity_type": "datasource",
        "name": "IMS, CLARIN-D Centre, University of Stuttgart"
      }
    }
  }
]
```

### Product Types

`product_type` is derived from the fabio classes a work carries besides `fabio:Work`:

| `product_type` | fabio classes |
|----------------|---------------|
| `research data` | `Dataset` |
| `research software` | `Software` |
| `literature` | `Article`, `JournalArticle`, `Book`, `BookChapter`, `ConferencePaper`, `Thesis`, `Report` |
| `other` | none of the above |

In the `product_type` filter, `publication` and `text` are accepted as aliases for `literature`. Any other non-URI value is matched as a substring of the RDF type URI.

## Error Responses

| Status | When | Body |
|--------|------|------|
| `404` | Single product not found | `{"detail": "Product not found"}` |
| `422` | Unsupported filter key | `{"detail": "Unsupported filter(s) requested", "unsupported_filters": [...]}` |
| `422` | URI value of `product_type`/`type`, `cf.contributions_aff_ror`, `cf.cites` or `cf.cited_by` contains characters not allowed in an IRI | `{"detail": "Invalid IRI(s) in filter", "invalid_iris": [...]}` |
| `422` | Invalid `page`/`limit`/`page_size`, or `filter` not in `name:value` form | FastAPI validation error |
| `502` | Triplestore query failed | `{"detail": "Failed to query triplestore", "error": "..."}` |
| `502` | RDF → JSON-LD conversion failed | `{"detail": "Failed to convert triplestore response to JSON-LD", "error": "..."}` |

## Response Headers

```
Content-Type: application/ld+json
```

## Usage Examples

```bash
# First page, default size
curl http://localhost:41012/api/v1/products

# Page 3 with 15 items (products 31-45)
curl "http://localhost:41012/api/v1/products?page=3&limit=15"

# Filtered
curl -G http://localhost:41012/api/v1/products \
  --data-urlencode "filter=product_type:research data,cf.search.title:corpus"

# Single product by DOI
curl http://localhost:41012/api/v1/products/10.1038/sdata.2016.18
```

### Python Example
```python
import requests

response = requests.get(
    "http://localhost:41012/api/v1/products",
    params={"page": 1, "page_size": 20, "filter": "product_type:literature"},
)
data = response.json()

next_page = data["meta"]["next_page"]["local_identifier"]
for product in data["@graph"]:
    print(product["local_identifier"], product["product_type"])
    if "titles" in product:
        print("  Title:", next(iter(product["titles"].values()))[0])
```

## Pagination Logic

Offset-based: `OFFSET = (page - 1) * limit`.

The list template selects one page of **distinct** subjects in a subquery (`ORDER BY ?s`), so `LIMIT`/`OFFSET` count products rather than result rows, and page contents are stable between requests.

## SPARQL Queries

| Endpoint | Template | Setting |
|----------|----------|---------|
| List | `resources/sparql/products.txt` | `sparql_products_path` |
| Single | `resources/sparql/product.txt` | `sparql_product_path` |

```toml
[default]
sparql_product_path = "@format {env[BASE_DIR]}/resources/sparql/product.txt"
sparql_products_path = "@format {env[BASE_DIR]}/resources/sparql/products.txt"
```

The list template must contain the placeholders `#FILTERS#` (inside the subquery) and `#PAGINATION#` (replaced by `LIMIT`/`OFFSET`); a template missing either raises an error. For the single-product template, the id filter is inserted before the final closing `}`.

## Data Flow

```
1. Validate page / limit / page_size / filter
2. Translate filter pairs to SPARQL patterns (422 on unsupported keys)
3. Fill products.txt: #FILTERS# and #PAGINATION#
4. Query GraphDB (CONSTRUCT → Turtle)
5. Parse Turtle; for each fabio:Work extract product_type, titles, abstracts, identifiers, topics
6. Build meta (current / next page, search result)
7. Return JSON-LD with the SKG-IF contexts
```

## Implementation

| File | Contents |
|------|----------|
| `src/ost_clairin_skg/api/v1/products.py` | `get_products()`, `get_product()`, filter translation, RDF → JSON-LD conversion |
| `src/ost_clairin_skg/infra/commons.py` | `build_products_sparql()`, `build_product_sparql()`, `build_filter_clause()`, `otf:` prefix helpers |
| `resources/sparql/products.txt`, `product.txt` | SPARQL CONSTRUCT templates |
| `tests/test_product_endpoint.py` | Unit tests |

## Known Limitations

- No `total_items` in `part_of`; this would need a separate `COUNT` query.
- `next_page` is emitted even when the current page is the last one.
- `filter` is not included in the pagination URLs.
- OFFSET pagination may get slow for deep pages on large datasets.

## Testing

```bash
uv run pytest tests/test_product_endpoint.py
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Empty `@graph` | No matching `fabio:Work` data, or filter too narrow | Check GraphDB data; run the logged SPARQL (DEBUG level) directly |
| Incorrect pagination URLs | Request base URL misconfigured | Check proxy / forwarded headers |
| `502` | GraphDB unreachable or SPARQL error | Check logs and the GraphDB connection |

## References

- **SKG-IF Research Products**: https://skg-if.github.io/interoperability-framework/docs/research-product.html
- **SKG-IF API / Pagination**: https://skg-if.github.io/interoperability-framework/docs/api.html#pagination
- **JSON-LD Specification**: https://www.w3.org/TR/json-ld11/
- **Related**: `PERSONS_ENDPOINT.md`, `ORGANISATIONS_ENDPOINT.md`, `SERVICES_ENDPOINT.md`

---

**Status**: ✅ IMPLEMENTED

**Last Updated**: 2026-09-28

**Version**: 1.1
