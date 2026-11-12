import json
import logging
import rdflib
from typing import Any, Callable, Dict, List, Optional
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import API_PREFIX
from src.ost_clairin_skg.infra.commons import DCAT, FABIO, FOAF, FRAPO
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore, count_triplestore

router = APIRouter(prefix=API_PREFIX)

DATASOURCE_FILTERS = {
    "name": ("foaf:name {v}", "exact"),
    "cf.search.name": ("foaf:name {v}", "contains"),
}
DATASOURCE_CLASSIFICATIONS = {
    "repository": FRAPO.Repository,
}

RESEARCH_PRODUCT_TYPES: Dict[str, List[rdflib.URIRef]] = {
    "research data": [FABIO.Dataset],
    "software": [FABIO.Software],
    "literature": [FABIO[c] for c in (
        "Article", "JournalArticle", "Book", "BookChapter", "ConferencePaper", "Thesis", "Report",
    )],
}

def classification_filter_clause(classification: str) -> Optional[str]:
    """Return the SPARQL pattern restricting ?s to the given classification, or None if it is unsupported."""
    cls = DATASOURCE_CLASSIFICATIONS.get(classification.strip().lower())
    return f"?s a <{cls}> ." if cls else None


def research_product_type_filter_clause(product_type: str) -> Optional[str]:
    """Return the SPARQL pattern restricting ?s to data sources hosting products of the given type, or None if it is unsupported."""
    classes = RESEARCH_PRODUCT_TYPES.get(product_type.strip().lower())
    if not classes:
        return None
    values = ", ".join(f"<{c}>" for c in classes)
    return (
        "FILTER EXISTS { ?fw frbr:realization/frbr:embodiment/dcat:accessService ?s ; a ?fwt . "
        f"FILTER(?fwt IN ({values})) }} ."
    )

# Filters that map a value to a SPARQL pattern rather than matching a literal: key -> (clause builder, supported values)
SPECIAL_FILTERS: Dict[str, tuple[Callable[[str], Optional[str]], List[str]]] = {
    "data_source_classification": (classification_filter_clause, list(DATASOURCE_CLASSIFICATIONS)),
    "research_product_type": (research_product_type_filter_clause, list(RESEARCH_PRODUCT_TYPES)),
}

def extract_datasource(g: rdflib.Graph, subject, local_identifier: str) -> Dict[str, Any]:
    datasource: Dict[str, Any] = {
        "local_identifier": local_identifier,
        "entity_type": "datasource",
    }

    names = sorted(str(n) for n in g.objects(subject, FOAF.name))
    if names:
        datasource["name"] = names[0]

    types = set(g.objects(subject, rdflib.RDF.type))
    classification = next((c for c, cls in DATASOURCE_CLASSIFICATIONS.items() if cls in types), None)
    if classification:
        datasource["data_source_classification"] = classification

    hosted_types = {t for w in g.objects(subject, DCAT.servesDataset) for t in g.objects(w, rdflib.RDF.type)}
    product_types = [pt for pt, classes in RESEARCH_PRODUCT_TYPES.items() if hosted_types.intersection(classes)]
    if product_types:
        datasource["research_product_types"] = product_types

    return datasource

