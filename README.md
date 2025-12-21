# MERALCO API

Provides a REST endpoint of the current MERALCO electricity rates.

## Setup

### Using pipenv

```bash
pipenv install
pipenv run playwright install chromium
```

### Using venv

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Usage

### Direct Script

```bash
pipenv run python scraper.py
```

### REST API

```bash
pipenv run python api.py
# API runs on http://localhost:5000
```

Endpoints:

- `GET /rates` - Returns current electricity rates
- `GET /health` - Health check

## Docker

### Using Docker Compose (Recommended)

```bash
docker compose up -d
```

### Using Docker directly

```bash
docker build -t meralco-api .
docker run -d -p 5000:5000 meralco-api
```

## Home Assistant Integration

### REST Sensor

Add to `configuration.yaml`:

```yaml
sensor:
  - platform: rest
    name: MERALCO Rate
    resource: http://localhost:5000/rates
    value_template: "{{ value_json.data.rate_kwh }}"
    unit_of_measurement: "PHP/kWh"
    scan_interval: 86400 # Once per day
    json_attributes_path: "$.data"
    json_attributes:
      - rate_kwh
      - rate_change
      - rate_change_percent
      - rate_unit
      - trend
```

## Output Format

```json
{
  "success": true,
  "url": "https://company.meralco.com.ph/news-and-advisories/lower-rates-december-2025",
  "data": {
    "rate_kwh": 13.1145,
    "rate_change": -0.3557,
    "rate_change_percent": -2.64,
    "rate_unit": "PHP/kWh",
    "trend": "down",
    "raw_text": "..."
  },
  "error": null,
  "timestamp": "2025-12-21T12:00:00"
}
```

| Field                 | Description                                      |
| --------------------- | ------------------------------------------------ |
| `rate_kwh`            | Current electricity rate per kWh                 |
| `rate_change`         | Change from previous month (negative = decrease) |
| `rate_change_percent` | Percentage change from previous month            |
| `rate_unit`           | Unit of measurement                              |
| `trend`               | Rate direction: `up` or `down`                   |
