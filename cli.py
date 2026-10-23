"""Command-line admin portal for the Inventory Management System API.

Start the API first (python app.py), then run: python cli.py
Set INVENTORY_API_URL to point at a different server.
"""

import os

import requests

API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:5000")


class APIError(Exception):
    """Raised when the API can't be reached or returns an error."""


def api_request(method, path, payload=None, params=None):
    """Send a request to the inventory API and return the parsed JSON body."""
    try:
        response = requests.request(
            method, f"{API_URL}{path}", json=payload, params=params, timeout=15
        )
    except requests.exceptions.RequestException as error:
        raise APIError(
            f"Could not reach the API at {API_URL}. Is the server running (python app.py)?"
        ) from error

    if response.status_code == 204:
        return None

    try:
        data = response.json()
    except ValueError:
        data = None

    if not response.ok:
        if isinstance(data, dict):
            message = data.get("error") or "; ".join(data.get("errors", []))
        else:
            message = ""
        raise APIError(message or f"Request failed with status {response.status_code}")

    return data


# --- Formatting ---

def format_item(item):
    """Multi-line description of one inventory item."""
    lines = [f"[{item['id']}] {item['name']}"]
    for label, key in (
        ("Brand", "brand"),
        ("Barcode", "barcode"),
        ("Category", "category"),
        ("Ingredients", "ingredients"),
        ("Image", "image_url"),
    ):
        if item.get(key):
            lines.append(f"    {label}: {item[key]}")
    if "price" in item:
        lines.append(f"    Price: ${item['price']:.2f}")
    if "quantity" in item:
        lines.append(f"    Quantity: {item['quantity']}")
    return "\n".join(lines)


def format_summary(item):
    """One-line summary of an inventory item."""
    brand = f" ({item['brand']})" if item.get("brand") else ""
    return f"[{item['id']}] {item['name']}{brand} - qty {item['quantity']} @ ${item['price']:.2f}"


def format_product(product):
    """One-line summary of an OpenFoodFacts product."""
    brand = f" ({product['brand']})" if product.get("brand") else ""
    return f"{product.get('name') or 'Unnamed product'}{brand} - barcode {product.get('barcode') or 'n/a'}"


def print_items(items):
    if not items:
        print("No items found.")
    for item in items:
        print(format_summary(item))


# --- Input helpers ---

def prompt(label, required=True):
    """Ask for text. Blank input returns None when not required."""
    while True:
        value = input(f"{label}: ").strip()
        if value or not required:
            return value or None
        print("This field is required.")


def prompt_number(label, cast, required=True):
    """Ask for a non-negative number, re-asking until the input is valid."""
    while True:
        value = prompt(label, required)
        if value is None:
            return None
        try:
            number = cast(value)
            if number >= 0:
                return number
        except ValueError:
            pass
        print("Please enter a number greater than or equal to 0.")


def prompt_id():
    return prompt_number("Item ID", int)


# --- Menu actions ---

def list_items():
    print_items(api_request("GET", "/inventory"))


def view_item():
    print(format_item(api_request("GET", f"/inventory/{prompt_id()}")))


def add_item():
    payload = {
        "name": prompt("Name"),
        "price": prompt_number("Price", float),
        "quantity": prompt_number("Quantity", int),
    }
    for field in ("brand", "barcode", "category"):
        value = prompt(f"{field.capitalize()} (optional)", required=False)
        if value:
            payload[field] = value

    item = api_request("POST", "/inventory", payload)
    print(f"Added:\n{format_item(item)}")


def update_item():
    item_id = prompt_id()
    print(format_item(api_request("GET", f"/inventory/{item_id}")))
    print("Press Enter to keep the current value.")

    payload = {}
    for field in ("name", "brand", "barcode", "category"):
        value = prompt(f"New {field}", required=False)
        if value:
            payload[field] = value
    price = prompt_number("New price", float, required=False)
    if price is not None:
        payload["price"] = price
    quantity = prompt_number("New quantity", int, required=False)
    if quantity is not None:
        payload["quantity"] = quantity

    if not payload:
        print("Nothing to update.")
        return
    item = api_request("PATCH", f"/inventory/{item_id}", payload)
    print(f"Updated:\n{format_item(item)}")


def delete_item():
    item_id = prompt_id()
    confirm = prompt(f"Delete item {item_id}? (y/n)").lower()
    if confirm != "y":
        print("Cancelled.")
        return
    api_request("DELETE", f"/inventory/{item_id}")
    print(f"Item {item_id} deleted.")


def search_inventory():
    print_items(api_request("GET", "/inventory", params={"name": prompt("Name contains")}))


def low_stock_report():
    threshold = prompt_number("Show items with quantity at or below", int)
    print_items(api_request("GET", "/inventory", params={"low_stock": threshold}))


def lookup_barcode():
    barcode = prompt("Barcode")
    product = api_request("GET", f"/external/products/{barcode}")
    print(format_product(product))
    if product.get("category"):
        print(f"    Category: {product['category']}")
    if product.get("ingredients"):
        print(f"    Ingredients: {product['ingredients']}")
    if prompt("Add this product to inventory? (y/n)").lower() == "y":
        import_product(barcode)


def search_openfoodfacts():
    products = api_request("GET", "/external/search", params={"name": prompt("Product name")})
    if not products:
        print("No products found.")
        return

    for number, product in enumerate(products, start=1):
        print(f"{number}. {format_product(product)}")

    choice = prompt("Enter a number to add it to inventory (or press Enter to skip)", required=False)
    if not choice:
        return
    if not choice.isdigit() or not 1 <= int(choice) <= len(products):
        print("Invalid choice.")
        return

    barcode = products[int(choice) - 1].get("barcode")
    if not barcode:
        print("That product has no barcode, so it can't be imported.")
        return
    import_product(barcode)


def import_product(barcode=None):
    """Add a product from OpenFoodFacts to the inventory by barcode."""
    payload = {
        "barcode": barcode or prompt("Barcode"),
        "price": prompt_number("Price", float),
        "quantity": prompt_number("Quantity", int),
    }
    item = api_request("POST", "/inventory/import", payload)
    print(f"Imported:\n{format_item(item)}")


def refresh_item():
    item = api_request("PATCH", f"/inventory/{prompt_id()}/refresh")
    print(f"Refreshed:\n{format_item(item)}")


MENU = [
    ("1", "List all items", list_items),
    ("2", "View an item", view_item),
    ("3", "Add an item", add_item),
    ("4", "Update an item", update_item),
    ("5", "Delete an item", delete_item),
    ("6", "Search inventory by name", search_inventory),
    ("7", "Low-stock report", low_stock_report),
    ("8", "Look up a product on OpenFoodFacts by barcode", lookup_barcode),
    ("9", "Search OpenFoodFacts by name", search_openfoodfacts),
    ("10", "Import a product from OpenFoodFacts by barcode", import_product),
    ("11", "Refresh an item's details from OpenFoodFacts", refresh_item),
    ("0", "Exit", None),
]
ACTIONS = {key: action for key, _, action in MENU}


def print_menu():
    print("\n=== Inventory Admin Portal ===")
    for key, label, _ in MENU:
        print(f"{key:>2}. {label}")


def main():
    while True:
        print_menu()
        try:
            choice = input("Choose an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return

        if choice == "0":
            print("Goodbye!")
            return
        action = ACTIONS.get(choice)
        if action is None:
            print("Invalid option, try again.")
            continue

        try:
            action()
        except APIError as error:
            print(f"Error: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")


if __name__ == "__main__":
    main()
