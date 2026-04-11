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
