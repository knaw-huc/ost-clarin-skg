import os
import tomli
import rdflib
import re
from dynaconf import Dynaconf
from typing import Any, List, Optional, Dict
from urllib.parse import urlencode

build_date = os.environ.get("BUILD_DATE", "unknown")

# SKG-IF context URLs
SKG_IF_CONTEXT_ONTOLOGY = "https://w3id.org/skg-if/context/1.1.0/skg-if.json"
SKG_IF_CONTEXT_API = "https://w3id.org/skg-if/context/1.0.0/skg-if-api.json"
SKG_IF_CONTEXT_EXT_SRV = "https://w3id.org/skg-if/extension/srv/context/skg-if.json"

# RDF namespace definitions
DATACITE = rdflib.Namespace("http://purl.org/spar/datacite/")
DC = rdflib.Namespace("http://purl.org/dc/terms/")
SILVIO = rdflib.Namespace("http://www.essepuntato.it/2010/06/literalreification/")
FABIO = rdflib.Namespace("http://purl.org/spar/fabio/")
BIDO = rdflib.Namespace("http://purl.org/spar/bido/")
FOAF = rdflib.Namespace("http://xmlns.com/foaf/0.1/")
SRV = rdflib.Namespace("https://w3id.org/skg-if/extension/srv/ontology/")
FRBR = rdflib.Namespace("http://purl.org/vocab/frbr/core#")
PSO = rdflib.Namespace("http://purl.org/spar/pso/")
DCAT = rdflib.Namespace("http://www.w3.org/ns/dcat#")
FRAPO = rdflib.Namespace("http://purl.org/cerif/frapo/")
TI = rdflib.Namespace("http://www.ontologydesignpatterns.org/cp/owl/timeinterval.owl#")
PRISM = rdflib.Namespace("http://prismstandard.org/namespaces/basic/2.0/")
RDF = rdflib.RDF
# Subject IRIs in the triplestore carry this scheme prefix; it is hidden from API output
LOCAL_ID_PREFIX = "otf:"
# Characters a SPARQL IRIREF may not contain; such values must not be placed inside <...>
IRI_INVALID_CHARS = re.compile(r'[\x00-\x20<>"{}|^`\\]')
LANG_CODE_PREFIX = re.compile(r"^\{code:[^}]*\}")
PAGE_SUBQUERY = re.compile(r"SELECT DISTINCT \?s WHERE \{(.*?)\}\s*ORDER BY", re.DOTALL)

def _normalize_prefix(raw: str | None, default: str = "/api/v1") -> str:
    if not raw:
        return default
    p = raw.strip()
    if not p:
        return default
    # ensure single leading slash and no trailing slash (root stays "/")
    return "/" + p.strip("/")

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# only set BASE_DIR if not already set in the environment
if not os.environ.get("BASE_DIR"):
    os.environ["BASE_DIR"] = _repo_root

_raw_app_settings = Dynaconf(root_path=f'{os.environ["BASE_DIR"]}/conf', settings_files=["*.toml"],
                    environments=True)


class SettingsWrapper:
    """Wrap dynaconf object and provide attribute-style access with fallbacks.

    - getattr -> try attribute, then .get(), then env var uppercase
    - get(name, default) -> dynaconf.get then env var fallback
    """

    def __init__(self, wrapped):
        self._wrapped = wrapped

    def __getattr__(self, name: str):
        # Try attribute access first
        try:
            return getattr(self._wrapped, name)
        except Exception:
            pass
        # Try .get() fallback
        try:
            v = self._wrapped.get(name)
            if v is not None:
                return v
        except Exception:
            pass
        # Fallback to environment variable (uppercase)
        env_key = name.upper()
        if env_key in os.environ:
            return os.environ[env_key]
        # If setting is missing, return None (don't raise) so code importing module at import-time won't fail
        return None

    def get(self, name, default=None):
        try:
            v = self._wrapped.get(name)
            if v is not None:
                return v
        except Exception:
            pass
        return os.environ.get(name.upper(), default)


# Export a wrapped settings object used across the project
app_settings = SettingsWrapper(_raw_app_settings)
API_PREFIX = getattr(app_settings, "API_PREFIX", None) or app_settings.get("API_PREFIX", None) or os.environ.get("API_PREFIX", None)
API_PREFIX = _normalize_prefix(API_PREFIX)

# avoid printing settings at import time (noisy in logs)
# print(app_settings.to_dict())  # commented out


def get_project_details(base_dir: str, keys: list):
    with open(os.path.join(base_dir, 'pyproject.toml'), 'rb') as file:
        package_details = tomli.load(file)
    poetry = package_details['project']
    return {key: poetry[key] for key in keys}

def is_uri(val: str) -> bool:
    return val.startswith("http://") or val.startswith("https://")

