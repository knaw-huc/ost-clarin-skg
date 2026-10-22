import json
import logging
import rdflib
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import API_PREFIX, SKG_IF_CONTEXT_API, SKG_IF_CONTEXT_ONTOLOGY
from src.ost_clairin_skg.infra.commons import DATACITE, SILVIO, FOAF, DC, FABIO, FRAPO, PRISM
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore, count_triplestore

router = APIRouter(prefix=API_PREFIX)

VENUE_FILTERS = {
    "name": ("foaf:name {v}", "exact"),
    "cf.search.name": ("foaf:name {v}", "contains"),
    "acronym": ("frapo:hasAcronym {v}", "exact"),
    "identifiers.id": ("datacite:hasIdentifier/silvio:hasLiteralValue {v}", "exact"),
    "identifiers.scheme": ("datacite:hasIdentifier/datacite:usesIdentifierScheme {v}", "scheme"),
}
VENUE_TYPES = {
    "journal": FABIO.Journal,
    "conference": FABIO.ConferenceProceedings,
    "book": FABIO.Book,
    "repository": FABIO.Repository,
    "other": FABIO.Work,
}
UNKNOWN_VENUE_TYPE = "unknown"

def type_filter_clause(venue_type: str) -> Optional[str]:
    """Return the SPARQL pattern restricting ?s to the given SKG-IF venue type, or None if the type is invalid."""
    venue_type = venue_type.strip().lower()
    if venue_type in VENUE_TYPES:
        return f"?s a <{VENUE_TYPES[venue_type]}> ."
    if venue_type == UNKNOWN_VENUE_TYPE:
        classes = " ".join(f"<{c}>" for c in VENUE_TYPES.values())
        return f"FILTER NOT EXISTS {{ ?s a ?ft . VALUES ?ft {{ {classes} }} }} ."
    return None


def extract_venue(g: rdflib.Graph, subject, local_identifier: str) -> Dict[str, Any]:
    venue: Dict[str, Any] = {
        "local_identifier": local_identifier,
        "entity_type": "venue",
    }

    identifiers: list = []
    for id_node in g.objects(subject, DATACITE.hasIdentifier):
        id_obj: Dict[str, Any] = {"value": None, "scheme": None}

        for literal_val in g.objects(id_node, SILVIO.hasLiteralValue):
            id_obj["value"] = str(literal_val)

        for scheme in g.objects(id_node, DATACITE.usesIdentifierScheme):
            scheme_str = str(scheme)
            if "#" in scheme_str:
                id_obj["scheme"] = scheme_str.split("#")[-1].lower()
            else:
                id_obj["scheme"] = scheme_str.split("/")[-1].lower()

        if id_obj["value"]:
            identifiers.append(id_obj)

    if identifiers:
        venue["identifiers"] = identifiers

    names = sorted(str(n) for n in g.objects(subject, FOAF.name))
    if names:
        venue["name"] = names[0]

    types = set(g.objects(subject, rdflib.RDF.type))
    venue["type"] = next((t for t, cls in VENUE_TYPES.items() if cls in types), UNKNOWN_VENUE_TYPE)

    for key, predicate in (
        ("acronym", FRAPO.hasAcronym),
        ("series", PRISM.seriesTitle),
        ("creation_date", DC.created),
    ):
        value = g.value(subject, predicate)
        if value is not None:
            venue[key] = str(value)

    return venue

def parse_graph_data(turtle_data: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")
    return g

def rdf_graph_to_venues(turtle_data: str) -> List[Dict[str, Any]]:
    """Convert RDF turtle data to a list of SKG-IF venues."""
    g = parse_graph_data(turtle_data)
    return [
        extract_venue(g,
                      s,
                      commons.strip_local_id_prefix(str(s))) for s in g.subjects(rdflib.RDF.type, FABIO.ExpressionCollection)
    ]

def rdf_graph_to_venue(turtle_data: str, venue_id: str) -> Optional[Dict[str, Any]]:
    """Convert RDF turtle data to a single SKG-IF venue, or None if no fabio:ExpressionCollection is present."""
    g = parse_graph_data(turtle_data)
    subject = next(g.subjects(rdflib.RDF.type, FABIO.ExpressionCollection), None)
    if subject is None:
        return None
    return extract_venue(g, subject, venue_id)

def _build_context(base_url: str) -> List[Any]:
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {"@base": f"{base_url}/"},
    ]


