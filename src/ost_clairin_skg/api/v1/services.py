import json
import logging
import rdflib
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from src.ost_clairin_skg.api.v1.organizations import _extract_organisation
from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import API_PREFIX, SKG_IF_CONTEXT_ONTOLOGY, SKG_IF_CONTEXT_API, SKG_IF_CONTEXT_EXT_SRV
from src.ost_clairin_skg.infra.commons import DC, FOAF, SRV
from src.ost_clairin_skg.infra.commons import LANG_CODE_PREFIX
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore

router = APIRouter(prefix=API_PREFIX)

# Organisation / venue classes -> SKG-IF srv extension types
ORGANISATION_TYPES = {
    SRV.HostingOrganisation: "srv_hosting_organisation",
    SRV.ResearchInfrastructure: "srv_research_infrastructure",
}
VENUE_TYPES = {
    SRV.Portal: "srv_portal",
}

_ORG_LINKS = {
    "relevant_organisations": "dc:relation",
    "srv_has_hosting_organisation": "srv:hasHostingOrganisation",
    "srv_has_research_infrastructure": "srv:isPartOfResearchInfrastructure",
}

# filter key -> (predicate path with {v} as the value variable, match mode); see commons.build_filter_patterns
SERVICE_FILTERS = {
    "name": ("foaf:name {v}", "exact"),
    "cf.search.name": ("foaf:name {v}", "contains"),
    "cf.search.org_name": (f"({'|'.join(_ORG_LINKS.values())})/foaf:name {{v}}", "contains"),
}
for _field, _link in _ORG_LINKS.items():
    SERVICE_FILTERS[f"{_field}.name"] = (f"{_link}/foaf:name {{v}}", "exact")
    SERVICE_FILTERS[f"{_field}.identifiers.value"] = (f"{_link}/datacite:hasIdentifier/silvio:hasLiteralValue {{v}}", "exact")
    SERVICE_FILTERS[f"{_field}.identifiers.scheme"] = (f"{_link}/datacite:hasIdentifier/datacite:usesIdentifierScheme {{v}}", "scheme")


def _extract_linked_organisation(g: rdflib.Graph, org) -> Dict[str, Any]:
    organisation = _extract_organisation(g, org, commons.strip_local_id_prefix(str(org)))
    types = sorted({ORGANISATION_TYPES[t] for t in g.objects(org, rdflib.RDF.type) if t in ORGANISATION_TYPES})
    if types:
        organisation["types"] = types
    return organisation


def _extract_venue(g: rdflib.Graph, venue) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "local_identifier": commons.strip_local_id_prefix(str(venue)),
        "entity_type": "venue",
    }
    name = g.value(venue, FOAF.name)
    if name is not None:
        result["name"] = str(name)
    homepage = g.value(venue, FOAF.homepage)
    if homepage is not None:
        result["website"] = str(homepage)
    types = sorted({VENUE_TYPES[t] for t in g.objects(venue, rdflib.RDF.type) if t in VENUE_TYPES})
    if types:
        result["types"] = types
    return result


def _extract_service(g: rdflib.Graph, subject, local_identifier: str) -> Dict[str, Any]:
    service: Dict[str, Any] = {
        "local_identifier": local_identifier,
        "entity_type": "srv_service",
    }

    name = g.value(subject, FOAF.name)
    if name is not None:
        service["name"] = str(name)

    descriptions: Dict[str, List[str]] = {}
    for description in g.objects(subject, DC.description):
        lang = getattr(description, "language", None)
        key = lang if lang and len(lang) == 2 else "none"
        descriptions.setdefault(key, []).append(LANG_CODE_PREFIX.sub("", str(description)))
    if descriptions:
        service["srv_descriptions"] = descriptions

    for field, predicate in (
        ("srv_has_hosting_organisation", SRV.hasHostingOrganisation),
        ("srv_has_research_infrastructure", SRV.isPartOfResearchInfrastructure),
        ("relevant_organisations", DC.relation),
    ):
        organisations = [_extract_linked_organisation(g, o) for o in sorted(g.objects(subject, predicate))]
        if organisations:
            service[field] = organisations

    venues = [_extract_venue(g, v) for v in sorted(g.objects(subject, SRV.hasVenue))]
    if venues:
        service["srv_venues"] = venues

    return service


