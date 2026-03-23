"""
MERALCO API - PDF Rate Schedule Parser

Parses the monthly rate schedule PDF from MERALCO to extract residential
electricity rates across all tiers with VAT-inclusive computation.
"""

import io
import logging
import re
from datetime import datetime

import pdfplumber
import urllib.request

logger = logging.getLogger(__name__)

PDF_BASE_URL = "https://meralcomain.s3.ap-southeast-1.amazonaws.com"

# Column indices in the PDF table for residential rows
COL_NAME = 0
COL_GENERATION = 1
COL_TRANSMISSION = 2
COL_SYSTEM_LOSS = 4
COL_DISTRIBUTION = 5
COL_SUPPLY_KWH = 7
COL_SUPPLY_MONTHLY = 8
COL_METERING_KWH = 9
COL_METERING_MONTHLY = 10
COL_AWAT = 11
COL_REGULATORY_RESET = 12
COL_LIFELINE_SUBSIDY = 13
COL_LIFELINE_DISCOUNT = 14
COL_SENIOR_CITIZEN = 15
COL_RPT = 16
COL_UC_ME_NPC = 17
COL_UC_ME_RED = 18
COL_UC_EC = 19
COL_UC_SD = 20
COL_FIT_ALL = 21
COL_GEA_ALL = 22


def get_pdf_url(target_date: datetime) -> str:
    """Generate the S3 URL for a month's rate schedule PDF."""
    month = f"{target_date.month:02d}"
    year = target_date.year
    return f"{PDF_BASE_URL}/{year}-{month}/{month}-{year}_rate_schedule.pdf"


def _parse_float(value: str | None) -> float | None:
    """Parse a float from a PDF cell value. Handles parentheses as negative."""
    if not value or not value.strip():
        return None
    value = value.strip().replace(',', '')
    if value.startswith('(') and value.endswith(')'):
        return -float(value[1:-1])
    try:
        return float(value)
    except ValueError:
        return None


def _parse_tier_name(raw: str) -> tuple[str, int, int | None]:
    """Parse tier name into (display_name, min_kwh, max_kwh)."""
    raw = raw.strip()
    if raw.startswith("OVER"):
        match = re.match(r'OVER\s+(\d+)\s+KWH', raw)
        if not match:
            logger.warning("Unexpected OVER tier format: %s", raw)
        limit = int(match.group(1)) if match else 400
        return f"Over {limit} kWh", limit + 1, None
    match = re.match(r'(\d+)\s+TO\s+(\d+)\s+KWH', raw)
    if match:
        lo, hi = int(match.group(1)), int(match.group(2))
        return f"{lo}-{hi} kWh", lo, hi
    return raw, 0, None


def _parse_lifeline_discount(value: str | None) -> float | None:
    """Parse lifeline discount percentage (e.g. '100.00%' -> 100.0)."""
    if not value or not value.strip():
        return None
    value = value.strip().rstrip('%')
    try:
        return float(value)
    except ValueError:
        return None


def parse_residential_tiers(table: list[list]) -> list[dict]:
    """Extract residential tier data from the main rate schedule table."""
    tiers = []
    in_residential = False

    for row in table:
        label = (row[COL_NAME] or '').strip()

        if label == 'Residential':
            in_residential = True
            continue

        if in_residential:
            if label and 'KWH' not in label.upper() and 'OVER' not in label.upper():
                break

            if not label:
                continue

            name, min_kwh, max_kwh = _parse_tier_name(label)

            tier = {
                "name": name,
                "min_kwh": min_kwh,
                "max_kwh": max_kwh,
                "generation": _parse_float(row[COL_GENERATION]),
                "transmission": _parse_float(row[COL_TRANSMISSION]),
                "system_loss": _parse_float(row[COL_SYSTEM_LOSS]),
                "distribution": _parse_float(row[COL_DISTRIBUTION]),
                "supply": _parse_float(row[COL_SUPPLY_KWH]),
                "metering": _parse_float(row[COL_METERING_KWH]),
                "supply_monthly": _parse_float(row[COL_SUPPLY_MONTHLY]),
                "metering_monthly": _parse_float(row[COL_METERING_MONTHLY]),
                "awat": _parse_float(row[COL_AWAT]),
                "regulatory_reset": _parse_float(row[COL_REGULATORY_RESET]),
                "lifeline_subsidy": _parse_float(row[COL_LIFELINE_SUBSIDY]),
                "lifeline_discount_pct": _parse_lifeline_discount(row[COL_LIFELINE_DISCOUNT]),
                "senior_citizen": _parse_float(row[COL_SENIOR_CITIZEN]),
                "rpt": _parse_float(row[COL_RPT]),
                "uc_me_npc": _parse_float(row[COL_UC_ME_NPC]),
                "uc_me_red": _parse_float(row[COL_UC_ME_RED]),
                "uc_ec": _parse_float(row[COL_UC_EC]),
                "uc_sd": _parse_float(row[COL_UC_SD]),
                "fit_all": _parse_float(row[COL_FIT_ALL]),
                "gea_all": _parse_float(row[COL_GEA_ALL]),
            }
            tiers.append(tier)

    return tiers


