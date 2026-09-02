import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from src.ost_clairin_skg.infra.commons import API_PREFIX, app_settings

router = APIRouter(prefix=API_PREFIX)

SKG_IF_CONTEXT_ONTOLOGY = "https://w3id.org/skg-if/context/1.1.0/skg-if.json"
SKG_IF_CONTEXT_API = "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json"
BASE_URL = app_settings.get("base_url", "https://w3id.org/skg-if/sandbox/acme/")

# Placeholder data until GraphDB-backed retrieval is implemented.
TOPICS_DATA: List[Dict[str, Any]] = [
    {
        "local_identifier": "topic-1-cs",
        "entity_type": "topic",
        "identifiers": [{"scheme": "wikidata", "value": "https://www.wikidata.org/wiki/Q21198"}],
        "labels": {
            "en": "Computer Science",
            "it": "Informatica",
        },
    },
    {
        "local_identifier": "topic-2-solar",
        "entity_type": "topic",
        "identifiers": [{"scheme": "wikidata", "value": "https://www.wikidata.org/wiki/Q12705"}],
        "labels": {
            "en": "Solar energy",
            "fr": "Energie solaire",
        },
    },
    {
        "local_identifier": "topic-3-data",
        "entity_type": "topic",
        "identifiers": [{"scheme": "local", "value": "data-management"}],
        "labels": {
            "en": "Data management",
            "de": "Datenmanagement",
        },
    },
]

SUPPORTED_FILTERS = {
    "identifiers.scheme",
    "identifiers.value",
    "cf.search.labels",
    "cf.search.language",
}


def _build_context() -> List[Any]:
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {"@base": BASE_URL},
    ]


def _api_url(path: str) -> str:
    base = BASE_URL.rstrip("/")
    return f"{base}{API_PREFIX}{path}"


def _page_url(query_base: str, filter_fragment: Optional[str], page: int) -> str:
    params = [p for p in [filter_fragment, f"page={page}"] if p]
    return f"{query_base}?{'&'.join(params)}"


def _parse_filters(filter_value: Optional[str]) -> List[Tuple[str, str]]:
    if not filter_value:
        return []
    filters: List[Tuple[str, str]] = []
    for item in filter_value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise HTTPException(status_code=422, detail=f"Invalid filter element '{item}'. Expected key:value")
        key, value = item.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise HTTPException(status_code=422, detail=f"Invalid filter element '{item}'. Expected key:value")
        if key not in SUPPORTED_FILTERS:
            raise HTTPException(status_code=422, detail=f"Unsupported filter '{key}'")
        filters.append((key, value))
    return filters


def _matches_filter(topic: Dict[str, Any], key: str, value: str) -> bool:
    if key == "identifiers.scheme":
        return any(identifier.get("scheme") == value for identifier in topic.get("identifiers", []))
    if key == "identifiers.value":
        return any(identifier.get("value") == value for identifier in topic.get("identifiers", []))
    if key == "cf.search.labels":
        return any(value.lower() in label.lower() for label in topic.get("labels", {}).values())
    if key == "cf.search.language":
        return value in topic.get("labels", {})
    return False


@router.get("/topics", tags=["Topic"])
async def get_topics(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma-separated filter_name:filter_value elements. "
            "Attribute filters (exact match): identifiers.scheme, identifiers.value. "
            "Convenience filters: cf.search.labels, cf.search.language. "
            "Examples: cf.search.labels:Solar | cf.search.labels:Solar,cf.search.language:en"
        ),
        pattern=r"^(,?.+:.+)*$",
    ),
) -> JSONResponse:
    logging.info(f"Getting topics - page={page}, page_size={page_size}, filter={filter}")

    parsed_filters = _parse_filters(filter)

    filtered = TOPICS_DATA
    for key, value in parsed_filters:
        filtered = [topic for topic in filtered if _matches_filter(topic, key, value)]

    total_items = len(filtered)
    total_pages = max(1, math.ceil(total_items / page_size))
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    query_base = _api_url("/topics")
    filter_fragment = f"filter={filter}" if filter else None
    part_of_params = [p for p in [filter_fragment] if p]
    part_of_local_identifier = (
        query_base if not part_of_params else f"{query_base}?{'&'.join(part_of_params)}"
    )

    meta: Dict[str, Any] = {
        "local_identifier": _page_url(query_base, filter_fragment, page),
        "entity_type": "search_result_page",
        "part_of": {
            "local_identifier": part_of_local_identifier,
            "entity_type": "search_result",
            "total_items": total_items,
            "first_page": {
                "local_identifier": _page_url(query_base, filter_fragment, 1),
                "entity_type": "search_result_page",
            },
            "last_page": {
                "local_identifier": _page_url(query_base, filter_fragment, total_pages),
                "entity_type": "search_result_page",
            },
        },
        "api_items": [
            {
                "local_identifier": topic["local_identifier"],
                "urls": [
                    {
                        "entity_type": "link",
                        "rel": "self",
                        "href": _api_url(f"/topics/{topic['local_identifier']}"),
                        "media_type": "application/json",
                    }
                ],
            }
            for topic in page_items
        ],
    }

    if page > 1:
        meta["prev_page"] = {
            "local_identifier": _page_url(query_base, filter_fragment, page - 1),
            "entity_type": "search_result_page",
        }

    if end < total_items:
        meta["next_page"] = {
            "local_identifier": _page_url(query_base, filter_fragment, page + 1),
            "entity_type": "search_result_page",
        }

    return JSONResponse(
        status_code=200,
        content={
            "@context": _build_context(),
            "meta": meta,
            "@graph": page_items,
        },
    )


@router.get("/topics/{local_identifier}", tags=["Topic"])
async def get_topic(
    local_identifier: str = Path(..., description="The local identifier of the topic"),
) -> JSONResponse:
    logging.info(f"Getting topic - local_identifier={local_identifier}")

    topic_data = next(
        (topic for topic in TOPICS_DATA if topic["local_identifier"] == local_identifier),
        None,
    )

    if not topic_data:
        logging.warning(f"Topic not found - local_identifier={local_identifier}")
        return JSONResponse(
            status_code=404,
            content={"message": f"Topic '{local_identifier}' not found"},
        )

    return JSONResponse(
        status_code=200,
        content={
            "@context": _build_context(),
            "meta": {
                "local_identifier": _api_url(f"/topics/{local_identifier}"),
                "entity_type": "single_entity",
            },
            "@graph": [topic_data],
        },
    )
