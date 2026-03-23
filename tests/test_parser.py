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


def test_get_pdf_url_february_2026():
    dt = datetime(2026, 2, 1)
    assert get_pdf_url(dt) == "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-02/02-2026_rate_schedule.pdf"


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
    def test_101_200_rate_reasonable(self):
        """Per-kWh rate should be close to MERALCO's published rate (excludes fixed charges)."""
        table = _load_fixture_table(FIXTURE_PDF_MAR)
        tiers = parse_residential_tiers(table)
        vat = parse_vat_rates(table)
        result = compute_effective_rates(tiers, vat)

        tier_101_200 = result[4]
        # Per-kWh rate is ~P0.12 below MERALCO's published rate (which includes fixed charges)
        assert abs(tier_101_200["rate"] - 13.8161) < 0.15

    def test_has_all_tiers(self):
        table = _load_fixture_table(FIXTURE_PDF_MAR)
        tiers = parse_residential_tiers(table)
        vat = parse_vat_rates(table)
        result = compute_effective_rates(tiers, vat)

        assert len(result) == 8
        for tier in result:
            assert tier["rate"] > 0
            assert tier["raw_rate"] > 0
            assert tier["rate"] > tier["raw_rate"]

    def test_higher_tiers_cost_more(self):
        table = _load_fixture_table(FIXTURE_PDF_MAR)
        tiers = parse_residential_tiers(table)
        vat = parse_vat_rates(table)
        result = compute_effective_rates(tiers, vat)

        rates = [t["rate"] for t in result]
        for i in range(1, 5):
            assert rates[i] == rates[0]
        assert rates[5] > rates[4]
        assert rates[6] > rates[5]
        assert rates[7] > rates[6]


from src.parser import compute_rate_changes


class TestComputeRateChanges:
    def test_rate_changes_have_correct_length(self):
        mar_table = _load_fixture_table(FIXTURE_PDF_MAR)
        feb_table = _load_fixture_table(FIXTURE_PDF_FEB)

        mar_computed = compute_effective_rates(parse_residential_tiers(mar_table), parse_vat_rates(mar_table))
        feb_computed = compute_effective_rates(parse_residential_tiers(feb_table), parse_vat_rates(feb_table))

        changed = compute_rate_changes(mar_computed, feb_computed)
        assert len(changed) == 8

    def test_rate_change_is_positive_mar_vs_feb(self):
        """March 2026 had higher rates than Feb 2026."""
        mar_table = _load_fixture_table(FIXTURE_PDF_MAR)
        feb_table = _load_fixture_table(FIXTURE_PDF_FEB)

        mar_computed = compute_effective_rates(parse_residential_tiers(mar_table), parse_vat_rates(mar_table))
        feb_computed = compute_effective_rates(parse_residential_tiers(feb_table), parse_vat_rates(feb_table))

        changed = compute_rate_changes(mar_computed, feb_computed)
        for tier in changed:
            assert tier["rate_change"] > 0
            assert tier["rate_change_percent"] > 0
            assert tier["trend"] == "up"

    def test_rate_change_values(self):
        mar_table = _load_fixture_table(FIXTURE_PDF_MAR)
        feb_table = _load_fixture_table(FIXTURE_PDF_FEB)

        mar_computed = compute_effective_rates(parse_residential_tiers(mar_table), parse_vat_rates(mar_table))
        feb_computed = compute_effective_rates(parse_residential_tiers(feb_table), parse_vat_rates(feb_table))

        changed = compute_rate_changes(mar_computed, feb_computed)
        tier = changed[4]  # 101-200 kWh
        assert tier["rate_change"] == round(tier["rate"] - feb_computed[4]["rate"], 4)

    def test_no_previous_month_returns_null_changes(self):
        mar_table = _load_fixture_table(FIXTURE_PDF_MAR)
        mar_computed = compute_effective_rates(parse_residential_tiers(mar_table), parse_vat_rates(mar_table))

        changed = compute_rate_changes(mar_computed, None)
        for tier in changed:
            assert tier["rate_change"] is None
            assert tier["rate_change_percent"] is None
            assert tier["trend"] is None


