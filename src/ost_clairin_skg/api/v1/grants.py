import json
import logging
import rdflib
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import API_PREFIX, SKG_IF_CONTEXT_API, SKG_IF_CONTEXT_ONTOLOGY
from src.ost_clairin_skg.infra.commons import DATACITE, SILVIO, FOAF, DC, FRAPO, TI, LANG_CODE_PREFIX
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore, count_triplestore

router = APIRouter(prefix=API_PREFIX)

GRANT_FILTERS = {
    "acronym": ("frapo:hasAcronym {v}", "exact"),
    "grant_number": ("frapo:hasGrantNumber {v}", "exact"),
    "funding_stream": ("frapo:hasCallIdentifier {v}", "exact"),
    "currency": ("frapo:hasCurrencyCode {v}", "exact"),
    "cf.search.title": ("dcterms:title {v}", "contains"),
    "cf.search.acronym": ("frapo:hasAcronym {v}", "contains"),
    "identifiers.id": ("datacite:hasIdentifier/silvio:hasLiteralValue {v}", "exact"),
    "identifiers.scheme": ("datacite:hasIdentifier/datacite:usesIdentifierScheme {v}", "scheme"),
}

def _organisation_ref(node) -> Dict[str, Any]:
    return {"local_identifier": commons.strip_local_id_prefix(str(node)), "entity_type": "organisation"}

