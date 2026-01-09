"""
MERALCO API - Philippines Electricity Rate API

Provides a REST endpoint for current MERALCO (Manila Electric Company)
electricity rates in the Philippines.
"""

import logging
from datetime import datetime

from flask import Flask, jsonify
from .scraper import get_meralco_rates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_cache = {"data": None, "month": None}


def is_cache_valid() -> bool:
    """Check if cache is valid for the current month."""
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


def clean_response(data: dict) -> dict:
    """Remove null values from response."""
    return {k: v for k, v in data.items() if v is not None}


@app.route("/rates")
def rates():
    """Get current MERALCO electricity rates."""
    if is_cache_valid():
        logger.info("Returning cached data for %s-%s", _cache["month"][0], _cache["month"][1])
        return jsonify(clean_response(_cache["data"]))

    logger.info("Cache expired or empty, fetching fresh data...")
    now = datetime.now()
    data = get_meralco_rates()

    if data.get("success"):
        if data.get("warning"):
            logger.info("Using previous month data - caching disabled")
        else:
            _cache["data"] = data
            _cache["month"] = (now.year, now.month)
            logger.info("Successfully fetched current month rate: %s PHP/kWh", data["data"].get("rate_kwh"))
        return jsonify(clean_response(data))

    logger.warning("Failed to fetch rates: %s", data.get("error"))

    if _cache["data"] and _cache["data"].get("success"):
        stale_data = _cache["data"].copy()
        if not stale_data.get("warning"):
            stale_data["warning"] = "Current rates temporarily unavailable. Using cached values."
        logger.info("Returning stale cached data from %s-%s", _cache["month"][0], _cache["month"][1])
        return jsonify(clean_response(stale_data))

    return jsonify(clean_response(data))


def main():
    """Main entry point for running the API server."""
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
