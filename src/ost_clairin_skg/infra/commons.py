import os

import tomli
from dynaconf import Dynaconf
build_date = os.environ.get("BUILD_DATE", "unknown")

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


# --- SPARQL builder utilities for product endpoint ---

def _is_uri(val: str) -> bool:
    return val.startswith("http://") or val.startswith("https://")


# Subject IRIs in the triplestore carry this scheme prefix; it is hidden from API output
LOCAL_ID_PREFIX = "otf:"


def strip_local_id_prefix(local_identifier: str) -> str:
    """Remove the `otf:` prefix from a local identifier for API output."""
    return local_identifier.removeprefix(LOCAL_ID_PREFIX)


def add_local_id_prefix(local_identifier: str) -> str:
    """Restore the `otf:` prefix on a requested local identifier (URIs and already prefixed ids are kept)."""
    if _is_uri(local_identifier) or local_identifier.startswith(LOCAL_ID_PREFIX):
        return local_identifier
    return LOCAL_ID_PREFIX + local_identifier


def build_filter_clause(product_id: str) -> str:
    """Return the SPARQL filter clause depending on whether id is a URI or a literal.

    A literal matches either the subject IRI (with the `otf:` prefix restored) or one of
    the product's identifier values (e.g. a DOI, compared as given).
    """
    import json as _json
    pid_literal = _json.dumps(product_id)
    if _is_uri(product_id):
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


def build_filter_patterns(filter_value: str, supported: dict[str, tuple[str, str]]) -> tuple[str | None, list[str]]:
    """Translate `name:value,...` pairs into SPARQL patterns on ?s (AND semantics).

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
        if name not in supported:
            unsupported.append(name)
            continue

        pattern, mode = supported[name]
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


# --- SPARQL builder utilities for organisation endpoint ---

def build_organisation_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single organisation, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_organisation_path", filter_clause)


def build_organisations_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of organisations with optional filter."""
    return _build_page_sparql("sparql_organisations_path", limit, offset, filter_clause)


# --- SPARQL builder utilities for datasource endpoint ---

def build_datasource_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single data source, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_datasource_path", filter_clause)


def build_datasources_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of data sources with optional filter."""
    return _build_page_sparql("sparql_datasources_path", limit, offset, filter_clause)


# --- SPARQL builder utilities for service endpoint (SKG-IF srv extension) ---

def build_service_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single service, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_service_path", filter_clause)


def build_services_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of services with optional filter."""
    return _build_page_sparql("sparql_services_path", limit, offset, filter_clause)


# --- SPARQL builder utilities for topic endpoint ---

def build_topic_sparql(filter_clause: str) -> str:
    """Return the SPARQL CONSTRUCT text for a single topic, inserting filter_clause."""
    return _load_sparql_with_filter("sparql_topic_path", filter_clause)


def build_topics_sparql(limit: int = 10, offset: int = 0, filter_clause: str | None = None) -> str:
    """Return the SPARQL CONSTRUCT text for one page of topics with optional filter."""
    return _build_page_sparql("sparql_topics_path", limit, offset, filter_clause)
