import logging
from typing import Dict, Any, List, Optional
import re
import rdflib
from fastapi import APIRouter, Request, Path, Query
from fastapi.responses import JSONResponse

from src.ost_clairin_skg.infra import commons
from src.ost_clairin_skg.infra.commons import app_settings, API_PREFIX, SKG_IF_CONTEXT_API, SKG_IF_CONTEXT_ONTOLOGY
from src.ost_clairin_skg.infra.commons import DATACITE, DC, SILVIO, FABIO, BIDO, RDF
from src.ost_clairin_skg.infra.commons import LANG_CODE_PREFIX
from src.ost_clairin_skg.api.v1.topics import extract_topic
from src.ost_clairin_skg.services.graphdb_connector import query_triplestore

USER = app_settings.USER
PASS = app_settings.PASS
ENDPOINT = app_settings.ENDPOINT
router = APIRouter(prefix=API_PREFIX)

# SKG-IF product_type derived from the fabio classes a work carries besides fabio:Work.
# Works with none of these classes are reported as "other".
PRODUCT_TYPE_CLASSES: Dict[str, List[str]] = {
    "research data": [f"{FABIO}Dataset"],
    "research software": [f"{FABIO}Software"],
    "literature": [f"{FABIO}{c}" for c in (
        "Article", "JournalArticle", "Book", "BookChapter", "ConferencePaper", "Thesis", "Report",
    )],
}

def _product_type(g: rdflib.Graph, subject) -> str:
    types = {str(t) for t in g.objects(subject, rdflib.RDF.type)}
    for product_type, classes in PRODUCT_TYPE_CLASSES.items():
        if types.intersection(classes):
            return product_type
    return "other"


def _topics(g: rdflib.Graph, subject) -> List[Dict[str, Any]]:
    """SKG-IF topics of a product: terms linked via bido:holdsBibliometricDataInTime/bido:withBibliometricData."""
    topics = []
    for bd in g.objects(subject, BIDO.holdsBibliometricDataInTime):
        for term in g.objects(bd, BIDO.withBibliometricData):
            if (term, RDF.type, FABIO.SubjectTerm) in g:
                topics.append({"term": extract_topic(g, term, commons.strip_local_id_prefix(str(term)))})
    return topics


def _product_type_filter(product_type: str) -> str:
    """SPARQL pattern restricting ?s to works of the given SKG-IF product_type."""
    if product_type == "other":
        all_classes = ", ".join(f"<{c}>" for classes in PRODUCT_TYPE_CLASSES.values() for c in classes)
        return f"FILTER NOT EXISTS {{ ?s a ?ftype . FILTER(?ftype IN ({all_classes})) }} ."
    classes = ", ".join(f"<{c}>" for c in PRODUCT_TYPE_CLASSES[product_type])
    return f"FILTER EXISTS {{ ?s a ?ftype . FILTER(?ftype IN ({classes})) }} ."


# --- helpers: keep RDF->JSON-LD and context selection here ---


