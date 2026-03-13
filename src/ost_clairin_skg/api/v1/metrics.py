import json
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.ost_clairin_skg.infra.commons import API_PREFIX
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore

router = APIRouter(prefix=API_PREFIX)


@router.get("/health")
def health_check():
    logging.debug("Health check endpoint called")
    return {"status": "ok"}


@router.get("/ping")
def ping():
    logging.debug("Ping endpoint called")
    return {"message": "pong"}


@router.get("/objects", tags=["Metrics"])
def objects_count():
    """Return the number of distinct subjects (objects) present in the triplestore.

    Uses a simple SPARQL SELECT COUNT query and requests JSON results from the
    triplestore. Returns a JSON response with the count or 502 on backend errors.
    """
    logging.debug("Objects count endpoint called")

    sparql = "SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE { ?s ?p ?o }"
    try:
        resp_text = query_triplestore(sparql, accept="application/sparql-results+json")
    except RuntimeError as exc:
        logging.exception("Failed to query triplestore for objects count")
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    try:
        data = json.loads(resp_text) if resp_text else {}
        # Safe extraction of count value
        count = 0
        if isinstance(data, dict):
            results = data.get("results", {}).get("bindings", [])
            if results:
                first = results[0]
                cnt_binding = first.get("count") or first.get("?count")
                if cnt_binding and "value" in cnt_binding:
                    try:
                        count = int(float(cnt_binding["value"]))
                    except Exception:
                        # fallback: try to parse as int directly
                        try:
                            count = int(cnt_binding.get("value"))
                        except Exception:
                            count = 0
    except Exception:
        logging.exception("Failed to parse SPARQL JSON result for objects count")
        return JSONResponse(status_code=502, content={"detail": "Failed to parse triplestore response"})

    return {"objects_count": count}
