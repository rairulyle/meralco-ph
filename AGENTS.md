# Agent-facing project summary

For AI agents (Cursor, Copilot, etc.) working in this repo.

## What this project does

- **MERALCO PH API**: REST API that scrapes current MERALCO (Manila Electric Company) electricity rates from the Philippines and serves them as JSON.
- Scrapes `https://company.meralco.com.ph/news-and-advisories` rate announcement pages, caches results, and exposes `/rates` and `/health`.
- Used for Home Assistant and similar automation; not affiliated with MERALCO.

## Repo layout

| Path | Purpose |
|------|---------|
| `src/scraper.py` | Scraping logic: URL generation, pyppeteer fetch, BeautifulSoup parsing. **URL pattern lives in `get_month_url()`.** |
| `src/api.py` | Flask app: `/`, `/rates`, `/health`; cache and fallback (current month → previous month). |
| `src/__init__.py` | Package root; **`__version__`** is defined here. |
| `tests/test_api.py` | Pytest tests for API and cache behavior (mocked scraper). |
| `scripts/bump_version.py` | Bump version in `src/__init__.py` and `src/api.py`. Supports `1.2.0` or `major` / `minor` / `patch`. Does **not** edit CHANGELOG. |
| `CHANGELOG.md` | Human-maintained; Keep a Changelog style. Update manually when releasing. |
| `docs/thoughts/` | Local notes (e.g. URL pattern history); **gitignored**. |
| `Pipfile` | Pipenv deps and scripts: `start`, `test`, `bump`. |
| `Dockerfile` / `docker-compose.yml` | Run API in container. |

## Conventions

- **Version**: Must be set in both `src/__init__.py` (`__version__`) and `src/api.py` (`"version"` in index response). Use `pipenv run bump patch` (or `minor` / `major` / explicit `1.x.x`).
- **Changelog**: Updated by hand when releasing; bump script reminds you.
- **MERALCO URLs**: The site changes URL patterns periodically. When they change, update `get_month_url()` in `src/scraper.py` and optionally note the pattern in `docs/thoughts/` (local only). Current format: `higher-residential-rates-{month}-{year}` and `lower-residential-rates-{month}-{year}` (month lowercase, e.g. `february`).

## Commands

- Run API: `pipenv run start` (or `PYTHONPATH=. python -m src.api`).
- Tests: `pipenv run test` or `pytest tests/ -v`.
- Bump version: `pipenv run bump patch` (or `minor`, `major`, or `1.2.0`).

## Tech stack

- Python 3.12, Flask, pyppeteer (headless Chromium), BeautifulSoup, python-dateutil.
- Tests: pytest with mocks; no live scraping in CI.

## When changing the scraper

1. URL or HTML structure change → update `src/scraper.py` (`get_month_url()` and/or `parse_rates()`).
2. Run tests: `pipenv run test`.
3. If you bump version, run `pipenv run bump patch` (or appropriate part) and update `CHANGELOG.md` manually.
