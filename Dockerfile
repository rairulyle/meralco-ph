FROM python:3.12-slim

WORKDIR /app

# Install system chromium (smaller than pyppeteer's bundled version)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Tell pyppeteer to use system chromium
ENV PYPPETEER_CHROMIUM_EXECUTABLE=/usr/bin/chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "src.api:app"]