def parse_graph_data(turtle_data: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")
    return g

def rdf_graph_to_datasources(turtle_data: str) -> List[Dict[str, Any]]:
    """Convert RDF turtle data to a list of SKG-IF data sources."""
    g = parse_graph_data(turtle_data)
    return [
        extract_datasource(g,
                           s,
                           commons.strip_local_id_prefix(str(s))) for s in g.subjects(rdflib.RDF.type, DCAT.DataService)
    ]

def rdf_graph_to_datasource(turtle_data: str, datasource_id: str) -> Optional[Dict[str, Any]]:
    """Convert RDF turtle data to a single SKG-IF data source, or None if no dcat:DataService is present."""
    g = parse_graph_data(turtle_data)
    subject = next(g.subjects(rdflib.RDF.type, DCAT.DataService), None)
    if subject is None:
        return None
    return extract_datasource(g, subject, datasource_id)


@router.get("/datasources", tags=["Datasource"])
def get_datasources(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated filter_name:filter_value elements. "
            "Supported keys: name, cf.search.name, data_source_classification, research_product_type"
        ),
    ),
) -> JSONResponse:
    """List data sources with pagination and optional filtering.

    Returns a paginated JSON-LD response following the SKG-IF specification. Each item in
    `@graph` is an `entity_type: datasource` object.

    **Filtering** — supply comma-separated `name:value` pairs.
    Supported filter keys:

    | Key | Description |
    |-----|-------------|
    | `name` | Exact match on any name |
    | `cf.search.name` | Case-insensitive substring match on any name |
    | `data_source_classification` | Classification: `repository` |
    | `research_product_type` | Hosts products of type `research data`, `software` or `literature` |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `422` — unsupported filter key or filter value supplied
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get datasources endpoint called with page=%d, page_size=%d, filter=%s", page, page_size, filter)

    filter_clause = None
    if filter:
        special_clauses: List[str] = []
        other_parts: List[str] = []
        for part in (p.strip() for p in filter.split(",")):
            name, _, value = part.partition(":")
            if name.strip() not in SPECIAL_FILTERS:
                other_parts.append(part)
                continue
            build_clause, supported_values = SPECIAL_FILTERS[name.strip()]
            clause = build_clause(value)
            if clause is None:
                return JSONResponse(status_code=422, content={
                    "detail": f"Unsupported {name.strip()} requested",
                    "supported_values": supported_values,
                })
            special_clauses.append(clause)

        filter_clause, unsupported = commons.build_filter_patterns(",".join(other_parts), DATASOURCE_FILTERS)
        if unsupported:
            return JSONResponse(status_code=422, content={
                "detail": "Unsupported filter(s) requested",
                "unsupported_filters": unsupported,
            })
        filter_clause = "\n    ".join(c for c in [filter_clause, *special_clauses] if c) or None

    offset = (page - 1) * page_size
    sparql = commons.build_datasources_sparql(limit=page_size, offset=offset, filter_clause=filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
        total_items = count_triplestore(commons.build_count_sparql("sparql_datasources_path", filter_clause))
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        datasources = rdf_graph_to_datasources(turtle_data) if turtle_data else []
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    base_url = str(request.base_url).rstrip("/")
    search_url = f"{base_url}{API_PREFIX}/datasources"
    response = {
        "@context": commons.build_context(base_url),
        "meta": {
            "local_identifier": commons.build_page_url(page, page_size, filter, search_url),
            "entity_type": "search_result_page",
            "part_of": {
                "local_identifier": commons.build_page_url(None, page_size, filter, search_url),
                "entity_type": "search_result",
                "total_items": total_items,
            },
        },
        "@graph": datasources,
    }

    if offset + page_size < total_items:
        response["meta"]["next_page"] = {
            "local_identifier": commons.build_page_url(page + 1, page_size, filter, search_url),
            "entity_type": "search_result_page",
        }

    return JSONResponse(content=response, media_type="application/ld+json")


@router.get("/datasources/{local_identifier:path}", tags=["Datasource"])
def get_datasource(
    request: Request,
    local_identifier: str = Path(..., description="The local identifier of the datasource"),
) -> JSONResponse:
    """Retrieve a single data source by local identifier.

    Returns a JSON-LD document following the SKG-IF specification (`entity_type: datasource`).

    **Responses**
    - `200` — data source found, returns JSON-LD
    - `404` — no data source with the given identifier
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get datasource endpoint called for local_identifier=%s", local_identifier)

    filter_clause = f"FILTER(STR(?s) = {json.dumps(commons.add_local_id_prefix(local_identifier))}) ."
    sparql = commons.build_datasource_sparql(filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        datasource = rdf_graph_to_datasource(turtle_data, commons.strip_local_id_prefix(local_identifier)) if turtle_data else None
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    if datasource is None:
        return JSONResponse(status_code=404, content={"detail": "Datasource not found"})

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={"@context": commons.build_context(base_url), "@graph": [datasource]},
        media_type="application/ld+json",
    )
