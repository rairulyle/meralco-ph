"""
MERALCO Add-on Main Entry Point

Runs as a Home Assistant add-on: reads configuration, branches on `mode`,
and either publishes MERALCO rates to MQTT or hands off to gunicorn for
the REST API.
"""

import json
import logging
import os
import signal
import sys
import time
import urllib.request
from pathlib import Path
from types import FrameType
from typing import TypedDict, cast

from src.api import VALID_KWH_LEVELS
from src.mqtt_bridge import MeralcoMQTTBridge, RateStateEntry
from src.parser import MeralcoRatesResult, get_meralco_rates

logger = logging.getLogger(__name__)

DEFAULT_OPTIONS_PATH = Path("/data/options.json")


class MqttCredentials(TypedDict):
    host: str
    port: int
    username: str | None
    password: str | None


class AddonConfig(TypedDict):
    mode: str
    log_level: str
    scan_interval: int
    kwh_levels: list[int]
    mqtt_topic_prefix: str
    mqtt_discovery_prefix: str


_DEFAULTS: AddonConfig = {
    "mode": "mqtt",
    "log_level": "info",
    "scan_interval": 86400,
    "kwh_levels": [200],
    "mqtt_topic_prefix": "meralco",
    "mqtt_discovery_prefix": "homeassistant",
}

_running = True


