# Agent-facing project summary

For AI agents (Cursor, Copilot, etc.) working in this repo.

## What this project does

- **MERALCO PH API**: REST API that parses MERALCO (Manila Electric Company) residential bills PDFs and serves per-kWh rates at each published consumption level.
- Downloads monthly `residential_bills.pdf` from MERALCO's S3 bucket and extracts the "For Non-Lifeline Customers" per-kWh rate table. Rates match MERALCO's published "typical household" figure 1:1 — no VAT math, no franchise tax estimation.
- Used for Home Assistant and similar automation; not affiliated with MERALCO.

## Repo layout

| Path | Purpose |
|------|---------|
| `src/parser.py` | PDF download, table extraction, residential bills parsing, month diff. **URL pattern lives in `get_pdf_url()`.** |
| `src/api.py` | Flask app: `/`, `/rates`, `/rates/typical`, `/rates/<kwh>`, `/health`; cache and fallback (current month → previous month). |
| `src/__init__.py` | Package root; **`__version__`** is defined here. |
| `tests/test_parser.py` | Pytest tests for PDF parsing and rate changes (uses real PDF fixtures). |
| `tests/test_api.py` | Pytest tests for API routes and cache behavior (mocked parser). |
| `tests/fixtures/` | Real MERALCO residential bills PDFs for testing. |
| `scripts/bump_version.py` | Bump version in `src/__init__.py` and `src/api.py`. Supports `1.2.0` or `major` / `minor` / `patch`. Does **not** edit CHANGELOG. |
| `CHANGELOG.md` | Human-maintained; Keep a Changelog style. Update manually when releasing. |
| `docs/thoughts/` | Local notes; **gitignored**. |
| `Pipfile` | Pipenv deps and scripts: `start`, `test`, `bump`. |
| `Dockerfile` / `docker-compose.yml` | Run API in container. |

## Conventions

- **Version**: Must be set in both `src/__init__.py` (`__version__`) and `src/api.py` (`"version"` in index response). Use `pipenv run bump patch` (or `minor` / `major` / explicit `1.x.x`).
- **Changelog**: Updated by hand when releasing; bump script reminds you.
- **PDF URL pattern**: `https://meralcomain.s3.ap-southeast-1.amazonaws.com/{YYYY-MM}/{MM-YYYY}_residential_bills.pdf`. If MERALCO changes this pattern, update `get_pdf_url()` in `src/parser.py`.
- **Valid consumption levels**: `50, 70, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 3000, 5000` (`typical` aliases `200`). This list is defined in `src/api.py` as `VALID_KWH_LEVELS`.

## Commands

- Run API: `pipenv run start` (or `PYTHONPATH=. python -m src.api`).
- Tests: `pipenv run test` or `pytest tests/ -v`.
- Bump version: `pipenv run bump patch` (or `minor`, `major`, or `1.2.0`).

## Tech stack

- Python 3.12, Flask, pdfplumber (PDF parsing), python-dateutil.
- Tests: pytest with real PDF fixtures and mocks; no live downloads in CI.

## When changing the parser

1. PDF URL pattern or table structure change → update `src/parser.py` (`get_pdf_url()` or `parse_residential_bills()`).
2. Run tests: `pipenv run test`.
3. If you bump version, run `pipenv run bump patch` (or appropriate part) and update `CHANGELOG.md` manually.
