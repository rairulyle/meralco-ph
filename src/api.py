"""
MERALCO API - Philippines Electricity Rate API

Provides REST endpoints for current MERALCO (Manila Electric Company)
electricity rates, sourced from the official residential_bills.pdf which
contains MERALCO's pre-computed per-kWh rates at standard consumption levels.
"""

import logging
import threading
from datetime import datetime
from typing import TypedDict

from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from flask.typing import ResponseReturnValue

from .parser import MeralcoRatesResult, RateEntry, get_meralco_rates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
assert isinstance(app.json, DefaultJSONProvider)
app.json.sort_keys = False

FALLBACK_RETRY_SECONDS = 3600


class CacheState(TypedDict):
    data: MeralcoRatesResult | None
    month: tuple[int, int] | None
    is_fallback: bool
    timestamp: datetime | None


_cache: CacheState = {
    "data": None,
    "month": None,
    "is_fallback": False,
    "timestamp": None,
}
_fetch_lock = threading.Lock()

VALID_KWH_LEVELS = {
    50,
    70,
    100,
    200,
    300,
    400,
    500,
    600,
    700,
    800,
    900,
    1000,
    1500,
    3000,
    5000,
}
TYPICAL_KWH = 200


def _is_cache_valid() -> bool:
    if not _cache["data"] or not _cache["month"]:
        return False

    now = datetime.now()

    if _cache["month"] == (now.year, now.month) and not _cache["is_fallback"]:
        return True

    timestamp = _cache["timestamp"]
    if _cache["is_fallback"] and timestamp is not None:
        elapsed = (now - timestamp).total_seconds()
        if elapsed < FALLBACK_RETRY_SECONDS:
            return True

    return False


def _fetch_and_cache() -> MeralcoRatesResult:
    """Fetch rates, update cache, and return the raw result."""
    if _is_cache_valid():
        cached = _cache["data"]
        assert cached is not None
        return cached

    with _fetch_lock:
        if _is_cache_valid():
            cached = _cache["data"]
            assert cached is not None
            return cached

        logger.info("Cache expired or empty, fetching fresh data...")
        now = datetime.now()
        result = get_meralco_rates()

        if result.get("success"):
            _cache["data"] = result
            _cache["month"] = (now.year, now.month)
            _cache["is_fallback"] = bool(result.get("warning"))
            _cache["timestamp"] = now
            return result

        logger.warning("Failed to fetch rates: %s", result.get("error"))

        cached_data = _cache["data"]
        if cached_data and cached_data.get("success"):
            stale: MeralcoRatesResult = {
                "success": cached_data["success"],
                "error": cached_data["error"],
                "warning": cached_data["warning"]
                or "Current rates temporarily unavailable. Using cached values.",
                "date": cached_data["date"],
                "data": cached_data["data"],
                "meta": cached_data["meta"],
            }
            return stale

        return result


def _find_entry(data: list[RateEntry], kwh: int) -> RateEntry | None:
    for entry in data:
        if entry["kwh"] == kwh:
            return entry
    return None


class _CleanedResult(TypedDict, total=False):
    success: bool
    error: str
    warning: str
    date: str | None
    data: list[RateEntry] | RateEntry | None
    meta: object


def _clean_response(data: MeralcoRatesResult) -> _CleanedResult:
    """Remove null error and warning fields from response."""
    cleaned: _CleanedResult = {}
    if data.get("success") is not None:
        cleaned["success"] = data["success"]
    if data.get("error") is not None:
        error = data["error"]
        assert error is not None
        cleaned["error"] = error
    if data.get("warning") is not None:
        warning = data["warning"]
        assert warning is not None
        cleaned["warning"] = warning
    cleaned["date"] = data.get("date")
    cleaned["data"] = data.get("data")
    cleaned["meta"] = data.get("meta")
    return cleaned


@app.route("/")
def index() -> ResponseReturnValue:
    return jsonify(
        {
            "service": "MERALCO API",
            "version": "2.0.0",
            "endpoints": {
                "/rates": "Get all consumption-level rates",
                "/rates/typical": "Get typical household (200 kWh) rate",
                "/rates/<kwh>": "Get rate at a specific consumption level (e.g. /rates/100, /rates/500)",
                "/health": "Health check",
            },
        }
    )


@app.route("/health")
def health() -> ResponseReturnValue:
    return jsonify({"status": "ok"})


class _RatesResponse(TypedDict, total=False):
    success: bool
    date: str | None
    data: list[RateEntry] | RateEntry | None
    meta: object
    warning: str


def _build_response(
    result: MeralcoRatesResult, data: list[RateEntry] | RateEntry | None
) -> _RatesResponse:
    """Build a standard success response."""
    resp: _RatesResponse = {
        "success": True,
        "date": result.get("date"),
        "data": data,
        "meta": result.get("meta"),
    }
    warning = result.get("warning")
    if warning:
        resp["warning"] = warning
    return resp


@app.route("/rates")
def rates() -> ResponseReturnValue:
    result = _fetch_and_cache()
    if not result.get("success"):
        return jsonify(_clean_response(result))
    return jsonify(_build_response(result, result.get("data")))


class _ErrorResponse(TypedDict, total=False):
    success: bool
    error: str
    date: str | None
    data: None
    meta: object


@app.route("/rates/<kwh_slug>")
def rates_by_kwh(kwh_slug: str) -> ResponseReturnValue:
    result = _fetch_and_cache()

    if not result.get("success"):
        return jsonify(_clean_response(result))

    kwh: int | None
    if kwh_slug == "typical":
        kwh = TYPICAL_KWH
    else:
        try:
            kwh = int(kwh_slug)
        except ValueError:
            kwh = None

    if kwh is None or kwh not in VALID_KWH_LEVELS:
        valid = ", ".join(str(k) for k in sorted(VALID_KWH_LEVELS))
        error_payload: _ErrorResponse = {
            "success": False,
            "error": f"Consumption level not available. Valid: {valid}, typical",
            "date": result.get("date"),
            "data": None,
            "meta": result.get("meta"),
        }
        return jsonify(error_payload), 404

    entries = result.get("data") or []
    entry = _find_entry(entries, kwh)
    if not entry:
        not_found_payload: _ErrorResponse = {
            "success": False,
            "error": f"Rate for {kwh} kWh not found in current data",
            "date": result.get("date"),
            "data": None,
            "meta": result.get("meta"),
        }
        return jsonify(not_found_payload), 404

    return jsonify(_build_response(result, entry))


def main() -> None:
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
