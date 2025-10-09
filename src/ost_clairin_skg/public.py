import logging

from fastapi import APIRouter


router = APIRouter()
@router.get("/health", tags=["Public"])
def health_check():
    logging.debug("Health check endpoint called")
    return {"status": "ok"}

@router.get("/ping", tags=["Public"])
def ping():
    logging.debug("Ping endpoint called")
    return {"message": "pong"}

@router.get("/product", tags=["Public"])
def get_product():
    logging.debug("Get product endpoint called")
    product = {}
    return product
@router.get("/products", tags=["Public"])
def get_products():
    logging.debug("Get products endpoint called")
    products = [
        {},
        {},
        {},
    ]
    return products