def _parse(turtle_data: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")
    return g


def _rdf_graph_to_services(turtle_data: str) -> List[Dict[str, Any]]:
    """Convert RDF turtle data to a list of SKG-IF services."""
    g = _parse(turtle_data)
    return [
        _extract_service(g, s, commons.strip_local_id_prefix(str(s)))
        for s in g.subjects(rdflib.RDF.type, SRV.Service)
    ]


def _rdf_graph_to_service(turtle_data: str, service_id: str) -> Optional[Dict[str, Any]]:
    """Convert RDF turtle data to a single SKG-IF service, or None if no srv:Service is present."""
    g = _parse(turtle_data)
    subject = next(g.subjects(rdflib.RDF.type, SRV.Service), None)
    if subject is None:
        return None
    return _extract_service(g, subject, service_id)


def _build_context(base_url: str) -> List[Any]:
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {"@base": f"{base_url}/"},
        SKG_IF_CONTEXT_EXT_SRV,
    ]


@router.get("/services", tags=["Service"])
def get_services(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated filter_name:filter_value elements. "
            "Supported keys: name, cf.search.name, cf.search.org_name, "
            "{relevant_organisations|srv_has_hosting_organisation|srv_has_research_infrastructure}"
            ".{name|identifiers.scheme|identifiers.value}"
        ),
    ),
) -> JSONResponse:
    """List services with pagination and optional filtering.

    Returns a paginated JSON-LD response following the SKG-IF
    [service extension](https://skg-if.github.io/ext-srv/api/api.html). Each item in `@graph` is an
    `entity_type: srv_service` object; linked organisations and venues are expanded to full objects.

    **Filtering** — supply comma-separated `name:value` pairs.
    Supported filter keys:

    | Key | Description |
    |-----|-------------|
    | `name` | Exact match on service name |
    | `cf.search.name` | Case-insensitive substring match on service name |
    | `cf.search.org_name` | Case-insensitive substring match on any related organisation name |
    | `relevant_organisations.name` | Exact match on a relevant organisation name |
    | `srv_has_hosting_organisation.name` | Exact match on a hosting organisation name |
    | `srv_has_research_infrastructure.name` | Exact match on a research infrastructure name |
    | `<one of the three above>.identifiers.value` | Exact match on an identifier value of that organisation |
    | `<one of the three above>.identifiers.scheme` | Identifier scheme of that organisation (e.g. `ror`) |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `422` — unsupported filter key supplied
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get services endpoint called with page=%d, page_size=%d, filter=%s", page, page_size, filter)

    filter_clause = None
    if filter:
        filter_clause, unsupported = commons.build_filter_patterns(filter, SERVICE_FILTERS)
        if unsupported:
            return JSONResponse(status_code=422, content={
                "detail": "Unsupported filter(s) requested",
                "unsupported_filters": unsupported,
            })

    offset = (page - 1) * page_size
    sparql = commons.build_services_sparql(limit=page_size, offset=offset, filter_clause=filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        services = _rdf_graph_to_services(turtle_data) if turtle_data else []
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    base_url = str(request.base_url).rstrip("/")
    search_url = f"{base_url}{API_PREFIX}/services"

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
        "@graph": services,
    }

    return JSONResponse(content=response, media_type="application/ld+json")


@router.get("/services/{local_identifier:path}", tags=["Service"])
def get_service(
    request: Request,
    local_identifier: str = Path(..., description="The local identifier of the service"),
) -> JSONResponse:
    """Retrieve a single service by local identifier.

    Returns a JSON-LD document following the SKG-IF service extension (`entity_type: srv_service`).

    **Responses**
    - `200` — service found, returns JSON-LD
    - `404` — no service with the given identifier
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get service endpoint called for local_identifier=%s", local_identifier)

    filter_clause = f"FILTER(STR(?s) = {json.dumps(commons.add_local_id_prefix(local_identifier))}) ."
    sparql = commons.build_service_sparql(filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        service = _rdf_graph_to_service(turtle_data, commons.strip_local_id_prefix(local_identifier)) if turtle_data else None
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    if service is None:
        return JSONResponse(status_code=404, content={"detail": "Service not found"})

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={"@context": _build_context(base_url), "@graph": [service]},
        media_type="application/ld+json",
    )
