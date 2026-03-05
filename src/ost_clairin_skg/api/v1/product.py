import json
import logging
from typing import Optional, Dict, Any, Set

import rdflib
from fastapi import APIRouter, Query, Request, Path
from fastapi.responses import JSONResponse
from pyld import jsonld

from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import app_settings, API_PREFIX
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore

USER = app_settings.USER
PASS = app_settings.PASS
ENDPOINT = app_settings.ENDPOINT
router = APIRouter(prefix=API_PREFIX)


# --- helpers: keep RDF->JSON-LD and context selection here ---

def _graph_to_compacted_jsonld(turtle_data: str) -> Dict[str, Any]:
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")

    nodes: Dict[str, Dict[str, Any]] = {}

    def node_id(term: rdflib.term.Node) -> str:
        if isinstance(term, rdflib.BNode):
            return f"_:{term}"
        return str(term)

    for s, p, o in g:
        sid = node_id(s)
        if sid not in nodes:
            nodes[sid] = {"@id": sid}
        pid = str(p)

        if isinstance(o, rdflib.Literal):
            value: Dict[str, Any] = {"@value": str(o)}
            if o.language:
                value["@language"] = o.language
            elif o.datatype:
                value["@type"] = str(o.datatype)
        else:
            oid = node_id(o)
            value = {"@id": oid}

        nodes[sid].setdefault(pid, []).append(value)

    expanded = list(nodes.values())
    doc = {"@graph": expanded}

    context = {
        "datacite": "http://purl.org/spar/datacite/",
        "dc": "http://purl.org/dc/terms/",
        "silvio": "http://www.essepuntato.it/2010/06/literalreification/",
        "fabio": "http://purl.org/spar/fabio/",
        "title": "http://purl.org/dc/terms/title",
        "hasIdentifier": "http://purl.org/spar/datacite/hasIdentifier",
        "usesIdentifierScheme": "http://purl.org/spar/datacite/usesIdentifierScheme",
        "hasLiteralValue": "http://www.essepuntato.it/2010/06/literalreification/hasLiteralValue",
    }

    compacted = jsonld.compact(doc, context)
    return compacted


def _select_minimal_context_for_item(item: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    used_terms: Set[str] = set()

    def collect(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.startswith("@"):
                    if k == "@type":
                        collect(v)
                    continue
                if k in context:
                    used_terms.add(k)
                collect(v)
        elif isinstance(obj, list):
            for it in obj:
                collect(it)
        elif isinstance(obj, str):
            if ":" in obj:
                prefix = obj.split(":", 1)[0]
                if prefix in context:
                    used_terms.add(prefix)

    collect(item)
    minimal_ctx = {k: context[k] for k in context.keys() if k in used_terms}
    return minimal_ctx


@router.get("/product/{id:path}", tags=["Product"])
def get_product(id: str = Path(..., description="Product identifier"), request: Request = None):
    logging.debug("Get product endpoint called for id=%s", id)

    filter_clause = commons.build_filter_clause(id)
    sparql = commons.build_product_sparql(filter_clause)
    print(sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    if not turtle_data:
        return JSONResponse(status_code=404, content={"detail": "Product not found"})

    try:
        compacted = _graph_to_compacted_jsonld(turtle_data)

        # extract items (graph) — preserve earlier semantics
        if isinstance(compacted, dict) and "@graph" in compacted:
            items = compacted["@graph"]
        else:
            items = [compacted]

        if not items:
            return JSONResponse(status_code=404, content={"detail": "Product not found"})

        item = items[0] if items else compacted
        ctx = compacted.get("@context") if isinstance(compacted, dict) else None

        if isinstance(item, dict) and isinstance(ctx, dict):
            minimal_ctx = _select_minimal_context_for_item(item, ctx)
            item = dict(item)
            item["@context"] = minimal_ctx

        return JSONResponse(content=item, media_type="application/ld+json")
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )


# ... rest of file (get_products) remains unchanged ...
