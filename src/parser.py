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