def parse_vat_rates(table: list[list]) -> dict:
    """Extract VAT rates from the bottom of the rate schedule table."""
    vat = {"generation": 0.0, "transmission": 0.0, "system_loss": 0.0, "other": 12.0}

    for row in table:
        label = (row[0] or '').strip()
        rate_str = (row[1] or '').strip() if len(row) > 1 else ''

        if label == 'Generation' and '%' in rate_str:
            vat["generation"] = float(rate_str.rstrip('%'))
        elif label == 'Transmission' and '%' in rate_str:
            vat["transmission"] = float(rate_str.rstrip('%'))
        elif label == 'System Loss' and '%' in rate_str:
            vat["system_loss"] = float(rate_str.rstrip('%'))
        elif label == 'Other Charges' and '%' in rate_str:
            vat["other"] = float(rate_str.rstrip('%'))

    if vat["generation"] == 0.0 or vat["transmission"] == 0.0 or vat["system_loss"] == 0.0:
        logger.warning("Some VAT rates not found in PDF, using defaults: %s", vat)

    return vat


def compute_effective_rates(tiers: list[dict], vat: dict, consumption_kwh: int = 200) -> dict:
    """
    Compute VAT-inclusive effective rates for each tier and the typical household rate.

    VAT application rules (from the PDF's VAT rates table):
    - Generation: variable % (e.g. 11.30%, includes franchise tax effect)
    - Transmission: variable % (e.g. 10.49%)
    - System Loss: variable % (e.g. 11.17%)
    - Other Charges (distribution, supply, metering, AWAT, reg reset,
      lifeline subsidy, senior citizen): 12%
    - Zero-VAT (RPT, universal charges, FIT-All, GEA-All): 0%

    Note: Excludes local franchise tax (~0.4%), which varies by LGU.
    """
    gen_mult = 1 + vat["generation"] / 100
    trans_mult = 1 + vat["transmission"] / 100
    sl_mult = 1 + vat["system_loss"] / 100
    other_mult = 1 + vat["other"] / 100

    enriched_tiers = []
    for tier in tiers:
        gen_eff = (tier["generation"] or 0) * gen_mult
        trans_eff = (tier["transmission"] or 0) * trans_mult
        sl_eff = (tier["system_loss"] or 0) * sl_mult

        other_per_kwh = (
            (tier["distribution"] or 0)
            + (tier["supply"] or 0)
            + (tier["metering"] or 0)
            + (tier.get("awat") or 0)
            + (tier.get("regulatory_reset") or 0)
            + (tier.get("lifeline_subsidy") or 0)
            + (tier.get("senior_citizen") or 0)
        )
        other_eff = other_per_kwh * other_mult

        zero_vat = (
            (tier.get("rpt") or 0)
            + (tier.get("uc_me_npc") or 0)
            + (tier.get("uc_me_red") or 0)
            + (tier.get("uc_ec") or 0)
            + (tier.get("uc_sd") or 0)
            + (tier.get("fit_all") or 0)
            + (tier.get("gea_all") or 0)
        )

        rate = round(gen_eff + trans_eff + sl_eff + other_eff + zero_vat, 4)

        enriched_tiers.append({
            "name": tier["name"],
            "min_kwh": tier["min_kwh"],
            "max_kwh": tier["max_kwh"],
            "rate": rate,
        })

    # Compute "typical household" effective rate (includes fixed monthly charges)
    typical_tier = None
    typical_idx = None
    for i, tier in enumerate(enriched_tiers):
        if tier["max_kwh"] is None or consumption_kwh <= tier["max_kwh"]:
            typical_tier = tier
            typical_idx = i
            break

    rate_kwh = None
    if typical_tier:
        raw_tier = tiers[typical_idx]
        fixed_monthly = (
            (raw_tier["supply_monthly"] or 0) + (raw_tier["metering_monthly"] or 0)
        ) * other_mult
        total_bill = typical_tier["rate"] * consumption_kwh + fixed_monthly
        rate_kwh = round(total_bill / consumption_kwh, 4)

    return {
        "rate_kwh": rate_kwh,
        "tiers": enriched_tiers,
    }


