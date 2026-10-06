from unittest.mock import patch

import pytest

LIST_ENDPOINT_MODULES = ["products", "persons", "organizations", "services", "topics"]

@pytest.fixture(autouse=True)
def mock_count():
    """Keep the list endpoints' total_items COUNT query off the real triplestore."""
    patchers = [
        patch(f"src.ost_clairin_skg.api.v1.{module}.count_triplestore", return_value=42)
        for module in LIST_ENDPOINT_MODULES
    ]
    mocks = {module: p.start() for module, p in zip(LIST_ENDPOINT_MODULES, patchers)}
    yield mocks
    for p in patchers:
        p.stop()
