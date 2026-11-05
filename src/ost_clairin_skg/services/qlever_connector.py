import subprocess
from src.ost_clairin_skg.infra.commons import app_settings
from src.ost_clairin_skg.services.triplestore import TripleStore

class QleverConnector(TripleStore):
    @staticmethod
    def query_triplestore(sparql: str, accept: str = "application/sparql-results+json") -> dict:
        """Send the given SPARQL query to the configured QLever endpoint and return the response as text.

            Uses `ENDPOINT` from `app_settings`. QLever needs no credentials for read queries.
            The query is POSTed (form-encoded) so long queries don't hit URL length limits.
            Raises RuntimeError on missing configuration, connection failure or an HTTP error status.
            """
        endpoint = getattr(app_settings, "ENDPOINT", None)
        if not endpoint:
            raise RuntimeError("Missing QLever configuration (ENDPOINT)")

        args = [
            "curl",
            "-sS",
            "--fail-with-body",
            "--data-urlencode",
            "query@-",
            "-H",
            f"Accept: {accept}",
            endpoint,
        ]
        proc = subprocess.run(args, input=sparql.encode("utf-8"), capture_output=True)
        if proc.returncode != 0:
            # QLever puts the reason for a rejected query in the response body
            detail = proc.stdout.decode("utf-8", "ignore") or proc.stderr.decode("utf-8", "ignore")
            raise RuntimeError(detail or "curl failed")
        return proc.stdout.decode("utf-8").strip()
