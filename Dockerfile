# check=skip=InvalidBaseImagePlatform

# HA base images are published per-arch as `amd64-…` / `aarch64-…` with no
# generic multi-arch manifest, so map buildx's TARGETARCH (amd64 / arm64)
# onto the matching base via stage aliases. Only the selected stage is pulled.
FROM ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20 AS base-amd64
FROM ghcr.io/home-assistant/aarch64-base-python:3.12-alpine3.20 AS base-arm64

ARG TARGETARCH
FROM base-${TARGETARCH}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Copy s6-overlay service definitions. The run script uses
# `#!/usr/bin/with-contenv bashio` so SUPERVISOR_TOKEN and other
# Supervisor-injected env vars are available to the Python process.
COPY rootfs /

EXPOSE 5000
