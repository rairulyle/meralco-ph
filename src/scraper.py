"""
MERALCO API - Scraper Module

Scrapes the current electricity rate from MERALCO (Manila Electric Company)
Philippines news and advisories page.
"""

import asyncio
import logging
import re
from datetime import datetime

from pyppeteer import launch
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def get_month_url(target_date: datetime) -> tuple[str, str]:
    """
    Generate the URL for a specific month's rate announcement.
    Returns tuple of (higher_url, lower_url) since we don't know which one exists.

    Note: Starting 2026, MERALCO changed their URL format to not include the year.
    """
    month = target_date.strftime("%B").lower()  # e.g., "december"
    year = target_date.year

    base_url = "https://company.meralco.com.ph/news-and-advisories"

    # New format: no year in URL
    higher_url = f"{base_url}/higher-rates-{month}"
    lower_url = f"{base_url}/lower-rates-{month}"

    # Old format: includes year
    # higher_url = f"{base_url}/higher-rates-{month}-{year}"
    # lower_url = f"{base_url}/lower-rates-{month}-{year}"

    return higher_url, lower_url


async def fetch_page_content(browser, url: str, trend: str) -> tuple[str, str | None, str]:
    """
    Fetch page content using pyppeteer for JavaScript-rendered pages.
    Returns tuple of (url, content, trend).
    """
    try:
        page = await browser.newPage()
        await page.goto(url, {'waitUntil': 'networkidle0', 'timeout': 30000})
        content = await page.content()
        await page.close()
        return (url, content, trend)
    except Exception as e:
        logger.error("Error fetching %s: %s", url, e)
        return (url, None, trend)


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
        main_content = soup.find("article") or soup.find(
            "div", class_="content")

    if main_content:
        text_content = main_content.get_text(separator=" ", strip=True)
        # Store first 1000 chars for debugging
        rates["raw_text"] = text_content[:1000]

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
                rates["rate_change_percent"] = round(
                    (rates["rate_change"] / previous_rate) * 100, 2)

    return rates


async def fetch_urls_parallel(urls_to_fetch: list[tuple[str, str]]) -> list[tuple[str, str | None, str]]:
    """Fetch multiple URLs in parallel using async."""
    import os
    chromium_path = os.environ.get('PYPPETEER_CHROMIUM_EXECUTABLE')
    launch_args = {
        'headless': True,
        'args': ['--no-sandbox', '--disable-dev-shm-usage']
    }
    if chromium_path:
        launch_args['executablePath'] = chromium_path

    browser = await launch(**launch_args)
    tasks = [fetch_page_content(browser, url, trend) for url, trend in urls_to_fetch]
    results = await asyncio.gather(*tasks)
    await browser.close()
    return list(results)


def try_fetch_rates_for_date(target_date: datetime) -> dict:
    """
    Try to fetch rates for a specific date.
    Fetches both URLs in parallel for speed.
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

    # Fetch both URLs in parallel
    urls_to_fetch = [(lower_url, "down"), (higher_url, "up")]

    logger.info("Fetching URLs in parallel...")
    fetched_results = asyncio.run(fetch_urls_parallel(urls_to_fetch))

    fetched_pages = []
    for url, content, trend in fetched_results:
        logger.info("Fetched %s: %s", url, "success" if content else "failed")
        if content:
            fetched_pages.append((url, content, trend))

    # Process fetched pages (prefer lower rates first)
    fetched_pages.sort(key=lambda x: 0 if x[2] == "down" else 1)

    for url, content, trend in fetched_pages:
        if "PAGE NOT FOUND" not in content:
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
