"""Tests for the add-on entry point glue."""

import json
import os
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def clean_supervisor_env() -> Iterator[None]:
    saved = os.environ.pop("SUPERVISOR_TOKEN", None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ["SUPERVISOR_TOKEN"] = saved


def test_get_mqtt_from_supervisor_returns_none_without_token(
    clean_supervisor_env: None,
) -> None:
    from src.addon_main import _get_mqtt_from_supervisor

    assert _get_mqtt_from_supervisor() is None


def test_get_mqtt_from_supervisor_parses_response(
    clean_supervisor_env: None,
) -> None:
    from src.addon_main import _get_mqtt_from_supervisor

    os.environ["SUPERVISOR_TOKEN"] = "fake-token"

    payload = json.dumps(
        {
            "data": {
                "host": "core-mosquitto",
                "port": 1883,
                "username": "addon_user",
                "password": "addon_pass",
            }
        }
    ).encode()

    fake_response = MagicMock()
    fake_response.read.return_value = payload
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_open:
        creds = _get_mqtt_from_supervisor()

    assert creds == {
        "host": "core-mosquitto",
        "port": 1883,
        "username": "addon_user",
        "password": "addon_pass",
    }
    request = mock_open.call_args.args[0]
    assert request.full_url == "http://supervisor/services/mqtt"
    assert request.headers["Authorization"] == "Bearer fake-token"


def test_get_mqtt_from_supervisor_returns_none_on_http_error(
    clean_supervisor_env: None,
) -> None:
    from src.addon_main import _get_mqtt_from_supervisor

    os.environ["SUPERVISOR_TOKEN"] = "fake-token"

    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        assert _get_mqtt_from_supervisor() is None


def test_get_mqtt_from_supervisor_returns_none_when_host_missing(
    clean_supervisor_env: None,
) -> None:
    """Empty/missing host means we treat the response as no broker available."""
    from src.addon_main import _get_mqtt_from_supervisor

    os.environ["SUPERVISOR_TOKEN"] = "fake-token"

    payload = json.dumps({"data": {"port": 1883}}).encode()
    fake_response = MagicMock()
    fake_response.read.return_value = payload
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=fake_response):
        assert _get_mqtt_from_supervisor() is None


def test_get_mqtt_from_env_reads_all_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.addon_main import _get_mqtt_from_env

    monkeypatch.setenv("MQTT_HOST", "broker.local")
    monkeypatch.setenv("MQTT_PORT", "8883")
    monkeypatch.setenv("MQTT_USERNAME", "alice")
    monkeypatch.setenv("MQTT_PASSWORD", "s3cret")

    assert _get_mqtt_from_env() == {
        "host": "broker.local",
        "port": 8883,
        "username": "alice",
        "password": "s3cret",
    }


def test_get_mqtt_from_env_returns_none_without_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.addon_main import _get_mqtt_from_env

    monkeypatch.delenv("MQTT_HOST", raising=False)

    assert _get_mqtt_from_env() is None


def test_get_mqtt_from_env_defaults_port_on_bad_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.addon_main import _get_mqtt_from_env

    monkeypatch.setenv("MQTT_HOST", "broker.local")
    monkeypatch.setenv("MQTT_PORT", "not-a-number")
    monkeypatch.delenv("MQTT_USERNAME", raising=False)
    monkeypatch.delenv("MQTT_PASSWORD", raising=False)

    creds = _get_mqtt_from_env()
    assert creds is not None
    assert creds["port"] == 1883
    assert creds["username"] is None
    assert creds["password"] is None