def _rdf_graph_to_product(turtle_data: str, product_id: str) -> Dict[str, Any]:
    """Convert RDF turtle data to SKG-IF product JSON-LD format."""
    g = rdflib.Graph()
    g.parse(data=turtle_data, format="turtle")

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
        "product_type": _product_type(g, product_subject),
    }

    # Extract titles
    titles: Dict[str, List[str]] = {}
    for t in g.objects(product_subject, DC.title):
        lang = getattr(t, "language", None)
        key = lang if lang and len(lang) == 2 else "none"
        titles.setdefault(key, []).append(LANG_CODE_PREFIX.sub("", str(t)))
    if titles:
        product["titles"] = titles

    # Extract abstracts
    abstracts: Dict[str, List[str]] = {}
    for a in g.objects(product_subject, DC.abstract):
        lang = getattr(a, "language", None)
        key = lang if lang and len(lang) == 2 else "none"
        abstracts.setdefault(key, []).append(LANG_CODE_PREFIX.sub("", str(a)))
    if abstracts:
        product["abstracts"] = abstracts

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

    topics = _topics(g, product_subject)
    if topics:
        product["topics"] = topics

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
def get_product(id: str = Path(..., description="Product identifier (local ID or full URI)"), request: Request = None):
    """Retrieve a single product by identifier.

    Returns a JSON-LD document following the [SKG-IF](https://skg-if.github.io/interoperability-framework/)
    specification (`entity_type: product`). The `@context` includes both the SKG-IF ontology and
    API contexts, with `@base` set to this service's URL.

    The `id` path segment may be a plain local identifier or a full URI — both are resolved against
    the triplestore. URL-encoded slashes are supported (e.g. `https%3A%2F%2F...`).

    **Responses**
    - `200` — product found, returns JSON-LD
    - `404` — no product with the given identifier
    - `502` — triplestore unreachable or returned unexpected data
    """
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
        try:
            product_data = _rdf_graph_to_product(turtle_data, commons.strip_local_id_prefix(id))
        except ValueError:
            # GraphDB returns only prefix declarations when the CONSTRUCT matches nothing
            return JSONResponse(status_code=404, content={"detail": "Product not found"})

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

    products = []

    # Find all fabio:Work subjects
    for product_subject in g.subjects(RDF.type, FABIO.Work):
        product: Dict[str, Any] = {
            "local_identifier": commons.strip_local_id_prefix(str(product_subject)),
            "entity_type": "product",
            "product_type": _product_type(g, product_subject),
        }

        # Extract titles
        titles: Dict[str, List[str]] = {}
        for t in g.objects(product_subject, DC.title):
            lang = getattr(t, "language", None)
            key = lang if lang and len(lang) == 2 else "none"
            titles.setdefault(key, []).append(LANG_CODE_PREFIX.sub("", str(t)))
        if titles:
            product["titles"] = titles

        # Extract abstracts
        abstracts: Dict[str, List[str]] = {}
        for a in g.objects(product_subject, DC.abstract):
            lang = getattr(a, "language", None)
            key = lang if lang and len(lang) == 2 else "none"
            abstracts.setdefault(key, []).append(LANG_CODE_PREFIX.sub("", str(a)))
        if abstracts:
            product["abstracts"] = abstracts

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

        topics = _topics(g, product_subject)
        if topics:
            product["topics"] = topics

        products.append(product)

    return products


