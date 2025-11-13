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


def build_filter_clause(product_id: str) -> str:
    """Return the SPARQL filter clause depending on whether id is a URI or a literal."""
    import json as _json
    pid_literal = _json.dumps(product_id)
    if _is_uri(product_id):
        return f"VALUES ?s {{ <{product_id}> }} ."
    return f"FILTER(?pid = {pid_literal}) ."


def build_product_sparql(filter_clause: str) -> str:
    """Return the preserved SPARQL CONSTRUCT text for a product, inserting filter_clause."""
    return f"""
PREFIX datacite: <http://purl.org/spar/datacite/>
PREFIX dc:       <http://purl.org/dc/terms/>
PREFIX silvio:   <http://www.essepuntato.it/2010/06/literalreification/>
PREFIX fabio:    <http://purl.org/spar/fabio/>

CONSTRUCT {{
  ?s a fabio:Work ;
     datacite:hasIdentifier ?id ;
     dc:abstract ?a ;
     dc:title ?t .
  ?id datacite:usesIdentifierScheme ?scheme ;
      silvio:hasLiteralValue ?pid .
}}
WHERE {{
  ?s a fabio:Work .
  OPTIONAL {{ ?s dc:abstract ?a . }}
  OPTIONAL {{ ?s dc:title ?t . }}
  OPTIONAL {{
    ?s datacite:hasIdentifier ?id .
    OPTIONAL {{ ?id datacite:usesIdentifierScheme ?scheme . }}
    OPTIONAL {{ ?id silvio:hasLiteralValue ?pid . }}
  }}
  {filter_clause}
}}
LIMIT 1
""".strip()