def extract_grant(g: rdflib.Graph, subject, local_identifier: str) -> Dict[str, Any]:
    grant: Dict[str, Any] = {
        "local_identifier": local_identifier,
        "entity_type": "grant",
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
        grant["identifiers"] = identifiers

    titles: Dict[str, List[str]] = {}
    for t in g.objects(subject, DC.title):
        lang = getattr(t, "language", None)
        key = lang if lang and len(lang) == 2 else "none"
        titles.setdefault(key, []).append(LANG_CODE_PREFIX.sub("", str(t)))
    if titles:
        grant["titles"] = titles

    abstracts: Dict[str, List[str]] = {}
    for a in g.objects(subject, DC.abstract):
        lang = getattr(a, "language", None)
        key = lang if lang and len(lang) == 2 else "none"
        abstracts.setdefault(key, []).append(LANG_CODE_PREFIX.sub("", str(a)))
    if abstracts:
        grant["abstracts"] = abstracts

    for key, predicate in (
        ("acronym", FRAPO.hasAcronym),
        ("grant_number", FRAPO.hasGrantNumber),
        ("funding_stream", FRAPO.hasCallIdentifier),
        ("currency", FRAPO.hasCurrencyCode),
        ("website", FOAF.homepage),
    ):
        value = g.value(subject, predicate)
        if value is not None:
            grant[key] = str(value)

    agency = g.value(subject, FRAPO.hasFundingAgency)
    if agency is not None:
        grant["funding_agency"] = _organisation_ref(agency)

    amount = g.value(subject, FRAPO.hasCurrency)
    if amount is not None:
        try:
            grant["funded_amount"] = float(amount)
        except ValueError:
            logging.warning("Ignoring non-numeric funded amount %r on %s", str(amount), subject)

    duration_node = g.value(subject, DC.temporal)
    if duration_node is not None:
        duration: Dict[str, str] = {}
        start = g.value(duration_node, TI.hasIntervalStartDate)
        end = g.value(duration_node, TI.hasIntervalEndDate)
        if start is not None:
            duration["start"] = str(start)
        if end is not None:
            duration["end"] = str(end)
        if duration:
            grant["duration"] = duration

    # Sorted so the output order is stable across queries
    beneficiaries = sorted(g.objects(subject, FRAPO.supports), key=str)
    if beneficiaries:
        grant["beneficiaries"] = [_organisation_ref(b) for b in beneficiaries]

    return grant

def parse(turtle_data: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")
    return g

def rdf_graph_to_grants(turtle_data: str) -> List[Dict[str, Any]]:
    """Convert RDF turtle data to a list of SKG-IF grants."""
    g = parse(turtle_data)
    return [
        extract_grant(g, s, commons.strip_local_id_prefix(str(s))) for s in g.subjects(rdflib.RDF.type, FRAPO.Grant)
    ]

def rdf_graph_to_grant(turtle_data: str, grant_id: str) -> Optional[Dict[str, Any]]:
    """Convert RDF turtle data to a single SKG-IF grant, or None if no frapo:Grant is present."""
    g = parse(turtle_data)
    subject = next(g.subjects(rdflib.RDF.type, FRAPO.Grant), None)
    if subject is None:
        return None
    return extract_grant(g, subject, grant_id)

def _build_context(base_url: str) -> List[Any]:
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {"@base": f"{base_url}/"},
    ]


@router.get("/grants", tags=["Grant"])
def get_grants(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated filter_name:filter_value elements. "
            "Supported keys: acronym, grant_number, funding_stream, currency, "
            "cf.search.title, cf.search.acronym, identifiers.id, identifiers.scheme"
        ),
    ),
) -> JSONResponse:
    """List grants with pagination and optional filtering.

    Returns a paginated JSON-LD response following the SKG-IF specification. Each item in
    `@graph` is an `entity_type: grant` object.

    **Filtering** — supply comma-separated `name:value` pairs.
    Supported filter keys:

    | Key | Description |
    |-----|-------------|
    | `acronym` | Exact match on acronym |
    | `grant_number` | Exact match on grant number |
    | `funding_stream` | Exact match on funding stream |
    | `currency` | Exact match on currency code |
    | `cf.search.title` | Case-insensitive substring match on any title |
    | `cf.search.acronym` | Case-insensitive substring match on acronym |
    | `identifiers.id` | Exact match on any identifier value |
    | `identifiers.scheme` | Identifier scheme (e.g. `doi`), case-insensitive |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `422` — unsupported filter key supplied
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get grants endpoint called with page=%d, page_size=%d, filter=%s", page, page_size, filter)

    filter_clause = None
    if filter:
        filter_clause, unsupported = commons.build_filter_patterns(filter, GRANT_FILTERS)
        if unsupported:
            return JSONResponse(status_code=422, content={
                "detail": "Unsupported filter(s) requested",
                "unsupported_filters": unsupported,
            })

    offset = (page - 1) * page_size
    sparql = commons.build_grants_sparql(limit=page_size, offset=offset, filter_clause=filter_clause)

    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
        total_items = count_triplestore(commons.build_count_sparql("sparql_grants_path", filter_clause))
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        grants = rdf_graph_to_grants(turtle_data) if turtle_data else []
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    base_url = str(request.base_url).rstrip("/")
    search_url = f"{base_url}{API_PREFIX}/grants"
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
        "@graph": grants,
    }

    if offset + page_size < total_items:
        response["meta"]["next_page"] = {
            "local_identifier": commons.build_page_url(page + 1, page_size, filter, search_url),
            "entity_type": "search_result_page",
        }

    return JSONResponse(content=response, media_type="application/ld+json")


@router.get("/grants/{local_identifier:path}", tags=["Grant"])
def get_grant(
    request: Request,
    local_identifier: str = Path(..., description="The local identifier of the grant"),
) -> JSONResponse:
    """Retrieve a single grant by local identifier.

    Returns a JSON-LD document following the SKG-IF specification (`entity_type: grant`).

    **Responses**
    - `200` — grant found, returns JSON-LD
    - `404` — no grant with the given identifier
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get grant endpoint called for local_identifier=%s", local_identifier)

    filter_clause = f"FILTER(STR(?s) = {json.dumps(commons.add_local_id_prefix(local_identifier))}) ."
    sparql = commons.build_grant_sparql(filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        grant = rdf_graph_to_grant(turtle_data, commons.strip_local_id_prefix(local_identifier)) if turtle_data else None
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    if grant is None:
        return JSONResponse(status_code=404, content={"detail": "Grant not found"})

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={"@context": _build_context(base_url), "@graph": [grant]},
        media_type="application/ld+json",
    )