def is_valid_iri(val: str) -> bool:
    """True if val can be safely written as <val> in a SPARQL query."""
    return not IRI_INVALID_CHARS.search(val)

def strip_local_id_prefix(local_identifier: str) -> str:
    """Remove the `otf:` prefix from a local identifier for API output."""
    return local_identifier.removeprefix(LOCAL_ID_PREFIX)

def add_local_id_prefix(local_identifier: str) -> str:
    """Restore the `otf:` prefix on a requested local identifier (URIs and already prefixed ids are kept)."""
    if is_uri(local_identifier) or local_identifier.startswith(LOCAL_ID_PREFIX):
        return local_identifier
    return LOCAL_ID_PREFIX + local_identifier

def build_filter_clause(product_id: str) -> str:
    """Return the SPARQL filter clause depending on whether id is a URI or a literal.

    A literal matches either the subject IRI (with the `otf:` prefix restored) or one of
    the product's identifier values (e.g. a DOI, compared as given).
    """
    import json as _json
    pid_literal = _json.dumps(product_id)
    if is_uri(product_id) and is_valid_iri(product_id):
        return f"VALUES ?s {{ <{product_id}> }} ."
    subject_literal = _json.dumps(add_local_id_prefix(product_id))
    return (
        f"FILTER(STR(?s) = {subject_literal} || EXISTS {{ "
        f"?s datacite:hasIdentifier/silvio:hasLiteralValue ?fpid . FILTER(STR(?fpid) = {pid_literal}) }}) ."
    )


def build_product_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a product from sparql_product_path setting, inserting filter_clause."""
    sparql_path = app_settings.get("sparql_product_path")
    if not sparql_path:
        raise ValueError("sparql_product_path not configured in settings")

    with open(sparql_path, 'r') as f:
        sparql_template = f.read().strip()

    # Replace the placeholder for filter clause in the WHERE clause
    # Find the WHERE clause and inject the filter before the closing }
    where_end = sparql_template.rfind("}")
    if where_end == -1:
        raise ValueError("Invalid SPARQL template: no closing } found")

    # Insert filter clause before the final closing brace
    modified_sparql = sparql_template[:where_end] + f"\n    {filter_clause}\n" + sparql_template[where_end:]

    return modified_sparql


def _build_page_sparql(setting_name: str, limit: int, offset: int, filter_clause: str | None) -> str:
    """Fill a list template configured under `setting_name`.

    List templates select one page of distinct subjects in a subquery (so LIMIT/OFFSET count
    entities, not result rows) and mark where filters and pagination go with the comment
    placeholders `#FILTERS#` and `#PAGINATION#`.
    """
    sparql_path = app_settings.get(setting_name)
    if not sparql_path:
        raise ValueError(f"{setting_name} not configured in settings")

    with open(sparql_path, 'r') as f:
        sparql_template = f.read().strip()

    for placeholder in ("#FILTERS#", "#PAGINATION#"):
        if placeholder not in sparql_template:
            raise ValueError(f"Invalid SPARQL template {sparql_path}: missing {placeholder} placeholder")

    return (
        sparql_template
        .replace("#FILTERS#", filter_clause or "")
        .replace("#PAGINATION#", f"LIMIT {limit}\n        OFFSET {offset}")
    )

def build_count_sparql(setting_name: str, filter_clause: str | None) -> str:
    """Return a SPARQL SELECT counting the distinct subjects matched by the list template
    configured under `setting_name`, i.e. the total number of items across all pages."""
    sparql_path = app_settings.get(setting_name)
    if not sparql_path:
        raise ValueError(f"{setting_name} not configured in settings")

    with open(sparql_path, 'r') as f:
        sparql_template = f.read().strip()

    match = PAGE_SUBQUERY.search(sparql_template)
    construct_start = sparql_template.find("CONSTRUCT")
    if not match or construct_start == -1:
        raise ValueError(f"Invalid SPARQL template {sparql_path}: cannot derive count query")

    prefixes = sparql_template[:construct_start]
    pattern = match.group(1).replace("#FILTERS#", filter_clause or "")
    return f"{prefixes}SELECT (COUNT(DISTINCT ?s) AS ?total) WHERE {{{pattern}}}"


def build_products_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of products with optional filter."""
    return _build_page_sparql("sparql_products_path", limit, offset, filter_clause)


# --- SPARQL builder utilities for person endpoint ---

def _load_sparql_with_filter(setting_name: str, filter_clause: str | None) -> str:
    """Load the SPARQL template configured under `setting_name` and inject `filter_clause`
    before the final closing brace of the WHERE block."""
    sparql_path = app_settings.get(setting_name)
    if not sparql_path:
        raise ValueError(f"{setting_name} not configured in settings")

    with open(sparql_path, 'r') as f:
        sparql_template = f.read().strip()

    if not filter_clause:
        return sparql_template

    where_end = sparql_template.rfind("}")
    if where_end == -1:
        raise ValueError("Invalid SPARQL template: no closing } found")
    return sparql_template[:where_end] + f"\n    {filter_clause}\n" + sparql_template[where_end:]

