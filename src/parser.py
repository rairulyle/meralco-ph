"""
MERALCO API - Residential Bills PDF Parser

Parses the monthly residential_bills PDF from MERALCO, which contains
pre-computed per-kWh rates at 15 consumption levels (50, 70, 100, 200, ...,
5000 kWh). These rates match MERALCO's published "typical household" figure
1:1 with no VAT math or franchise tax estimation required.
"""

import io
import logging
import os
import re
import urllib.request
from datetime import datetime

import pdfplumber

logger = logging.getLogger(__name__)

PDF_BASE_URL = "https://meralcomain.s3.ap-southeast-1.amazonaws.com"

PDF_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache", "pdf")


def get_pdf_url(target_date: datetime) -> str:
    """Generate the S3 URL for a month's residential bills PDF."""
    month = f"{target_date.month:02d}"
    year = target_date.year
    return f"{PDF_BASE_URL}/{year}-{month}/{month}-{year}_residential_bills.pdf"


def parse_residential_bills(rows: list[list]) -> list[dict]:
    """Extract per-kWh rates from the 'For Non-Lifeline Customers' rate section.

    Finds the LAST occurrence of 'For Non-Lifeline Customers' and reads
    numeric rows that follow until hitting a non-numeric first column.
    The last column of each row is the final per-kWh rate, which may
    contain stray whitespace (e.g. '1 3.8161') that must be stripped.
    """
    non_lifeline_starts = [
        i for i, row in enumerate(rows)
        if row and (row[0] or "").strip() == "For Non-Lifeline Customers"
    ]
    if not non_lifeline_starts:
        return []

    start = non_lifeline_starts[-1]
    result = []
    for row in rows[start + 1:]:
        first = (row[0] or "").strip()
        if not first.isdigit():
            break
        kwh = int(first)
        last_cell = (row[-1] or "").strip().replace(" ", "").replace(",", "")
        try:
            rate = float(last_cell)
        except ValueError:
            continue
        result.append({"kwh": kwh, "rate": rate})
    return result


def compute_rate_changes(current_entries: list[dict], previous_entries: list[dict] | None) -> list[dict]:
    """Add rate_change, rate_change_percent, and trend to each entry by
    comparing with the previous month's rate at the same kWh level.
    """
    prev_map = {e["kwh"]: e["rate"] for e in (previous_entries or [])}
    result = []
    for entry in current_entries:
        prev_rate = prev_map.get(entry["kwh"])
        if prev_rate is not None:
            change = round(entry["rate"] - prev_rate, 4)
            pct = round((change / prev_rate) * 100, 2) if prev_rate else None
            trend = "up" if change > 0 else "down" if change < 0 else "stable"
        else:
            change = None
            pct = None
            trend = None
        result.append({
            "kwh": entry["kwh"],
            "rate": entry["rate"],
            "rate_change": change,
            "rate_change_percent": pct,
            "trend": trend,
        })
    return result


def _get_cache_path(url: str) -> str:
    filename = url.rsplit("/", 1)[-1]
    return os.path.join(PDF_CACHE_DIR, filename)


def download_pdf(url: str) -> bytes | None:
    """Download PDF from URL with disk caching. Returns bytes or None on failure."""
    cache_path = _get_cache_path(url)

    if os.path.exists(cache_path):
        logger.info("Using cached PDF: %s", cache_path)
        with open(cache_path, "rb") as f:
            return f.read()

    try:
        logger.info("Downloading PDF: %s", url)
        os.makedirs(PDF_CACHE_DIR, exist_ok=True)
        with urllib.request.urlopen(url, timeout=30) as response:
            pdf_bytes = response.read()
        with open(cache_path, "wb") as f:
            f.write(pdf_bytes)
        return pdf_bytes
    except Exception as e:
        logger.error("Failed to download PDF from %s: %s", url, e)
        return None


