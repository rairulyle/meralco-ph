# ⚡ MERALCO PH - API

Konnichiwassup! This is a REST API that provides current MERALCO (Manila Electric Company) electricity rates in the Philippines.

MERALCO is the largest electric distribution utility company in the Philippines, serving Metro Manila and nearby provinces. This API automatically parses MERALCO's monthly residential bills and serves per-kWh rates at every consumption level they publish. Rates match MERALCO's published [typical household article](https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-april-2026).

## ✨ Features

- Rates at 15 consumption levels: 50, 70, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 3000, 5000 kWh
- Month-over-month rate changes with trend indicator
- `/rates/typical` endpoint — matches MERALCO's published "typical household" (200 kWh) rate exactly
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

| Endpoint             | Description                                                                                                                                                 |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /rates`         | All 15 consumption levels                                                                                                                                   |
| `GET /rates/typical` | Typical household (200 kWh) — matches MERALCO's published [article](https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-april-2026) |
| `GET /rates/<kwh>`   | Specific consumption level (e.g. `/rates/100`, `/rates/500`)                                                                                                |
| `GET /health`        | Health check                                                                                                                                                |

### Valid consumption levels

`50`, `70`, `100`, `200`, `300`, `400`, `500`, `600`, `700`, `800`, `900`, `1000`, `1500`, `3000`, `5000`, `typical` (alias for 200)

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

### `GET /rates` — All consumption levels

```json
{
  "success": true,
  "date": "03/2026",
  "data": [
    {
      "kwh": 50,
      "rate": 14.1766,
      "rate_change": 0.6289,
      "rate_change_percent": 4.65,
      "trend": "up"
    },
    ...
    {
      "kwh": 200,
      "rate": 13.8161,
      "rate_change": 0.6427,
      "rate_change_percent": 4.88,
      "trend": "up"
    },
    ...
  ],
  "meta": {
    "timestamp": "2026-03-24T02:09:08.653424",
    "source": "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-03/03-2026_residential_bills.pdf"
  }
}
```

### `GET /rates/typical` — 200 kWh household

```json
{
  "success": true,
  "date": "03/2026",
  "data": {
    "kwh": 200,
    "rate": 13.8161,
    "rate_change": 0.6427,
    "rate_change_percent": 4.88,
    "trend": "up"
  },
  "meta": {
    "timestamp": "2026-03-24T02:09:08.653424",
    "source": "https://meralcomain.s3.ap-southeast-1.amazonaws.com/2026-03/03-2026_residential_bills.pdf"
  }
}
```

| Field                 | Description                                                      | Example   |
| --------------------- | ---------------------------------------------------------------- | --------- |
| `kwh`                 | Consumption level in kWh                                         | `200`     |
| `rate`                | Final per-kWh rate (PHP, matches MERALCO published rate exactly) | `13.8161` |
| `rate_change`         | Change from previous month (negative = decrease)                 | `0.6427`  |
| `rate_change_percent` | Percentage change from previous month                            | `4.88`    |
| `trend`               | Rate direction: `up`, `down`, or `stable`                        | `"up"`    |

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
