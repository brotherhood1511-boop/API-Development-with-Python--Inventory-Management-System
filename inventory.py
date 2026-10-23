"""In-memory inventory "database" and helpers for working with it."""

import copy

# Starting data loaded when the app starts (and restored by reset_inventory)
SEED_INVENTORY = [
    {
        "id": 1,
        "name": "Nutella",
        "brand": "Ferrero",
        "barcode": "3017620422003",
        "category": "Spreads",
        "price": 5.49,
        "quantity": 12,
    },
    {
        "id": 2,
        "name": "Organic Almond Milk",
        "brand": "Silk",
        "barcode": "025293600232",
        "category": "Beverages",
        "price": 3.99,
        "quantity": 24,
    },
    {
        "id": 3,
        "name": "Whole Wheat Bread",
        "brand": "Dave's Killer Bread",
        "barcode": "013764027015",
        "category": "Bakery",
        "price": 4.29,
        "quantity": 8,
    },
]

REQUIRED_FIELDS = {"name", "price", "quantity"}
TEXT_FIELDS = {"brand", "barcode", "category", "ingredients", "image_url"}
ALLOWED_FIELDS = REQUIRED_FIELDS | TEXT_FIELDS

# The "database array" the API reads from and writes to
inventory = copy.deepcopy(SEED_INVENTORY)


def reset_inventory():
    """Restore the inventory to its seed data (used by tests)."""
    inventory.clear()
    inventory.extend(copy.deepcopy(SEED_INVENTORY))


def find_item(item_id):
    """Return the item with the given id, or None if it doesn't exist."""
    return next((item for item in inventory if item["id"] == item_id), None)


def find_by_barcode(barcode):
    """Return the item with the given barcode, or None if it doesn't exist."""
    return next((item for item in inventory if item.get("barcode") == barcode), None)


def next_id():
    """Next id is one past the highest existing id so ids stay unique."""
    return max((item["id"] for item in inventory), default=0) + 1


def add_item(data):
    """Add a new item built from already-validated data and return it."""
    item = {"id": next_id(), **data}
    inventory.append(item)
    return item


def validate_item(data, partial=False):
    """Return a list of validation errors for item data (empty list if valid).

    With partial=True (used for PATCH), required fields may be omitted, but
    any field that is present must still be valid.
    """
    if not isinstance(data, dict):
        return ["Request body must be a JSON object"]

    errors = []

    unknown = set(data) - ALLOWED_FIELDS
    if unknown:
        errors.append(f"Unknown field(s): {', '.join(sorted(unknown))}")

    if not partial:
        for field in sorted(REQUIRED_FIELDS - set(data)):
            errors.append(f"'{field}' is required")

    if "name" in data and (not isinstance(data["name"], str) or not data["name"].strip()):
        errors.append("'name' must be a non-empty string")

    for field in sorted(TEXT_FIELDS & set(data)):
        if not isinstance(data[field], str):
            errors.append(f"'{field}' must be a string")

    # bool is a subclass of int in Python, so rule it out explicitly
    if "price" in data:
        price = data["price"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
            errors.append("'price' must be a number greater than or equal to 0")

    if "quantity" in data:
        quantity = data["quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
            errors.append("'quantity' must be a whole number greater than or equal to 0")

    return errors
