"""Tests for the inventory CRUD routes."""

from inventory import find_item, inventory


def test_home_route_describes_api(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "endpoints" in response.get_json()


# --- Read ---

def test_get_all_items(client):
    response = client.get("/inventory")
    assert response.status_code == 200
    assert len(response.get_json()) == 3


def test_filter_by_name_is_case_insensitive(client):
    data = client.get("/inventory?name=MILK").get_json()
    assert [item["name"] for item in data] == ["Organic Almond Milk"]


def test_filter_by_category(client):
    data = client.get("/inventory?category=bakery").get_json()
    assert [item["id"] for item in data] == [3]


def test_filter_by_low_stock(client):
    data = client.get("/inventory?low_stock=10").get_json()
    assert [item["id"] for item in data] == [3]


def test_low_stock_must_be_a_number(client):
    response = client.get("/inventory?low_stock=abc")
    assert response.status_code == 400


def test_get_item_by_id(client):
    response = client.get("/inventory/1")
    assert response.status_code == 200
    assert response.get_json()["name"] == "Nutella"


def test_get_missing_item_returns_404(client):
    response = client.get("/inventory/999")
    assert response.status_code == 404
    assert "error" in response.get_json()


# --- Create ---

def test_create_item(client):
    payload = {"name": "Oat Milk", "brand": "Oatly", "price": 4.5, "quantity": 10}
    response = client.post("/inventory", json=payload)
    data = response.get_json()

    assert response.status_code == 201
    assert data["id"] == 4
    assert data["name"] == "Oat Milk"
    assert find_item(4) is not None


def test_create_item_with_missing_fields_returns_400(client):
    response = client.post("/inventory", json={"name": "Oat Milk"})
    assert response.status_code == 400
    assert "'price' is required" in response.get_json()["errors"]
    assert len(inventory) == 3


def test_create_item_without_json_returns_400(client):
    response = client.post("/inventory", data="not json", content_type="text/plain")
    assert response.status_code == 400


def test_create_item_with_duplicate_barcode_returns_409(client):
    payload = {"name": "Nutella 2", "barcode": "3017620422003", "price": 1, "quantity": 1}
    response = client.post("/inventory", json=payload)
    assert response.status_code == 409


# --- Update ---

def test_patch_updates_only_given_fields(client):
    response = client.patch("/inventory/1", json={"price": 6.0, "quantity": 20})
    data = response.get_json()

    assert response.status_code == 200
    assert data["price"] == 6.0
    assert data["quantity"] == 20
    assert data["name"] == "Nutella"


def test_patch_missing_item_returns_404(client):
    response = client.patch("/inventory/999", json={"price": 1})
    assert response.status_code == 404


def test_patch_with_invalid_data_returns_400(client):
    response = client.patch("/inventory/1", json={"quantity": -5})
    assert response.status_code == 400
    assert find_item(1)["quantity"] == 12


def test_patch_with_empty_body_returns_400(client):
    response = client.patch("/inventory/1", json={})
    assert response.status_code == 400


def test_patch_to_duplicate_barcode_returns_409(client):
    response = client.patch("/inventory/2", json={"barcode": "3017620422003"})
    assert response.status_code == 409


def test_patch_keeping_own_barcode_is_allowed(client):
    response = client.patch("/inventory/1", json={"barcode": "3017620422003"})
    assert response.status_code == 200


# --- Delete ---

def test_delete_item(client):
    response = client.delete("/inventory/2")
    assert response.status_code == 204
    assert find_item(2) is None
    assert len(inventory) == 2


def test_delete_missing_item_returns_404(client):
    response = client.delete("/inventory/999")
    assert response.status_code == 404
