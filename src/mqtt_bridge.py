"""
MERALCO MQTT Bridge

Connects to an MQTT broker and publishes MERALCO electricity rate sensors
via Home Assistant MQTT discovery. One device, four sensors per kWh level
in `kwh_levels`. The 200 kWh "typical" baseline is always exposed unsuffixed
(meralco_rate, meralco_rate_change, etc.) so its entity IDs stay stable when
users add or remove other levels.
"""

import json
import logging
import time
from typing import TypedDict

import paho.mqtt.client as mqtt
from paho.mqtt.client import Client, ConnectFlags, DisconnectFlags, MQTTMessage
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from src import __version__

logger = logging.getLogger(__name__)

DEVICE_ID = "meralco_ph"
DEVICE_NAME = "MERALCO Electricity Rates"

# 200 kWh is the "typical household" baseline and is always exposed unsuffixed
# so its entity IDs stay stable when users add/remove other levels.
TYPICAL_KWH = 200


class RateStateEntry(TypedDict):
    rate: float | None
    rate_change: float | None
    rate_change_percent: float | None
    trend: str | None


class SensorKind(TypedDict):
    suffix: str
    name: str
    unit: str | None
    device_class: str | None
    state_class: str | None
    icon: str
    value_template: str
    precision: int | None


SENSOR_KINDS: list[SensorKind] = [
    {
        "suffix": "rate",
        "name": "Rate",
        "unit": "PHP/kWh",
        "device_class": "monetary",
        "state_class": "measurement",
        "icon": "mdi:flash",
        "value_template": "{{ value_json.rate }}",
        "precision": 4,
    },
    {
        "suffix": "rate_change",
        "name": "Rate Change",
        "unit": "PHP/kWh",
        "device_class": None,
        "state_class": None,
        "icon": "mdi:delta",
        "value_template": "{{ value_json.rate_change }}",
        "precision": 4,
    },
    {
        "suffix": "rate_change_percent",
        "name": "Rate Change Percent",
        "unit": "%",
        "device_class": None,
        "state_class": None,
        "icon": "mdi:percent",
        "value_template": "{{ value_json.rate_change_percent }}",
        "precision": 2,
    },
    {
        "suffix": "trend",
        "name": "Rate Trend",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:trending-up",
        "value_template": "{{ value_json.trend }}",
        "precision": None,
    },
]


