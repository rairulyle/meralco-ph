"""Tests for the MERALCO API."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.api import app, _cache, FALLBACK_RETRY_SECONDS

FIXED_NOW = datetime(2026, 6, 15, 12, 0, 0)

MOCK_RATES = {
    "success": True,
    "error": None,
    "warning": None,
    "date": "03/2026",
    "data": [
        {"name": "0-20 kWh", "min_kwh": 0, "max_kwh": 20,
         "rate": 13.7458, "rate_change": 0.6289, "rate_change_percent": 4.80, "trend": "up"},
        {"name": "21-50 kWh", "min_kwh": 21, "max_kwh": 50,
         "rate": 13.7458, "rate_change": 0.6289, "rate_change_percent": 4.80, "trend": "up"},
        {"name": "51-70 kWh", "min_kwh": 51, "max_kwh": 70,
         "rate": 13.7458, "rate_change": 0.6289, "rate_change_percent": 4.80, "trend": "up"},
        {"name": "71-100 kWh", "min_kwh": 71, "max_kwh": 100,
         "rate": 13.7458, "rate_change": 0.6289, "rate_change_percent": 4.80, "trend": "up"},
        {"name": "101-200 kWh", "min_kwh": 101, "max_kwh": 200,
         "rate": 13.7580, "rate_change": 0.6411, "rate_change_percent": 4.89, "trend": "up"},
        {"name": "201-300 kWh", "min_kwh": 201, "max_kwh": 300,
         "rate": 14.0936, "rate_change": 0.6289, "rate_change_percent": 4.67, "trend": "up"},
        {"name": "301-400 kWh", "min_kwh": 301, "max_kwh": 400,
         "rate": 14.4216, "rate_change": 0.6289, "rate_change_percent": 4.56, "trend": "up"},
        {"name": "Over 400 kWh", "min_kwh": 401, "max_kwh": None,
         "rate": 14.9933, "rate_change": 0.6289, "rate_change_percent": 4.38, "trend": "up"},
    ],
    "meta": {"timestamp": "2026-06-09T10:00:00", "source": "https://example.com/test.pdf"},
}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_cache():
    _cache["data"] = None
    _cache["month"] = None
    _cache["is_fallback"] = False
    _cache["timestamp"] = None
    yield
    _cache["data"] = None
    _cache["month"] = None
    _cache["is_fallback"] = False
    _cache["timestamp"] = None


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["service"] == "MERALCO API"
    assert "/rates" in data["endpoints"]
    assert "/rates/typical" in data["endpoints"]
    assert "/rates/<tier>" in data["endpoints"]


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "ok"


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_returns_all_tiers(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert len(data["data"]) == 8
    assert data["date"] == "03/2026"


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_typical(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/typical")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["data"]["name"] == "101-200 kWh"
    assert data["data"]["rate"] == 13.7580


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_specific_tier(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/201-300")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["data"]["name"] == "201-300 kWh"
    assert data["data"]["rate"] == 14.0936


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_over_400(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/over-400")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["name"] == "Over 400 kWh"


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_invalid_tier(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/999-1000")
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data["success"] is False
    assert data["error"] == "Tier not found"
    assert data["data"] is None


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_caches_current_month(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    client.get("/rates")
    client.get("/rates")
    assert mock_get_rates.call_count == 1


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_fallback_retries_after_interval(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW
    mock_rates_with_warning = {**MOCK_RATES, "warning": "Using previous month"}
    mock_get_rates.return_value = mock_rates_with_warning

    client.get("/rates")
    assert mock_get_rates.call_count == 1

    _cache["timestamp"] = FIXED_NOW - timedelta(seconds=FALLBACK_RETRY_SECONDS + 1)
    client.get("/rates")
    assert mock_get_rates.call_count == 2


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_failure_returns_stale_cache(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW

    # Populate cache
    mock_get_rates.return_value = MOCK_RATES
    client.get("/rates")

    # Expire cache and return failure
    _cache["month"] = (2026, 5)
    mock_get_rates.return_value = {
        "success": False,
        "error": "Failed",
        "warning": None,
        "date": None,
        "data": None,
        "meta": {"timestamp": "2026-06-09T10:00:00", "source": None},
    }

    response = client.get("/rates")
    data = json.loads(response.data)
    assert data["success"] is True
    assert "warning" in data


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_complete_failure_no_cache(mock_get_rates, mock_datetime, client):
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = {
        "success": False,
        "error": "Could not find rate information",
        "warning": None,
        "date": None,
        "data": None,
        "meta": {"timestamp": "2026-06-09T10:00:00", "source": None},
    }

    response = client.get("/rates")
    data = json.loads(response.data)
    assert data["success"] is False
    assert data["error"] is not None
