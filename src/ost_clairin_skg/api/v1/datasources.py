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
DATASOURCES_DATA: List[Dict[str, Any]] = [
    {
        "local_identifier": "datasource-1-oura",
        "entity_type": "datasource",
        "identifiers": [
            {"scheme": "doi", "value": "10.25504/FAIRsharing.rkwr6y"}
        ],
        "name": "Oxford University Research Archive",
        "data_source_classification": "repository",
        "research_product_types": ["research data", "literature"],
    },
    {
        "local_identifier": "datasource-2-zenodo",
        "entity_type": "datasource",
        "identifiers": [
            {"scheme": "doi", "value": "10.25504/FAIRsharing.wy4egf"}
        ],
        "name": "Zenodo",
        "data_source_classification": "repository",
        "research_product_types": ["research data", "literature", "software"],
    },
    {
        "local_identifier": "datasource-3-pubmed",
        "entity_type": "datasource",
        "identifiers": [
            {"scheme": "url", "value": "https://pubmed.ncbi.nlm.nih.gov/"}
        ],
        "name": "PubMed",
        "data_source_classification": "aggregator",
        "research_product_types": ["literature"],
    },
]

SUPPORTED_FILTERS = {
    # Attribute filters (exact match)
    "identifiers.scheme",
    "identifiers.value",
    "name",
    "acronym",
    "data_source_classification",
    "research_product_type",   # singular — filter key per spec
    # Convenience filters
    "cf.search.name",
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
            raise HTTPException(
                status_code=422,
                detail=f"Invalid filter element '{item}'. Expected key:value",
            )
        key, value = item.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid filter element '{item}'. Expected key:value",
            )
        if key not in SUPPORTED_FILTERS:
            raise HTTPException(status_code=422, detail=f"Unsupported filter '{key}'")
        filters.append((key, value))
    return filters


def _matches_filter(ds: Dict[str, Any], key: str, value: str) -> bool:
    if key == "name":
        return ds.get("name") == value
    if key == "acronym":
        return ds.get("acronym") == value
    if key == "data_source_classification":
        return ds.get("data_source_classification") == value
    if key == "research_product_type":
        # filter key is singular; field in data is a list
        return value in (ds.get("research_product_types") or [])
    if key == "identifiers.scheme":
        return any(i.get("scheme") == value for i in ds.get("identifiers", []))
    if key == "identifiers.value":
        return any(i.get("value") == value for i in ds.get("identifiers", []))
    if key == "cf.search.name":
        return value.lower() in (ds.get("name") or "").lower()
    return False


@router.get("/datasources/{local_identifier}", tags=["Datasource"])
async def get_datasource(
    local_identifier: str = Path(..., description="The local identifier of the datasource"),
) -> JSONResponse:
    """Get single datasource by id following SKG-IF Data Source (entity_type: datasource)."""
    logging.info(f"Getting datasource - local_identifier={local_identifier}")

    ds_data = next(
        (ds for ds in DATASOURCES_DATA if ds["local_identifier"] == local_identifier),
        None,
    )

    if not ds_data:
        logging.warning(f"Datasource not found - local_identifier={local_identifier}")
        return JSONResponse(
            status_code=404,
            content={"message": f"Datasource '{local_identifier}' not found"},
        )

    return JSONResponse(
        status_code=200,
        content={
            "@context": _build_context(),
            "meta": {
                "local_identifier": _api_url(f"/datasources/{local_identifier}"),
                "entity_type": "single_entity",
            },
            "@graph": [ds_data],
        },
    )


@router.get("/datasources", tags=["Datasource"])
async def get_datasources(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma-separated filter_name:filter_value elements (AND logic). "
            "Format: filter_name_1:filter_value_1,filter_name_2:filter_value_2. "
            "Attribute filters (exact match): data_source_classification, research_product_type, "
            "identifiers.scheme, identifiers.value, acronym. "
            "Convenience filters: cf.search.name. "
            "Examples: data_source_classification:repository | "
            "cf.search.name:Oxford | research_product_type:literature"
        ),
        pattern=r"^(,?.+:.+)*$",
    ),
) -> JSONResponse:
    """Get list of datasources following SKG-IF Data Source (entity_type: datasource)."""
    logging.info(f"Getting datasources - page={page}, page_size={page_size}, filter={filter}")

    parsed_filters = _parse_filters(filter)

    filtered = DATASOURCES_DATA
    for key, value in parsed_filters:
        filtered = [ds for ds in filtered if _matches_filter(ds, key, value)]

    total_items = len(filtered)
    total_pages = max(1, math.ceil(total_items / page_size))
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    query_base = _api_url("/datasources")
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
                "local_identifier": ds["local_identifier"],
                "urls": [
                    {
                        "entity_type": "link",
                        "rel": "self",
                        "href": _api_url(f"/datasources/{ds['local_identifier']}"),
                        "media_type": "application/json",
                    }
                ],
            }
            for ds in page_items
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