def test_main_mqtt_mode_publishes_discovery_and_state(
    clean_supervisor_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src import addon_main

    # Stub config: mqtt mode, two kwh levels.
    monkeypatch.setattr(
        addon_main,
        "read_addon_config",
        lambda: {
            "mode": "mqtt",
            "log_level": "info",
            "scan_interval": 86400,
            "kwh_levels": [200, 300],
            "mqtt_topic_prefix": "meralco",
            "mqtt_discovery_prefix": "homeassistant",
        },
    )

    # Stub Supervisor: return creds.
    monkeypatch.setattr(
        addon_main,
        "_get_mqtt_from_supervisor",
        lambda: {
            "host": "core-mosquitto",
            "port": 1883,
            "username": "u",
            "password": "p",
        },
    )

    # Stub the rate fetcher to return one cycle of data, then signal stop.
    rate_payload = {
        "success": True,
        "data": [
            {
                "kwh": 200,
                "rate": 13.8,
                "rate_change": 0.6,
                "rate_change_percent": 4.8,
                "trend": "up",
            },
            {
                "kwh": 300,
                "rate": 14.5,
                "rate_change": 0.5,
                "rate_change_percent": 3.4,
                "trend": "up",
            },
        ],
    }
    monkeypatch.setattr(addon_main, "get_meralco_rates", lambda: rate_payload)

    # Stub the bridge so we can introspect calls.
    bridge = MagicMock()
    bridge.connect.return_value = True
    monkeypatch.setattr(addon_main, "MeralcoMQTTBridge", lambda **kwargs: bridge)

    # Run one iteration only: the first wait() trips the stop event and returns.
    original_wait = addon_main._stop_event.wait

    def fake_wait(timeout: float | None = None) -> bool:
        addon_main._stop_event.set()
        return original_wait(0)

    monkeypatch.setattr(addon_main._stop_event, "wait", fake_wait)
    addon_main._stop_event.clear()

    addon_main.main()

    bridge.connect.assert_called_once()
    bridge.publish_online.assert_called_once()
    bridge.publish_discovery.assert_called_once()
    bridge.publish_state.assert_called_once()
    state_arg = bridge.publish_state.call_args.args[0]
    assert state_arg[200]["rate"] == 13.8
    assert state_arg[300]["rate"] == 14.5


def test_main_rest_mode_execs_gunicorn(
    clean_supervisor_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src import addon_main

    monkeypatch.setattr(
        addon_main,
        "read_addon_config",
        lambda: {
            "mode": "rest",
            "log_level": "info",
            "scan_interval": 86400,
            "kwh_levels": [200],
            "mqtt_topic_prefix": "meralco",
            "mqtt_discovery_prefix": "homeassistant",
        },
    )

    captured: dict[str, str | list[str]] = {}

    def fake_execvp(file: str, args: list[str]) -> None:
        captured["file"] = file
        captured["args"] = args

    monkeypatch.setattr("os.execvp", fake_execvp)

    addon_main.main()

    assert captured["file"] == "gunicorn"
    assert captured["args"] == [
        "gunicorn",
        "--bind",
        "0.0.0.0:5000",
        "--workers",
        "1",
        "--timeout",
        "120",
        "src.api:app",
    ]


def test_main_mqtt_mode_exits_when_no_broker_credentials(
    clean_supervisor_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src import addon_main

    monkeypatch.setattr(
        addon_main,
        "read_addon_config",
        lambda: {
            "mode": "mqtt",
            "log_level": "info",
            "scan_interval": 86400,
            "kwh_levels": [200],
            "mqtt_topic_prefix": "meralco",
            "mqtt_discovery_prefix": "homeassistant",
        },
    )
    monkeypatch.setattr(addon_main, "_get_mqtt_from_supervisor", lambda: None)
    # Ensure env vars are clean (clean_supervisor_env handles SUPERVISOR_TOKEN
    # but not the MQTT_* fallback set).
    for key in ("MQTT_HOST", "MQTT_PORT", "MQTT_USERNAME", "MQTT_PASSWORD"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        addon_main.main()

    assert excinfo.value.code == 2


def test_main_mqtt_mode_exits_when_kwh_levels_empty(
    clean_supervisor_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src import addon_main

    monkeypatch.setattr(
        addon_main,
        "read_addon_config",
        lambda: {
            "mode": "mqtt",
            "log_level": "info",
            "scan_interval": 86400,
            "kwh_levels": [],
            "mqtt_topic_prefix": "meralco",
            "mqtt_discovery_prefix": "homeassistant",
        },
    )

    with pytest.raises(SystemExit) as excinfo:
        addon_main.main()

    assert excinfo.value.code == 2
