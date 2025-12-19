from __future__ import annotations

import logging
from typing import Any

from .hass import device_slug, sensor_entities
from .models import Device

DISCOVERY_PREFIX = "homeassistant"
logger = logging.getLogger(__name__)


def _device_info(device: Device) -> dict[str, Any]:
    return {
        "identifiers": [device.device],
        "name": device.name,
        "manufacturer": "Govee",
        "model": device.sku,
    }


def light_discovery_payload(
    device: Device, base_topic: str, effects: list[str] | None = None
) -> tuple[str, dict[str, Any]]:
    slug = device_slug(device)
    object_id = f"{slug}_light"
    topic = f"{DISCOVERY_PREFIX}/light/{object_id}/config"
    state_topic = f"{base_topic}/{slug}/light/state"
    command_topic = f"{base_topic}/{slug}/light/set"
    payload: dict[str, Any] = {
        "name": device.name,
        "unique_id": f"govee2mqtt_v2_{slug}_light",
        "schema": "json",
        "command_topic": command_topic,
        "state_topic": state_topic,
        "brightness": True,
        "rgb": True,
        "color_temp": True,
        "device": _device_info(device),
    }
    if effects:
        payload["effect"] = True
        payload["effect_list"] = effects
    logger.debug("Discovery light: %s -> %s", device.name, topic)
    return topic, payload


def switch_discovery_payload(device: Device, base_topic: str) -> tuple[str, dict[str, Any]]:
    slug = device_slug(device)
    object_id = f"{slug}_switch"
    topic = f"{DISCOVERY_PREFIX}/switch/{object_id}/config"
    state_topic = f"{base_topic}/{slug}/switch/state"
    command_topic = f"{base_topic}/{slug}/switch/set"
    payload: dict[str, Any] = {
        "name": device.name,
        "unique_id": f"govee2mqtt_v2_{slug}_switch",
        "state_topic": state_topic,
        "command_topic": command_topic,
        "device": _device_info(device),
    }
    logger.debug("Discovery switch: %s -> %s", device.name, topic)
    return topic, payload


def sensor_discovery_payloads(device: Device, base_topic: str) -> list[tuple[str, dict[str, Any]]]:
    slug = device_slug(device)
    base_state_topic = f"{base_topic}/{slug}/sensor/state"
    payloads: list[tuple[str, dict[str, Any]]] = []
    for entity in sensor_entities(device):
        instance = entity["instance"]
        object_id = f"{slug}_{instance}"
        if entity.get("binary"):
            topic = f"{DISCOVERY_PREFIX}/binary_sensor/{object_id}/config"
            payload = {
                "name": f"{device.name} {instance}",
                "unique_id": f"govee2mqtt_v2_{slug}_{instance}",
                "state_topic": base_state_topic,
                "value_template": f"{{{{ value_json.{instance} }}}}",
                "device_class": entity["device_class"],
                "device": _device_info(device),
            }
        else:
            topic = f"{DISCOVERY_PREFIX}/sensor/{object_id}/config"
            payload = {
                "name": f"{device.name} {instance}",
                "unique_id": f"govee2mqtt_v2_{slug}_{instance}",
                "state_topic": base_state_topic,
                "value_template": f"{{{{ value_json.{instance} }}}}",
                "device_class": entity["device_class"],
                "unit_of_measurement": entity["unit"],
                "device": _device_info(device),
            }
        payloads.append((topic, payload))
        logger.debug("Discovery sensor: %s %s -> %s", device.name, instance, topic)
    return payloads


def capability_discovery_payloads(
    device: Device, base_topic: str, entities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    slug = device_slug(device)
    payloads: list[dict[str, Any]] = []
    for entity in entities:
        instance = entity["instance"]
        entity_type = entity["entity_type"]
        object_id = f"{slug}_cap_{instance}"
        state_topic = f"{base_topic}/{slug}/cap_{instance}/state"
        command_topic = f"{base_topic}/{slug}/cap_{instance}/set"
        attributes_topic = f"{base_topic}/{slug}/cap_{instance}/attributes"

        topic = f"{DISCOVERY_PREFIX}/{entity_type}/{object_id}/config"
        payload: dict[str, Any] = {
            "name": f"{device.name} {instance}",
            "unique_id": f"govee2mqtt_v2_{slug}_cap_{instance}",
            "object_id": object_id,
            "state_topic": state_topic,
            "command_topic": command_topic,
            "json_attributes_topic": attributes_topic,
            "device": _device_info(device),
        }

        if entity_type == "switch":
            payload["payload_on"] = "ON"
            payload["payload_off"] = "OFF"
        elif entity_type == "number":
            if entity.get("min") is not None:
                payload["min"] = entity["min"]
            if entity.get("max") is not None:
                payload["max"] = entity["max"]
            payload["step"] = entity.get("step", 1)
            if entity.get("unit"):
                payload["unit_of_measurement"] = entity["unit"]
            payload["mode"] = "box"
        elif entity_type == "select":
            payload["options"] = entity.get("options", [])
        elif entity_type == "text":
            payload["mode"] = "text"

        payloads.append(
            {
                "topic": topic,
                "payload": payload,
                "attributes_topic": attributes_topic,
                "attributes_payload": {
                    "capability_type": entity["capability_type"],
                    "parameters": entity.get("parameters", {}),
                },
            }
        )
        logger.debug("Discovery %s: %s -> %s", entity_type, instance, topic)

    return payloads
