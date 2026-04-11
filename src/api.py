"""
MERALCO API - Philippines Electricity Rate API

Provides REST endpoints for current MERALCO (Manila Electric Company)
electricity rates, sourced from the official residential_bills.pdf which
contains MERALCO's pre-computed per-kWh rates at standard consumption levels.
"""

import logging
import threading
from datetime import datetime

from flask import Flask, jsonify
from .parser import get_meralco_rates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.json.sort_keys = False

FALLBACK_RETRY_SECONDS = 3600

_cache = {"data": None, "month": None, "is_fallback": False, "timestamp": None}
_fetch_lock = threading.Lock()

VALID_KWH_LEVELS = {50, 70, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 3000, 5000}
TYPICAL_KWH = 200


def _is_cache_valid() -> bool:
    if not _cache["data"] or not _cache["month"]:
        return False

    now = datetime.now()

    if _cache["month"] == (now.year, now.month) and not _cache["is_fallback"]:
        return True

    if _cache["is_fallback"] and _cache["timestamp"]:
        elapsed = (now - _cache["timestamp"]).total_seconds()
        if elapsed < FALLBACK_RETRY_SECONDS:
            return True

    return False


def _fetch_and_cache() -> dict:
    """Fetch rates, update cache, and return the raw result."""
    if _is_cache_valid():
        return _cache["data"]

    with _fetch_lock:
        if _is_cache_valid():
            return _cache["data"]

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

        if _cache["data"] and _cache["data"].get("success"):
            stale = {**_cache["data"]}
            if not stale.get("warning"):
                stale["warning"] = "Current rates temporarily unavailable. Using cached values."
            return stale

        return result


def _find_entry(data: list[dict], kwh: int) -> dict | None:
    for entry in data:
        if entry["kwh"] == kwh:
            return entry
    return None


def _clean_response(data: dict) -> dict:
    """Remove null error and warning fields from response."""
    return {k: v for k, v in data.items() if not (k in ("error", "warning") and v is None)}


@app.route("/")
def index():
    return jsonify({
        "service": "MERALCO API",
        "version": "2.1.0",
        "endpoints": {
            "/rates": "Get all consumption-level rates",
            "/rates/typical": "Get typical household (200 kWh) rate",
            "/rates/<kwh>": "Get rate at a specific consumption level (e.g. /rates/100, /rates/500)",
            "/health": "Health check",
        }
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def _build_response(result: dict, data) -> dict:
    """Build a standard success response."""
    resp = {"success": True, "date": result.get("date"), "data": data, "meta": result.get("meta")}
    if result.get("warning"):
        resp["warning"] = result["warning"]
    return resp


@app.route("/rates")
def rates():
    result = _fetch_and_cache()
    if not result.get("success"):
        return jsonify(_clean_response(result))
    return jsonify(_build_response(result, result.get("data")))


@app.route("/rates/<kwh_slug>")
def rates_by_kwh(kwh_slug):
    result = _fetch_and_cache()

    if not result.get("success"):
        return jsonify(_clean_response(result))

    if kwh_slug == "typical":
        kwh = TYPICAL_KWH
    else:
        try:
            kwh = int(kwh_slug)
        except ValueError:
            kwh = None

    if kwh not in VALID_KWH_LEVELS:
        valid = ", ".join(str(k) for k in sorted(VALID_KWH_LEVELS))
        return jsonify(_clean_response({
            "success": False,
            "error": f"Consumption level not available. Valid: {valid}, typical",
            "date": result.get("date"),
            "data": None,
            "meta": result.get("meta"),
        })), 404

    entry = _find_entry(result.get("data", []), kwh)
    if not entry:
        return jsonify(_clean_response({
            "success": False,
            "error": f"Rate for {kwh} kWh not found in current data",
            "date": result.get("date"),
            "data": None,
            "meta": result.get("meta"),
        })), 404

    return jsonify(_build_response(result, entry))


def main():
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
