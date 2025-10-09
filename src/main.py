import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import ost_clairin_skg
from src.ost_clairin_skg import public
from src.ost_clairin_skg.commons import app_settings, get_project_details

APP_NAME = os.environ.get("APP_NAME", "Guidance API Service")
EXPOSE_PORT = os.environ.get("EXPOSE_PORT", 41012)
build_date = os.environ.get("BUILD_DATE", "unknown")
LOG_FILE = app_settings.LOG_FILE
log_config = uvicorn.config.LOGGING_CONFIG
logging.basicConfig(
    filename=app_settings.LOG_FILE, level=app_settings.LOG_LEVEL, format=app_settings.LOG_FORMAT
)
app = FastAPI(
    title=get_project_details(os.getenv("BASE_DIR"), ["name"])["name"],
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