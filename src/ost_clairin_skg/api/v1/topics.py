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
FABIO = rdflib.Namespace("http://purl.org/spar/fabio/")

# filter key -> (predicate path with {v} as the value variable, match mode); see commons.build_filter_patterns
TOPIC_FILTERS = {
    "identifiers.scheme": ("datacite:hasIdentifier/datacite:usesIdentifierScheme {v}", "scheme"),
    "identifiers.value": ("datacite:hasIdentifier/silvio:hasLiteralValue {v}", "exact"),
    "cf.search.labels": ("skos:prefLabel {v}", "contains"),
    "cf.search.language": ("skos:prefLabel {v}", "lang"),
}


def extract_topic(g: rdflib.Graph, subject, local_identifier: str) -> Dict[str, Any]:
    """Convert a fabio:SubjectTerm to an SKG-IF topic; also used for the topics of a product."""
    topic: Dict[str, Any] = {
        "local_identifier": local_identifier,
        "entity_type": "topic",
    }

    # One label per language; sorted so the choice is stable when the source holds several
    labels: Dict[str, str] = {}
    for label in sorted(g.objects(subject, rdflib.SKOS.prefLabel), key=str):
        lang = getattr(label, "language", None)
        key = lang if lang and len(lang) == 2 else "none"
        labels.setdefault(lang if lang and len(lang) == 2 else "none", str(label))
    if labels:
        topic["labels"] = labels

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
        topic["identifiers"] = identifiers

    return topic


def _parse(turtle_data: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")
    return g


def _rdf_graph_to_topics(turtle_data: str) -> List[Dict[str, Any]]:
    """Convert RDF turtle data to a list of SKG-IF topics."""
    g = _parse(turtle_data)
    return [extract_topic(g, s, commons.strip_local_id_prefix(str(s))) for s in g.subjects(rdflib.RDF.type, FABIO.SubjectTerm)]


def _rdf_graph_to_topic(turtle_data: str, topic_id: str) -> Optional[Dict[str, Any]]:
    """Convert RDF turtle data to a single SKG-IF topic, or None if no fabio:SubjectTerm is present."""
    g = _parse(turtle_data)
    subject = next(g.subjects(rdflib.RDF.type, FABIO.SubjectTerm), None)
    if subject is None:
        return None
    return extract_topic(g, subject, topic_id)


def _build_context(base_url: str) -> List[Any]:
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {"@base": f"{base_url}/"},
    ]


@router.get("/topics", tags=["Topic"])
def get_topics(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated filter_name:filter_value elements. "
            "Supported keys: identifiers.scheme, identifiers.value, cf.search.labels, cf.search.language. "
            "Examples: cf.search.labels:Solar | cf.search.labels:Solar,cf.search.language:en"
        ),
    ),
) -> JSONResponse:
    """List topics with pagination and optional filtering.

    Topics are the `fabio:SubjectTerm` resources in the triplestore. Returns a paginated JSON-LD
    response following the SKG-IF specification. Each item in `@graph` is an `entity_type: topic` object.

    **Filtering** — supply comma-separated `name:value` pairs.
    Supported filter keys:

    | Key | Description |
    |-----|-------------|
    | `identifiers.scheme` | Identifier scheme (e.g. `wikidata`), case-insensitive |
    | `identifiers.value` | Exact match on any identifier value |
    | `cf.search.labels` | Case-insensitive substring match on any label |
    | `cf.search.language` | Topic has a label in this language (e.g. `en`) |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `422` — unsupported filter key supplied
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get topics endpoint called with page=%d, page_size=%d, filter=%s", page, page_size, filter)

    filter_clause = None
    if filter:
        filter_clause, unsupported = commons.build_filter_patterns(filter, TOPIC_FILTERS)
        if unsupported:
            return JSONResponse(status_code=422, content={
                "detail": "Unsupported filter(s) requested",
                "unsupported_filters": unsupported,
            })

    offset = (page - 1) * page_size
    sparql = commons.build_topics_sparql(limit=page_size, offset=offset, filter_clause=filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        topics = _rdf_graph_to_topics(turtle_data) if turtle_data else []
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    base_url = str(request.base_url).rstrip("/")
    search_url = f"{base_url}{API_PREFIX}/topics"

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
        "@graph": topics,
    }

    return JSONResponse(content=response, media_type="application/ld+json")


@router.get("/topics/{local_identifier:path}", tags=["Topic"])
def get_topic(
    request: Request,
    local_identifier: str = Path(..., description="The local identifier of the topic"),
) -> JSONResponse:
    """Retrieve a single topic by local identifier.

    Returns a JSON-LD document following the SKG-IF specification (`entity_type: topic`).

    **Responses**
    - `200` — topic found, returns JSON-LD
    - `404` — no topic with the given identifier
    - `502` — triplestore unreachable or returned unexpected data
    """
    logging.debug("Get topic endpoint called for local_identifier=%s", local_identifier)

    filter_clause = f"FILTER(STR(?s) = {json.dumps(commons.add_local_id_prefix(local_identifier))}) ."
    sparql = commons.build_topic_sparql(filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        topic = _rdf_graph_to_topic(turtle_data, commons.strip_local_id_prefix(local_identifier)) if turtle_data else None
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )

    if topic is None:
        return JSONResponse(status_code=404, content={"detail": "Topic not found"})

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={"@context": _build_context(base_url), "@graph": [topic]},
        media_type="application/ld+json",
    )
