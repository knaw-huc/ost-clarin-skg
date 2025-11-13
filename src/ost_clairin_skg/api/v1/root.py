import logging
import os

from fastapi import APIRouter
from starlette.responses import JSONResponse

from src.ost_clairin_skg.infra.commons import get_project_details, build_date
router = APIRouter()

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    logging.info("favicon route")
    return JSONResponse(status_code=404, content={"message": "favicon.ico Not found"})


@router.get("/", include_in_schema=False)
async def root():
    logging.info("root route")
    return JSONResponse(
        status_code=200,
        content={
            "message": "Welcome to the OSTrails Clarin SKG-IF API Service",
            "version": f"{get_project_details(os.getenv('BASE_DIR'), ["version"])["version"]} (Build Date: {build_date})",
            "build_date": build_date
        }
    )
