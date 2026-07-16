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
GRANTS_DATA: List[Dict[str, Any]] = [
    {
        "local_identifier": "grant-1-go",
        "entity_type": "grant",
        "identifiers": [
            {"scheme": "doi", "value": "https://doi.org/10.3030/101095129"}
        ],
        "grant_number": "101095129",
        "titles": {
            "en": "GraspOS: next Generation Research Assessment to Promote Open Science"
        },
        "abstracts": {
            "en": "GraspOS aims to build and operate a data infrastructure to support the policy reforms..."
        },
        "acronym": "GraspOS",
        "funding_agency": {
            "local_identifier": "organisation-2-bu",
            "entity_type": "organisation",
            "identifiers": [{"scheme": "ror", "value": "https://ror.org/05gq02987"}],
            "name": "Brown University",
            "short_name": "BU",
            "country": "US",
            "website": "https://www.brown.edu/",
        },
        "funding_stream": "Horizon Europe",
        "currency": "EUR",
        "funded_amount": 50000,
        "duration": {
            "start": "2023-01-01T00:00:00Z",
            "end": "2025-12-31T23:59:59Z",
        },
        "website": "https://graspos.eu",
        "beneficiaries": [
            {
                "local_identifier": "organisation-2-bu",
                "entity_type": "organisation",
                "identifiers": [{"scheme": "ror", "value": "https://ror.org/05gq02987"}],
                "name": "Brown University",
                "short_name": "BU",
                "country": "US",
                "website": "https://www.brown.edu/",
            }
        ],
        "contributions": [
            {
                "by": {
                    "local_identifier": "person-1-jc",
                    "entity_type": "person",
                    "identifiers": [{"scheme": "orcid", "value": "0000-0002-1825-0097"}],
                    "given_name": "Josiah",
                    "family_name": "Carberry",
                    "name": "Josiah Carberry",
                    "declared_affiliations": [
                        {
                            "local_identifier": "organisation-2-bu",
                            "entity_type": "organisation",
                            "identifiers": [{"scheme": "ror", "value": "https://ror.org/05gq02987"}],
                            "name": "Brown University",
                            "short_name": "BU",
                            "country": "US",
                            "website": "https://www.brown.edu/",
                        }
                    ],
                    "roles": ["co-applicant"],
                }
            }
        ],
    },
    {
        "local_identifier": "grant-2-os",
        "entity_type": "grant",
        "identifiers": [
            {"scheme": "doi", "value": "https://doi.org/10.3030/123456789"}
        ],
        "grant_number": "123456789",
        "titles": {
            "en": "OpenScience Foundations"
        },
        "abstracts": {
            "en": "A project to build open science infrastructure across Europe."
        },
        "acronym": "OSF",
        "funding_agency": {
            "local_identifier": "organisation-1-mit",
            "entity_type": "organisation",
            "identifiers": [{"scheme": "ror", "value": "https://ror.org/042nb2s44"}],
            "name": "Massachusetts Institute of Technology",
            "short_name": "MIT",
            "country": "US",
            "website": "https://www.mit.edu/",
        },
        "funding_stream": "Horizon Europe",
        "currency": "EUR",
        "funded_amount": 120000,
        "duration": {
            "start": "2024-01-01T00:00:00Z",
            "end": "2026-12-31T23:59:59Z",
        },
        "website": "https://osf-example.eu",
        "beneficiaries": [],
        "contributions": [],
    },
]

