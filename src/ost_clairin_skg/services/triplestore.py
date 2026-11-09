import json
from abc import ABC, abstractmethod

from src.ost_clairin_skg.infra.commons import app_settings

class TripleStore(ABC):
    @abstractmethod
    def query_triplestore(self, query: str, accept: str = "text/turtle") -> str:
        pass

    def count_triples(self, query: str) -> int:
        response = self.query_triplestore(query, accept="application/sparql-results+json")
        try:
            bindings = json.loads(response)["results"]["bindings"]
            return int(next(iter(bindings[0].values()))["value"]) if bindings else 0
        except (ValueError, KeyError, TypeError, StopIteration) as exc:
            raise RuntimeError(f"Unexpected count query response: { response[:200] }") from exc

def get_triplestore() -> TripleStore:
    # Imported here to avoid a circular import (the connectors import TripleStore)
    from src.ost_clairin_skg.services.graphdb_connector import GraphDBConnector
    from src.ost_clairin_skg.services.qlever_connector import QleverConnector

    stores = {
        "graphdb": GraphDBConnector,
        "qlever": QleverConnector
    }
    name = str(app_settings.get("TRIPLESTORE", "graphdb")).lower()
    try:
        return stores[name]()
    except KeyError:
        raise RuntimeError(f"Unknown triple store '{name}', expected one of {sorted(stores)}")

# Facade functions
def query_triplestore(sparql: str, accept: str = "text/turtle") -> str:
    return get_triplestore().query_triplestore(sparql, accept)

def count_triplestore(sparql: str) -> int:
    return get_triplestore().count_triples(sparql)