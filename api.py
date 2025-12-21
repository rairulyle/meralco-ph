"""
MERALCO API - Philippines Electricity Rate API

Provides a REST endpoint for current MERALCO (Manila Electric Company)
electricity rates in the Philippines.
"""

from datetime import datetime
from flask import Flask, jsonify
from scraper import get_meralco_rates

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
        return jsonify(_cache["data"])

    # Fetch fresh data
    now = datetime.now()
    data = get_meralco_rates()
    _cache["data"] = data
    _cache["month"] = (now.year, now.month)

    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
