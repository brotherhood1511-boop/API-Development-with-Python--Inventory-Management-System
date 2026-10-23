"""Flask REST API for the inventory management system."""

from flask import Flask, jsonify, request

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


if __name__ == "__main__":
    app.run(debug=True)
