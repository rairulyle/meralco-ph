# MERALCO API

A REST API that scrapes and provides current MERALCO (Manila Electric Company) electricity rates in the Philippines.

MERALCO is the largest electric distribution utility company in the Philippines, serving Metro Manila and nearby provinces. This API fetches the latest electricity rates from MERALCO's official announcements.

## Quick Start (Recommended)

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

## API Endpoints

- `GET /rates` - Returns current electricity rates
- `GET /health` - Health check

## Home Assistant Integration

Add to `configuration.yaml`:

```yaml
rest:
  - resource: http://localhost:5000/rates
    scan_interval: 86400 # Once per day
    sensor:
      - name: "MERALCO Rate"
        unit_of_measurement: "PHP/kWh"
        value_template: "{{ value_json.data.rate_kwh }}"
      - name: "MERALCO Rate Change"
        unit_of_measurement: "PHP/kWh"
        value_template: "{{ value_json.data.rate_change }}"
      - name: "MERALCO Rate Change Percent"
        unit_of_measurement: "%"
        value_template: "{{ value_json.data.rate_change_percent }}"
      - name: "MERALCO Rate Trend"
        value_template: "{{ value_json.data.trend }}"
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

## Disclaimer

This project scrapes publicly available electricity rate announcements from MERALCO's official website for personal/home automation use. It is not affiliated with or endorsed by MERALCO. The API fetches data infrequently (once per month) to minimize server impact. Use responsibly.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Keywords:** MERALCO rates, Philippines electricity rates, Philippine power rates, Manila Electric Company, MERALCO kWh rate, Philippine electricity price, Home Assistant MERALCO integration, MERALCO API, MERALCO Docker