SUPPORTED_FILTERS = {
    # Attribute filters
    "identifiers.scheme",
    "identifiers.value",
    "acronym",
    "currency",
    "website",
    "grant_number",
    "funding_stream",
    "beneficiaries.identifiers.scheme",
    "beneficiaries.identifiers.value",
    "beneficiaries.name",
    "beneficiaries.short_name",
    "beneficiaries.website",
    "beneficiaries.country",
    "contributions.by.local_identifier",
    "contributions.by.identifiers.scheme",
    "contributions.by.identifiers.value",
    "contributions.by.given_name",
    "contributions.by.family_name",
    "contributions.by.name",
    "contributions.declared_affiliations.local_identifier",
    "contributions.declared_affiliations.identifiers.scheme",
    "contributions.declared_affiliations.identifiers.value",
    "contributions.declared_affiliations.name",
    "contributions.declared_affiliations.short_name",
    "contributions.declared_affiliations.website",
    "contributions.declared_affiliations.country",
    "contributions.role",
    "funding_agency.identifiers.scheme",
    "funding_agency.identifiers.value",
    "funding_agency.name",
    "funding_agency.short_name",
    "funding_agency.website",
    "funding_agency.country",
    "funding_agency.local_identifier",
    # Convenience filters
    "cf.search.title",
    "cf.search.title_abstract",
    "cf.search.acronym",
    "cf.funded_amount.from",
    "cf.funded_amount.to",
    "cf.duration.start.from",
    "cf.duration.start.to",
    "cf.duration.end.from",
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


def _contains(haystack: Optional[str], needle: str) -> bool:
    return needle.lower() in (haystack or "").lower()


def _iso_to_date(value: str) -> str:
    """Strip time component for simple date comparison."""
    return value[:10] if value else ""


def _matches_filter(grant: Dict[str, Any], key: str, value: str) -> bool:
    # --- simple attribute filters ---
    if key == "acronym":
        return grant.get("acronym") == value
    if key == "grant_number":
        return grant.get("grant_number") == value
    if key == "funding_stream":
        return grant.get("funding_stream") == value
    if key == "currency":
        return grant.get("currency") == value
    if key == "website":
        return grant.get("website") == value

    # identifiers
    if key == "identifiers.scheme":
        return any(i.get("scheme") == value for i in grant.get("identifiers", []))
    if key == "identifiers.value":
        return any(i.get("value") == value for i in grant.get("identifiers", []))

    # funding_agency
    fa = grant.get("funding_agency") or {}
    if key == "funding_agency.local_identifier":
        return fa.get("local_identifier") == value
    if key == "funding_agency.name":
        return fa.get("name") == value
    if key == "funding_agency.short_name":
        return fa.get("short_name") == value
    if key == "funding_agency.website":
        return fa.get("website") == value
    if key == "funding_agency.country":
        return fa.get("country") == value
    if key == "funding_agency.identifiers.scheme":
        return any(i.get("scheme") == value for i in fa.get("identifiers", []))
    if key == "funding_agency.identifiers.value":
        return any(i.get("value") == value for i in fa.get("identifiers", []))

    # beneficiaries
    beneficiaries = grant.get("beneficiaries", [])
    if key == "beneficiaries.identifiers.scheme":
        return any(i.get("scheme") == value for b in beneficiaries for i in b.get("identifiers", []))
    if key == "beneficiaries.identifiers.value":
        return any(i.get("value") == value for b in beneficiaries for i in b.get("identifiers", []))
    if key == "beneficiaries.name":
        return any(b.get("name") == value for b in beneficiaries)
    if key == "beneficiaries.short_name":
        return any(b.get("short_name") == value for b in beneficiaries)
    if key == "beneficiaries.website":
        return any(b.get("website") == value for b in beneficiaries)
    if key == "beneficiaries.country":
        return any(b.get("country") == value for b in beneficiaries)

    # contributions
    contributions = grant.get("contributions", [])
    if key == "contributions.by.local_identifier":
        return any(c.get("by", {}).get("local_identifier") == value for c in contributions)
    if key == "contributions.by.identifiers.scheme":
        return any(i.get("scheme") == value for c in contributions for i in c.get("by", {}).get("identifiers", []))
    if key == "contributions.by.identifiers.value":
        return any(i.get("value") == value for c in contributions for i in c.get("by", {}).get("identifiers", []))
    if key == "contributions.by.given_name":
        return any(c.get("by", {}).get("given_name") == value for c in contributions)
    if key == "contributions.by.family_name":
        return any(c.get("by", {}).get("family_name") == value for c in contributions)
    if key == "contributions.by.name":
        return any(c.get("by", {}).get("name") == value for c in contributions)
    if key == "contributions.role":
        return any(value in (c.get("roles") or []) for c in contributions)
    if key == "contributions.declared_affiliations.local_identifier":
        return any(
            aff.get("local_identifier") == value
            for c in contributions
            for aff in c.get("declared_affiliations", [])
        )
    if key == "contributions.declared_affiliations.identifiers.scheme":
        return any(
            i.get("scheme") == value
            for c in contributions
            for aff in c.get("declared_affiliations", [])
            for i in aff.get("identifiers", [])
        )
    if key == "contributions.declared_affiliations.identifiers.value":
        return any(
            i.get("value") == value
            for c in contributions
            for aff in c.get("declared_affiliations", [])
            for i in aff.get("identifiers", [])
        )
    if key == "contributions.declared_affiliations.name":
        return any(aff.get("name") == value for c in contributions for aff in c.get("declared_affiliations", []))
    if key == "contributions.declared_affiliations.short_name":
        return any(aff.get("short_name") == value for c in contributions for aff in c.get("declared_affiliations", []))
    if key == "contributions.declared_affiliations.website":
        return any(aff.get("website") == value for c in contributions for aff in c.get("declared_affiliations", []))
    if key == "contributions.declared_affiliations.country":
        return any(aff.get("country") == value for c in contributions for aff in c.get("declared_affiliations", []))

    # --- convenience filters ---
    if key == "cf.search.title":
        return any(_contains(t, value) for t in (grant.get("titles") or {}).values())
    if key == "cf.search.title_abstract":
        in_title = any(_contains(t, value) for t in (grant.get("titles") or {}).values())
        in_abstract = any(_contains(t, value) for t in (grant.get("abstracts") or {}).values())
        return in_title or in_abstract
    if key == "cf.search.acronym":
        return _contains(grant.get("acronym"), value)
    if key == "cf.funded_amount.from":
        try:
            return (grant.get("funded_amount") or 0) >= float(value)
        except ValueError:
            return False
    if key == "cf.funded_amount.to":
        try:
            return (grant.get("funded_amount") or 0) <= float(value)
        except ValueError:
            return False
    if key == "cf.duration.start.from":
        start = _iso_to_date((grant.get("duration") or {}).get("start", ""))
        return bool(start) and start >= _iso_to_date(value)
    if key == "cf.duration.start.to":
        start = _iso_to_date((grant.get("duration") or {}).get("start", ""))
        return bool(start) and start <= _iso_to_date(value)
    if key == "cf.duration.end.from":
        end = _iso_to_date((grant.get("duration") or {}).get("end", ""))
        return bool(end) and end >= _iso_to_date(value)

    return False


def _build_meta_api_items(grant: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build api_items linking all related persons and organisations referenced in the grant."""
    items: List[Dict[str, Any]] = []
    seen: set = set()

    def _add_item(local_id: str, entity_type: str) -> None:
        if local_id in seen:
            return
        seen.add(local_id)
        path = "persons" if entity_type == "person" else "organisations"
        items.append(
            {
                "local_identifier": local_id,
                "urls": [
                    {
                        "entity_type": "link",
                        "rel": "self",
                        "href": _api_url(f"/{path}/{local_id}"),
                    }
                ],
            }
        )

    # Funding agency
    fa = grant.get("funding_agency")
    if fa and fa.get("local_identifier"):
        _add_item(fa["local_identifier"], "organisation")

    # Beneficiaries
    for b in grant.get("beneficiaries", []):
        if b.get("local_identifier"):
            _add_item(b["local_identifier"], "organisation")

    # Contributors
    for c in grant.get("contributions", []):
        by = c.get("by", {})
        if by.get("local_identifier"):
            _add_item(by["local_identifier"], by.get("entity_type", "person"))
        for aff in by.get("declared_affiliations", []):
            if aff.get("local_identifier"):
                _add_item(aff["local_identifier"], "organisation")

    return items


@router.get("/grants/{local_identifier}", tags=["Grant"])
async def get_grant(
    local_identifier: str = Path(..., description="The local identifier of the grant"),
) -> JSONResponse:
    """Get single grant by id following SKG-IF Grant (entity_type: grant)."""
    logging.info(f"Getting grant - local_identifier={local_identifier}")

    grant_data = next(
        (g for g in GRANTS_DATA if g["local_identifier"] == local_identifier), None
    )

    if not grant_data:
        logging.warning(f"Grant not found - local_identifier={local_identifier}")
        return JSONResponse(
            status_code=404,
            content={"message": f"Grant '{local_identifier}' not found"},
        )

    return JSONResponse(
        status_code=200,
        content={
            "@context": _build_context(),
            "meta": {
                "local_identifier": _api_url(f"/grants/{local_identifier}"),
                "entity_type": "single_entity",
                "api_items": _build_meta_api_items(grant_data),
            },
            "@graph": [grant_data],
        },
    )


@router.get("/grants", tags=["Grant"])
async def get_grants(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma-separated filter_name:filter_value elements (AND logic). "
            "Attribute filters (exact match): identifiers.scheme, identifiers.value, acronym, currency, website, "
            "grant_number, funding_stream, "
            "funding_agency.local_identifier, funding_agency.name, funding_agency.short_name, "
            "funding_agency.website, funding_agency.country, funding_agency.identifiers.scheme, funding_agency.identifiers.value, "
            "beneficiaries.identifiers.scheme, beneficiaries.identifiers.value, beneficiaries.name, "
            "beneficiaries.short_name, beneficiaries.website, beneficiaries.country, "
            "contributions.by.local_identifier, contributions.by.identifiers.scheme, contributions.by.identifiers.value, "
            "contributions.by.given_name, contributions.by.family_name, contributions.by.name, contributions.role, "
            "contributions.declared_affiliations.local_identifier, contributions.declared_affiliations.identifiers.scheme, "
            "contributions.declared_affiliations.identifiers.value, contributions.declared_affiliations.name, "
            "contributions.declared_affiliations.short_name, contributions.declared_affiliations.website, "
            "contributions.declared_affiliations.country. "
            "Convenience filters: cf.search.title, cf.search.title_abstract, cf.search.acronym, "
            "cf.funded_amount.from, cf.funded_amount.to, cf.duration.start.from, cf.duration.start.to, cf.duration.end.from. "
            "Examples: cf.search.title:GraspOS | acronym:GraspOS | cf.funded_amount.from:1000000"
        ),
    ),
) -> JSONResponse:
    """Get list of grants following SKG-IF Grant (entity_type: grant)."""
    logging.info(f"Getting grants - page={page}, page_size={page_size}, filter={filter}")

    parsed_filters = _parse_filters(filter)

    filtered = GRANTS_DATA
    for key, value in parsed_filters:
        filtered = [g for g in filtered if _matches_filter(g, key, value)]

    total_items = len(filtered)
    total_pages = max(1, math.ceil(total_items / page_size))
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    query_base = _api_url("/grants")
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
                "local_identifier": g["local_identifier"],
                "urls": [
                    {
                        "entity_type": "link",
                        "rel": "self",
                        "href": _api_url(f"/grants/{g['local_identifier']}"),
                        "media_type": "application/json",
                    }
                ],
            }
            for g in page_items
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

