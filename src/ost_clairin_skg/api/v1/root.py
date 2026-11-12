import logging
import os

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from src.ost_clairin_skg.infra.commons import API_PREFIX, get_project_details, build_date
router = APIRouter()

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    logging.info("favicon route")
    return JSONResponse(status_code=404, content={"message": "favicon.ico Not found"})


@router.get("/", include_in_schema=False)
async def root(request: Request):
    logging.info("root route")
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        status_code=200,
        content={
            "message": "Welcome to the OSTrails Clarin SKG-IF API Service",
            "version": f"{get_project_details(os.getenv('BASE_DIR'), ["version"])["version"]} (Build Date: {build_date})",
            "build_date": build_date,
            "service": {
                "entity_type": "service",
                "name": "OSTrails Clarin SKG-IF API Service",
                "local_identifier": base_url,
                "api_base": f"{base_url}{API_PREFIX}",
                "documentation": {
                    "openapi": f"{base_url}/docs/openapi",
                    "openapi_yaml": f"{base_url}/docs/openapi.yaml",
                    "openapi_json": f"{base_url}/docs/openapi.json",
                },
            },
        }
    )
