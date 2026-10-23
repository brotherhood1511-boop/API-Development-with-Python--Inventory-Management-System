"""Tests for the CLI.

The CLI's HTTP calls are routed into the Flask test client, so these tests
exercise the CLI and the API together. OpenFoodFacts itself is mocked.
"""

import pytest
import requests

import cli
import external_api
from app import app
from inventory import find_by_barcode, find_item, inventory

OAT_MILK = {
    "name": "Oat Milk",
    "brand": "Oatly",
    "barcode": "7394376616228",
    "category": "Plant-based milks",
    "ingredients": "water, oats",
    "image_url": "",
}


class FakeResponse:
    """Wrap a Flask test response so it looks like a requests.Response."""

    def __init__(self, flask_response):
        self.status_code = flask_response.status_code
        self.ok = self.status_code < 400
        self._flask_response = flask_response

    def json(self):
        data = self._flask_response.get_json(silent=True)
        if data is None:
            raise ValueError("No JSON")
        return data


@pytest.fixture(autouse=True)
def cli_uses_test_client(monkeypatch):
    test_client = app.test_client()

    def fake_request(method, url, json=None, params=None, timeout=None):
        path = url.replace(cli.API_URL, "")
        response = test_client.open(path, method=method, json=json, query_string=params)
        return FakeResponse(response)

    monkeypatch.setattr(cli.requests, "request", fake_request)


@pytest.fixture(autouse=True)
def fake_openfoodfacts(monkeypatch):
    def lookup(barcode):
        return dict(OAT_MILK) if barcode == OAT_MILK["barcode"] else None

    monkeypatch.setattr(external_api, "fetch_product_by_barcode", lookup)
    monkeypatch.setattr(external_api, "search_products", lambda name: [dict(OAT_MILK)])


@pytest.fixture
def answers(monkeypatch):
    """Call answers("a", "b") to queue up what the user types."""
    def queue(*values):
        values = iter(values)
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(values))
    return queue


# --- api_request ---

def test_api_request_returns_json():
    assert len(cli.api_request("GET", "/inventory")) == 3


def test_api_request_raises_api_error_with_message():
    with pytest.raises(cli.APIError, match="not found"):
        cli.api_request("GET", "/inventory/999")


def test_api_request_joins_validation_errors():
    with pytest.raises(cli.APIError, match="'price' is required"):
        cli.api_request("POST", "/inventory", {"name": "X"})


def test_api_request_when_server_is_down(monkeypatch):
    def refuse(*args, **kwargs):
        raise requests.exceptions.ConnectionError()
    monkeypatch.setattr(cli.requests, "request", refuse)

    with pytest.raises(cli.APIError, match="Could not reach the API"):
        cli.api_request("GET", "/inventory")


# --- Formatting ---

def test_format_summary_and_item():
    item = find_item(1)
    assert cli.format_summary(item) == "[1] Nutella (Ferrero) - qty 12 @ $5.49"
    assert "Barcode: 3017620422003" in cli.format_item(item)


# --- Input helpers ---

def test_prompt_number_reasks_until_valid(answers, capsys):
    answers("abc", "-2", "7")
    assert cli.prompt_number("Quantity", int) == 7
    assert capsys.readouterr().out.count("Please enter a number") == 2


def test_prompt_reasks_when_required_and_blank(answers):
    answers("", "Milk")
    assert cli.prompt("Name") == "Milk"


def test_optional_prompt_returns_none_on_blank(answers):
    answers("")
    assert cli.prompt_number("Price", float, required=False) is None


# --- Inventory actions ---

def test_list_items(capsys):
    cli.list_items()
    output = capsys.readouterr().out
    assert "[1] Nutella" in output
    assert "[3] Whole Wheat Bread" in output


def test_view_item(answers, capsys):
    answers("2")
    cli.view_item()
    assert "Organic Almond Milk" in capsys.readouterr().out


