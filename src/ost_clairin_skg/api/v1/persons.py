import json
import logging
import rdflib
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import API_PREFIX, SKG_IF_CONTEXT_API, SKG_IF_CONTEXT_ONTOLOGY
from src.ost_clairin_skg.infra.commons import DATACITE, SILVIO, FOAF
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore, count_triplestore
router = APIRouter(prefix=API_PREFIX)

# filter key -> (graph pattern with {v} as the value variable, match mode)
# The pattern is prefixed with the subject ?s; identifier filters go through an intermediate node.
PERSON_FILTERS = {
    "name": ("foaf:name {v}", "exact"),
    "given_name": ("foaf:givenName {v}", "exact"),
    "family_name": ("foaf:familyName {v}", "exact"),
    "cf.search.name": ("foaf:name {v}", "contains"),
    "cf.search.given_name": ("foaf:givenName {v}", "contains"),
    "cf.search.family_name": ("foaf:familyName {v}", "contains"),
    "identifiers.id": ("datacite:hasIdentifier/silvio:hasLiteralValue {v}", "exact"),
    "identifiers.scheme": ("datacite:hasIdentifier/datacite:usesIdentifierScheme {v}", "scheme"),
}


def _extract_person(g: rdflib.Graph, subject, local_identifier: str) -> Dict[str, Any]:
    person: Dict[str, Any] = {
        "local_identifier": local_identifier,
        "entity_type": "person",
    }

    for key, predicate in (("name", FOAF.name), ("given_name", FOAF.givenName), ("family_name", FOAF.familyName)):
        value = g.value(subject, predicate)
        if value is not None:
            person[key] = str(value)

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
        person["identifiers"] = identifiers

    return person


def _parse(turtle_data: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")
    return g


def _rdf_graph_to_persons(turtle_data: str) -> List[Dict[str, Any]]:
    """Convert RDF turtle data to a list of SKG-IF persons."""
    g = _parse(turtle_data)
    return [_extract_person(g, s, commons.strip_local_id_prefix(str(s))) for s in g.subjects(rdflib.RDF.type, FOAF.Person)]


def _rdf_graph_to_person(turtle_data: str, person_id: str) -> Optional[Dict[str, Any]]:
    """Convert RDF turtle data to a single SKG-IF person, or None if no foaf:Person is present."""
    g = _parse(turtle_data)
    subject = next(g.subjects(rdflib.RDF.type, FOAF.Person), None)
    if subject is None:
        return None
    return _extract_person(g, subject, person_id)


def _build_context(base_url: str) -> List[Any]:
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {"@base": f"{base_url}/"},
    ]


@router.get("/persons", tags=["Person"])
def get_persons(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated filter_name:filter_value elements. "
            "Supported keys: identifiers.id, identifiers.scheme, given_name, family_name, name, "
            "cf.search.family_name, cf.search.given_name, cf.search.name"
        ),
    ),
) -> JSONResponse:
    """List persons with pagination and optional filtering.

    Returns a paginated JSON-LD response following the SKG-IF specification. Each item in
    `@graph` is an `entity_type: person` object (SKG-IF Agent).

    **Filtering** — supply comma-separated `name:value` pairs.
    Supported filter keys:

    | Key | Description |
    |-----|-------------|
    | `given_name` | Exact match on given (first) name |
    | `family_name` | Exact match on family (last) name |
    | `name` | Exact match on full name |
    | `cf.search.given_name` | Case-insensitive substring match on given name |
    | `cf.search.family_name` | Case-insensitive substring match on family name |
    | `cf.search.name` | Case-insensitive substring match on full name |
    | `identifiers.id` | Exact match on any identifier value |
    | `identifiers.scheme` | Identifier scheme (e.g. `orcid`), case-insensitive |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `422` — unsupported filter key supplied
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get persons endpoint called with page=%d, page_size=%d, filter=%s", page, page_size, filter)

    filter_clause = None
    if filter:
        filter_clause, unsupported = commons.build_filter_patterns(filter, PERSON_FILTERS)
        if unsupported:
            return JSONResponse(status_code=422, content={
                "detail": "Unsupported filter(s) requested",
                "unsupported_filters": unsupported,
            })

    offset = (page - 1) * page_size
    sparql = commons.build_persons_sparql(limit=page_size, offset=offset, filter_clause=filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
        total_items = count_triplestore(commons.build_count_sparql("sparql_persons_path", filter_clause))
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        persons = _rdf_graph_to_persons(turtle_data) if turtle_data else []
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    base_url = str(request.base_url).rstrip("/")
    search_url = f"{base_url}{API_PREFIX}/persons"

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
        "@graph": persons,
    }

    if offset + page_size < total_items:
        response["meta"]["next_page"] = {
            "local_identifier": page_url(page + 1),
            "entity_type": "search_result_page",
        }

    return JSONResponse(content=response, media_type="application/ld+json")


@router.get("/persons/{local_identifier:path}", tags=["Person"])
def get_person(
    request: Request,
    local_identifier: str = Path(..., description="The local identifier of the person"),
) -> JSONResponse:
    """Retrieve a single person by local identifier.

    Returns a JSON-LD document following the SKG-IF specification (`entity_type: person`).

    **Responses**
    - `200` — person found, returns JSON-LD
    - `404` — no person with the given identifier
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get person endpoint called for local_identifier=%s", local_identifier)

    filter_clause = f"FILTER(STR(?s) = {json.dumps(commons.add_local_id_prefix(local_identifier))}) ."
    sparql = commons.build_person_sparql(filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        person = _rdf_graph_to_person(turtle_data, commons.strip_local_id_prefix(local_identifier)) if turtle_data else None
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    if person is None:
        return JSONResponse(status_code=404, content={"detail": "Person not found"})

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={"@context": _build_context(base_url), "@graph": [person]},
        media_type="application/ld+json",
    )
