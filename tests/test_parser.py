"""Tests for the MERALCO residential bills PDF parser."""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pdfplumber
import pytest

from src.parser import (
    ParsedRate,
    PdfRow,
    _cleanup_old_pdfs,
    _extract_billing_date,
    compute_rate_changes,
    download_pdf,
    get_meralco_rates,
    get_pdf_url,
    parse_residential_bills,
)

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_BILLS_MAR = os.path.join(FIXTURE_DIR, "03-2026_residential_bills.pdf")
FIXTURE_BILLS_FEB = os.path.join(FIXTURE_DIR, "02-2026_residential_bills.pdf")
# Nov 2025 fixture: regression for the multi-line VAT cell format that
# broke parsing in commit 8db84eb. Keep until MERALCO drops the format.
FIXTURE_BILLS_NOV_2025 = os.path.join(FIXTURE_DIR, "11-2025_residential_bills.pdf")

EXPECTED_KWH_LEVELS = [
    50,
    70,
    100,
    200,
    300,
    400,
    500,
    600,
    700,
    800,
    900,
    1000,
    1500,
    3000,
    5000,
]


def _load_rows(pdf_path: str) -> list[PdfRow]:
    """Concatenate all tables on page 1 into a single row list."""
    with pdfplumber.open(pdf_path) as pdf:
        rows: list[PdfRow] = []
        for table in pdf.pages[0].extract_tables():
            rows.extend(table)
        return rows


# -------------------------------------------------------------------
# get_pdf_url
# -------------------------------------------------------------------


def test_get_pdf_url_march_2026() -> None:
    dt = datetime(2026, 3, 15)
    assert (
        get_pdf_url(dt)
        == "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-03/03-2026_residential_bills.pdf"
    )


def test_get_pdf_url_february_2026() -> None:
    dt = datetime(2026, 2, 1)
    assert (
        get_pdf_url(dt)
        == "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-02/02-2026_residential_bills.pdf"
    )


# -------------------------------------------------------------------
# parse_residential_bills
# -------------------------------------------------------------------


class TestParseResidentialBills:
    def test_returns_all_consumption_levels(self) -> None:
        result = parse_residential_bills(_load_rows(FIXTURE_BILLS_MAR))
        assert [r["kwh"] for r in result] == EXPECTED_KWH_LEVELS

    def test_200_kwh_matches_published_rate_mar(self) -> None:
        result = parse_residential_bills(_load_rows(FIXTURE_BILLS_MAR))
        row_200 = next(r for r in result if r["kwh"] == 200)
        assert row_200["rate"] == 13.8161

    def test_200_kwh_matches_published_rate_feb(self) -> None:
        result = parse_residential_bills(_load_rows(FIXTURE_BILLS_FEB))
        row_200 = next(r for r in result if r["kwh"] == 200)
        assert row_200["rate"] == 13.1734

    def test_each_entry_has_kwh_and_rate_only(self) -> None:
        result = parse_residential_bills(_load_rows(FIXTURE_BILLS_MAR))
        for entry in result:
            assert set(entry.keys()) == {"kwh", "rate"}
            assert isinstance(entry["kwh"], int)
            assert isinstance(entry["rate"], float)

    def test_empty_rows_returns_empty_list(self) -> None:
        assert parse_residential_bills([]) == []

    def test_rows_without_non_lifeline_marker_returns_empty(self) -> None:
        rows: list[PdfRow] = [["50", "foo", "bar"], ["100", "baz", "qux"]]
        assert parse_residential_bills(rows) == []

    def test_skips_empty_rows(self) -> None:
        rows: list[PdfRow] = [
            ["For Non-Lifeline Customers", None, None, None],
            [],
            ["50", None, None, "13.5"],
        ]
        result = parse_residential_bills(rows)
        assert result == [{"kwh": 50, "rate": 13.5}]

    def test_nov_2025_multi_line_vat_format(self) -> None:
        """Regression: Nov 2025 PDF used multi-line VAT cells that broke parsing.

        Commit 8db84eb fixed the parser; this fixture locks in the fix.
        """
        result = parse_residential_bills(_load_rows(FIXTURE_BILLS_NOV_2025))
        assert [r["kwh"] for r in result] == EXPECTED_KWH_LEVELS
        row_200 = next(r for r in result if r["kwh"] == 200)
        assert row_200["rate"] == 13.4702


