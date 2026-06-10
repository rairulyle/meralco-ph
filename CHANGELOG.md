# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.3] - 2026-06-10

### Changed

- HA Add-on image is now a single multi-arch package (`meralco-ph-addon`) replacing the per-arch `amd64-meralco-ph` and `aarch64-meralco-ph` packages.

## [2.0.2] - 2026-04-22

### Changed

- Add-on now pulls a pre-built image from GHCR instead of building locally. Installs and updates are faster and the Rebuild button is replaced with Reinstall.
- Standalone Docker image is now multi-arch (amd64 + aarch64). `docker pull ghcr.io/rairulyle/meralco-ph:latest` works on ARM hosts.

## [2.0.1] - 2026-04-11

### Fixed

- Home Assistant add-on now installs correctly (added missing `repository.yaml`).
- Add-on no longer crashes on startup with `No MQTT broker available`.
- Add-on icon (`icon.png`) shown in the HA add-on store.

### Changed

- Renamed add-on to `MERALCO PH`.
- Replaced "scrape" wording with "parse" in user-facing docs and the HA device model field.

## [2.0.0] - 2026-04-11

### Changed

- **BREAKING**: Switched from web scraping to PDF-based rate parsing. Data source is MERALCO's official `residential_bills.pdf`, their own pre-computed bill table containing per-kWh rates at 15 consumption levels
- **BREAKING**: API routes now accept kWh consumption levels (`/rates/200`, `/rates/500`, etc.) instead of news article metadata
- Rates match MERALCO's published "typical household" article
- New routes: `/rates`, `/rates/typical`, `/rates/<kwh>`
- Response entries: `{kwh, rate, rate_change, rate_change_percent, trend}`
- Month-over-month rate changes computed by diffing current and previous month PDFs
- Standardized response shape with `success`, `error`, `warning`, `date`, `data`, `meta`
- Renamed `src/scraper.py` to `src/parser.py`
- Docker image significantly smaller (no Chromium dependency)
- The standalone GHCR image now builds from `Dockerfile.standalone`. The root `Dockerfile` is the Home Assistant add-on Dockerfile. The standalone image content and entrypoint are unchanged.

### Added

- `parse_residential_bills()` parser
- `/rates/<kwh>` routes for 15 consumption levels (50, 70, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 3000, 5000)
- `/rates/typical` as an alias for `/rates/200`
- Home Assistant Supervisor add-on. Install via the HA add-on store by adding the repository URL.
- Two add-on modes: `mqtt` (default, auto-publishes sensors via Home Assistant MQTT discovery) and `rest` (runs the existing Flask API on port 5000 for `rest:` integration users).
- `kwh_levels` add-on option lets users expose multiple consumption levels as sensors (e.g. `[200, 300]`). Each level publishes four sensors under one device: rate, rate change, rate change percent, and trend. The 200 kWh "typical" baseline is always exposed with unsuffixed entity IDs (`sensor.meralco_rate`, etc.) so existing dashboards stay stable when other levels are added or removed.
- Auto-discovery of MQTT broker credentials via the Supervisor service API. Users never type broker credentials.

### Removed

- pyppeteer and beautifulsoup4 dependencies (replaced by pdfplumber)
- `raw_text` field from response

## [1.1.2] - 2026-02-21

### Fixed

- Updated rate page URL pattern to match MERALCO change: `higher-residential-rates-{month}-{year}` and `lower-residential-rates-{month}-{year}`

### Changed

- Added `docs/thoughts/` to `.gitignore` for local AI agent notes

## [1.1.1] - 2026-02-01

### Fixed

- Fixed infinite scraping loop when current month rates are unavailable by caching fallback data with a 1-hour retry interval
- Added fetch lock to prevent concurrent requests from spawning multiple Chromium browsers
- Fixed tests to use mocked dates instead of depending on the current month

## [1.1.0] - 2026-01-16

### Added

- Disable cache when current month data is unavailable and fallback to previous month data
- Test suite for improved code quality

### Changed

- Restructured project folder organization
- Refactored scraper to use parallel fetching for improved performance
- Updated URL format to prefer no year for 2026 and beyond
- Docker build now uses pyppeteer for smaller image size

## [1.0.0] - 2025-12-22

### Added

- Standardized API response format for consistent data structure
- Docker workflow for automated builds and publishing
- Cache expiration at the start of each month to ensure fresh data retrieval
- Home Assistant integration example with REST to sensor configuration

### Changed

- Optimized scraper to only open Chromium browser when HTTP HEAD request returns 200
- Improved logging with better formatting and production server preferences
- Docker image now uses `latest` tag
- Project renamed to `meralco-ph` for consistency

### Documentation

- Updated README with improved SEO keywords and formatting
- Added setup instructions and improvements
- Added Home Assistant sample configuration (REST to sensor)
- Standardized README format
- Added project signature
- Removed redundant sentence about MERALCO

[2.0.0]: https://github.com/rairulyle/meralco-ph/compare/3ca1a31...HEAD
[1.1.2]: https://github.com/rairulyle/meralco-ph/compare/76aa0f2da563d8a6b8e162297583305fad153a93...3ca1a31
[1.1.1]: https://github.com/rairulyle/meralco-ph/compare/e5c841beceb9963acf638ca2bbb06d300ba9b9e6...76aa0f2da563d8a6b8e162297583305fad153a93
[1.1.0]: https://github.com/rairulyle/meralco-ph/compare/509d4782be32d639f2fa711437c36117941121fb...e5c841beceb9963acf638ca2bbb06d300ba9b9e6
[1.0.0]: https://github.com/rairulyle/meralco-ph/compare/509d4782be32d639f2fa711437c36117941121fb...e5c841beceb9963acf638ca2bbb06d300ba9b9e6
