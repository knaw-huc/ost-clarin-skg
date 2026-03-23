import logging
from typing import Dict, Any, List, Optional

import rdflib
from fastapi import APIRouter, Request, Path, Query
from fastapi.responses import JSONResponse

from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import app_settings, API_PREFIX
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore

USER = app_settings.USER
PASS = app_settings.PASS
ENDPOINT = app_settings.ENDPOINT
router = APIRouter(prefix=API_PREFIX)

# SKG-IF context URLs
SKG_IF_CONTEXT_ONTOLOGY = "https://w3id.org/skg-if/context/1.1.0/skg-if.json"
SKG_IF_CONTEXT_API = "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json"


# --- helpers: keep RDF->JSON-LD and context selection here ---



def _rdf_graph_to_product(turtle_data: str, product_id: str) -> Dict[str, Any]:
    """Convert RDF turtle data to SKG-IF product JSON-LD format."""
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")

    # RDF namespace definitions
    DATACITE = rdflib.Namespace("http://purl.org/spar/datacite/")
    DC = rdflib.Namespace("http://purl.org/dc/terms/")
    SILVIO = rdflib.Namespace("http://www.essepuntato.it/2010/06/literalreification/")
    FABIO = rdflib.Namespace("http://purl.org/spar/fabio/")
    RDF = rdflib.RDF

    # Find the main product subject (should be a fabio:Work)
    product_subject = None
    for s in g.subjects(RDF.type, FABIO.Work):
        product_subject = s
        break

    if not product_subject:
        raise ValueError("No fabio:Work found in RDF data")

    # Extract product data
    product: Dict[str, Any] = {
        "local_identifier": str(product_id),
        "entity_type": "product",
        "product_type": "literature",
    }

    # Extract titles
    titles = list(g.objects(product_subject, DC.title))
    if titles:
        product["titles"] = {"en": [str(t) for t in titles]}

    # Extract abstracts
    abstracts = list(g.objects(product_subject, DC.abstract))
    if abstracts:
        product["abstracts"] = {"en": [str(a) for a in abstracts]}

    # Extract identifiers
    identifiers: list = []
    for id_node in g.objects(product_subject, DATACITE.hasIdentifier):
        id_obj: Dict[str, Any] = {"value": None, "scheme": None}

        # Get the literal value
        for literal_val in g.objects(id_node, SILVIO.hasLiteralValue):
            id_obj["value"] = str(literal_val)

        # Get the scheme
        for scheme in g.objects(id_node, DATACITE.usesIdentifierScheme):
            scheme_str = str(scheme)
            # Extract scheme name from URI
            if "#" in scheme_str:
                id_obj["scheme"] = scheme_str.split("#")[-1].lower()
            else:
                id_obj["scheme"] = scheme_str.split("/")[-1].lower()

        if id_obj["value"]:
            identifiers.append(id_obj)

    if identifiers:
        product["identifiers"] = identifiers

    return product


def _build_skg_if_response(product_data: Dict[str, Any], base_url: str = "https://w3id.org/skg-if/sandbox/api/") -> Dict[str, Any]:
    """Build the final SKG-IF JSON-LD response with multiple contexts."""
    return {
        "@context": [
            SKG_IF_CONTEXT_ONTOLOGY,
            SKG_IF_CONTEXT_API,
            {
                "@base": base_url
            }
        ],
        "@graph": [product_data]
    }


@router.get("/products/{id:path}", tags=["Product"])
def get_product(id: str = Path(..., description="Product identifier"), request: Request = None):
    logging.debug("Get product endpoint called for id=%s", id)

    filter_clause = commons.build_filter_clause(id)
    sparql = commons.build_product_sparql(filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"detail": "Failed to query triplestore", "error": str(exc)})

    if not turtle_data:
        return JSONResponse(status_code=404, content={"detail": "Product not found"})

    try:
        # Transform RDF to SKG-IF product format
        product_data = _rdf_graph_to_product(turtle_data, id)

        # Build response with SKG-IF contexts -- compute base_url from request if available
        if request is not None:
            base_url = str(request.base_url).rstrip("/")
            response = _build_skg_if_response(product_data, base_url=f"{base_url}/")
        else:
            response = _build_skg_if_response(product_data)

        return JSONResponse(content=response, media_type="application/ld+json")
    except Exception as exc:
        logging.exception("Failed to convert triplestore response to JSON-LD")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
        )


def _rdf_graph_to_products(turtle_data: str) -> List[Dict[str, Any]]:
    """Convert RDF turtle data to list of SKG-IF products."""
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")

    # RDF namespace definitions
    DATACITE = rdflib.Namespace("http://purl.org/spar/datacite/")
    DC = rdflib.Namespace("http://purl.org/dc/terms/")
    SILVIO = rdflib.Namespace("http://www.essepuntato.it/2010/06/literalreification/")
    FABIO = rdflib.Namespace("http://purl.org/spar/fabio/")
    RDF = rdflib.RDF

    products = []

    # Find all fabio:Work subjects
    for product_subject in g.subjects(RDF.type, FABIO.Work):
        product: Dict[str, Any] = {
            "local_identifier": str(product_subject),
            "entity_type": "product",
            "product_type": "literature",
        }

        # Extract titles
        titles = list(g.objects(product_subject, DC.title))
        if titles:
            product["titles"] = {"en": [str(t) for t in titles]}

        # Extract abstracts
        abstracts = list(g.objects(product_subject, DC.abstract))
        if abstracts:
            product["abstracts"] = {"en": [str(a) for a in abstracts]}

        # Extract identifiers
        identifiers: list = []
        for id_node in g.objects(product_subject, DATACITE.hasIdentifier):
            id_obj: Dict[str, Any] = {"value": None, "scheme": None}

            # Get the literal value
            for literal_val in g.objects(id_node, SILVIO.hasLiteralValue):
                id_obj["value"] = str(literal_val)

            # Get the scheme
            for scheme in g.objects(id_node, DATACITE.usesIdentifierScheme):
                scheme_str = str(scheme)
                # Extract scheme name from URI
                if "#" in scheme_str:
                    id_obj["scheme"] = scheme_str.split("#")[-1].lower()
                else:
                    id_obj["scheme"] = scheme_str.split("/")[-1].lower()

            if id_obj["value"]:
                identifiers.append(id_obj)

        if identifiers:
            product["identifiers"] = identifiers

        products.append(product)

    return products


