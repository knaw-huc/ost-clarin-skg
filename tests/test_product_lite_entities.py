from src.ost_clairin_skg.api.v1.products import rdf_graph_to_product, _rdf_graph_to_products


RELATED_ENTITIES_TURTLE = """
@prefix datacite: <http://purl.org/spar/datacite/> .
@prefix dc: <http://purl.org/dc/terms/> .
@prefix silvio: <http://www.essepuntato.it/2010/06/literalreification/> .
@prefix fabio: <http://purl.org/spar/fabio/> .
@prefix pro: <http://purl.org/spar/pro/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix frbr: <http://purl.org/vocab/frbr/core#> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix pso: <http://purl.org/spar/pso/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://example.org/products/1>
    a fabio:Work ;
    dc:title "A product" ;
    pro:isRelatedToRoleInTime <https://example.org/contributions/1> ;
    frbr:realization <https://example.org/expressions/1> .

<https://example.org/contributions/1>
    pro:isHeldBy <https://example.org/persons/1> .

<https://example.org/persons/1>
    foaf:givenName "Ada" ;
    foaf:familyName "Lovelace" ;
    foaf:name "Ada Lovelace" ;
    datacite:hasIdentifier _:orcid .

_:orcid
    datacite:usesIdentifierScheme datacite:orcid ;
    silvio:hasLiteralValue "0000-0001-2345-6789" .

<https://example.org/expressions/1>
    a fabio:Expression ;
    frbr:embodiment <https://example.org/manifestations/1> .

<https://example.org/manifestations/1>
    a fabio:Manifestation ;
    dc:license <https://example.org/license> ;
    pso:holdsStatusInTime [
        pso:withStatus pso:open-access ;
        rdfs:comment "Open" ;
    ] ;
    dcat:accessService <https://example.org/datasources/1> .

<https://example.org/datasources/1>
    foaf:name "Example Repository" ;
    datacite:hasIdentifier _:repository-id .

_:repository-id
    datacite:usesIdentifierScheme datacite:doi ;
    silvio:hasLiteralValue "10.1234/repository" .
"""


def _assert_lite_entities(product):
    person = product["contributions"][0]["by"]
    assert person == {
        "local_identifier": "https://example.org/persons/1",
        "entity_type": "person",
        "identifiers": [{"value": "0000-0001-2345-6789", "scheme": "orcid"}],
        "given_name": "Ada",
        "family_name": "Lovelace",
        "name": "Ada Lovelace",
    }

    datasource = product["manifestations"][0]["biblio"]["hosting_data_source"]
    assert datasource == {
        "local_identifier": "https://example.org/datasources/1",
        "entity_type": "datasource",
        "identifiers": [{"value": "10.1234/repository", "scheme": "doi"}],
        "name": "Example Repository",
    }


def test_single_product_includes_person_lite_and_datasource_lite():
    product = rdf_graph_to_product(RELATED_ENTITIES_TURTLE, "product-1")

    assert product["local_identifier"] == "product-1"
    _assert_lite_entities(product)
    manifestation = product["manifestations"][0]
    assert manifestation["access_rights"]["status"] == "open"
    assert manifestation["license"] == "https://example.org/license"


def test_product_list_includes_person_lite_and_datasource_lite():
    products = _rdf_graph_to_products(RELATED_ENTITIES_TURTLE)

    assert len(products) == 1
    assert products[0]["local_identifier"] == "https://example.org/products/1"
    _assert_lite_entities(products[0])
