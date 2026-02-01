# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.1.1]: https://github.com/rairulyle/meralco-ph/compare/76aa0f2da563d8a6b8e162297583305fad153a93...HEAD
[1.1.0]: https://github.com/rairulyle/meralco-ph/compare/e5c841beceb9963acf638ca2bbb06d300ba9b9e6...76aa0f2da563d8a6b8e162297583305fad153a93
[1.0.0]: https://github.com/rairulyle/meralco-ph/compare/509d4782be32d639f2fa711437c36117941121fb...e5c841beceb9963acf638ca2bbb06d300ba9b9e6
