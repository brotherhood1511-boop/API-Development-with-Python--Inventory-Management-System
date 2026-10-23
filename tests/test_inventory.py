"""Tests for the inventory data helpers and validation."""

from inventory import (
    add_item,
    find_by_barcode,
    find_item,
    inventory,
    next_id,
    reset_inventory,
    validate_item,
)

VALID_ITEM = {"name": "Oat Milk", "price": 4.5, "quantity": 10}


def test_find_item_returns_item_or_none():
    assert find_item(1)["name"] == "Nutella"
    assert find_item(999) is None


def test_find_by_barcode():
    assert find_by_barcode("3017620422003")["id"] == 1
    assert find_by_barcode("0000") is None


def test_add_item_assigns_next_id():
    expected_id = next_id()
    item = add_item(dict(VALID_ITEM))
    assert item["id"] == expected_id
    assert item in inventory


def test_next_id_on_empty_inventory():
    inventory.clear()
    assert next_id() == 1


def test_reset_inventory_restores_seed_data():
    inventory.clear()
    reset_inventory()
    assert len(inventory) == 3


def test_validate_accepts_valid_item():
    assert validate_item(VALID_ITEM) == []


def test_validate_requires_fields_on_create():
    errors = validate_item({"name": "Oat Milk"})
    assert "'price' is required" in errors
    assert "'quantity' is required" in errors


def test_validate_partial_allows_missing_required_fields():
    assert validate_item({"quantity": 3}, partial=True) == []


def test_validate_rejects_bad_types_and_values():
    errors = validate_item({"name": "  ", "price": -1, "quantity": 1.5, "brand": 7})
    assert "'name' must be a non-empty string" in errors
    assert "'price' must be a number greater than or equal to 0" in errors
    assert "'quantity' must be a whole number greater than or equal to 0" in errors
    assert "'brand' must be a string" in errors


def test_validate_rejects_booleans_as_numbers():
    errors = validate_item({"name": "X", "price": True, "quantity": False})
    assert len(errors) == 2


def test_validate_rejects_unknown_fields_and_non_objects():
    assert validate_item({**VALID_ITEM, "color": "red"}) == ["Unknown field(s): color"]
    assert validate_item(["not", "a", "dict"]) == ["Request body must be a JSON object"]
    assert validate_item(None) == ["Request body must be a JSON object"]
