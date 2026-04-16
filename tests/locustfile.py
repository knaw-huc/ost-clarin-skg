"""Locust load test for SKG-IF Product endpoints

Usage:
  Install locust (recommended in a virtualenv):
    pip install locust

  Run locust against local server:
    locust -f locustfile.py --host=http://localhost:41012

  Open http://localhost:8089 in your browser and start the test.

Configuration:
  LOCUST_PRODUCT_IDS   Comma-separated list of product ids/URIs to hit for individual product requests.
                       Example: 10.1038/sdata.2016.18,http://example.com/product-1

This file defines two tasks:
  - list_products: GET /api/v1/products with random paging and optional filters
  - get_product: GET /api/v1/products/{id} using sample ids

The tests validate basic response status and content-type.
"""

from locust import HttpUser, task, between
import os
import random


def load_product_ids():
    raw = os.getenv("LOCUST_PRODUCT_IDS", "")
    if raw:
        # allow either comma-separated or newline-separated values
        ids = [p.strip() for p in raw.replace('\n', ',').split(',') if p.strip()]
        if ids:
            return ids
    # fallback sample ids (these should be replaced with real ids for meaningful tests)
    return [
        "10.1038/sdata.2016.18",
        "http://localhost:8080/cmd2rdf/graph/oai_ortolang_fr_7af0efee_2426_4452_92e0_ecc4fcad8d32.rdf",
        "http://example.com/skg-if/api/products/prd-c66c6-38be-4d5f-85db-d44c9f869333"
    ]


PRODUCT_IDS = load_product_ids()


class SKGUser(HttpUser):
    """User behavior for SKG product API."""

    # Wait between requests to simulate real users
    wait_time = between(1, 3)

    @task(3)
    def list_products(self):
        """Call the products listing endpoint with random paging and filters."""
        page = random.randint(1, 20)
        limit = random.choice([5, 10, 20])

        # select filters (None means no filter parameter)
        candidate_filters = [None, "cf.search.title:ocean", "product_type:literature", "cf.contributions_orcid:0000-0002-1825-0097"]
        filt = random.choice(candidate_filters)

        params = {"page": page, "limit": limit}
        if filt:
            params["filter"] = filt

        with self.client.get("/api/v1/products", params=params, headers={"Accept": "application/ld+json"}, name="GET /api/v1/products", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status {resp.status_code}")
            else:
                ct = resp.headers.get("Content-Type", "")
                if "application/ld+json" not in ct and "application/json" not in ct:
                    resp.failure(f"Unexpected content-type: {ct}")
                else:
                    # optional lightweight validation: ensure valid JSON
                    try:
                        _ = resp.json()
                    except Exception as e:
                        resp.failure(f"Invalid JSON response: {e}")

    @task(1)
    def get_product(self):
        """Call the single-product endpoint using a random sample id."""
        pid = random.choice(PRODUCT_IDS)

        # If pid looks like a URI, don't encode - locust/httpx will encode path automatically
        path = f"/api/v1/products/{pid}"

        with self.client.get(path, headers={"Accept": "application/ld+json"}, name="GET /api/v1/products/[id]", catch_response=True) as resp:
            if resp.status_code not in (200, 404):
                resp.failure(f"Unexpected status {resp.status_code} for {pid}")
            else:
                # if found, check content-type and JSON
                if resp.status_code == 200:
                    ct = resp.headers.get("Content-Type", "")
                    if "application/ld+json" not in ct and "application/json" not in ct:
                        resp.failure(f"Unexpected content-type: {ct}")
                    else:
                        try:
                            _ = resp.json()
                        except Exception as e:
                            resp.failure(f"Invalid JSON response: {e}")

