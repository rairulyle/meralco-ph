"""
MERALCO API
Provides a REST endpoint of the current MERALCO electricity rates.
"""

from flask import Flask, jsonify
from scraper import get_meralco_rates

app = Flask(__name__)

# Cache to avoid hammering the website
_cache = {"data": None, "timestamp": None}
CACHE_DURATION_SECONDS = 3600  # 1 hour


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
    from datetime import datetime, timedelta

    # Check cache
    if _cache["data"] and _cache["timestamp"]:
        cache_age = datetime.now() - _cache["timestamp"]
        if cache_age < timedelta(seconds=CACHE_DURATION_SECONDS):
            return jsonify(_cache["data"])

    # Fetch fresh data
    data = get_meralco_rates()
    _cache["data"] = data
    _cache["timestamp"] = datetime.now()

    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