def build_filter_patterns(filter_value: str, supported_filters: dict[str, tuple[str, str]]) -> tuple[str | None, list[str]]:
    """Translate `name:value,...` pairs into their corresponding SPARQL patterns on ?s (AND semantics).

    `supported` maps a filter key to (predicate path with {v} as the value variable, match mode),
    where match mode is "exact", "contains" (case-insensitive substring), "scheme"
    (case-insensitive match on the local name of an identifier scheme IRI) or "lang"
    (case-insensitive match on the language tag of a literal).
    Returns (filter_clause, unsupported_keys).
    """
    import json as _json
    filters: list[str] = []
    unsupported: list[str] = []
    for part in (p.strip() for p in filter_value.split(",")):
        if ":" not in part:
            continue
        name, value = (x.strip() for x in part.split(":", 1))
        if name not in supported_filters:
            unsupported.append(name)
            continue

        pattern, mode = supported_filters[name]
        var = f"?fv{len(filters)}"
        literal = _json.dumps(value)
        if mode == "exact":
            condition = f"STR({var}) = {literal}"
        elif mode == "contains":
            condition = f"CONTAINS(LCASE(STR({var})), LCASE({literal}))"
        elif mode == "lang":
            condition = f"LCASE(LANG({var})) = LCASE({literal})"
        else:
            # Compare the scheme's local name (e.g. datacite:orcid -> "orcid")
            condition = f'LCASE(REPLACE(STR({var}), "^.*[/#]", "")) = LCASE({literal})'
        filters.append(f"?s {pattern.format(v=var)} . FILTER({condition}) .")

    return ("\n    ".join(filters) or None), unsupported


def build_person_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single person, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_person_path", filter_clause)

def build_persons_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of persons with optional filter."""
    return _build_page_sparql("sparql_persons_path", limit, offset, filter_clause)


# --- SPARQL organisation endpoint ---
def build_organisation_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single organisation, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_organisation_path", filter_clause)

def build_organisations_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of organisations with optional filter."""
    return _build_page_sparql("sparql_organisations_path", limit, offset, filter_clause)


# --- SPARQL grant endpoint ---
def build_grant_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single grant, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_grant_path", filter_clause)

def build_grants_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of grants with optional filter."""
    return _build_page_sparql("sparql_grants_path", limit, offset, filter_clause)


# --- SPARQL venue endpoint ---
def build_venue_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single venue, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_venue_path", filter_clause)

def build_venues_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of venues with optional filter."""
    return _build_page_sparql("sparql_venues_path", limit, offset, filter_clause)


# --- SPARQL datasource endpoint ---
def build_datasource_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single data source, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_datasource_path", filter_clause)

def build_datasources_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of data sources with optional filter."""
    return _build_page_sparql("sparql_datasources_path", limit, offset, filter_clause)


# --- SPARQL service endpoint (SKG-IF srv extension) ---
def build_service_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single service, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_service_path", filter_clause)

def build_services_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of services with optional filter."""
    return _build_page_sparql("sparql_services_path", limit, offset, filter_clause)


# --- SPARQL topic endpoint ---
def build_topic_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single topic, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_topic_path", filter_clause)

def build_topics_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of topics with optional filter."""
    return _build_page_sparql("sparql_topics_path", limit, offset, filter_clause)

# --- Response building helpers
def build_context(base_url: str, contexts: Optional[List[str]] = None) -> List[Any]:
    return [ SKG_IF_CONTEXT_ONTOLOGY, SKG_IF_CONTEXT_API, {"@base": f"{base_url}/"}, ] + (contexts or [])

def build_page_url(page: Optional[int], page_size: int, fltr: Optional[str], search_url: str) -> str:
    params: Dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if page_size != 10:
        params["page_size"] = page_size
    if fltr:
        params["filter"] = fltr
    return f"{search_url}?{urlencode(params)}" if params else search_url

def build_json_response(base_url: str, page: int, page_size: int, filter: str, totalitcontexts: Optional[List[str]] = None) -> List[Any]:
    base_url = str(request.base_url).rstrip("/")
    search_url = f"{base_url}{API_PREFIX}/persons"
    response = {
        "@context": build_context(base_url),
        "meta": {
            "local_identifier": build_page_url(page, page_size, filter, search_url),
            "entity_type": "search_result_page",
            "part_of": {
                "local_identifier": build_page_url(None, page_size, filter, search_url),
                "entity_type": "search_result",
                "total_items": total_items,
            },
        },
        "@graph": persons,
    }

    if offset + page_size < total_items:
        response["meta"]["next_page"] = {
            "local_identifier": commons.build_page_url(page + 1, page_size, filter, search_url),
            "entity_type": "search_result_page",
        }