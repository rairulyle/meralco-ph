# ⚡ MERALCO PH - API

Konnichiwassup! This is a REST API that provides current MERALCO (Manila Electric Company) electricity rates in the Philippines.

MERALCO is the largest electric distribution utility company in the Philippines, serving Metro Manila and nearby provinces. This API automatically parses the latest monthly electricity rates from MERALCO's official rate schedule PDFs, making it easy to integrate real-time rate data into your Home Assistant setup or any other automation platform.

**✨ Features:**

- All 8 residential rate tiers with VAT-inclusive computation
- Month-over-month rate changes with trend indicator
- `/rates/typical` endpoint — the "typical household" rate (200 kWh) that MERALCO publishes in their monthly news articles
- Caches data to minimize requests (refreshes monthly)
- Returns previous month's rates if current month is unavailable
- Lightweight REST API with health check endpoint
- Docker-ready for easy deployment
- Home Assistant Add-on (Coming soon)

## 🚀 Quick Start (Recommended)

Create a `docker-compose.yml` file:

```yaml
services:
  meralco-ph:
    image: ghcr.io/rairulyle/meralco-ph:latest
    container_name: meralco-ph
    ports:
      - "5000:5000"
    restart: unless-stopped
    environment:
      - TZ=Asia/Manila
```

Then run:

```bash
docker compose up -d
```

The API will be available at `http://localhost:5000/rates`

### Alternative: Using Docker run

```bash
docker run -d -p 5000:5000 --name meralco-ph ghcr.io/rairulyle/meralco-ph:latest
```

## 📡 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /rates` | All 8 residential tier rates |
| `GET /rates/typical` | Typical household (200 kWh) rate — this is the same rate MERALCO publishes in their monthly news articles |
| `GET /rates/<tier>` | Specific tier (e.g. `/rates/101-200`, `/rates/over-400`) |
| `GET /health` | Health check |

### Valid tier slugs

`0-20`, `21-50`, `51-70`, `71-100`, `101-200`, `201-300`, `301-400`, `over-400`, `typical`

## 🏠 Home Assistant Integration

Add to `configuration.yaml`:

```yaml
rest:
  - resource: http://localhost:5000/rates/typical
    scan_interval: 86400 # Once per day
    sensor:
      - name: "MERALCO - Rate"
        unit_of_measurement: "PHP/kWh"
        value_template: "{{ value_json.data.rate }}"
      - name: "MERALCO - Rate Change"
        unit_of_measurement: "PHP/kWh"
        value_template: "{{ value_json.data.rate_change }}"
      - name: "MERALCO - Rate Change Percent"
        unit_of_measurement: "%"
        value_template: "{{ value_json.data.rate_change_percent }}"
      - name: "MERALCO - Trend"
        value_template: "{{ value_json.data.trend }}"
```

## 📋 Output Format

### `GET /rates` — All tiers

```json
{
  "success": true,
  "error": null,
  "warning": null,
  "date": "03/2026",
  "data": [
    {
      "name": "0-20 kWh",
      "min_kwh": 0,
      "max_kwh": 20,
      "rate": 13.7458,
      "rate_change": 0.6289,
      "rate_change_percent": 4.80,
      "trend": "up"
    },
    ...
  ],
  "meta": {
    "timestamp": "2026-03-23T17:10:22",
    "source": "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-03/03-2026_rate_schedule.pdf"
  }
}
```

### `GET /rates/typical` — Single tier

```json
{
  "success": true,
  "error": null,
  "warning": null,
  "date": "03/2026",
  "data": {
    "name": "101-200 kWh",
    "min_kwh": 101,
    "max_kwh": 200,
    "rate": 13.758,
    "rate_change": 0.6411,
    "rate_change_percent": 4.89,
    "trend": "up"
  },
  "meta": {
    "timestamp": "2026-03-23T17:10:22",
    "source": "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-03/03-2026_rate_schedule.pdf"
  }
}
```

| Field | Description | Example |
|-------|-------------|---------|
| `rate` | Current electricity rate per kWh (PHP, incl. VAT) | `13.758` |
| `rate_change` | Change from previous month (negative = decrease) | `0.6411` |
| `rate_change_percent` | Percentage change from previous month | `4.89` |
| `trend` | Rate direction: `up`, `down`, or `stable` | `up` |

> **Note:** The computed rate excludes local franchise tax (~0.4%), which varies by municipality. MERALCO's published "typical household" rate includes this tax and may differ slightly.

---

## 🔧 Manual Installation

If you prefer to build from source, clone the repository first:

```bash
git clone https://github.com/rairulyle/meralco-ph.git
cd meralco-ph
```

### Using Docker Compose

```bash
docker compose up -d
```

### Building Docker image locally

```bash
docker build -t meralco-ph .
docker run -d -p 5000:5000 meralco-ph
```

### Using pipenv

```bash
pipenv install
pipenv run start
```

### Running tests

```bash
pipenv run test
```

---

## ⚠️ Disclaimer

This project parses publicly available electricity rate schedule PDFs from MERALCO's official website for personal/home automation use. It is not affiliated with or endorsed by MERALCO. The API fetches data infrequently (once per month) to minimize server impact. Use responsibly.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**Keywords:** MERALCO rates, Philippines electricity rates, Philippine power rates, Manila Electric Company, MERALCO kWh rate, Philippine electricity price, Home Assistant MERALCO integration, MERALCO API, MERALCO Docker
