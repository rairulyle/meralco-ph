"""
MERALCO API - Philippines Electricity Rate API

Provides a REST endpoint for current MERALCO (Manila Electric Company)
electricity rates in the Philippines.
"""

import logging
from datetime import datetime

from flask import Flask, jsonify
from scraper import get_meralco_rates

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cache to avoid hammering the website
_cache = {"data": None, "month": None}


def is_cache_valid() -> bool:
    """Check if cache is valid (same month as current date)."""
    if not _cache["data"] or not _cache["month"]:
        return False
    now = datetime.now()
    return _cache["month"] == (now.year, now.month)


@app.route("/")
def index():
    return jsonify({
        "service": "MERALCO API",
        "endpoints": {
            "/rates": "Get current electricity rates",
            "/health": "Health check",
        }
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/rates")
def rates():
    # Check cache - expires on first day of next month
    if is_cache_valid():
        logger.info("Returning cached data for %s-%s", _cache["month"][0], _cache["month"][1])
        return jsonify(_cache["data"])

    # Fetch fresh data
    logger.info("Cache expired or empty, fetching fresh data...")
    now = datetime.now()
    data = get_meralco_rates()

    if data.get("success"):
        # Success - update cache with new data
        _cache["data"] = data
        _cache["month"] = (now.year, now.month)
        logger.info("Successfully fetched rate: %s PHP/kWh", data["data"].get("rate_kwh"))
        return jsonify(data)

    # Fetch failed - return stale cache if available
    logger.warning("Failed to fetch rates: %s", data.get("error"))

    if _cache["data"] and _cache["data"].get("success"):
        # Return previous data with error message
        stale_data = _cache["data"].copy()
        stale_data["error"] = f"{data.get('error')}. Using previous month's values instead."
        logger.info("Returning stale cached data from %s-%s", _cache["month"][0], _cache["month"][1])
        return jsonify(stale_data)

    # No cache available, return error
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
