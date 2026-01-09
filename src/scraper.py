"""
MERALCO API - Scraper Module

Scrapes the current electricity rate from MERALCO (Manila Electric Company)
Philippines news and advisories page.
"""

import logging
import re
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def is_url_reachable(url: str) -> bool:
    """Check if URL exists using a lightweight HEAD request."""
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_current_month_url() -> tuple[str, str]:
    """
    Generate the URL for the current month's rate announcement.
    Returns tuple of (higher_url, lower_url) since we don't know which one exists.
    """
    now = datetime.now()
    month = now.strftime("%B").lower()  # e.g., "december"
    year = now.year

    base_url = "https://company.meralco.com.ph/news-and-advisories"
    higher_url = f"{base_url}/higher-rates-{month}-{year}"
    lower_url = f"{base_url}/lower-rates-{month}-{year}"

    return higher_url, lower_url


def get_month_url(target_date: datetime) -> tuple[str, str]:
    """
    Generate the URL for a specific month's rate announcement.
    Returns tuple of (higher_url, lower_url) since we don't know which one exists.
    """
    month = target_date.strftime("%B").lower()  # e.g., "december"
    year = target_date.year

    base_url = "https://company.meralco.com.ph/news-and-advisories"
    higher_url = f"{base_url}/higher-rates-{month}-{year}"
    lower_url = f"{base_url}/lower-rates-{month}-{year}"

    return higher_url, lower_url


def fetch_page_content(url: str) -> str | None:
    """Fetch page content using Playwright for JavaScript-rendered pages."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        logger.error("Error fetching %s: %s", url, e)
        return None


def parse_rates(html_content: str) -> dict:
    """Parse electricity rates from the page content."""
    soup = BeautifulSoup(html_content, "html.parser")

    rates = {
        "rate_kwh": None,
        "rate_change": None,
        "rate_change_percent": None,
        "rate_unit": "PHP/kWh",
        "raw_text": None,
    }

    # Find the main content area
    main_content = soup.find("main", id="main-content")
    if not main_content:
        main_content = soup.find("article") or soup.find("div", class_="content")

    if main_content:
        text_content = main_content.get_text(separator=" ", strip=True)
        rates["raw_text"] = text_content[:1000]  # Store first 1000 chars for debugging

        # Pattern matching for common rate formats
        # Overall rate: "overall rate for a typical household to P13.1145 per kWh"
        overall_pattern = r'overall\s+rate\s+for\s+a\s+typical\s+household\s+to\s+[P₱]\s*(\d+\.?\d*)\s*per\s*kWh'
        overall_match = re.search(overall_pattern, text_content, re.IGNORECASE)
        if overall_match:
            rates["rate_kwh"] = float(overall_match.group(1))

        # Rate change: "reduction of P0.3557 per kWh" or "increase of P0.1234 per kWh"
        change_pattern = r'(increase|decrease|reduction|upward\s+adjustment)\s+(?:of\s+)?[P₱]\s*(\d+\.?\d*)\s*per\s*kWh'
        change_match = re.search(change_pattern, text_content, re.IGNORECASE)
        if change_match:
            direction = change_match.group(1).lower()
            amount = float(change_match.group(2))
            if direction in ["decrease", "reduction"]:
                amount = -amount
            rates["rate_change"] = amount

            # Calculate percentage change if we have both values
            if rates["rate_kwh"] and rates["rate_change"]:
                previous_rate = rates["rate_kwh"] - rates["rate_change"]
                rates["rate_change_percent"] = round((rates["rate_change"] / previous_rate) * 100, 2)

    return rates


def try_fetch_rates_for_date(target_date: datetime) -> dict:
    """
    Try to fetch rates for a specific date.
    Returns a dictionary with rate information.
    """
    higher_url, lower_url = get_month_url(target_date)

    result = {
        "success": False,
        "url": None,
        "data": {},
        "error": None,
        "warning": None,
        "timestamp": datetime.now().isoformat(),
        "target_month": target_date.strftime("%B %Y"),
    }

    # Try lower rates first (more common to have decreases)
    for url, trend in [(lower_url, "down"), (higher_url, "up")]:
        logger.info("Checking URL: %s", url)

        # First, check if URL exists with lightweight HEAD request
        if not is_url_reachable(url):
            logger.info("URL not reachable, skipping")
            continue

        # URL exists, now fetch with Playwright for JS-rendered content
        logger.info("URL reachable, fetching content with Playwright...")
        content = fetch_page_content(url)

        if content and "Page not found" not in content:
            data = parse_rates(content)
            if data.get("rate_kwh") or data.get("raw_text"):
                data["trend"] = trend
                result["success"] = True
                result["url"] = url
                result["data"] = data
                return result

    result["error"] = f"Could not find rate information for {target_date.strftime('%B %Y')}"
    return result


def get_meralco_rates() -> dict:
    """
    Main function to get current MERALCO electricity rates.
    Tries current month first, then falls back to previous month if needed.
    Returns a dictionary with rate information.
    """
    from dateutil.relativedelta import relativedelta

    now = datetime.now()

    # Try current month
    logger.info("Attempting to fetch rates for current month...")
    result = try_fetch_rates_for_date(now)

    if result["success"]:
        return result

    # Current month failed, try previous month
    logger.warning("Current month failed, trying previous month...")
    previous_month = now - relativedelta(months=1)
    result = try_fetch_rates_for_date(previous_month)

    if result["success"]:
        result["warning"] = f"{now.strftime('%B %Y')} rates not yet available. Using {previous_month.strftime('%B %Y')} rates instead."
        return result

    # Both failed
    result["error"] = "Could not find rate information for current or previous month"
    return result


def main():
    """Main entry point for running the scraper."""
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Fetching MERALCO electricity rates...")
    rates = get_meralco_rates()
    print(json.dumps(rates, indent=2, default=str))


if __name__ == "__main__":
    main()
