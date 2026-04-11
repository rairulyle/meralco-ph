"""Tests for the MERALCO MQTT bridge."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace paho-mqtt's Client with a MagicMock that records publish calls."""
    client = MagicMock()
    client.is_connected.return_value = True

    def _client_factory(*args: object, **kwargs: object) -> MagicMock:
        return client

    monkeypatch.setattr("paho.mqtt.client.Client", _client_factory)
    return client


def test_publish_discovery_200kwh_is_unsuffixed_others_are_suffixed(
    mock_client: MagicMock,
) -> None:
    """200 kWh entries are always unsuffixed; other levels get _<kwh>kwh."""
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(
        host="broker.local",
        port=1883,
        kwh_levels=[200, 300],
    )
    bridge.publish_discovery()

    discovery_topics = [
        call.args[0]
        for call in mock_client.publish.call_args_list
        if "/config" in call.args[0]
    ]

    expected = {
        # 200 kWh: unsuffixed (the "typical" baseline)
        "homeassistant/sensor/meralco_rate/config",
        "homeassistant/sensor/meralco_rate_change/config",
        "homeassistant/sensor/meralco_rate_change_percent/config",
        "homeassistant/sensor/meralco_trend/config",
        # 300 kWh: suffixed
        "homeassistant/sensor/meralco_rate_300kwh/config",
        "homeassistant/sensor/meralco_rate_change_300kwh/config",
        "homeassistant/sensor/meralco_rate_change_percent_300kwh/config",
        "homeassistant/sensor/meralco_trend_300kwh/config",
    }
    assert set(discovery_topics) == expected


def test_publish_discovery_all_suffixed_when_200_not_in_levels(
    mock_client: MagicMock,
) -> None:
    """When 200 kWh is excluded, every level is suffixed normally."""
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[300, 500])
    bridge.publish_discovery()

    discovery_topics = {
        call.args[0]
        for call in mock_client.publish.call_args_list
        if "/config" in call.args[0]
    }

    assert "homeassistant/sensor/meralco_rate_300kwh/config" in discovery_topics
    assert "homeassistant/sensor/meralco_rate_500kwh/config" in discovery_topics
    # And the unsuffixed variant must NOT appear.
    assert "homeassistant/sensor/meralco_rate/config" not in discovery_topics