def test_add_item(answers, capsys):
    answers("Oat Milk", "4.50", "10", "Oatly", "", "Dairy Alternatives")
    cli.add_item()

    item = find_item(4)
    assert item["name"] == "Oat Milk"
    assert item["price"] == 4.5
    assert item["quantity"] == 10
    assert item["brand"] == "Oatly"
    assert "barcode" not in item
    assert "Added" in capsys.readouterr().out


def test_update_item_changes_only_entered_fields(answers):
    # id, then name/brand/barcode/category/price/quantity (blank = keep)
    answers("1", "", "", "", "", "6.25", "30")
    cli.update_item()

    item = find_item(1)
    assert item["price"] == 6.25
    assert item["quantity"] == 30
    assert item["name"] == "Nutella"


def test_update_item_with_no_changes(answers, capsys):
    answers("1", "", "", "", "", "", "")
    cli.update_item()
    assert "Nothing to update" in capsys.readouterr().out


def test_delete_item_after_confirmation(answers):
    answers("2", "y")
    cli.delete_item()
    assert find_item(2) is None


def test_delete_item_cancelled(answers):
    answers("2", "n")
    cli.delete_item()
    assert find_item(2) is not None


def test_search_inventory(answers, capsys):
    answers("bread")
    cli.search_inventory()
    output = capsys.readouterr().out
    assert "Whole Wheat Bread" in output
    assert "Nutella" not in output


def test_low_stock_report(answers, capsys):
    answers("10")
    cli.low_stock_report()
    output = capsys.readouterr().out
    assert "Whole Wheat Bread" in output
    assert "Nutella" not in output


# --- OpenFoodFacts actions ---

def test_lookup_barcode_and_add_to_inventory(answers, capsys):
    answers("7394376616228", "y", "5.99", "6")
    cli.lookup_barcode()

    item = find_by_barcode("7394376616228")
    assert item["name"] == "Oat Milk"
    assert item["quantity"] == 6
    assert "Oatly" in capsys.readouterr().out


def test_lookup_barcode_without_adding(answers):
    answers("7394376616228", "n")
    cli.lookup_barcode()
    assert len(inventory) == 3


def test_search_openfoodfacts_and_import_choice(answers):
    answers("oat milk", "1", "5.99", "6")
    cli.search_openfoodfacts()
    assert find_by_barcode("7394376616228") is not None


def test_search_openfoodfacts_skip(answers):
    answers("oat milk", "")
    cli.search_openfoodfacts()
    assert len(inventory) == 3


def test_search_openfoodfacts_invalid_choice(answers, capsys):
    answers("oat milk", "9")
    cli.search_openfoodfacts()
    assert "Invalid choice" in capsys.readouterr().out
    assert len(inventory) == 3


def test_import_product(answers):
    answers("7394376616228", "5.99", "6")
    cli.import_product()
    assert find_by_barcode("7394376616228")["price"] == 5.99


def test_refresh_item(answers, monkeypatch, capsys):
    monkeypatch.setattr(
        external_api, "fetch_product_by_barcode", lambda barcode: dict(OAT_MILK, barcode=barcode)
    )
    answers("1")
    cli.refresh_item()
    assert find_item(1)["ingredients"] == "water, oats"
    assert "Refreshed" in capsys.readouterr().out


# --- Main menu ---

def test_main_runs_actions_and_exits(answers, capsys):
    answers("1", "0")
    cli.main()
    output = capsys.readouterr().out
    assert "Inventory Admin Portal" in output
    assert "[1] Nutella" in output
    assert "Goodbye!" in output


def test_main_reports_invalid_option(answers, capsys):
    answers("42", "0")
    cli.main()
    assert "Invalid option" in capsys.readouterr().out


def test_main_shows_api_errors_and_keeps_running(answers, capsys):
    answers("2", "999", "0")
    cli.main()
    output = capsys.readouterr().out
    assert "Error: Item with id 999 not found" in output
    assert "Goodbye!" in output


def test_main_exits_on_ctrl_d(monkeypatch, capsys):
    def eof(_prompt=""):
        raise EOFError
    monkeypatch.setattr("builtins.input", eof)
    cli.main()
    assert "Goodbye!" in capsys.readouterr().out
