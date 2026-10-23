"""Tests for the routes that use OpenFoodFacts. The external client is mocked."""

import pytest

import external_api
from external_api import ExternalAPIError
from inventory import find_by_barcode, find_item, inventory

OAT_MILK = {
    "name": "Oat Milk Barista Edition",
    "brand": "Oatly",
    "barcode": "7394376616228",
    "category": "Plant-based milks",
    "ingredients": "water, oats, rapeseed oil",
    "image_url": "",
}


@pytest.fixture
def fake_lookup(monkeypatch):
    """Make fetch_product_by_barcode return OAT_MILK for its barcode, None otherwise."""
    def lookup(barcode):
        return dict(OAT_MILK, barcode=barcode) if barcode in ("7394376616228", "3017620422003") else None
    monkeypatch.setattr(external_api, "fetch_product_by_barcode", lookup)


@pytest.fixture
def broken_service(monkeypatch):
    def fail(*args, **kwargs):
        raise ExternalAPIError("connection refused")
    monkeypatch.setattr(external_api, "fetch_product_by_barcode", fail)
    monkeypatch.setattr(external_api, "search_products", fail)


# --- GET /external/products/<barcode> ---

def test_lookup_external_product(client, fake_lookup):
    response = client.get("/external/products/7394376616228")
    assert response.status_code == 200
    assert response.get_json()["brand"] == "Oatly"
    assert len(inventory) == 3  # lookup alone doesn't save anything


def test_lookup_unknown_barcode_returns_404(client, fake_lookup):
    response = client.get("/external/products/000")
    assert response.status_code == 404


def test_lookup_when_service_down_returns_502(client, broken_service):
    response = client.get("/external/products/7394376616228")
    assert response.status_code == 502
    assert "unavailable" in response.get_json()["error"]


# --- GET /external/search ---

def test_search_external(client, monkeypatch):
    monkeypatch.setattr(external_api, "search_products", lambda name: [OAT_MILK])
    response = client.get("/external/search?name=oat milk")
    assert response.status_code == 200
    assert response.get_json()[0]["name"] == "Oat Milk Barista Edition"


def test_search_requires_name(client):
    assert client.get("/external/search").status_code == 400
    assert client.get("/external/search?name=  ").status_code == 400


def test_search_when_service_down_returns_502(client, broken_service):
    assert client.get("/external/search?name=oat").status_code == 502


# --- POST /inventory/import ---

def test_import_adds_product_to_inventory(client, fake_lookup):
    response = client.post(
        "/inventory/import",
        json={"barcode": "7394376616228", "price": 5.99, "quantity": 6},
    )
    data = response.get_json()

    assert response.status_code == 201
    assert data["id"] == 4
    assert data["name"] == "Oat Milk Barista Edition"
    assert data["brand"] == "Oatly"
    assert data["price"] == 5.99
    assert data["quantity"] == 6
    assert "image_url" not in data  # empty details are dropped
    assert find_by_barcode("7394376616228") is not None


def test_import_lets_request_override_details(client, fake_lookup):
    response = client.post(
        "/inventory/import",
        json={"barcode": "7394376616228", "name": "Oat Milk", "price": 5.99, "quantity": 6},
    )
    assert response.get_json()["name"] == "Oat Milk"


def test_import_requires_barcode(client, fake_lookup):
    response = client.post("/inventory/import", json={"price": 1, "quantity": 1})
    assert response.status_code == 400


def test_import_requires_price_and_quantity(client, fake_lookup):
    response = client.post("/inventory/import", json={"barcode": "7394376616228"})
    assert response.status_code == 400
    assert len(inventory) == 3


def test_import_rejects_non_object_body(client):
    response = client.post("/inventory/import", json=["7394376616228"])
    assert response.status_code == 400


def test_import_existing_barcode_returns_409(client, fake_lookup):
    response = client.post(
        "/inventory/import",
        json={"barcode": "3017620422003", "price": 1, "quantity": 1},
    )
    assert response.status_code == 409


def test_import_unknown_barcode_returns_404(client, fake_lookup):
    response = client.post("/inventory/import", json={"barcode": "000", "price": 1, "quantity": 1})
    assert response.status_code == 404
    assert len(inventory) == 3


def test_import_when_service_down_returns_502(client, broken_service):
    response = client.post(
        "/inventory/import",
        json={"barcode": "7394376616228", "price": 1, "quantity": 1},
    )
    assert response.status_code == 502


# --- PATCH /inventory/<id>/refresh ---

def test_refresh_updates_details_but_keeps_stock_and_price(client, fake_lookup):
    response = client.patch("/inventory/1/refresh")
    data = response.get_json()

    assert response.status_code == 200
    assert data["ingredients"] == "water, oats, rapeseed oil"
    assert data["price"] == 5.49
    assert data["quantity"] == 12


def test_refresh_missing_item_returns_404(client, fake_lookup):
    assert client.patch("/inventory/999/refresh").status_code == 404


def test_refresh_item_without_barcode_returns_400(client, fake_lookup):
    find_item(2).pop("barcode")
    assert client.patch("/inventory/2/refresh").status_code == 400


def test_refresh_when_product_not_found_returns_404(client, fake_lookup):
    # Item 2's barcode isn't known to the fake lookup
    assert client.patch("/inventory/2/refresh").status_code == 404


def test_refresh_when_service_down_returns_502(client, broken_service):
    assert client.patch("/inventory/1/refresh").status_code == 502