@router.get("/venues", tags=["Venue"])
def get_venues(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated filter_name:filter_value elements. "
            "Supported keys: name, cf.search.name, acronym, type, identifiers.id, identifiers.scheme"
        ),
    ),
) -> JSONResponse:
    """List venues with pagination and optional filtering.

    Returns a paginated JSON-LD response following the SKG-IF specification. Each item in
    `@graph` is an `entity_type: venue` object.

    **Filtering** — supply comma-separated `name:value` pairs.
    Supported filter keys:

    | Key | Description |
    |-----|-------------|
    | `name` | Exact match on any name |
    | `cf.search.name` | Case-insensitive substring match on any name |
    | `acronym` | Exact match on acronym |
    | `type` | Venue type: `journal`, `conference`, `book`, `repository`, `other` or `unknown` |
    | `identifiers.id` | Exact match on any identifier value |
    | `identifiers.scheme` | Identifier scheme (e.g. `issn`), case-insensitive |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `422` — unsupported filter key or venue type supplied
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get venues endpoint called with page=%d, page_size=%d, filter=%s", page, page_size, filter)

    filter_clause = None
    if filter:
        # `type` maps a value to a class rather than matching a literal, so it is handled here
        type_clauses: List[str] = []
        other_parts: List[str] = []
        for part in (p.strip() for p in filter.split(",")):
            name, _, value = part.partition(":")
            if name.strip() != "type":
                other_parts.append(part)
                continue
            clause = type_filter_clause(value)
            if clause is None:
                return JSONResponse(status_code=422, content={
                    "detail": "Unsupported venue type requested",
                    "supported_types": [*VENUE_TYPES, UNKNOWN_VENUE_TYPE],
                })
            type_clauses.append(clause)

        filter_clause, unsupported = commons.build_filter_patterns(",".join(other_parts), VENUE_FILTERS)
        if unsupported:
            return JSONResponse(status_code=422, content={
                "detail": "Unsupported filter(s) requested",
                "unsupported_filters": unsupported,
            })
        filter_clause = "\n    ".join(c for c in [filter_clause, *type_clauses] if c) or None

    offset = (page - 1) * page_size
    sparql = commons.build_venues_sparql(limit=page_size, offset=offset, filter_clause=filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
        total_items = count_triplestore(commons.build_count_sparql("sparql_venues_path", filter_clause))
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        venues = rdf_graph_to_venues(turtle_data) if turtle_data else []
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    base_url = str(request.base_url).rstrip("/")
    search_url = f"{base_url}{API_PREFIX}/venues"

    def page_url(p: Optional[int]) -> str:
        params: Dict[str, Any] = {}
        if p is not None:
            params["page"] = p
        if page_size != 10:
            params["page_size"] = page_size
        if filter:
            params["filter"] = filter
        return f"{search_url}?{urlencode(params)}" if params else search_url

    response = {
        "@context": _build_context(base_url),
        "meta": {
            "local_identifier": page_url(page),
            "entity_type": "search_result_page",
            "part_of": {
                "local_identifier": page_url(None),
                "entity_type": "search_result",
                "total_items": total_items,
            },
        },
        "@graph": venues,
    }

    if offset + page_size < total_items:
        response["meta"]["next_page"] = {
            "local_identifier": page_url(page + 1),
            "entity_type": "search_result_page",
        }

    return JSONResponse(content=response, media_type="application/ld+json")


@router.get("/venues/{local_identifier:path}", tags=["Venue"])
def get_venue(
    request: Request,
    local_identifier: str = Path(..., description="The local identifier of the venue"),
) -> JSONResponse:
    """Retrieve a single venue by local identifier.

    Returns a JSON-LD document following the SKG-IF specification (`entity_type: venue`).

    **Responses**
    - `200` — venue found, returns JSON-LD
    - `404` — no venue with the given identifier
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get venue endpoint called for local_identifier=%s", local_identifier)

    filter_clause = f"FILTER(STR(?s) = {json.dumps(commons.add_local_id_prefix(local_identifier))}) ."
    sparql = commons.build_venue_sparql(filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        venue = rdf_graph_to_venue(turtle_data, commons.strip_local_id_prefix(local_identifier)) if turtle_data else None
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    if venue is None:
        return JSONResponse(status_code=404, content={"detail": "Venue not found"})

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={"@context": _build_context(base_url), "@graph": [venue]},
        media_type="application/ld+json",
    )
