import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from src import ost_clairin_skg
from src.ost_clairin_skg import public
from src.ost_clairin_skg.commons import app_settings, get_project_details

APP_NAME = os.environ.get("APP_NAME", "OSTrails Clarin SKG-IF Service")
EXPOSE_PORT = os.environ.get("EXPOSE_PORT", 41012)
build_date = os.environ.get("BUILD_DATE", "unknown")
import logging
from logging.handlers import TimedRotatingFileHandler

log_file = app_settings.get("log_file", "trs.log")
handler = TimedRotatingFileHandler(
    log_file,
    when="midnight",  # rotate every second for testing
    interval=1,
    backupCount=7,
    encoding="utf-8",
    utc=True
)
handler.suffix = "%Y-%m-%d"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[handler]
)

@asynccontextmanager
async def lifespan(application: FastAPI):
    logging.info("start up")
    yield

app = FastAPI(
    title=get_project_details(os.getenv("BASE_DIR"), ["title"])["title"],
    version=f"{get_project_details(os.getenv('BASE_DIR'), ["version"])["version"]} (Build Date: {build_date})",
    description=get_project_details(os.getenv("BASE_DIR"), ["description"])["description"],
    # openapi_url=settings.openapi_url,
    # docs_url=settings.docs_url,
    # redoc_url=settings.redoc_url,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router, tags=["Public"], prefix="")

@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={"message": "Endpoint not found"})
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    logging.info("favicon route")
    return JSONResponse(status_code=404, content={"message": "favicon.ico Not found"})


@app.get("/", include_in_schema=False)
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    num_workers = max(1, os.cpu_count() or 1)
    logging.info(f"=====Starting server with {num_workers} workers on port {EXPOSE_PORT} =====")
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=int(EXPOSE_PORT),
        workers=1,
        factory=False,
    )