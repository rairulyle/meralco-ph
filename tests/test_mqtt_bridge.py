"""Tests for the MERALCO MQTT bridge."""

import json
from typing import cast
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


def _publish_calls_by_topic(client: MagicMock) -> dict[str, dict[str, object]]:
    """Decode all retained config publishes into a topic-keyed dict."""
    out: dict[str, dict[str, object]] = {}
    for call in client.publish.call_args_list:
        topic = call.args[0]
        if not topic.endswith("/config"):
            continue
        out[topic] = json.loads(call.args[1])
    return out


def test_rate_sensor_discovery_payload_has_expected_fields_unsuffixed(
    mock_client: MagicMock,
) -> None:
    """200 kWh sensor uses unsuffixed unique_id and state topic."""
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])
    bridge.publish_discovery()

    payloads = _publish_calls_by_topic(mock_client)
    payload = payloads["homeassistant/sensor/meralco_rate/config"]

    assert payload["unique_id"] == "meralco_rate"
    assert payload["state_topic"] == "meralco/state"
    assert payload["unit_of_measurement"] == "PHP/kWh"
    assert payload["device_class"] == "monetary"
    assert payload["state_class"] == "measurement"
    assert payload["value_template"] == "{{ value_json.rate }}"
    assert payload["suggested_display_precision"] == 4
    assert cast(dict[str, object], payload["device"])["identifiers"] == ["meralco_ph"]
    assert payload["availability_topic"] == "meralco/status"
    assert payload["name"] == "Rate"  # no "(200 kWh)" suffix on the friendly name


def test_rate_sensor_discovery_payload_for_non_typical_level(
    mock_client: MagicMock,
) -> None:
    """Non-200 levels use suffixed unique_id and state topic."""
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[300])
    bridge.publish_discovery()

    payloads = _publish_calls_by_topic(mock_client)
    payload = payloads["homeassistant/sensor/meralco_rate_300kwh/config"]

    assert payload["unique_id"] == "meralco_rate_300kwh"
    assert payload["state_topic"] == "meralco/state/300"
    assert payload["name"] == "Rate (300 kWh)"


def test_trend_sensor_omits_unit_and_device_class(
    mock_client: MagicMock,
) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])
    bridge.publish_discovery()

    payloads = _publish_calls_by_topic(mock_client)
    payload = payloads["homeassistant/sensor/meralco_trend/config"]

    assert "unit_of_measurement" not in payload
    assert "device_class" not in payload
    assert "state_class" not in payload
    assert payload["value_template"] == "{{ value_json.trend }}"


def _state_publish_calls(client: MagicMock) -> dict[str, dict[str, object]]:
    """Decode every publish whose topic looks like a state topic."""
    out: dict[str, dict[str, object]] = {}
    for call in client.publish.call_args_list:
        topic = call.args[0]
        if topic.endswith("/config"):
            continue
        if not (topic == "meralco/state" or topic.startswith("meralco/state/")):
            continue
        out[topic] = json.loads(call.args[1])
    return out


def test_publish_state_writes_one_payload_per_kwh(mock_client: MagicMock) -> None:
    """200 publishes to meralco/state, 300 publishes to meralco/state/300."""
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200, 300])

    rate_data: dict[int, dict[str, object]] = {
        200: {
            "rate": 13.8161,
            "rate_change": 0.6427,
            "rate_change_percent": 4.88,
            "trend": "up",
        },
        300: {
            "rate": 14.5,
            "rate_change": 0.5,
            "rate_change_percent": 3.5,
            "trend": "up",
        },
    }
    bridge.publish_state(rate_data)

    state_calls = _state_publish_calls(mock_client)

    assert state_calls["meralco/state"]["rate"] == 13.8161
    assert state_calls["meralco/state"]["trend"] == "up"
    assert state_calls["meralco/state/300"]["rate"] == 14.5


def test_publish_state_skips_levels_not_in_data(mock_client: MagicMock) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200, 300])
    bridge.publish_state(
        {
            200: {
                "rate": 13.8,
                "rate_change": 0,
                "rate_change_percent": 0,
                "trend": "stable",
            }
        }
    )

    state_calls = _state_publish_calls(mock_client)
    assert "meralco/state" in state_calls
    assert "meralco/state/300" not in state_calls


def test_publish_online_writes_to_availability_topic(mock_client: MagicMock) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])
    bridge.publish_online()

    mock_client.publish.assert_any_call("meralco/status", "online", qos=1, retain=True)


def test_publish_offline_writes_to_availability_topic(mock_client: MagicMock) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])
    bridge.publish_offline()

    mock_client.publish.assert_any_call("meralco/status", "offline", qos=1, retain=True)


def test_will_set_uses_availability_topic(mock_client: MagicMock) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])

    mock_client.will_set.assert_called_once_with(
        "meralco/status", payload="offline", qos=1, retain=True
    )


def test_connect_calls_paho_connect_and_loop_start(mock_client: MagicMock) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    # Simulate the on_connect callback firing immediately by flipping the flag.
    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])
    bridge._connected = True  # pretend the broker accepted us

    result = bridge.connect(timeout=1)

    assert result is True
    mock_client.connect.assert_called_once_with("broker.local", 1883, keepalive=60)
    mock_client.loop_start.assert_called_once()


def test_connect_returns_false_after_retries_when_never_connected(
    mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    monkeypatch.setattr("time.sleep", lambda _: None)

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])
    # _connected stays False; broker never sends on_connect.

    result = bridge.connect(timeout=0)

    assert result is False
    assert mock_client.connect.call_count == 3  # 3 retries


def test_on_connect_subscribes_to_ha_status_topic(mock_client: MagicMock) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])
    bridge._on_connect(mock_client, None, {}, 0, None)

    mock_client.subscribe.assert_called_once_with("homeassistant/status", qos=1)
    assert bridge._connected is True


def test_on_message_homeassistant_online_republishes_discovery(
    mock_client: MagicMock,
) -> None:
    from src.mqtt_bridge import MeralcoMQTTBridge

    bridge = MeralcoMQTTBridge(host="broker.local", kwh_levels=[200])

    msg = MagicMock()
    msg.topic = "homeassistant/status"
    msg.payload = b"online"

    mock_client.publish.reset_mock()
    bridge._on_message(mock_client, None, msg)

    discovery_calls = [
        c for c in mock_client.publish.call_args_list if "/config" in c.args[0]
    ]
    assert len(discovery_calls) == 4  # 1 kwh × 4 sensor kinds
