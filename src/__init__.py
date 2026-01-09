"""
MERALCO Scraper - Philippines Electricity Rate API

Provides tools to scrape and serve current MERALCO electricity rates.
"""

__version__ = "1.0.0"

from .scraper import get_meralco_rates
from .api import app

__all__ = ["get_meralco_rates", "app"]
