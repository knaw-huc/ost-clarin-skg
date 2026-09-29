import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import rdflib
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import API_PREFIX
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore

router = APIRouter(prefix=API_PREFIX)

# SKG-IF context URLs
SKG_IF_CONTEXT_ONTOLOGY = "https://w3id.org/skg-if/context/1.1.0/skg-if.json"
SKG_IF_CONTEXT_API = "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json"

DATACITE = rdflib.Namespace("http://purl.org/spar/datacite/")
SILVIO = rdflib.Namespace("http://www.essepuntato.it/2010/06/literalreification/")
FOAF = rdflib.Namespace("http://xmlns.com/foaf/0.1/")

# filter key -> (predicate path with {v} as the value variable, match mode); see commons.build_filter_patterns
ORGANISATION_FILTERS = {
    "name": ("foaf:name {v}", "exact"),
    "cf.search.name": ("foaf:name {v}", "contains"),
    "identifiers.id": ("datacite:hasIdentifier/silvio:hasLiteralValue {v}", "exact"),
    "identifiers.scheme": ("datacite:hasIdentifier/datacite:usesIdentifierScheme {v}", "scheme"),
}


def _extract_organisation(g: rdflib.Graph, subject, local_identifier: str) -> Dict[str, Any]:
    organisation: Dict[str, Any] = {
        "local_identifier": local_identifier,
        "entity_type": "organisation",
    }

    # Sorted so the primary name is stable when the source holds several spellings
    names = sorted(str(n) for n in g.objects(subject, FOAF.name))
    if names:
        organisation["name"] = names[0]
        if len(names) > 1:
            organisation["other_names"] = names[1:]

    homepage = g.value(subject, FOAF.homepage)
    if homepage is not None:
        organisation["website"] = str(homepage)

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
        organisation["identifiers"] = identifiers

    return organisation


def _parse(turtle_data: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")
    return g


def _rdf_graph_to_organisations(turtle_data: str) -> List[Dict[str, Any]]:
    """Convert RDF turtle data to a list of SKG-IF organisations."""
    g = _parse(turtle_data)
    return [_extract_organisation(g, s, commons.strip_local_id_prefix(str(s))) for s in g.subjects(rdflib.RDF.type, FOAF.Organization)]


def _rdf_graph_to_organisation(turtle_data: str, organisation_id: str) -> Optional[Dict[str, Any]]:
    """Convert RDF turtle data to a single SKG-IF organisation, or None if no foaf:Organization is present."""
    g = _parse(turtle_data)
    subject = next(g.subjects(rdflib.RDF.type, FOAF.Organization), None)
    if subject is None:
        return None
    return _extract_organisation(g, subject, organisation_id)


def _build_context(base_url: str) -> List[Any]:
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {"@base": f"{base_url}/"},
    ]


@router.get("/organisations", tags=["Organisation"])
def get_organisations(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated filter_name:filter_value elements. "
            "Supported keys: name, cf.search.name, identifiers.id, identifiers.scheme"
        ),
    ),
) -> JSONResponse:
    """List organisations with pagination and optional filtering.

    Returns a paginated JSON-LD response following the SKG-IF specification. Each item in
    `@graph` is an `entity_type: organisation` object.

    **Filtering** — supply comma-separated `name:value` pairs.
    Supported filter keys:

    | Key | Description |
    |-----|-------------|
    | `name` | Exact match on any name |
    | `cf.search.name` | Case-insensitive substring match on any name |
    | `identifiers.id` | Exact match on any identifier value |
    | `identifiers.scheme` | Identifier scheme (e.g. `ror`), case-insensitive |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `422` — unsupported filter key supplied
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get organisations endpoint called with page=%d, page_size=%d, filter=%s", page, page_size, filter)

    filter_clause = None
    if filter:
        filter_clause, unsupported = commons.build_filter_patterns(filter, ORGANISATION_FILTERS)
        if unsupported:
            return JSONResponse(status_code=422, content={
                "detail": "Unsupported filter(s) requested",
                "unsupported_filters": unsupported,
            })

    offset = (page - 1) * page_size
    sparql = commons.build_organisations_sparql(limit=page_size, offset=offset, filter_clause=filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        organisations = _rdf_graph_to_organisations(turtle_data) if turtle_data else []
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    base_url = str(request.base_url).rstrip("/")
    search_url = f"{base_url}{API_PREFIX}/organisations"

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
            "next_page": {
                "local_identifier": page_url(page + 1),
                "entity_type": "search_result_page",
            },
            "part_of": {
                "local_identifier": page_url(None),
                "entity_type": "search_result",
            },
        },
        "@graph": organisations,
    }

    return JSONResponse(content=response, media_type="application/ld+json")


@router.get("/organisations/{local_identifier:path}", tags=["Organisation"])
def get_organisation(
    request: Request,
    local_identifier: str = Path(..., description="The local identifier of the organisation"),
) -> JSONResponse:
    """Retrieve a single organisation by local identifier.

    Returns a JSON-LD document following the SKG-IF specification (`entity_type: organisation`).

    **Responses**
    - `200` — organisation found, returns JSON-LD
    - `404` — no organisation with the given identifier
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get organisation endpoint called for local_identifier=%s", local_identifier)

    filter_clause = f"FILTER(STR(?s) = {json.dumps(commons.add_local_id_prefix(local_identifier))}) ."
    sparql = commons.build_organisation_sparql(filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        organisation = _rdf_graph_to_organisation(turtle_data, commons.strip_local_id_prefix(local_identifier)) if turtle_data else None
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    if organisation is None:
        return JSONResponse(status_code=404, content={"detail": "Organisation not found"})

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={"@context": _build_context(base_url), "@graph": [organisation]},
        media_type="application/ld+json",
    )
