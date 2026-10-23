"""Client for the OpenFoodFacts API, used to look up real product details."""

import requests

PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
SEARCH_URL = "https://search.openfoodfacts.org/search"
PRODUCT_FIELDS = "code,product_name,brands,categories,ingredients_text,image_url"
# OpenFoodFacts asks API users to identify their app with a User-Agent
HEADERS = {"User-Agent": "InventoryManagementSystem/1.0 (Flatiron student project)"}
TIMEOUT = 10


class ExternalAPIError(Exception):
    """Raised when OpenFoodFacts can't be reached or returns bad data."""


def _get_json(url, params=None, missing_ok=False):
    """GET a URL and return its JSON. With missing_ok, a 404 returns None."""
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if missing_ok and response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        raise ExternalAPIError(f"OpenFoodFacts request failed: {error}") from error
    except ValueError as error:
        raise ExternalAPIError("OpenFoodFacts returned invalid JSON") from error


def _first(value):
    """Return the first entry of a comma-separated string or a list ("" if empty)."""
    if isinstance(value, list):
        return value[0].strip() if value else ""
    if isinstance(value, str):
        return value.split(",")[0].strip()
    return ""


def normalize_product(product):
    """Convert an OpenFoodFacts product into the fields our inventory uses."""
    return {
        "name": (product.get("product_name") or "").strip(),
        "brand": _first(product.get("brands")),
        "barcode": str(product.get("code") or ""),
        "category": _first(product.get("categories")),
        "ingredients": (product.get("ingredients_text") or "").strip(),
        "image_url": product.get("image_url") or "",
    }


def fetch_product_by_barcode(barcode):
    """Look up one product by barcode. Returns normalized details, or None if not found."""
    data = _get_json(
        PRODUCT_URL.format(barcode=barcode),
        params={"fields": PRODUCT_FIELDS},
        missing_ok=True,
    )

    # Unknown products come back as HTTP 404 and/or "status": 0
    if not data or data.get("status") != 1 or not data.get("product"):
        return None

    product = data["product"]
    product.setdefault("code", data.get("code") or barcode)
    return normalize_product(product)


def search_products(name, limit=5):
    """Search products by name. Returns a list of normalized product details."""
    data = _get_json(SEARCH_URL, params={"q": name, "page_size": limit, "fields": PRODUCT_FIELDS})
    return [normalize_product(product) for product in data.get("hits", [])]
