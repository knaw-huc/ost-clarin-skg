# New graph DB connector helpers
import subprocess
from typing import Optional

from src.ost_clairin_skg.infra.commons import app_settings


def query_triplestore(sparql: str, accept: str = "text/turtle") -> str:
    """Send the given SPARQL query to the configured triplestore and return the response as text.

    Uses the `USER`, `PASS`, and `ENDPOINT` values from `app_settings`. Raises RuntimeError
    on command failure or Missing configuration.
    """
    USER = getattr(app_settings, "USER", None)
    PASS = getattr(app_settings, "PASS", None)
    ENDPOINT = getattr(app_settings, "ENDPOINT", None)

    if not USER or not PASS or not ENDPOINT:
        raise RuntimeError("Missing GRAPHDB configuration (USER/PASS/ENDPOINT)")

    args = [
        "curl",
        "-u",
        f"{USER}:{PASS}",
        "-G",
        "--data-urlencode",
        "query@-",
        "-H",
        f"Accept: {accept}",
        ENDPOINT,
    ]
    proc = subprocess.run(args, input=sparql.encode("utf-8"), capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "ignore")
        raise RuntimeError(stderr or "curl failed")
    return proc.stdout.decode("utf-8").strip()



def count_triplestore(sparql: str) -> int:
    """Run a SPARQL SELECT that binds a single count variable and return it as an int."""
    import json
    response = query_triplestore(sparql, accept="application/sparql-results+json")
    try:
        bindings = json.loads(response)["results"]["bindings"]
        return int(next(iter(bindings[0].values()))["value"]) if bindings else 0
    except (ValueError, KeyError, TypeError, StopIteration) as exc:
        raise RuntimeError(f"Unexpected count query response: {response[:200]}") from exc
