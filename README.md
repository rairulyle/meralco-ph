# MERALCO Electricity Rate Scraper

Scrapes current electricity rates from MERALCO's official website for Home Assistant integration.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Usage

### Direct Script

```bash
python scraper.py
```

### REST API

```bash
python api.py
# API runs on http://localhost:5000
```

Endpoints:
- `GET /rates` - Returns current electricity rates
- `GET /health` - Health check

## Home Assistant Integration

### Option 1: REST Sensor

Add to `configuration.yaml`:

```yaml
sensor:
  - platform: rest
    name: MERALCO Rate
    resource: http://localhost:5000/rates
    value_template: "{{ value_json.rates.overall_rate }}"
    unit_of_measurement: "PHP/kWh"
    scan_interval: 86400  # Once per day
    json_attributes:
      - rate_direction
      - rates
      - url
      - timestamp
```

### Option 2: Command Line Sensor

```yaml
sensor:
  - platform: command_line
    name: MERALCO Rate
    command: "cd /path/to/meralco-scraper && python scraper.py"
    value_template: "{{ value_json.rates.overall_rate }}"
    unit_of_measurement: "PHP/kWh"
    scan_interval: 86400
    json_attributes:
      - rate_direction
      - rates
```

## Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && playwright install chromium && playwright install-deps

COPY . .
CMD ["python", "api.py"]
```

## Output Format

```json
{
  "success": true,
  "url": "https://company.meralco.com.ph/news-and-advisories/lower-rates-december-2025",
  "rate_direction": "lower",
  "rates": {
    "overall_rate": 11.7665,
    "generation_charge": 6.1234,
    "transmission_charge": 1.2345,
    "distribution_charge": null,
    "rate_change": -0.1234
  },
  "timestamp": "2025-12-21T12:00:00"
}
```
