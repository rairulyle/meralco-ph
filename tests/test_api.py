"""Tests for the MERALCO API."""

import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from flask.testing import FlaskClient

from src.api import FALLBACK_RETRY_SECONDS, _cache, app
from src.parser import MeralcoRatesResult

FIXED_NOW = datetime(2026, 6, 15, 12, 0, 0)

MOCK_RATES: MeralcoRatesResult = {
    "success": True,
    "error": None,
    "warning": None,
    "date": "03/2026",
    "data": [
        {
            "kwh": 50,
            "rate": 14.1766,
            "rate_change": 0.6289,
            "rate_change_percent": 4.65,
            "trend": "up",
        },
        {
            "kwh": 70,
            "rate": 14.0395,
            "rate_change": 0.6289,
            "rate_change_percent": 4.69,
            "trend": "up",
        },
        {
            "kwh": 100,
            "rate": 13.9364,
            "rate_change": 0.6289,
            "rate_change_percent": 4.73,
            "trend": "up",
        },
        {
            "kwh": 200,
            "rate": 13.8161,
            "rate_change": 0.6427,
            "rate_change_percent": 4.88,
            "trend": "up",
        },
        {
            "kwh": 300,
            "rate": 14.1253,
            "rate_change": 0.6289,
            "rate_change_percent": 4.66,
            "trend": "up",
        },
        {
            "kwh": 400,
            "rate": 14.4348,
            "rate_change": 0.6289,
            "rate_change_percent": 4.55,
            "trend": "up",
        },
        {
            "kwh": 500,
            "rate": 14.9969,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
        {
            "kwh": 600,
            "rate": 14.9889,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
        {
            "kwh": 700,
            "rate": 14.9902,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
        {
            "kwh": 800,
            "rate": 14.9977,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
        {
            "kwh": 900,
            "rate": 15.0034,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
        {
            "kwh": 1000,
            "rate": 15.0079,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
        {
            "kwh": 1500,
            "rate": 15.0548,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
        {
            "kwh": 3000,
            "rate": 15.1769,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
        {
            "kwh": 5000,
            "rate": 15.2256,
            "rate_change": 0.6289,
            "rate_change_percent": 4.38,
            "trend": "up",
        },
    ],
    "meta": {
        "timestamp": "2026-06-09T10:00:00",
        "source": "https://example.com/test.pdf",
    },
}


@pytest.fixture
def client() -> Iterator[FlaskClient]:
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def reset_cache() -> Iterator[None]:
    _cache["data"] = None
    _cache["month"] = None
    _cache["is_fallback"] = False
    _cache["timestamp"] = None
    yield
    _cache["data"] = None
    _cache["month"] = None
    _cache["is_fallback"] = False
    _cache["timestamp"] = None


def test_index(client: FlaskClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["service"] == "MERALCO API"
    assert "/rates" in data["endpoints"]
    assert "/rates/typical" in data["endpoints"]
    assert "/rates/<kwh>" in data["endpoints"]


def test_health(client: FlaskClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "ok"


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_returns_all_levels(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert len(data["data"]) == 15
    assert data["date"] == "03/2026"
    assert "error" not in data
    assert "warning" not in data


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_typical_is_200(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/typical")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["data"]["kwh"] == 200
    assert data["data"]["rate"] == 13.8161
    assert "error" not in data
    assert "warning" not in data


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_by_kwh(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/200")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["kwh"] == 200
    assert data["data"]["rate"] == 13.8161


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_over_400(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/500")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["kwh"] == 500
    assert data["data"]["rate"] == 14.9969


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_invalid_kwh_integer(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/999")
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data["success"] is False
    assert "Consumption level not available" in data["error"]
    assert data["data"] is None


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_invalid_kwh_nonnumeric(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/101-200")
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data["success"] is False


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_404_shape_matches_clean_response(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    """404 payload must carry the same fields _clean_response produces."""
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    response = client.get("/rates/999")
    assert response.status_code == 404
    data = json.loads(response.data)
    assert set(data.keys()) == {"success", "error", "date", "data", "meta"}
    assert data["data"] is None
    assert data["date"] == "03/2026"
    assert data["meta"]["source"] == "https://example.com/test.pdf"


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_caches_current_month(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW
    mock_get_rates.return_value = MOCK_RATES

    client.get("/rates")
    client.get("/rates")
    assert mock_get_rates.call_count == 1


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_fallback_retries_after_interval(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW
    mock_rates_with_warning: MeralcoRatesResult = {
        **MOCK_RATES,
        "warning": "Using previous month",
    }
    mock_get_rates.return_value = mock_rates_with_warning

    client.get("/rates")
    assert mock_get_rates.call_count == 1

    _cache["timestamp"] = FIXED_NOW - timedelta(seconds=FALLBACK_RETRY_SECONDS + 1)
    client.get("/rates")
    assert mock_get_rates.call_count == 2


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_failure_returns_stale_cache(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    mock_datetime.now.return_value = FIXED_NOW

    mock_get_rates.return_value = MOCK_RATES
    client.get("/rates")

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
def test_rates_failure_does_not_hammer_upstream(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
    """After a fetch failure with stale cache, subsequent requests within
    FALLBACK_RETRY_SECONDS should serve cached data without re-fetching.
    """
    mock_datetime.now.return_value = FIXED_NOW

    mock_get_rates.return_value = MOCK_RATES
    client.get("/rates")
    assert mock_get_rates.call_count == 1

    # Force the cache to look stale (different month) so the next request
    # tries to refetch.
    _cache["month"] = (2026, 5)
    mock_get_rates.return_value = {
        "success": False,
        "error": "Failed",
        "warning": None,
        "date": None,
        "data": None,
        "meta": {"timestamp": "2026-06-09T10:00:00", "source": None},
    }

    client.get("/rates")
    assert mock_get_rates.call_count == 2

    client.get("/rates")
    client.get("/rates")
    assert mock_get_rates.call_count == 2


@patch("src.api.datetime")
@patch("src.api.get_meralco_rates")
def test_rates_complete_failure_no_cache(
    mock_get_rates: MagicMock, mock_datetime: MagicMock, client: FlaskClient
) -> None:
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