@router.get("/products", tags=["Product"])
def get_products(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    filter: Optional[str] = Query(None, description="Search filter. Format: comma separated name:value pairs", regex=r'^(,?.+:.+)*$')
):
    """Get paginated list of products in SKG-IF format."""
    logging.debug("Get products endpoint called with page=%d, limit=%d", page, limit)

    # Calculate offset from page number
    offset = (page - 1) * limit

    # Build filter clause from filter param
    filter_clause = None
    if filter:
        # Parse comma separated name:value pairs
        parts = [p.strip() for p in filter.split(',') if p.strip()]
        filters = []
        for part in parts:
            if ':' not in part:
                continue
            name, value = part.split(':', 1)
            name = name.strip()
            value = value.strip()
            # map common filter names to SPARQL triple patterns or FILTERs
            if name == 'product_type':
                # support either a full URI or a simple token like 'literature'
                if value.startswith('http://') or value.startswith('https://'):
                    filters.append(f"?s a <{value}> .")
                else:
                    # match rdf:type URI that contains the token (case-insensitive)
                    filters.append(f"?s a ?type . FILTER(CONTAINS(LCASE(STR(?type)), LCASE(\"{value}\"))) .")
            elif name.startswith('contributions.person.identifiers.id'):
                # pattern: contributions.person.identifiers.id:0000-... map to identifier literal match
                filters.append(f"?s datacite:hasIdentifier ?id . ?id silvio:hasLiteralValue \"{value}\" .")
            elif name.startswith('contributions.person.identifiers.scheme') or name.endswith('.scheme'):
                filters.append(f"?s datacite:hasIdentifier ?id . ?id datacite:usesIdentifierScheme ?scheme . FILTER( LCASE(STR(?scheme)) = LCASE(\"{value}\") ) .")
            elif name.startswith('cf.search.title') or name == 'title':
                # simple CONTAINS match on dc:title
                filters.append(f"?s dc:title ?t . FILTER(CONTAINS(LCASE(STR(?t)), LCASE(\"{value}\"))) .")
            else:
                # Generic fallback: try matching a literal on subject with property named by 'name'
                # Treat name as simple predicate local name in skg or dc
                # This fallback simply binds a variable and checks for literal equality
                filters.append(f"?s <{name}> ?v . FILTER(STR(?v) = \"{value}\") .")

        # Combine filters with newline (AND semantics)
        if filters:
            filter_clause = '\n    '.join(filters)

    # Build SPARQL query with pagination and optional filter
    sparql = commons.build_products_sparql(limit=limit, offset=offset, filter_clause=filter_clause)
    logging.debug("SPARQL query: %s", sparql)

    try:
        turtle_data = query_triplestore(sparql)
    except RuntimeError as exc:
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to query triplestore", "error": str(exc)}
        )

    if not turtle_data:
        # Return empty result set
        products = []
    else:
        try:
            products = _rdf_graph_to_products(turtle_data)
        except Exception as exc:
            logging.exception("Failed to convert triplestore response to JSON-LD")
            return JSONResponse(
                status_code=502,
                content={"detail": "Failed to convert triplestore response to JSON-LD", "error": str(exc)},
            )

    # Build base URL from request
    base_url = str(request.base_url).rstrip("/")
    api_path = f"{API_PREFIX}/products"

    # Build current page URL
    current_url = f"{base_url}{api_path}?page={page}"
    if limit != 10:
        current_url += f"&limit={limit}"

    # Build next page URL (always include for pagination, even if we don't know if there are more items)
    next_page_url = f"{base_url}{api_path}?page={page + 1}"
    if limit != 10:
        next_page_url += f"&limit={limit}"

    # Build search result base URL (without page param)
    search_url = f"{base_url}{api_path}"
    if limit != 10:
        search_url += f"?limit={limit}"

    # Build response with SKG-IF metadata
    response = {
        "@context": [
            SKG_IF_CONTEXT_ONTOLOGY,
            SKG_IF_CONTEXT_API,
            {
                "@base": f"{base_url}/"
            }
        ],
        "meta": {
            "local_identifier": current_url,
            "entity_type": "search_result_page",
            "next_page": {
                "local_identifier": next_page_url,
                "entity_type": "search_result_page"
            },
            "part_of": {
                "local_identifier": search_url,
                "entity_type": "search_result"
                # Note: total_items would require a separate COUNT query
                # Can be added if needed
            }
        },
        "@graph": products
    }

    return JSONResponse(content=response, media_type="application/ld+json")