# -------------------------------------------------------------------
# compute_rate_changes
# -------------------------------------------------------------------


class TestComputeRateChanges:
    def test_correct_length(self) -> None:
        mar = parse_residential_bills(_load_rows(FIXTURE_BILLS_MAR))
        feb = parse_residential_bills(_load_rows(FIXTURE_BILLS_FEB))
        changed = compute_rate_changes(mar, feb)
        assert len(changed) == len(mar) == 15

    def test_positive_change_mar_vs_feb(self) -> None:
        mar = parse_residential_bills(_load_rows(FIXTURE_BILLS_MAR))
        feb = parse_residential_bills(_load_rows(FIXTURE_BILLS_FEB))
        changed = compute_rate_changes(mar, feb)
        entry_200 = next(e for e in changed if e["kwh"] == 200)
        assert entry_200["rate"] == 13.8161
        assert entry_200["rate_change"] == round(13.8161 - 13.1734, 4)
        assert entry_200["rate_change_percent"] is not None
        assert entry_200["trend"] == "up"

    def test_null_changes_when_no_previous(self) -> None:
        mar = parse_residential_bills(_load_rows(FIXTURE_BILLS_MAR))
        changed = compute_rate_changes(mar, None)
        for entry in changed:
            assert entry["rate_change"] is None
            assert entry["rate_change_percent"] is None
            assert entry["trend"] is None

    def test_null_changes_when_empty_previous(self) -> None:
        mar = parse_residential_bills(_load_rows(FIXTURE_BILLS_MAR))
        changed = compute_rate_changes(mar, [])
        for entry in changed:
            assert entry["rate_change"] is None

    def test_down_trend(self) -> None:
        current: list[ParsedRate] = [{"kwh": 200, "rate": 12.0}]
        previous: list[ParsedRate] = [{"kwh": 200, "rate": 13.0}]
        result = compute_rate_changes(current, previous)
        assert result[0]["rate_change"] == -1.0
        assert result[0]["trend"] == "down"

    def test_stable_trend(self) -> None:
        current: list[ParsedRate] = [{"kwh": 200, "rate": 13.0}]
        previous: list[ParsedRate] = [{"kwh": 200, "rate": 13.0}]
        result = compute_rate_changes(current, previous)
        assert result[0]["rate_change"] == 0.0
        assert result[0]["trend"] == "stable"


# -------------------------------------------------------------------
# _extract_billing_date
# -------------------------------------------------------------------


class TestExtractBillingDate:
    def test_extracts_date_from_mar_fixture(self) -> None:
        rows = _load_rows(FIXTURE_BILLS_MAR)
        assert _extract_billing_date(rows) == "03/2026"

    def test_extracts_date_from_feb_fixture(self) -> None:
        rows = _load_rows(FIXTURE_BILLS_FEB)
        assert _extract_billing_date(rows) == "02/2026"

    def test_nov_2025_date_falls_back_to_page_text(self) -> None:
        """Nov 2025 PDF has the month outside the table grid; the row-only
        extractor returns None and `_parse_single_month` should fall back to
        extract_text() to recover the date.
        """
        from src.parser import _parse_single_month

        with open(FIXTURE_BILLS_NOV_2025, "rb") as f:
            parsed = _parse_single_month(f.read())
        assert parsed is not None
        assert parsed["billing_date"] == "11/2025"

    def test_returns_none_for_empty_rows(self) -> None:
        assert _extract_billing_date([]) is None

    def test_returns_none_when_no_month_found(self) -> None:
        assert _extract_billing_date([["foo", "bar"]]) is None


# -------------------------------------------------------------------
# download_pdf (mocked)
# -------------------------------------------------------------------