def _install_signal_handlers() -> None:
    def _handler(signum: int, _frame: FrameType | None) -> None:
        global _running
        logger.info("Received signal %s, shutting down", signum)
        _running = False

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def read_addon_config(options_path: Path = DEFAULT_OPTIONS_PATH) -> AddonConfig:
    """Load add-on options from /data/options.json with env var fallback."""
    config: AddonConfig = cast(AddonConfig, dict(_DEFAULTS))

    _apply_env_vars(config)

    if options_path.is_file():
        try:
            options = json.loads(options_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read add-on options at %s: %s", options_path, exc)
        else:
            if not isinstance(options, dict):
                logger.warning(
                    "Add-on options at %s is not a JSON object; using defaults",
                    options_path,
                )
            else:
                for key in _DEFAULTS:
                    if key in options:
                        config[key] = options[key]  # type: ignore[literal-required]
                logger.info("Loaded add-on options from %s", options_path)

    config["kwh_levels"] = _validate_kwh_levels(config["kwh_levels"])
    return config


def _apply_env_vars(config: AddonConfig) -> None:
    """Overlay environment-variable overrides on top of defaults (mutates config)."""
    if value := os.environ.get("MODE"):
        config["mode"] = value
    if value := os.environ.get("LOG_LEVEL"):
        config["log_level"] = value
    if value := os.environ.get("SCAN_INTERVAL"):
        try:
            config["scan_interval"] = int(value)
        except ValueError:
            logger.warning("Invalid SCAN_INTERVAL=%s, using default", value)
    if value := os.environ.get("KWH_LEVELS"):
        try:
            config["kwh_levels"] = [
                int(v.strip()) for v in value.split(",") if v.strip()
            ]
        except ValueError:
            logger.warning("Invalid KWH_LEVELS=%s, using default", value)
    if value := os.environ.get("MQTT_TOPIC_PREFIX"):
        config["mqtt_topic_prefix"] = value
    if value := os.environ.get("MQTT_DISCOVERY_PREFIX"):
        config["mqtt_discovery_prefix"] = value


def _validate_kwh_levels(levels: list[int]) -> list[int]:
    """Drop levels not in VALID_KWH_LEVELS, log a warning per drop."""
    valid: list[int] = []
    for level in levels:
        if level in VALID_KWH_LEVELS:
            valid.append(level)
        else:
            logger.warning(
                "Dropping invalid kwh_level=%s (not in VALID_KWH_LEVELS)", level
            )
    return valid


def _get_mqtt_from_supervisor() -> MqttCredentials | None:
    """Fetch MQTT broker credentials from the HA Supervisor service API.

    Returns None if SUPERVISOR_TOKEN is missing, the HTTP call fails,
    or the response is missing a host field.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None

    try:
        request = urllib.request.Request(
            "http://supervisor/services/mqtt",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
    except (OSError, ValueError) as exc:
        logger.warning("Could not fetch MQTT broker from Supervisor: %s", exc)
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Supervisor returned invalid JSON: %s", exc)
        return None

    if not isinstance(parsed, dict):
        logger.warning("Supervisor returned non-object root; ignoring")
        return None

    payload = parsed.get("data")
    if not isinstance(payload, dict):
        return None

    host = payload.get("host")
    if not isinstance(host, str) or not host:
        return None

    port_value = payload.get("port", 1883)
    if isinstance(port_value, int):
        port = port_value
    elif isinstance(port_value, str) and port_value.isdigit():
        port = int(port_value)
    else:
        port = 1883

    username = payload.get("username")
    password = payload.get("password")

    return {
        "host": host,
        "port": port,
        "username": username if isinstance(username, str) else None,
        "password": password if isinstance(password, str) else None,
    }


def _get_mqtt_from_env() -> MqttCredentials | None:
    host = os.environ.get("MQTT_HOST")
    if not host:
        return None

    port_str = os.environ.get("MQTT_PORT", "1883")
    try:
        port = int(port_str)
    except ValueError:
        port = 1883

    return {
        "host": host,
        "port": port,
        "username": os.environ.get("MQTT_USERNAME"),
        "password": os.environ.get("MQTT_PASSWORD"),
    }


def _exec_gunicorn() -> None:
    logger.info("Starting REST API via gunicorn on :5000")
    os.execvp(
        "gunicorn",
        [
            "gunicorn",
            "--bind",
            "0.0.0.0:5000",
            "--workers",
            "1",
            "--timeout",
            "120",
            "src.api:app",
        ],
    )


def _publish_one_cycle(bridge: MeralcoMQTTBridge, kwh_levels: list[int]) -> None:
    result: MeralcoRatesResult = get_meralco_rates()
    if not result.get("success"):
        logger.warning("Rate fetch failed: %s", result.get("error"))
        return

    by_kwh: dict[int, RateStateEntry] = {}
    for entry in result.get("data") or []:
        kwh = entry.get("kwh")
        if kwh in kwh_levels:
            rate = entry.get("rate")
            rate_change = entry.get("rate_change")
            rate_change_percent = entry.get("rate_change_percent")
            trend = entry.get("trend")
            by_kwh[kwh] = {
                "rate": rate,
                "rate_change": rate_change,
                "rate_change_percent": rate_change_percent,
                "trend": trend,
            }
    bridge.publish_state(by_kwh)


def main() -> None:
    """Add-on entry point."""
    config = read_addon_config()
    logging.basicConfig(
        level=getattr(logging, config["log_level"].upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Starting MERALCO add-on (mode=%s)", config["mode"])

    if config["mode"] == "rest":
        _exec_gunicorn()
        return  # unreachable; execvp replaces the process

    if config["mode"] != "mqtt":
        logger.error("Unknown mode=%s, exiting", config["mode"])
        sys.exit(2)

    if not config["kwh_levels"]:
        logger.error(
            "kwh_levels is empty after validation. "
            "Set at least one valid level (e.g. 200) and restart the add-on."
        )
        sys.exit(2)

    creds = _get_mqtt_from_supervisor() or _get_mqtt_from_env()
    if creds is None:
        logger.error(
            "No MQTT broker available. Install the Mosquitto add-on or set "
            "MQTT_HOST/MQTT_PORT/MQTT_USERNAME/MQTT_PASSWORD env vars."
        )
        sys.exit(2)

    bridge = MeralcoMQTTBridge(
        host=creds["host"],
        port=creds["port"],
        username=creds["username"],
        password=creds["password"],
        topic_prefix=config["mqtt_topic_prefix"],
        discovery_prefix=config["mqtt_discovery_prefix"],
        kwh_levels=config["kwh_levels"],
    )

    if not bridge.connect():
        logger.error("Failed to connect to MQTT broker after retries")
        sys.exit(1)

    _install_signal_handlers()
    bridge.publish_online()
    bridge.publish_discovery()

    try:
        while _running:
            _publish_one_cycle(bridge, config["kwh_levels"])
            time.sleep(config["scan_interval"])
    finally:
        bridge.disconnect()


if __name__ == "__main__":
    main()
