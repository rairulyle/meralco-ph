"""Tests for the MERALCO API."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.api import app, _cache, clean_response, is_cache_valid, FALLBACK_RETRY_SECONDS

FIXED_NOW = datetime(2026, 6, 15, 12, 0, 0)


@pytest.fixture
def client():
    """Create a test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache before each test."""
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
    """Test the index endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["service"] == "MERALCO API"
    assert "/rates" in data["endpoints"]


def test_health(client):
    """Test the health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "ok"


def test_clean_response_removes_null_values():
    """Test that clean_response removes null values."""
    data = {
        "success": True,
        "error": None,
        "warning": None,
        "data": {"rate": 13.1145},
    }
    cleaned = clean_response(data)
    assert "error" not in cleaned
    assert "warning" not in cleaned
    assert "success" in cleaned
    assert "data" in cleaned


def test_clean_response_keeps_non_null_values():
    """Test that clean_response keeps non-null values."""
    data = {
        "success": True,
        "error": None,
        "warning": "Test warning",
        "data": {"rate": 13.1145},
    }
    cleaned = clean_response(data)
    assert "error" not in cleaned
    assert "warning" in cleaned
    assert cleaned["warning"] == "Test warning"


@patch("src.api.datetime")
def test_is_cache_valid_empty_cache(mock_datetime):
    """Test cache validation with empty cache."""
    mock_datetime.now.return_value = FIXED_NOW
    assert not is_cache_valid()


@patch("src.api.datetime")
def test_is_cache_valid_current_month(mock_datetime):
    """Test cache validation for current month."""
    mock_datetime.now.return_value = FIXED_NOW
    _cache["data"] = {"success": True}
    _cache["month"] = (2026, 6)
    assert is_cache_valid()


@patch("src.api.datetime")
def test_is_cache_valid_expired_month(mock_datetime):
    """Test cache validation for expired month."""
    mock_datetime.now.return_value = FIXED_NOW
    _cache["data"] = {"success": True}
    _cache["month"] = (2026, 5)
    assert not is_cache_valid()


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_current_month_success(mock_get_rates, mock_datetime, client):
    """Test /rates endpoint with current month data."""
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = {
        "success": True,
        "error": None,
        "warning": None,
        "data": {"rate_kwh": 13.1145, "trend": "down"},
        "url": "https://example.com",
        "timestamp": "2026-06-09T10:00:00",
    }

    response = client.get("/rates")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert "error" not in data
    assert "warning" not in data
    assert data["data"]["rate_kwh"] == 13.1145


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_previous_month_cached_with_retry(mock_get_rates, mock_datetime, client):
    """Test /rates endpoint with previous month data (cached with retry interval)."""
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = {
        "success": True,
        "error": None,
        "warning": "June 2026 rates not yet available. Using May 2026 rates instead.",
        "data": {"rate_kwh": 13.1145, "trend": "down"},
        "url": "https://example.com",
        "timestamp": "2026-06-09T10:00:00",
    }

    # First request
    response = client.get("/rates")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert "warning" in data
    assert "error" not in data

    # Second request should use cache (not fetch again)
    response = client.get("/rates")
    assert mock_get_rates.call_count == 1  # Only called once, cached


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_previous_month_retries_after_interval(mock_get_rates, mock_datetime, client):
    """Test /rates endpoint retries fetching after fallback retry interval expires."""
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = {
        "success": True,
        "error": None,
        "warning": "June 2026 rates not yet available. Using May 2026 rates instead.",
        "data": {"rate_kwh": 13.1145, "trend": "down"},
        "url": "https://example.com",
        "timestamp": "2026-06-09T10:00:00",
    }

    # First request caches fallback data
    response = client.get("/rates")
    assert response.status_code == 200
    assert mock_get_rates.call_count == 1

    # Simulate cache timestamp expiring
    _cache["timestamp"] = FIXED_NOW - timedelta(seconds=FALLBACK_RETRY_SECONDS + 1)

    # Next request should retry
    response = client.get("/rates")
    assert mock_get_rates.call_count == 2  # Retried after interval


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_current_month_uses_cache(mock_get_rates, mock_datetime, client):
    """Test /rates endpoint caches current month data."""
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = {
        "success": True,
        "error": None,
        "warning": None,
        "data": {"rate_kwh": 13.1145, "trend": "down"},
        "url": "https://example.com",
        "timestamp": "2026-06-09T10:00:00",
    }

    # First request
    response = client.get("/rates")
    assert response.status_code == 200

    # Second request should use cache
    response = client.get("/rates")
    assert response.status_code == 200
    assert mock_get_rates.call_count == 1  # Only called once


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_both_months_fail_with_stale_cache(mock_get_rates, mock_datetime, client):
    """Test /rates endpoint when both months fail but stale cache exists."""
    mock_datetime.now.return_value = FIXED_NOW
    # First, populate cache with successful data from a previous month
    _cache["data"] = {
        "success": True,
        "error": None,
        "warning": None,
        "data": {"rate_kwh": 13.0, "trend": "down"},
        "url": "https://example.com",
        "timestamp": "2026-05-01T10:00:00",
    }
    _cache["month"] = (2026, 5)

    # Now return failure
    mock_get_rates.return_value = {
        "success": False,
        "error": "Could not find rate information for current or previous month",
        "warning": None,
        "data": {},
    }

    response = client.get("/rates")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True  # Returns stale cache
    assert "warning" in data
    assert "temporarily unavailable" in data["warning"]


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_complete_failure_no_cache(mock_get_rates, mock_datetime, client):
    """Test /rates endpoint when both months fail and no cache exists."""
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = {
        "success": False,
        "error": "Could not find rate information for current or previous month",
        "warning": None,
        "data": {},
    }

    response = client.get("/rates")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is False
    assert "error" in data
    assert "warning" not in data
