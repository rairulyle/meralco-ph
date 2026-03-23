"""Tests for the MERALCO PDF rate schedule parser."""

import os
from datetime import datetime

import pdfplumber

from src.parser import get_pdf_url

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_PDF_MAR = os.path.join(FIXTURE_DIR, "03-2026_rate_schedule.pdf")
FIXTURE_PDF_FEB = os.path.join(FIXTURE_DIR, "02-2026_rate_schedule.pdf")


def test_get_pdf_url_march_2026():
    dt = datetime(2026, 3, 15)
    assert get_pdf_url(dt) == "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-03/03-2026_rate_schedule.pdf"


def test_get_pdf_url_january_2026():
    dt = datetime(2026, 1, 1)
    assert get_pdf_url(dt) == "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-01/01-2026_rate_schedule.pdf"


def test_get_pdf_url_december_2025():
    dt = datetime(2025, 12, 25)
    assert get_pdf_url(dt) == "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2025-12/12-2025_rate_schedule.pdf"


from src.parser import parse_residential_tiers, parse_vat_rates


def _load_fixture_table(pdf_path):
    """Load the main table from a PDF fixture."""
    with pdfplumber.open(pdf_path) as pdf:
        tables = pdf.pages[0].extract_tables()
        return tables[0]


class TestParseResidentialTiers:
    def test_returns_8_tiers(self):
        tiers = parse_residential_tiers(_load_fixture_table(FIXTURE_PDF_MAR))
        assert len(tiers) == 8

    def test_first_tier_basic_fields(self):
        tiers = parse_residential_tiers(_load_fixture_table(FIXTURE_PDF_MAR))
        t = tiers[0]
        assert t["name"] == "0-20 kWh"
        assert t["min_kwh"] == 0
        assert t["max_kwh"] == 20
        assert t["generation"] == 7.8607
        assert t["transmission"] == 1.5223
        assert t["system_loss"] == 0.7456
        assert t["distribution"] == 0.9803
        assert t["supply"] == 0.4979
        assert t["metering"] == 0.3350
        assert t["supply_monthly"] == 16.38
        assert t["metering_monthly"] == 5.00
        assert t["lifeline_discount_pct"] == 100.0

    def test_first_tier_additional_charges(self):
        tiers = parse_residential_tiers(_load_fixture_table(FIXTURE_PDF_MAR))
        t = tiers[0]
        assert t["awat"] == -0.2024
        assert t["regulatory_reset"] == -0.0023
        assert t["lifeline_subsidy"] == 0.0100
        assert t["senior_citizen"] == 0.0001
        assert t["rpt"] == 0.0058
        assert t["uc_me_npc"] == 0.2662
        assert t["uc_me_red"] == 0.0101
        assert t["uc_ec"] == 0.0025
        assert t["uc_sd"] == 0.0428
        assert t["fit_all"] == 0.2011
        assert t["gea_all"] == 0.0371

    def test_distribution_varies_by_tier(self):
        tiers = parse_residential_tiers(_load_fixture_table(FIXTURE_PDF_MAR))
        for i in range(5):
            assert tiers[i]["distribution"] == 0.9803
        assert tiers[5]["distribution"] == 1.2908
        assert tiers[6]["distribution"] == 1.5837
        assert tiers[7]["distribution"] == 2.0941

    def test_last_tier(self):
        tiers = parse_residential_tiers(_load_fixture_table(FIXTURE_PDF_MAR))
        t = tiers[7]
        assert t["name"] == "Over 400 kWh"
        assert t["min_kwh"] == 401
        assert t["max_kwh"] is None
        assert t["lifeline_discount_pct"] is None


class TestParseVatRates:
    def test_vat_rates(self):
        vat = parse_vat_rates(_load_fixture_table(FIXTURE_PDF_MAR))
        assert vat["generation"] == 11.30
        assert vat["transmission"] == 10.49
        assert vat["system_loss"] == 11.17
        assert vat["other"] == 12.00

    def test_vat_rates_all_present(self):
        vat = parse_vat_rates(_load_fixture_table(FIXTURE_PDF_MAR))
        assert vat["generation"] > 0
        assert vat["transmission"] > 0
        assert vat["system_loss"] > 0


from src.parser import compute_effective_rates


class TestComputeEffectiveRates:
    def test_200kwh_rate_near_meralco_published(self):
        """
        MERALCO publishes P13.8161 for 200 kWh. Our formula excludes local
        franchise tax (~0.4%), so we expect ~P13.76 within P0.10 tolerance.
        """
        table = _load_fixture_table(FIXTURE_PDF_MAR)
        tiers = parse_residential_tiers(table)
        vat = parse_vat_rates(table)
        result = compute_effective_rates(tiers, vat, consumption_kwh=200)

        assert result["rate_kwh"] is not None
        assert abs(result["rate_kwh"] - 13.8161) < 0.10

    def test_has_all_tiers(self):
        table = _load_fixture_table(FIXTURE_PDF_MAR)
        tiers = parse_residential_tiers(table)
        vat = parse_vat_rates(table)
        result = compute_effective_rates(tiers, vat, consumption_kwh=200)

        assert len(result["tiers"]) == 8
        for tier in result["tiers"]:
            assert tier["rate"] > 0

    def test_higher_tiers_cost_more(self):
        table = _load_fixture_table(FIXTURE_PDF_MAR)
        tiers = parse_residential_tiers(table)
        vat = parse_vat_rates(table)
        result = compute_effective_rates(tiers, vat, consumption_kwh=200)

        rates = [t["rate"] for t in result["tiers"]]
        for i in range(1, 5):
            assert rates[i] == rates[0]
        assert rates[5] > rates[4]
        assert rates[6] > rates[5]
        assert rates[7] > rates[6]

    def test_typical_rate_includes_fixed_charges(self):
        table = _load_fixture_table(FIXTURE_PDF_MAR)
        tiers = parse_residential_tiers(table)
        vat = parse_vat_rates(table)
        result = compute_effective_rates(tiers, vat, consumption_kwh=200)

        tier_101_200 = result["tiers"][4]
        assert result["rate_kwh"] > tier_101_200["rate"]
