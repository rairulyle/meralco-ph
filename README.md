# ⚡ MERALCO PH - API

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]][license]
[![Build Status][github-actions-shield]][github-actions]
![Project Maintenance][maintenance-shield]
[![GitHub Activity][commits-shield]][commits]

![Supports amd64 Architecture][amd64-shield]
![Supports aarch64 Architecture][aarch64-shield]

[![Buy Me a Coffee][bmc-shield]][bmc]

Konnichiwassup! This is a REST API that provides current MERALCO (Manila Electric Company) electricity rates in the Philippines.

MERALCO is the largest electric distribution utility company in the Philippines, serving Metro Manila and nearby provinces. This API automatically parses MERALCO's monthly residential bills and serves per-kWh rates at every consumption level they publish. Rates match MERALCO's published [typical household article](https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-april-2026).

## ✨ Features

- Home Assistant Add-on
- Rates at 15 consumption levels (Default: 200): 50, 70, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 3000, 5000 kWh
- Month-over-month rate changes with trend indicator
- Caches data to minimize requests (refreshes monthly)
- Returns previous month's rates if current month is unavailable
- Lightweight REST API with health check endpoint
- Docker-ready for easy deployment

## 🏠 Home Assistant Add-on (Recommended)

The easiest way to use MERALCO PH with Home Assistant. Install the add-on and sensor entities are created automatically via MQTT discovery, no manual `configuration.yaml` editing needed.

[Add repository to my Home Assistant](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Frairulyle%2Fmeralco-ph)

### Prerequisites

- A running **Home Assistant Supervisor** install (Home Assistant OS or Supervised). Home Assistant Container is not supported because it has no add-on store.
- The official **Mosquitto broker** add-on installed and running.
- The **MQTT integration** configured in Home Assistant (this happens automatically when Mosquitto is installed and started).

If you don't have an MQTT broker yet, install the Mosquitto broker add-on first:

**Settings → Add-ons → Add-on Store → Mosquitto broker → Install → Start**.

### Installation

1. Click the **Add repository** button above, or manually add the repository in **Settings → Add-ons → Add-on Store → ⋮ (top right) → Repositories** and paste:

   ```
   https://github.com/rairulyle/meralco-ph
   ```

2. Refresh the Add-on Store page, find **MERALCO Electricity Rates**, and click **Install**.
3. Open the **Configuration** tab. Defaults are fine for most users; see [DOCS.md](DOCS.md) for the full options reference.
4. Click **Start** on the **Info** tab.
5. Check **Settings → Devices & Services → MQTT**. A new **MERALCO Electricity Rates** device should appear with sensors for each level in `kwh_levels` (default: 200 kWh).

### Sensors created

For each entry in `kwh_levels`, the add-on creates four sensors under one device. The 200 kWh "typical" baseline is always exposed unsuffixed so dashboards stay stable when you add or remove other levels:

- `sensor.meralco_rate`, `sensor.meralco_rate_change`, `sensor.meralco_rate_change_percent`, `sensor.meralco_trend`: always 200 kWh
- `sensor.meralco_rate_<kwh>kwh`, etc.: for every other level (e.g. `300`, `500`)

Example: with `kwh_levels: [200, 300]` you get eight sensors total.

## 🐳 Standalone Docker (alternative)

If you're not using Home Assistant Supervisor, or you prefer the REST API over MQTT, you can run the standalone container with `docker compose`:

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

The API will be available at `http://localhost:5000/rates`.

### Alternative: Using Docker run

```bash
docker run -d -p 5000:5000 --name meralco-ph ghcr.io/rairulyle/meralco-ph:latest
```

### Consuming the standalone API from Home Assistant

If you're running the standalone container alongside Home Assistant (e.g. on the same host or LAN), use the built-in `rest:` integration to expose the rates as sensors. Add to `configuration.yaml`:

```yaml
rest:
  - resource: http://localhost:5000/rates/typical
    scan_interval: 86400
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

## 📡 API Endpoints

| Endpoint             | Description                                                                                                                                                |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /rates`         | All 15 consumption levels                                                                                                                                  |
| `GET /rates/typical` | Typical household (200 kWh), matches MERALCO's published [article](https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-april-2026) |
| `GET /rates/<kwh>`   | Specific consumption level (e.g. `/rates/100`, `/rates/500`)                                                                                               |
| `GET /health`        | Health check                                                                                                                                               |

### Valid consumption levels

`50`, `70`, `100`, `200`, `300`, `400`, `500`, `600`, `700`, `800`, `900`, `1000`, `1500`, `3000`, `5000`, `typical` (alias for 200)

## 📋 Output Format

### `GET /rates`: All consumption levels

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

### `GET /rates/typical`: 200 kWh household

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

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and the pull request workflow.

## 📄 License

MIT License, see [LICENSE](LICENSE) for details.

---

**Keywords:** MERALCO rates, Philippines electricity rates, Philippine power rates, Manila Electric Company, MERALCO kWh rate, Philippine electricity price, Home Assistant MERALCO integration, MERALCO API, MERALCO Docker

[releases-shield]: https://img.shields.io/github/v/release/rairulyle/meralco-ph
[releases]: https://github.com/rairulyle/meralco-ph/releases
[license-shield]: https://img.shields.io/github/license/rairulyle/meralco-ph
[license]: https://github.com/rairulyle/meralco-ph/blob/main/LICENSE
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[github-actions-shield]: https://img.shields.io/github/actions/workflow/status/rairulyle/meralco-ph/docker-publish.yml
[github-actions]: https://github.com/rairulyle/meralco-ph/actions
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026
[commits-shield]: https://img.shields.io/github/commit-activity/m/rairulyle/meralco-ph
[commits]: https://github.com/rairulyle/meralco-ph/commits/main
[bmc-shield]: https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?logo=buymeacoffee&logoColor=black
[bmc]: https://buymeacoffee.com/rairulyle