def _cleanup_old_pdfs(keep_urls: list[str]) -> None:
    """Remove cached PDFs that are not in the keep list."""
    if not os.path.exists(PDF_CACHE_DIR):
        return

    keep_filenames = {url.rsplit("/", 1)[-1] for url in keep_urls}

    for filename in os.listdir(PDF_CACHE_DIR):
        if filename.endswith(".pdf") and filename not in keep_filenames:
            filepath = os.path.join(PDF_CACHE_DIR, filename)
            logger.info("Cleaning up old cached PDF: %s", filename)
            os.remove(filepath)


MONTH_REGEX = re.compile(
    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
    re.IGNORECASE,
)


def _extract_billing_date(rows: list[list]) -> str | None:
    """Extract billing date as MM/YYYY from the PDF rows.

    The residential_bills PDF header contains the month name and year,
    e.g. 'RESIDENTIAL BILLS AT TYPICAL CONSUMPTION LEVELS' / 'April 2026'.
    """
    for row in rows:
        for cell in row:
            if not cell:
                continue
            match = MONTH_REGEX.search(str(cell))
            if match:
                from dateutil.parser import parse as parse_date
                dt = parse_date(f"{match.group(1)} {match.group(2)}")
                return f"{dt.month:02d}/{dt.year}"
    return None


def _parse_single_month(pdf_bytes: bytes) -> dict | None:
    """Parse a single month's residential_bills PDF, returning entries and billing date."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return None
            tables = pdf.pages[0].extract_tables()
            if not tables:
                return None
            rows = [row for table in tables for row in table]
            entries = parse_residential_bills(rows)
            if not entries:
                return None
            billing_date = _extract_billing_date(rows)
            if not billing_date:
                # Fallback: try the raw page text
                page_text = pdf.pages[0].extract_text() or ""
                match = MONTH_REGEX.search(page_text)
                if match:
                    from dateutil.parser import parse as parse_date
                    dt = parse_date(f"{match.group(1)} {match.group(2)}")
                    billing_date = f"{dt.month:02d}/{dt.year}"
            return {"entries": entries, "billing_date": billing_date}
    except Exception as e:
        logger.error("Error parsing PDF: %s", e)
        return None


def get_meralco_rates() -> dict:
    """Main entry point: fetch current and previous month PDFs, compute rate changes."""
    from dateutil.relativedelta import relativedelta

    now = datetime.now()
    result = {
        "success": False,
        "error": None,
        "warning": None,
        "date": None,
        "data": None,
        "meta": {
            "timestamp": now.isoformat(),
            "source": None,
        },
    }

    current_url = get_pdf_url(now)
    current_bytes = download_pdf(current_url)
    current_parsed = _parse_single_month(current_bytes) if current_bytes else None

    if not current_parsed:
        logger.warning("Current month failed, trying previous month...")
        prev = now - relativedelta(months=1)
        current_url = get_pdf_url(prev)
        current_bytes = download_pdf(current_url)
        current_parsed = _parse_single_month(current_bytes) if current_bytes else None

        if not current_parsed:
            result["error"] = "Could not find rate information for current or previous month"
            return result

        result["warning"] = (
            f"{now.strftime('%B %Y')} rates not yet available. "
            f"Using {prev.strftime('%B %Y')} rates instead."
        )
        prev_for_diff = prev - relativedelta(months=1)
    else:
        prev_for_diff = now - relativedelta(months=1)

    prev_url = get_pdf_url(prev_for_diff)
    prev_bytes = download_pdf(prev_url)
    prev_parsed = _parse_single_month(prev_bytes) if prev_bytes else None
    prev_entries = prev_parsed["entries"] if prev_parsed else None

    entries_with_changes = compute_rate_changes(current_parsed["entries"], prev_entries)

    result["success"] = True
    result["date"] = current_parsed["billing_date"]
    result["data"] = entries_with_changes
    result["meta"]["source"] = current_url

    _cleanup_old_pdfs([current_url, prev_url])

    return result


def main():
    """Main entry point for running the parser standalone."""
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
