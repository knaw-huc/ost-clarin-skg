import json
import logging
import os

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter()


def _load_spec_with_base_url(request: Request) -> dict:
    """Load the OpenAPI YAML spec and replace the servers list with the actual base URL."""
    yaml_path = os.path.join(os.environ.get("BASE_DIR", ""), "resources", "skg-if-openapi.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    base_url = str(request.base_url).rstrip("/")
    spec["servers"] = [{"url": base_url, "description": "This service"}]

    return spec


@router.get("/docs/openapi.yaml", include_in_schema=False)
async def openapi_yaml(request: Request):
    logging.info("openapi yaml route")
    spec = _load_spec_with_base_url(request)
    return Response(
        content=yaml.dump(spec, allow_unicode=True, sort_keys=False),
        media_type="text/plain; charset=utf-8",
    )


@router.get("/docs/openapi.json", include_in_schema=False)
async def openapi_json(request: Request):
    logging.info("openapi json route")
    spec = _load_spec_with_base_url(request)
    return Response(
        content=json.dumps(spec, ensure_ascii=False, indent=2),
        media_type="application/json",
    )


@router.get("/docs/openapi", include_in_schema=False)
async def openapi_negotiate(request: Request):
    """Serve the OpenAPI spec as YAML or JSON based on the Accept header."""
    logging.info("openapi content-negotiation route")
    accept = request.headers.get("accept", "")
    spec = _load_spec_with_base_url(request)

    if "application/json" in accept:
        return Response(
            content=json.dumps(spec, ensure_ascii=False, indent=2),
            media_type="application/json",
        )

    # Default: YAML (text/plain so browsers render inline)
    return Response(
        content=yaml.dump(spec, allow_unicode=True, sort_keys=False),
        media_type="text/plain; charset=utf-8",
    )
