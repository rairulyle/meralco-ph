"""
MERALCO Electricity Rate Scraper

Scrapes the current electricity rate from MERALCO's news and advisories page.
Designed for integration with Home Assistant.
"""

import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


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
        print(f"Error fetching {url}: {e}")
        return None


def parse_rates(html_content: str) -> dict:
    """Parse electricity rates from the page content."""
    soup = BeautifulSoup(html_content, "html.parser")

    rates = {
        "overall_rate": None,
        "generation_charge": None,
        "transmission_charge": None,
        "distribution_charge": None,
        "others": None,
        "rate_change": None,
        "effective_date": None,
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
            rates["overall_rate"] = float(overall_match.group(1))

        # Rate change: "reduction of P0.3557 per kWh" or "increase of P0.1234 per kWh"
        change_pattern = r'(increase|decrease|reduction)\s+(?:of\s+)?[P₱]\s*(\d+\.?\d*)\s*per\s*kWh'
        change_match = re.search(change_pattern, text_content, re.IGNORECASE)
        if change_match:
            direction = change_match.group(1).lower()
            amount = float(change_match.group(2))
            if direction in ["decrease", "reduction"]:
                amount = -amount
            rates["rate_change"] = amount

        # Generation charge
        gen_pattern = r'generation\s+charge[:\s]+[P₱]\s*(\d+\.?\d*)'
        gen_match = re.search(gen_pattern, text_content, re.IGNORECASE)
        if gen_match:
            rates["generation_charge"] = float(gen_match.group(1))

        # Transmission charge
        trans_pattern = r'transmission\s+charge[:\s]+[P₱]\s*(\d+\.?\d*)'
        trans_match = re.search(trans_pattern, text_content, re.IGNORECASE)
        if trans_match:
            rates["transmission_charge"] = float(trans_match.group(1))

    return rates


def get_meralco_rates() -> dict:
    """
    Main function to get current MERALCO electricity rates.
    Returns a dictionary with rate information.
    """
    higher_url, lower_url = get_current_month_url()

    result = {
        "success": False,
        "url": None,
        "rate_direction": None,
        "rates": {},
        "error": None,
        "timestamp": datetime.now().isoformat(),
    }

    # Try lower rates first (more common to have decreases)
    for url, direction in [(lower_url, "lower"), (higher_url, "higher")]:
        print(f"Trying: {url}")
        content = fetch_page_content(url)

        if content and "Page not found" not in content:
            rates = parse_rates(content)
            if rates.get("overall_rate") or rates.get("raw_text"):
                result["success"] = True
                result["url"] = url
                result["rate_direction"] = direction
                result["rates"] = rates
                return result

    result["error"] = "Could not find rate information for current month"
    return result


if __name__ == "__main__":
    import json

    print("Fetching MERALCO electricity rates...")
    rates = get_meralco_rates()
    print(json.dumps(rates, indent=2, default=str))