@router.get("/products", tags=["Product"])
def get_products(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Alias for `limit` (page_size will override `limit` if provided)"),
    filter: Optional[str] = Query(None, description="Search filter. Format: comma separated name:value pairs", regex=r'^(,?.+:.+)*$')
):
    """List products with pagination and optional filtering.

    Returns a paginated JSON-LD response following the SKG-IF specification. Each item in
    `@graph` is an `entity_type: product` object. The `meta` block contains pagination links.

    **Pagination** — use `page` (1-based) together with `limit` or `page_size` (they are
    aliases; `page_size` takes priority when both are supplied).

    **Filtering** — supply comma-separated `name:value` pairs.  
    Supported filter keys:

    | Key | Description |
    |-----|-------------|
    | `product_type` / `type` | `literature`, `research data`, `research software`, `other`, or an RDF type URI |
    | `cf.search.title` / `title` | Case-insensitive substring match on title |
    | `cf.search.title_abstract` | Substring match on title **or** abstract |
    | `cf.contributions_orcid` | Contributor ORCID value |
    | `cf.contributions_aff_ror` | Contributor affiliation ROR URI or value |
    | `cf.contributions_aff_country` | Contributor affiliation country code |
    | `cf.cites` | Local identifier or URI of a cited product |
    | `cf.cited_by` | Local identifier or URI of a citing product |
    | `cf.cites_doi` | DOI of a cited product |
    | `cf.cited_by_doi` | DOI of a citing product |

    **Responses**
    - `200` — JSON-LD list (may be empty)
    - `422` — unsupported filter key supplied
    - `502` — triplestore unreachable or returned unexpected data
    """
    # If client provided page_size, treat it as an alias for limit
    effective_limit = page_size if page_size is not None else limit
    used_page_size = page_size is not None

    logging.debug("Get products endpoint called with page=%d, limit=%d (effective_limit=%d, page_size_used=%s)", page, limit, effective_limit, used_page_size)

    # Calculate offset from page number
    offset = (page - 1) * effective_limit

    # Build filter clause from filter param
    filter_clause = None
    if filter:
        # Parse comma separated name:value pairs
        parts = [p.strip() for p in filter.split(',') if p.strip()]
        filters = []

        # Supported exact filter names
        supported = {
            'product_type', 'type',
            'cf.search.title', 'title', 'cf.search.title_abstract',
            'cf.contributions_orcid', 'cf.contributions_aff_ror', 'cf.contributions_aff_country',
            'cf.cites', 'cf.cited_by', 'cf.cites_doi', 'cf.cited_by_doi'
        }

        # Supported patterns (prefixes or suffixes)
        # - contributions.person.identifiers.id* (starts with)
        # - contributions.person.identifiers.scheme* (starts with)
        # - any name that ends with '.scheme'
        unsupported = []

        for part in parts:
            if ':' not in part:
                continue
            name, value = part.split(':', 1)
            name = name.strip()
            value = value.strip()

            # Validate supported names/patterns first
            is_supported = (
                name in supported
                or name.startswith('contributions.person.identifiers.id')
                or name.startswith('contributions.person.identifiers.scheme')
                or name.endswith('.scheme')
            )

            if not is_supported:
                unsupported.append(name)
                continue

            # --- product type / rdf:type ---
            if name in ('product_type', 'type'):
                # Map common product_type tokens to RDF classes where appropriate
                low = value.strip().lower()
                if low in ('publication', 'text'):
                    low = 'literature'
                if value.startswith('http://') or value.startswith('https://'):
                    filters.append(f"?s a <{value}> .")
                elif low in PRODUCT_TYPE_CLASSES or low == 'other':
                    filters.append(_product_type_filter(low))
                else:
                    # Generic match on rdf:type URI containing the token
                    filters.append(f"?s a ?type . FILTER(CONTAINS(LCASE(STR(?type)), LCASE(\"{value}\"))) .")

            # --- title / title OR abstract search ---
            elif name == 'cf.search.title' or name == 'title':
                filters.append(f"?s dc:title ?t . FILTER(CONTAINS(LCASE(STR(?t)), LCASE(\"{value}\"))) .")
            elif name == 'cf.search.title_abstract':
                filters.append(
                    f"FILTER( EXISTS {{ ?s dc:title ?t . FILTER(CONTAINS(LCASE(STR(?t)), LCASE(\"{value}\"))) }} || EXISTS {{ ?s dc:abstract ?a . FILTER(CONTAINS(LCASE(STR(?a)), LCASE(\"{value}\"))) }} ) ."
                )

            # --- contributions: ORCID ---
            elif name == 'cf.contributions_orcid':
                filters.append(
                    f"?s skg:hasContribution ?contrib . ?contrib skg:hasAgent ?agent . ?agent datacite:hasIdentifier ?pid . ?pid silvio:hasLiteralValue \"{value}\" . ?pid datacite:usesIdentifierScheme ?ps . FILTER(CONTAINS(LCASE(STR(?ps)), \"orcid\")) ."
                )

            # --- contributions: affiliation ROR ---
            elif name == 'cf.contributions_aff_ror':
                if value.startswith('http://') or value.startswith('https://'):
                    filters.append(f"?s skg:hasContribution ?contrib . ?contrib skg:declaredAffiliations <{value}> .")
                else:
                    filters.append(f"?s skg:hasContribution ?contrib . ?contrib skg:declaredAffiliations ?aff . ?aff skg:ror ?ror . FILTER(CONTAINS(LCASE(STR(?ror)), LCASE(\"{value}\"))) .")

            # --- contributions: affiliation country ---
            elif name == 'cf.contributions_aff_country':
                filters.append(f"?s skg:hasContribution ?contrib . ?contrib skg:declaredAffiliations ?aff . ?aff skg:country ?country . FILTER(LCASE(STR(?country)) = LCASE(\"{value}\")) .")

            # --- cites / cited_by by local identifier or URI ---
            elif name == 'cf.cites':
                if value.startswith('http://') or value.startswith('https://'):
                    filters.append(f"?s skg:cites <{value}> .")
                else:
                    filters.append(f"?s skg:cites ?other . ?other silvio:hasLiteralValue \"{value}\" .")

            elif name == 'cf.cited_by':
                if value.startswith('http://') or value.startswith('https://'):
                    filters.append(f"?other skg:cites <{value}> . ?other ?p ?o .")
                else:
                    filters.append(f"?other skg:cites ?s . ?other silvio:hasLiteralValue \"{value}\" .")

            # --- cites/cited_by by DOI ---
            elif name == 'cf.cites_doi':
                filters.append(
                    f"?s skg:cites ?other . ?other datacite:hasIdentifier ?idc . ?idc silvio:hasLiteralValue \"{value}\" . ?idc datacite:usesIdentifierScheme ?schc . FILTER(CONTAINS(LCASE(STR(?schc)), \"doi\")) ."
                )

            elif name == 'cf.cited_by_doi':
                filters.append(
                    f"?other skg:cites ?s . ?other datacite:hasIdentifier ?idc . ?idc silvio:hasLiteralValue \"{value}\" . ?idc datacite:usesIdentifierScheme ?schc . FILTER(CONTAINS(LCASE(STR(?schc)), \"doi\")) ."
                )

            # --- backward/compatibility: nested contributions.person.* patterns ---
            elif name.startswith('contributions.person.identifiers.id'):
                filters.append(f"?s datacite:hasIdentifier ?id . ?id silvio:hasLiteralValue \"{value}\" .")
            elif name.startswith('contributions.person.identifiers.scheme') or name.endswith('.scheme'):
                filters.append(f"?s datacite:hasIdentifier ?id . ?id datacite:usesIdentifierScheme ?scheme . FILTER( LCASE(STR(?scheme)) = LCASE(\"{value}\") ) .")

        # If any unsupported filters were requested, return 422
        if unsupported:
            return JSONResponse(status_code=422, content={
                "detail": "Unsupported filter(s) requested",
                "unsupported_filters": unsupported
            })

        # Combine filters with newline (AND semantics)
        if filters:
            filter_clause = '\n    '.join(filters)

    # Build SPARQL query with pagination and optional filter
    sparql = commons.build_products_sparql(limit=effective_limit, offset=offset, filter_clause=filter_clause)
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
    if used_page_size:
        if effective_limit != 10:
            current_url += f"&page_size={effective_limit}"
    else:
        if effective_limit != 10:
            current_url += f"&limit={effective_limit}"

    # Build next page URL (always include for pagination, even if we don't know if there are more items)
    next_page_url = f"{base_url}{api_path}?page={page + 1}"
    if used_page_size:
        if effective_limit != 10:
            next_page_url += f"&page_size={effective_limit}"
    else:
        if effective_limit != 10:
            next_page_url += f"&limit={effective_limit}"

    # Build search result base URL (without page param)
    search_url = f"{base_url}{api_path}"
    if used_page_size:
        if effective_limit != 10:
            search_url += f"?page_size={effective_limit}"
    else:
        if effective_limit != 10:
            search_url += f"?limit={effective_limit}"

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