class TestDownloadPdf:
    def test_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.parser.PDF_CACHE_DIR", str(tmp_path))
        mock_response = MagicMock()
        mock_response.read.return_value = b"pdf-bytes"
        mock_response.__enter__.return_value = mock_response

        with patch("src.parser.urllib.request.urlopen", return_value=mock_response):
            result = download_pdf("https://example.com/test.pdf")

        assert result == b"pdf-bytes"

    def test_failure_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.parser.PDF_CACHE_DIR", str(tmp_path))
        with patch(
            "src.parser.urllib.request.urlopen", side_effect=Exception("network error")
        ):
            result = download_pdf("https://example.com/test.pdf")
        assert result is None

    def test_uses_cache_on_second_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.parser.PDF_CACHE_DIR", str(tmp_path))
        mock_response = MagicMock()
        mock_response.read.return_value = b"pdf-bytes"
        mock_response.__enter__.return_value = mock_response

        with patch(
            "src.parser.urllib.request.urlopen", return_value=mock_response
        ) as mock_urlopen:
            download_pdf("https://example.com/test.pdf")
            download_pdf("https://example.com/test.pdf")
            assert mock_urlopen.call_count == 1


# -------------------------------------------------------------------
# _cleanup_old_pdfs
# -------------------------------------------------------------------


class TestCleanupOldPdfs:
    def test_removes_old_pdfs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.parser.PDF_CACHE_DIR", str(tmp_path))
        (tmp_path / "01-2026_residential_bills.pdf").write_bytes(b"old")
        (tmp_path / "02-2026_residential_bills.pdf").write_bytes(b"prev")
        (tmp_path / "03-2026_residential_bills.pdf").write_bytes(b"current")

        _cleanup_old_pdfs(
            [
                "https://x.com/02-2026_residential_bills.pdf",
                "https://x.com/03-2026_residential_bills.pdf",
            ]
        )

        remaining = sorted(os.listdir(tmp_path))
        assert remaining == [
            "02-2026_residential_bills.pdf",
            "03-2026_residential_bills.pdf",
        ]


# -------------------------------------------------------------------
# get_meralco_rates (integration)
# -------------------------------------------------------------------


class TestGetMeralcoRates:
    @patch("src.parser.download_pdf")
    def test_success_with_real_pdfs(self, mock_download: MagicMock) -> None:
        with open(FIXTURE_BILLS_MAR, "rb") as f:
            mar_bytes = f.read()
        with open(FIXTURE_BILLS_FEB, "rb") as f:
            feb_bytes = f.read()

        def side_effect(url: str) -> bytes | None:
            if "03-2026" in url:
                return mar_bytes
            if "02-2026" in url:
                return feb_bytes
            return None

        mock_download.side_effect = side_effect

        with patch("src.parser.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 15)
            mock_datetime.strptime = datetime.strptime
            result = get_meralco_rates()

        assert result["success"] is True
        assert result["date"] == "03/2026"
        data = result["data"]
        assert data is not None
        assert len(data) == 15
        entry_200 = next(e for e in data if e["kwh"] == 200)
        assert entry_200["rate"] == 13.8161
        assert entry_200["rate_change"] == round(13.8161 - 13.1734, 4)
        assert entry_200["trend"] == "up"

    @patch("src.parser.download_pdf")
    def test_current_month_fails_falls_back(self, mock_download: MagicMock) -> None:
        call_count = [0]

        def side_effect(url: str) -> bytes | None:
            call_count[0] += 1
            if call_count[0] <= 1:
                return None
            with open(FIXTURE_BILLS_MAR, "rb") as f:
                return f.read()

        mock_download.side_effect = side_effect
        result = get_meralco_rates()
        assert result["success"] is True
        assert result["warning"] is not None

    @patch("src.parser.download_pdf")
    def test_both_months_fail(self, mock_download: MagicMock) -> None:
        mock_download.return_value = None
        result = get_meralco_rates()
        assert result["success"] is False
        assert result["error"] is not None