from unittest.mock import patch, MagicMock
from src.parser import download_pdf, get_meralco_rates, _extract_billing_date


class TestExtractBillingDate:
    def test_extracts_date_from_fixture(self):
        table = _load_fixture_table(FIXTURE_PDF_MAR)
        assert _extract_billing_date(table) == "03/2026"

    def test_returns_none_for_empty_table(self):
        assert _extract_billing_date([['', '']]) is None


from src.parser import _cleanup_old_pdfs, PDF_CACHE_DIR
import tempfile
import shutil


class TestDownloadPdf:
    @patch("src.parser.PDF_CACHE_DIR", new_callable=lambda: property(lambda self: self._tmpdir))
    @patch("src.parser.urllib.request.urlopen")
    def test_success(self, mock_urlopen, _):
        mock_response = MagicMock()
        mock_response.read.return_value = b"fake pdf content"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with patch("src.parser.PDF_CACHE_DIR", tempfile.mkdtemp()):
            result = download_pdf("https://example.com/test.pdf")
            assert result == b"fake pdf content"

    @patch("src.parser.urllib.request.urlopen")
    def test_failure_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Network error")
        with patch("src.parser.PDF_CACHE_DIR", tempfile.mkdtemp()):
            assert download_pdf("https://example.com/test.pdf") is None

    @patch("src.parser.urllib.request.urlopen")
    def test_uses_cache_on_second_call(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"pdf data"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        tmpdir = tempfile.mkdtemp()
        try:
            with patch("src.parser.PDF_CACHE_DIR", tmpdir):
                download_pdf("https://example.com/test.pdf")
                download_pdf("https://example.com/test.pdf")
                # Only downloaded once — second call uses cache
                assert mock_urlopen.call_count == 1
        finally:
            shutil.rmtree(tmpdir)


class TestCleanupOldPdfs:
    def test_removes_old_pdfs(self):
        tmpdir = tempfile.mkdtemp()
        try:
            # Create some cached PDFs
            for name in ["01-2026_rate_schedule.pdf", "02-2026_rate_schedule.pdf", "03-2026_rate_schedule.pdf"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("fake")

            with patch("src.parser.PDF_CACHE_DIR", tmpdir):
                _cleanup_old_pdfs([
                    "https://example.com/02-2026_rate_schedule.pdf",
                    "https://example.com/03-2026_rate_schedule.pdf",
                ])

            remaining = os.listdir(tmpdir)
            assert "01-2026_rate_schedule.pdf" not in remaining
            assert "02-2026_rate_schedule.pdf" in remaining
            assert "03-2026_rate_schedule.pdf" in remaining
        finally:
            shutil.rmtree(tmpdir)


class TestGetMeralcoRates:
    @patch("src.parser.download_pdf")
    def test_success_with_real_pdfs(self, mock_download):
        """Use real PDF fixtures (current + previous month) to test full pipeline."""
        def side_effect(url):
            if "03-2026" in url:
                with open(FIXTURE_PDF_MAR, "rb") as f:
                    return f.read()
            elif "02-2026" in url:
                with open(FIXTURE_PDF_FEB, "rb") as f:
                    return f.read()
            return None

        mock_download.side_effect = side_effect

        result = get_meralco_rates()
        assert result["success"] is True
        assert result["date"] is not None
        assert len(result["data"]) == 8

        for tier in result["data"]:
            assert "rate" in tier
            assert "rate_change" in tier
            assert "rate_change_percent" in tier

        for tier in result["data"]:
            assert tier["rate_change"] > 0

    @patch("src.parser.download_pdf")
    def test_current_month_fails_falls_back(self, mock_download):
        call_count = [0]
        def side_effect(url):
            call_count[0] += 1
            if call_count[0] <= 1:
                return None
            with open(FIXTURE_PDF_MAR, "rb") as f:
                return f.read()
        mock_download.side_effect = side_effect

        result = get_meralco_rates()
        assert result["success"] is True
        assert result["warning"] is not None

    @patch("src.parser.download_pdf")
    def test_both_months_fail(self, mock_download):
        mock_download.return_value = None
        result = get_meralco_rates()
        assert result["success"] is False
        assert result["error"] is not None
