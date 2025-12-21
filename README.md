# MERALCO API

A REST API that scrapes and provides current MERALCO (Manila Electric Company) electricity rates in the Philippines.

MERALCO is the largest electric distribution utility company in the Philippines, serving Metro Manila and nearby provinces. This API fetches the latest electricity rates from MERALCO's official announcements.

## Quick Start (Recommended)

Create a `docker-compose.yml` file:

```yaml
services:
  meralco-api:
    image: ghcr.io/rairulyle/meralco-api:main
    container_name: meralco-api
    ports:
      - "5000:5000"
    restart: unless-stopped
```

Then run:

```bash
docker compose up -d
```

The API will be available at `http://localhost:5000/rates`

### Alternative: Using Docker run

```bash
docker run -d -p 5000:5000 --name meralco-api ghcr.io/rairulyle/meralco-api:main
```

## API Endpoints

- `GET /rates` - Returns current electricity rates
- `GET /health` - Health check

## Home Assistant Integration

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

---

## Manual Installation

If you prefer to build from source, clone the repository first:

```bash
git clone https://github.com/rairulyle/meralco-api.git
cd meralco-api
```

### Using Docker Compose

```bash
docker compose up -d
```

### Building Docker image locally

```bash
docker build -t meralco-api .
docker run -d -p 5000:5000 meralco-api
```

### Using pipenv

```bash
pipenv install
pipenv run playwright install chromium
pipenv run python api.py
```

### Using venv

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python api.py
```

---

**Keywords:** MERALCO rates, Philippines electricity rates, Philippine power rates, Manila Electric Company, MERALCO kWh rate, Philippine electricity price, Home Assistant MERALCO integration, MERALCO API, MERALCO Docker