def compute_rate_changes(current_tiers: list[dict], previous_tiers: list[dict] | None) -> list[dict]:
    """
    Add rate_change and rate_change_percent to each tier by comparing
    with previous month's tiers. If previous_tiers is None, changes are null.
    """
    result = []
    for i, tier in enumerate(current_tiers):
        entry = {**tier}
        if previous_tiers and i < len(previous_tiers):
            prev_rate = previous_tiers[i]["rate"]
            change = round(tier["rate"] - prev_rate, 4)
            pct = round((change / prev_rate) * 100, 2) if prev_rate else None
            entry["rate_change"] = change
            entry["rate_change_percent"] = pct
        else:
            entry["rate_change"] = None
            entry["rate_change_percent"] = None
        result.append(entry)
    return result


def download_pdf(url: str) -> bytes | None:
    """Download PDF from URL, return bytes or None on failure."""
    try:
        logger.info("Downloading PDF: %s", url)
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except Exception as e:
        logger.error("Failed to download PDF from %s: %s", url, e)
        return None


def _extract_billing_date(table: list[list]) -> str | None:
    """Extract billing date as MM/YYYY from the table header."""
    header = (table[0][0] or '') if table and table[0] else ''
    match = re.search(r'EFFECTIVE\s+(\w+)\s+(\d{4})', header, re.IGNORECASE)
    if match:
        from dateutil.parser import parse as parse_date
        month_name = match.group(1)
        year = match.group(2)
        dt = parse_date(f"{month_name} {year}")
        return f"{dt.month:02d}/{dt.year}"
    return None


def _parse_single_month(pdf_bytes: bytes) -> dict | None:
    """Parse a single month's PDF and return tiers with rates, or None on failure."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return None

            tables = pdf.pages[0].extract_tables()
            if not tables:
                return None

            main_table = tables[0]
            tiers = parse_residential_tiers(main_table)
            if not tiers:
                return None

            vat = parse_vat_rates(main_table)
            computed = compute_effective_rates(tiers, vat, consumption_kwh=200)
            billing_date = _extract_billing_date(main_table)

            return {
                "tiers": computed["tiers"],
                "rate_kwh": computed["rate_kwh"],
                "billing_date": billing_date,
            }
    except Exception as e:
        logger.error("Error parsing PDF: %s", e)
        return None


def get_meralco_rates() -> dict:
    """
    Main function to get current MERALCO electricity rates with rate changes.

    Downloads current and previous month PDFs, computes rates for both,
    then diffs them for rate_change values.
    """
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

    # Try current month
    current_url = get_pdf_url(now)
    current_bytes = download_pdf(current_url)
    current_parsed = _parse_single_month(current_bytes) if current_bytes else None

    if not current_parsed:
        # Fall back to previous month as "current"
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

        # Previous month's previous for rate change
        prev_prev = prev - relativedelta(months=1)
        prev_url = get_pdf_url(prev_prev)
    else:
        # Previous month for rate change
        prev = now - relativedelta(months=1)
        prev_url = get_pdf_url(prev)

    # Fetch previous month for rate changes
    prev_bytes = download_pdf(prev_url)
    prev_parsed = _parse_single_month(prev_bytes) if prev_bytes else None
    prev_tiers = prev_parsed["tiers"] if prev_parsed else None

    # Compute rate changes
    tiers_with_changes = compute_rate_changes(current_parsed["tiers"], prev_tiers)

    result["success"] = True
    result["date"] = current_parsed["billing_date"]
    result["data"] = tiers_with_changes
    result["meta"]["source"] = current_url

    return result


def main():
    """Main entry point for running the parser."""
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
