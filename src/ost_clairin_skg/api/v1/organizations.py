import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse

from src.ost_clairin_skg.infra.commons import app_settings, API_PREFIX

router = APIRouter(prefix=API_PREFIX)

# SKG-IF context URLs
SKG_IF_CONTEXT_ONTOLOGY = "https://w3id.org/skg-if/context/1.1.0/skg-if.json"
SKG_IF_CONTEXT_API = "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json"
BASE_URL = app_settings.get("base_url", "https://w3id.org/skg-if/sandbox/my-skg-acronym/")


def _build_context() -> List[Any]:
    """Build the JSON-LD context for organisations."""
    return [
        SKG_IF_CONTEXT_ONTOLOGY,
        SKG_IF_CONTEXT_API,
        {
            "@base": BASE_URL
        }
    ]


@router.get("/organisations", tags=["Organisation"])
async def get_organisations(
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    filter: Optional[str] = Query(None, description="Search filter (comma-separated key:value pairs)")
) -> JSONResponse:
    """
    List organisations with pagination and optional filtering.

    Returns a paginated JSON-LD response following the SKG-IF specification. Each item in
    `@graph` is an `entity_type: organisation` object.

    **Filtering** — supply comma-separated `name:value` pairs (format: `key:value,key2:value2`).

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `502` — backend error
    """
    logging.info(f"Getting organisations - page={page}, page_size={page_size}, filter={filter}")

    # Placeholder response structure following SKG-IF specification
    response = {
        "@context": _build_context(),
        "meta": {
            "local_identifier": f"{BASE_URL}organisations?page={page}&page_size={page_size}",
            "entity_type": "search_result_page",
            "part_of": {
                "local_identifier": f"{BASE_URL}organisations",
                "entity_type": "search_result",
                "total_items": 0  # Placeholder
            }
        },
        "@graph": []  # Placeholder - will contain organisation objects
    }

    # Add next_page link if there are more results
    if page < 1:  # Placeholder logic
        response["meta"]["next_page"] = {
            "local_identifier": f"{BASE_URL}organisations?page={page + 1}&page_size={page_size}",
            "entity_type": "search_result_page"
        }

    return JSONResponse(status_code=200, content=response)


@router.get("/organisations/{local_identifier}", tags=["Organisation"])
async def get_organisation(
    local_identifier: str = Path(..., description="The local identifier of the organisation")
) -> JSONResponse:
    """
    Retrieve a single organisation by local identifier.

    Returns a JSON-LD document following the SKG-IF specification (`entity_type: organisation`).
    Includes name, country, identifier schemes (e.g. ROR), and organisation type.

    **Responses**
    - `200` — organisation found, returns JSON-LD
    - `404` — no organisation with the given identifier
    """
    logging.info(f"Getting organisation - local_identifier={local_identifier}")

    # Sample organisations data (placeholder - will be replaced with GraphDB queries)
    organisations_data = {
        "organisation-2-bu": {
            "name": "Brown University.",
            "short_name": "BU",
            "country": "US",
            "identifiers": [
                {
                    "scheme": "ror",
                    "value": "https://ror.org/05gq02987"
                }
            ],
            "types": ["education"]
        },
        "organisation-1-mit": {
            "name": "Massachusetts Institute of Technology",
            "short_name": "MIT",
            "country": "US",
            "identifiers": [
                {
                    "scheme": "ror",
                    "value": "https://ror.org/05gq02987"
                }
            ],
            "types": ["education", "research"]
        }
    }

    # Get organisation data or return 404
    org_data = organisations_data.get(local_identifier)
    if not org_data:
        logging.warning(f"Organisation not found - local_identifier={local_identifier}")
        return JSONResponse(
            status_code=404,
            content={"message": f"Organisation '{local_identifier}' not found"}
        )

    # Build response following SKG-IF specification
    response = {
        "@context": _build_context(),
        "@graph": [
            {
                "local_identifier": local_identifier,
                "entity_type": "organisation",
                "identifiers": org_data.get("identifiers", []),
                "name": org_data.get("name"),
                "short_name": org_data.get("short_name"),
                "country": org_data.get("country"),
                "types": org_data.get("types", [])
            }
        ]
    }

    return JSONResponse(status_code=200, content=response)

