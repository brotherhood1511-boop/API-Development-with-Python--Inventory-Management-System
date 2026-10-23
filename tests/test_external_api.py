"""Tests for the OpenFoodFacts client. Network calls are mocked."""

from unittest.mock import Mock

import pytest
import requests

import external_api
from external_api import (
    ExternalAPIError,
    fetch_product_by_barcode,
    normalize_product,
    search_products,
)

NUTELLA = {
    "code": "3017620422003",
    "product_name": "Nutella",
    "brands": "Nutella, Ferrero",
    "categories": "Spreads, Sweet spreads",
    "ingredients_text": "sugar, palm oil",
    "image_url": "https://images.openfoodfacts.org/nutella.jpg",
}


def mock_get(monkeypatch, json_data=None, error=None):
    """Replace requests.get with a mock returning json_data or raising error."""
    response = Mock(status_code=200)
    response.json.return_value = json_data
    response.raise_for_status.return_value = None
    get = Mock(side_effect=error) if error else Mock(return_value=response)
    monkeypatch.setattr(external_api.requests, "get", get)
    return get


def test_normalize_product_maps_fields():
    assert normalize_product(NUTELLA) == {
        "name": "Nutella",
        "brand": "Nutella",
        "barcode": "3017620422003",
        "category": "Spreads",
        "ingredients": "sugar, palm oil",
        "image_url": "https://images.openfoodfacts.org/nutella.jpg",
    }


def test_normalize_product_handles_lists_and_missing_fields():
    product = normalize_product({"code": 123, "brands": ["Oatly"], "categories": []})
    assert product["brand"] == "Oatly"
    assert product["category"] == ""
    assert product["name"] == ""
    assert product["barcode"] == "123"


def test_fetch_product_by_barcode_found(monkeypatch):
    get = mock_get(monkeypatch, {"code": "3017620422003", "status": 1, "product": NUTELLA})

    product = fetch_product_by_barcode("3017620422003")

    assert product["name"] == "Nutella"
    assert "3017620422003" in get.call_args.args[0]
    assert "User-Agent" in get.call_args.kwargs["headers"]


def test_fetch_product_by_barcode_not_found(monkeypatch):
    mock_get(monkeypatch, {"code": "000", "status": 0, "status_verbose": "product not found"})
    assert fetch_product_by_barcode("000") is None


def test_fetch_product_by_barcode_http_404_means_not_found(monkeypatch):
    get = mock_get(monkeypatch, {"code": "000", "status": 0})
    get.return_value.status_code = 404
    assert fetch_product_by_barcode("000") is None


def test_fetch_product_raises_on_server_error(monkeypatch):
    get = mock_get(monkeypatch)
    get.return_value.status_code = 503
    get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("503")
    with pytest.raises(ExternalAPIError):
        fetch_product_by_barcode("3017620422003")


def test_fetch_product_raises_on_connection_error(monkeypatch):
    mock_get(monkeypatch, error=requests.exceptions.ConnectionError("down"))
    with pytest.raises(ExternalAPIError):
        fetch_product_by_barcode("3017620422003")


def test_fetch_product_raises_on_invalid_json(monkeypatch):
    get = mock_get(monkeypatch)
    get.return_value.json.side_effect = ValueError("bad json")
    with pytest.raises(ExternalAPIError):
        fetch_product_by_barcode("3017620422003")


def test_search_products_returns_normalized_hits(monkeypatch):
    get = mock_get(monkeypatch, {"hits": [NUTELLA, {"code": "1", "product_name": "Nutella B-ready"}]})

    results = search_products("nutella")

    assert [product["name"] for product in results] == ["Nutella", "Nutella B-ready"]
    assert get.call_args.kwargs["params"]["q"] == "nutella"


def test_search_products_with_no_hits(monkeypatch):
    mock_get(monkeypatch, {"hits": []})
    assert search_products("zzzz") == []