class MeralcoMQTTBridge:
    """Manages an MQTT connection and HA discovery for MERALCO rate sensors."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        topic_prefix: str = "meralco",
        discovery_prefix: str = "homeassistant",
        kwh_levels: list[int] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.topic_prefix = topic_prefix
        self.discovery_prefix = discovery_prefix
        self.kwh_levels = list(kwh_levels or [])

        self._connected = False
        self._client = mqtt.Client(
            client_id=f"meralco-ph-{int(time.time())}",
            callback_api_version=CallbackAPIVersion.VERSION2,
        )
        if username and password:
            self._client.username_pw_set(username, password)

        self._availability_topic = f"{topic_prefix}/status"
        self._client.will_set(
            self._availability_topic, payload="offline", qos=1, retain=True
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._ha_status_topic = f"{discovery_prefix}/status"

    def _device_block(self) -> dict[str, object]:
        return {
            "identifiers": [DEVICE_ID],
            "name": DEVICE_NAME,
            "manufacturer": "MERALCO PH",
            "model": "Rate Scraper",
            "sw_version": __version__,
        }

    def _unique_id(self, kwh: int, kind_suffix: str) -> str:
        """Build a unique ID. 200 kWh is unsuffixed; everything else carries _<kwh>kwh."""
        if kwh == TYPICAL_KWH:
            return f"meralco_{kind_suffix}"
        return f"meralco_{kind_suffix}_{kwh}kwh"

    def _state_topic(self, kwh: int) -> str:
        if kwh == TYPICAL_KWH:
            return f"{self.topic_prefix}/state"
        return f"{self.topic_prefix}/state/{kwh}"

    def _discovery_topic(self, kwh: int, kind_suffix: str) -> str:
        return (
            f"{self.discovery_prefix}/sensor/{self._unique_id(kwh, kind_suffix)}/config"
        )

    def _sensor_friendly_name(self, kwh: int, kind_name: str) -> str:
        if kwh == TYPICAL_KWH:
            return kind_name
        return f"{kind_name} ({kwh} kWh)"

    def _build_discovery_payload(self, kwh: int, kind: SensorKind) -> dict[str, object]:
        unique_id = self._unique_id(kwh, kind["suffix"])
        payload: dict[str, object] = {
            "name": self._sensor_friendly_name(kwh, kind["name"]),
            "unique_id": unique_id,
            "object_id": unique_id,
            "state_topic": self._state_topic(kwh),
            "value_template": kind["value_template"],
            "availability_topic": self._availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": self._device_block(),
            "icon": kind["icon"],
        }
        if kind["unit"] is not None:
            payload["unit_of_measurement"] = kind["unit"]
        if kind["device_class"] is not None:
            payload["device_class"] = kind["device_class"]
        if kind["state_class"] is not None:
            payload["state_class"] = kind["state_class"]
        if kind["precision"] is not None:
            payload["suggested_display_precision"] = kind["precision"]
        return payload

    def publish_discovery(self) -> None:
        for kwh in self.kwh_levels:
            for kind in SENSOR_KINDS:
                topic = self._discovery_topic(kwh, kind["suffix"])
                payload = self._build_discovery_payload(kwh, kind)
                self._client.publish(topic, json.dumps(payload), qos=1, retain=True)

    def publish_state(self, rate_data: dict[int, RateStateEntry]) -> None:
        """Publish one JSON payload per configured kWh level present in rate_data."""
        for kwh in self.kwh_levels:
            entry = rate_data.get(kwh)
            if entry is None:
                logger.debug("No rate data for kwh=%s, skipping", kwh)
                continue
            payload = json.dumps(entry)
            self._client.publish(self._state_topic(kwh), payload, qos=1, retain=True)

    def publish_online(self) -> None:
        self._client.publish(self._availability_topic, "online", qos=1, retain=True)

    def publish_offline(self) -> None:
        self._client.publish(self._availability_topic, "offline", qos=1, retain=True)

    def _on_connect(
        self,
        client: Client,
        userdata: None,
        connect_flags: ConnectFlags,
        reason_code: ReasonCode,
        properties: Properties | None = None,
    ) -> None:
        if reason_code == 0:
            logger.info("Connected to MQTT broker at %s:%s", self.host, self.port)
            self._connected = True
            self._client.subscribe(self._ha_status_topic, qos=1)
        else:
            logger.error("MQTT connect failed with reason_code=%s", reason_code)
            self._connected = False

    def _on_disconnect(
        self,
        client: Client,
        userdata: None,
        disconnect_flags: DisconnectFlags,
        reason_code: ReasonCode,
        properties: Properties | None = None,
    ) -> None:
        logger.warning("Disconnected from MQTT broker (reason_code=%s)", reason_code)
        self._connected = False

    def _on_message(
        self,
        client: Client,
        userdata: None,
        message: MQTTMessage,
    ) -> None:
        if message.topic == self._ha_status_topic:
            payload = message.payload.decode("utf-8", errors="replace")
            if payload == "online":
                logger.info("Home Assistant came online, re-publishing discovery")
                self.publish_discovery()

    def connect(self, timeout: int = 30) -> bool:
        retries = 3
        for attempt in range(1, retries + 1):
            try:
                logger.info(
                    "Connecting to MQTT broker %s:%s (attempt %d/%d)",
                    self.host,
                    self.port,
                    attempt,
                    retries,
                )
                self._client.connect(self.host, self.port, keepalive=60)
                self._client.loop_start()

                deadline = time.time() + timeout
                while not self._connected and time.time() < deadline:
                    time.sleep(0.1)

                if self._connected:
                    return True

                logger.warning("Connect attempt %d timed out", attempt)
                self._client.loop_stop()
            except Exception as exc:  # noqa: BLE001
                logger.error("Connect attempt %d failed: %s", attempt, exc)
                try:
                    self._client.loop_stop()
                except Exception:  # noqa: BLE001
                    pass

            if attempt < retries:
                time.sleep(5)

        return False

    def disconnect(self) -> None:
        try:
            self.publish_offline()
            self._client.loop_stop()
            self._client.disconnect()
        except Exception as exc:  # noqa: BLE001
            logger.error("Error during MQTT disconnect: %s", exc)
        finally:
            self._connected = False
