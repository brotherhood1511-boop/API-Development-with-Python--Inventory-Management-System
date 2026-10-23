# Inventory Management System

A Flask REST API and command-line admin portal for managing a small retail store's inventory. Employees can add, view, update, and delete items, and pull real product details (name, brand, category, ingredients, image) from the [OpenFoodFacts API](https://world.openfoodfacts.org/data) by barcode or product name.

## Features

- **REST API (Flask)** with full CRUD for inventory items, plus filtering by name, category, and low stock
- **OpenFoodFacts integration** to look up products by barcode, search by name, import a product straight into inventory, and refresh an existing item's details
- **CLI admin portal** that talks to the API through an interactive menu
- **Validation and clear errors**: required fields, types, non-negative price and quantity, duplicate barcodes, and friendly messages when the external API is down
- **Test suite** for each feature (88 tests), with no network access needed

## Project Structure

```
.
├── app.py              # Flask app and all routes
├── inventory.py        # In-memory inventory "database", lookups, and validation
├── external_api.py     # OpenFoodFacts client (barcode lookup and name search)
├── cli.py              # Interactive command-line admin portal
├── tests/
│   ├── conftest.py              # Resets inventory between tests, Flask test client
│   ├── test_inventory.py        # Data helpers and validation
│   ├── test_crud_routes.py      # CRUD routes
│   ├── test_external_api.py     # OpenFoodFacts client (HTTP mocked)
│   ├── test_external_routes.py  # Lookup, search, import, and refresh routes
│   └── test_cli.py              # CLI wired to the real API via the Flask test client
├── Pipfile
└── pytest.ini
```

## Setup

Requires Python 3.12 and Pipenv.

```bash
pipenv install --dev
pipenv shell
```

## Usage

### 1. Start the API

```bash
python app.py
```

The API runs at `http://127.0.0.1:5000`.

### 2. Run the CLI (in a second terminal)

```bash
python cli.py
```

```
=== Inventory Admin Portal ===
 1. List all items
 2. View an item
 3. Add an item
 4. Update an item
 5. Delete an item
 6. Search inventory by name
 7. Low-stock report
 8. Look up a product on OpenFoodFacts by barcode
 9. Search OpenFoodFacts by name
10. Import a product from OpenFoodFacts by barcode
11. Refresh an item's details from OpenFoodFacts
 0. Exit
```

Example: searching OpenFoodFacts and adding a result to the inventory:

```
Choose an option: 9
Product name: oat milk
1. Boring Oat Milk (Boring Oat Milk) - barcode 9421903594204
2. Oat Milk (Just Oat Milk) - barcode 9348470001129
...
Enter a number to add it to inventory (or press Enter to skip): 1
Price: 3.49
Quantity: 15
Imported:
[4] Boring Oat Milk
    Brand: Boring
    Barcode: 9421903594204
    Category: Oat-based drinks
    Price: $3.49
    Quantity: 15
```

To point the CLI at a different server, set `INVENTORY_API_URL`, for example `INVENTORY_API_URL=http://127.0.0.1:5055 python cli.py`.

## API Reference

Inventory items look like this:

```json
{
  "id": 1,
  "name": "Nutella",
  "brand": "Ferrero",
  "barcode": "3017620422003",
  "category": "Spreads",
  "price": 5.49,
  "quantity": 12
}
```

`name`, `price`, and `quantity` are required. `brand`, `barcode`, `category`, `ingredients`, and `image_url` are optional. Barcodes must be unique.

### Inventory (CRUD)

| Method | Route | Description | Success |
| --- | --- | --- | --- |
| GET | `/` | API overview and list of endpoints | 200 |
| GET | `/inventory` | List items. Optional filters: `?name=`, `?category=`, `?low_stock=<n>` | 200 |
| GET | `/inventory/<id>` | Get one item | 200 |
| POST | `/inventory` | Create an item | 201 |
| PATCH | `/inventory/<id>` | Update only the fields you send | 200 |
| DELETE | `/inventory/<id>` | Delete an item | 204 |

### OpenFoodFacts

| Method | Route | Description | Success |
| --- | --- | --- | --- |
| GET | `/external/products/<barcode>` | Look up a product (doesn't save it) | 200 |
| GET | `/external/search?name=` | Search products by name | 200 |
| POST | `/inventory/import` | Fetch a product by barcode and add it to inventory. Body: `{"barcode": "...", "price": 3.49, "quantity": 15}`. Any other item fields you send override the OpenFoodFacts values. | 201 |
| PATCH | `/inventory/<id>/refresh` | Re-fetch an item's product details by its barcode. Price and quantity are kept. | 200 |

### Errors

| Status | When |
| --- | --- |
| 400 | Missing or invalid fields (`{"errors": [...]}`), or a bad query parameter |
| 404 | Item or product not found |
| 409 | An item with that barcode already exists |
| 502 | OpenFoodFacts couldn't be reached |

### curl examples

```bash
curl http://127.0.0.1:5000/inventory?low_stock=10

curl -X POST http://127.0.0.1:5000/inventory \
  -H "Content-Type: application/json" \
  -d '{"name": "Oat Milk", "brand": "Oatly", "price": 4.5, "quantity": 10}'

curl -X PATCH http://127.0.0.1:5000/inventory/1 \
  -H "Content-Type: application/json" \
  -d '{"quantity": 30}'

curl -X DELETE http://127.0.0.1:5000/inventory/2

curl -X POST http://127.0.0.1:5000/inventory/import \
  -H "Content-Type: application/json" \
  -d '{"barcode": "9421903594204", "price": 3.49, "quantity": 15}'
```

## Testing

```bash
pytest
```

The tests reset the inventory before each test and mock all OpenFoodFacts calls, so they run offline. The CLI tests send the CLI's requests through Flask's test client, so they cover the CLI and the API working together.

## Notes and Limitations

- The inventory is stored in memory, so changes are lost when the server restarts.
- Name search uses the OpenFoodFacts search service (`search.openfoodfacts.org`). Barcode lookups use the v2 product API.
- OpenFoodFacts is a community database, so some products are missing details.
