"""Flask REST API for the inventory management system."""

from flask import Flask, jsonify, request

import external_api
from external_api import ExternalAPIError
from inventory import add_item, find_by_barcode, find_item, inventory, validate_item

app = Flask(__name__)


def not_found(item_id):
    return jsonify({"error": f"Item with id {item_id} not found"}), 404


@app.route("/", methods=["GET"])
def home():
    """Helper route describing the API."""
    return jsonify({
        "message": "Welcome to the Inventory Management System API",
        "endpoints": {
            "GET /inventory": "List items (optional ?name=, ?category=, ?low_stock=)",
            "GET /inventory/<id>": "Get one item",
            "POST /inventory": "Create an item",
            "PATCH /inventory/<id>": "Update fields on an item",
            "DELETE /inventory/<id>": "Delete an item",
            "GET /external/products/<barcode>": "Look up a product on OpenFoodFacts",
            "GET /external/search?name=": "Search OpenFoodFacts by product name",
            "POST /inventory/import": "Add a product from OpenFoodFacts by barcode",
            "PATCH /inventory/<id>/refresh": "Refresh an item's details from OpenFoodFacts",
        },
    }), 200


@app.route("/inventory", methods=["GET"])
def get_inventory():
    """List all items, optionally filtered by name, category, or low stock."""
    items = inventory

    name = request.args.get("name")
    if name:
        # Case-insensitive partial match so "milk" finds "Organic Almond Milk"
        items = [item for item in items if name.lower() in item["name"].lower()]

    category = request.args.get("category")
    if category:
        items = [item for item in items if item.get("category", "").lower() == category.lower()]

    low_stock = request.args.get("low_stock")
    if low_stock is not None:
        if not low_stock.isdigit():
            return jsonify({"error": "'low_stock' must be a whole number"}), 400
        items = [item for item in items if item["quantity"] <= int(low_stock)]

    return jsonify(items), 200


@app.route("/inventory/<int:item_id>", methods=["GET"])
def get_item(item_id):
    item = find_item(item_id)
    if item is None:
        return not_found(item_id)
    return jsonify(item), 200


@app.route("/inventory", methods=["POST"])
def create_item():
    data = request.get_json(silent=True)
    errors = validate_item(data)
    if errors:
        return jsonify({"errors": errors}), 400

    # Barcodes identify products, so don't allow the same one twice
    barcode = data.get("barcode")
    if barcode and find_by_barcode(barcode):
        return jsonify({"error": f"An item with barcode {barcode} already exists"}), 409

    item = add_item(data)
    return jsonify(item), 201


@app.route("/inventory/<int:item_id>", methods=["PATCH"])
def update_item(item_id):
    item = find_item(item_id)
    if item is None:
        return not_found(item_id)

    data = request.get_json(silent=True)
    errors = validate_item(data, partial=True)
    if not errors and not data:
        errors = ["Provide at least one field to update"]
    if errors:
        return jsonify({"errors": errors}), 400

    barcode = data.get("barcode")
    if barcode:
        existing = find_by_barcode(barcode)
        if existing and existing["id"] != item_id:
            return jsonify({"error": f"An item with barcode {barcode} already exists"}), 409

    item.update(data)
    return jsonify(item), 200


@app.route("/inventory/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    item = find_item(item_id)
    if item is None:
        return not_found(item_id)

    inventory.remove(item)
    return "", 204


# --- OpenFoodFacts integration ---

def external_error(error):
    return jsonify({"error": f"External product service unavailable: {error}"}), 502


@app.route("/external/products/<barcode>", methods=["GET"])
def lookup_external_product(barcode):
    """Look up a product on OpenFoodFacts without saving it."""
    try:
        product = external_api.fetch_product_by_barcode(barcode)
    except ExternalAPIError as error:
        return external_error(error)

    if product is None:
        return jsonify({"error": f"No product found for barcode {barcode}"}), 404
    return jsonify(product), 200


@app.route("/external/search", methods=["GET"])
def search_external_products():
    """Search OpenFoodFacts by product name."""
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"error": "'name' query parameter is required"}), 400

    try:
        products = external_api.search_products(name)
    except ExternalAPIError as error:
        return external_error(error)
    return jsonify(products), 200


@app.route("/inventory/import", methods=["POST"])
def import_item():
    """Fetch a product from OpenFoodFacts by barcode and add it to the inventory.

    Body: {"barcode": "...", "price": 4.99, "quantity": 10}
    Store-specific fields (price, quantity) come from the request; product
    details (name, brand, category, ingredients, image) come from OpenFoodFacts.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"errors": ["Request body must be a JSON object"]}), 400

    barcode = data.get("barcode")
    if not isinstance(barcode, str) or not barcode.strip():
        return jsonify({"errors": ["'barcode' is required"]}), 400
    barcode = barcode.strip()

    if find_by_barcode(barcode):
        return jsonify({"error": f"An item with barcode {barcode} already exists"}), 409

    try:
        product = external_api.fetch_product_by_barcode(barcode)
    except ExternalAPIError as error:
        return external_error(error)

    if product is None:
        return jsonify({"error": f"No product found for barcode {barcode}"}), 404

    # Drop empty details, then let the request override anything (e.g. a nicer name)
    new_item = {key: value for key, value in product.items() if value}
    new_item.update({key: value for key, value in data.items() if key != "barcode"})
    new_item["barcode"] = barcode
    if not new_item.get("name"):
        new_item["name"] = f"Product {barcode}"

    errors = validate_item(new_item)
    if errors:
        return jsonify({"errors": errors}), 400

    item = add_item(new_item)
    return jsonify(item), 201


@app.route("/inventory/<int:item_id>/refresh", methods=["PATCH"])
def refresh_item(item_id):
    """Update an item's product details from OpenFoodFacts, keeping price and quantity."""
    item = find_item(item_id)
    if item is None:
        return not_found(item_id)

    barcode = item.get("barcode")
    if not barcode:
        return jsonify({"error": "Item has no barcode to look up"}), 400

    try:
        product = external_api.fetch_product_by_barcode(barcode)
    except ExternalAPIError as error:
        return external_error(error)

    if product is None:
        return jsonify({"error": f"No product found for barcode {barcode}"}), 404

    item.update({key: value for key, value in product.items() if value})
    return jsonify(item), 200


if __name__ == "__main__":
    app.run(debug=True)
