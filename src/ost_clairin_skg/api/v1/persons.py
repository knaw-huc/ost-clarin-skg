import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from src.ost_clairin_skg.infra.commons import API_PREFIX, app_settings

router = APIRouter(prefix=API_PREFIX)

SKG_IF_CONTEXT_ONTOLOGY = "https://w3id.org/skg-if/context/1.1.0/skg-if.json"
SKG_IF_CONTEXT_API = "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json"
BASE_URL = app_settings.get("base_url", "https://w3id.org/skg-if/sandbox/acme/")

# Placeholder data until GraphDB-backed retrieval is implemented.
PERSONS_DATA: List[Dict[str, Any]] = [
    {
        "local_identifier": "person-1-jc",
        "entity_type": "person",
        "identifiers": [{"scheme": "orcid", "value": "0000-0002-1825-0097"}],
        "given_name": "Josiah",
        "family_name": "Carberry",
        "name": "Josiah Carberry",
        "affiliations": [
            {
                "role": "affiliate",
                "affiliation": {
                    "local_identifier": "http://example.com/skg-if/api/organisations/org-c66c6-38be-4d5f-85db-d44c9f869333",
                    "name": "Brown University",
                    "short_name": "BU",
                },
            }
        ],
    },
    {
        "local_identifier": "person-2-gc",
        "entity_type": "person",
        "given_name": "Gerard",
        "family_name": "Carberry",
        "name": "Gerard Carberry",
    },
    {
        "local_identifier": "person-3-ab",
        "entity_type": "person",
        "given_name": "Alice",
        "family_name": "Brown",
        "name": "Alice Brown",
    },
    {
        "local_identifier": "person-4-jd",
        "entity_type": "person",
        "given_name": "John",
        "family_name": "Doe",
        "name": "John Doe",
    },
]

SUPPORTED_FILTERS = {
    "identifiers.id",
    "identifiers.scheme",
    "given_name",
    "family_name",
    "name",
    "affiliations.affiliation.local_identifier",
    "affiliations.affiliation.name",
    "affiliations.affiliation.short_name",
    "affiliations.role",
    "cf.search.family_name",
    "cf.search.given_name",
    "cf.search.name",
}


def _build_context() -> List[Any]:
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {"@base": BASE_URL},
    ]


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
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise HTTPException(status_code=422, detail=f"Invalid filter element '{item}'. Expected key:value")
        if key not in SUPPORTED_FILTERS:
            raise HTTPException(status_code=422, detail=f"Unsupported filter '{key}'")
        filters.append((key, value))
    return filters


def _contains(haystack: Optional[str], needle: str) -> bool:
    return needle.lower() in (haystack or "").lower()


def _matches_filter(person: Dict[str, Any], key: str, value: str) -> bool:
    if key == "identifiers.id":
        return any(identifier.get("value") == value for identifier in person.get("identifiers", []))
    if key == "identifiers.scheme":
        return any(identifier.get("scheme") == value for identifier in person.get("identifiers", []))
    if key in {"given_name", "family_name", "name"}:
        return person.get(key) == value
    if key == "affiliations.affiliation.local_identifier":
        return any(
            affiliation.get("affiliation", {}).get("local_identifier") == value
            for affiliation in person.get("affiliations", [])
        )
    if key == "affiliations.affiliation.name":
        return any(
            affiliation.get("affiliation", {}).get("name") == value
            for affiliation in person.get("affiliations", [])
        )
    if key == "affiliations.affiliation.short_name":
        return any(
            affiliation.get("affiliation", {}).get("short_name") == value
            for affiliation in person.get("affiliations", [])
        )
    if key == "affiliations.role":
        return any(affiliation.get("role") == value for affiliation in person.get("affiliations", []))
    if key == "cf.search.family_name":
        return _contains(person.get("family_name"), value)
    if key == "cf.search.given_name":
        return _contains(person.get("given_name"), value)
    if key == "cf.search.name":
        return _contains(person.get("name"), value)
    return False


def _api_url(path: str) -> str:
    base = BASE_URL.rstrip("/")
    return f"{base}{API_PREFIX}{path}"


@router.get("/persons", tags=["Person"])
async def get_persons(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated filter_name:filter_value elements. "
            "Supported keys: identifiers.id, identifiers.scheme, given_name, family_name, name, "
            "affiliations.affiliation.local_identifier, affiliations.affiliation.name, "
            "affiliations.affiliation.short_name, affiliations.role, cf.search.family_name, "
            "cf.search.given_name, cf.search.name"
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
    | `identifiers.scheme` | Exact match on identifier scheme (e.g. `orcid`) |
    | `affiliations.affiliation.local_identifier` | Affiliation local ID |
    | `affiliations.affiliation.name` | Affiliation name (exact) |
    | `affiliations.affiliation.short_name` | Affiliation short name (exact) |
    | `affiliations.role` | Role within affiliation |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `502` — backend error
    """
    logging.info(f"Getting persons - page={page}, page_size={page_size}, filter={filter}")

    parsed_filters = _parse_filters(filter)

    filtered = PERSONS_DATA
    for key, value in parsed_filters:
        filtered = [person for person in filtered if _matches_filter(person, key, value)]

    total_items = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    query_base = _api_url("/persons")
    filter_fragment = f"filter={filter}" if filter else None
    current_params = [p for p in [filter_fragment, f"page={page}"] if p]
    meta_local_identifier = f"{query_base}?{'&'.join(current_params)}"

    part_of_params = [p for p in [filter_fragment] if p]
    part_of_local_identifier = query_base if not part_of_params else f"{query_base}?{'&'.join(part_of_params)}"

    meta: Dict[str, Any] = {
        "local_identifier": meta_local_identifier,
        "entity_type": "search_result_page",
        "part_of": {
            "local_identifier": part_of_local_identifier,
            "entity_type": "search_result",
            "total_items": total_items,
        },
        "api_items": [
            {
                "local_identifier": person["local_identifier"],
                "urls": [
                    {
                        "entity_type": "link",
                        "rel": "self",
                        "href": _api_url(f"/persons/{person['local_identifier']}"),
                    }
                ],
            }
            for person in page_items
        ],
    }

    if end < total_items:
        next_params = [p for p in [filter_fragment, f"page={page + 1}"] if p]
        meta["next_page"] = {
            "local_identifier": f"{query_base}?{'&'.join(next_params)}",
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


@router.get("/persons/{local_identifier}", tags=["Person"])
async def get_person(
    local_identifier: str = Path(..., description="The local identifier of the person"),
) -> JSONResponse:
    """Retrieve a single person by local identifier.

    Returns a JSON-LD document following the SKG-IF specification (`entity_type: person`).

    **Responses**
    - `200` — person found, returns JSON-LD
    - `404` — no person with the given identifier
    """
    logging.info(f"Getting person - local_identifier={local_identifier}")

    person_data = next((person for person in PERSONS_DATA if person["local_identifier"] == local_identifier), None)
    if not person_data:
        return JSONResponse(
            status_code=404,
            content={"message": f"Person '{local_identifier}' not found"},
        )

    return JSONResponse(
        status_code=200,
        content={
            "@context": _build_context(),
            "@graph": [person_data],
        },
    )

