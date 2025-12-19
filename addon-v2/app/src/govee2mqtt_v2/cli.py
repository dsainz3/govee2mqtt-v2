from __future__ import annotations

import argparse
import json
import logging
import queue
import time
from typing import Any

import httpx

from .api import GoveeApiClient
from .config import load_config
from .discovery import (
    capability_discovery_payloads,
    light_discovery_payload,
    sensor_discovery_payloads,
    switch_discovery_payload,
)
from .hass import (
    capability_entities,
    device_slug,
    is_light,
    is_switch,
    light_command_to_capabilities,
    light_state_from_device_state,
    sensor_entities,
    sensor_state_from_device_state,
    switch_command_to_capabilities,
    switch_state_from_device_state,
)
from .mqtt_client import MqttClient

logger = logging.getLogger(__name__)


def _state_supported(device) -> bool:
    if not device.capabilities:
        return False
    if device.device_type:
        device_type = device.device_type.lower()
        if "group" in device_type or "scene" in device_type:
            return False
    if device.sku and not device.sku.upper().startswith("H"):
        return False
    return True


def _merge_scene_options(device, scene_caps: list) -> None:
    for scene_cap in scene_caps:
        scene_params = scene_cap.parameters or {}
        options = scene_params.get("options") or []
        if not options:
            continue
        for base_cap in device.capabilities:
            if base_cap.type == scene_cap.type and base_cap.instance == scene_cap.instance:
                for key, value in scene_params.items():
                    base_cap.parameters.setdefault(key, value)
                base_cap.parameters["options"] = options


def _build_capability_maps(devices: list) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    capability_map: dict[str, dict[str, Any]] = {}
    capability_options: dict[str, Any] = {}
    for device in devices:
        exclude: set[tuple[str, str]] = set()
        if is_light(device):
            exclude.update(
                {
                    ("devices.capabilities.on_off", "powerSwitch"),
                    ("devices.capabilities.range", "brightness"),
                    ("devices.capabilities.color_setting", "colorRgb"),
                    ("devices.capabilities.color_setting", "colorTemperatureK"),
                }
            )
        elif is_switch(device):
            exclude.add(("devices.capabilities.on_off", "powerSwitch"))

        sensor_instances = {entity["instance"] for entity in sensor_entities(device)}
        for cap in device.capabilities:
            if cap.instance in sensor_instances:
                exclude.add((cap.type, cap.instance))

        entities = capability_entities(device, exclude=exclude)
        logger.debug("Capability entities for %s: %d", device.name, len(entities))
        capability_map[device.device] = {entity["instance"]: entity for entity in entities}
        option_map: dict[str, Any] = {}
        for entity in entities:
            if entity["entity_type"] != "select":
                continue
            name_to_value = {}
            value_to_name = {}
            for opt in entity.get("option_values", []):
                name = opt.get("name")
                value = opt.get("value")
                if name is None:
                    continue
                name_to_value[name] = value
                value_to_name[json.dumps(value, sort_keys=True)] = name
            option_map[entity["instance"]] = {
                "name_to_value": name_to_value,
                "value_to_name": value_to_name,
            }
        capability_options[device.device] = option_map
    return capability_map, capability_options


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Log level set to %s", level.lower())


def _print_dry_run(devices: list) -> None:
    for device in devices:
        slug = device_slug(device)
        print(f"{device.name} ({device.sku}) [{slug}]")
        if is_light(device):
            print("  - light")
        elif is_switch(device):
            print("  - switch")
        for entity in sensor_entities(device):
            kind = "binary_sensor" if entity.get("binary") else "sensor"
            print(f"  - {kind}: {entity['instance']}")


def _publish_discovery(
    mqtt: MqttClient,
    base_topic: str,
    devices: list,
    capability_map: dict[str, dict[str, Any]],
) -> None:
    for device in devices:
        if is_light(device):
            topic, payload = light_discovery_payload(device, base_topic)
            mqtt.publish_discovery(topic, payload)
        elif is_switch(device):
            topic, payload = switch_discovery_payload(device, base_topic)
            mqtt.publish_discovery(topic, payload)

        for topic, payload in sensor_discovery_payloads(device, base_topic):
            mqtt.publish_discovery(topic, payload)

        for item in capability_discovery_payloads(
            device, base_topic, list(capability_map.get(device.device, {}).values())
        ):
            mqtt.publish_discovery(item["topic"], item["payload"])
            mqtt.publish(item["attributes_topic"], item["attributes_payload"], retain=True)


def _publish_state(
    mqtt: MqttClient,
    base_topic: str,
    device,
    state,
    capability_map: dict[str, dict[str, Any]],
    capability_options: dict[str, Any],
) -> None:
    slug = device_slug(device)
    if is_light(device):
        payload = light_state_from_device_state(state)
        if payload:
            mqtt.publish(f"{base_topic}/{slug}/light/state", payload, retain=True)
    elif is_switch(device):
        value = switch_state_from_device_state(state)
        if value is not None:
            mqtt.publish(f"{base_topic}/{slug}/switch/state", value, retain=True)

    sensor_payload = sensor_state_from_device_state(state)
    if sensor_payload:
        mqtt.publish(f"{base_topic}/{slug}/sensor/state", sensor_payload, retain=True)

    cap_entities = capability_map.get(device.device, {})
    if not cap_entities:
        return

    options_map = capability_options.get(device.device, {})
    for cap in state.capabilities:
        entity = cap_entities.get(cap.instance)
        if not entity:
            continue
        topic = f"{base_topic}/{slug}/cap_{cap.instance}/state"
        value = cap.state_value
        if value is None:
            continue

        entity_type = entity["entity_type"]
        if entity_type == "switch":
            payload = "ON" if value else "OFF"
        elif entity_type == "number":
            payload = value
        elif entity_type == "select":
            value_key = json.dumps(value, sort_keys=True)
            payload = options_map.get(cap.instance, {}).get("value_to_name", {}).get(value_key)
            if payload is None:
                payload = str(value)
        elif entity_type == "text":
            payload = json.dumps(value) if isinstance(value, dict | list) else str(value)
        else:
            continue

        mqtt.publish(topic, payload, retain=True)


def _handle_command(
    api: GoveeApiClient,
    mqtt: MqttClient,
    base_topic: str,
    device_map: dict[str, Any],
    capability_map: dict[str, dict[str, Any]],
    capability_options: dict[str, Any],
    command: tuple[str, str, str],
) -> None:
    device_id, entity, payload = command
    device = device_map.get(device_id)
    if not device:
        logger.warning("Received command for unknown device %s", device_id)
        return

    if entity == "light":
        try:
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            logger.warning("Invalid JSON payload for light command: %s", payload)
            return
        logger.debug("Handling light command for %s: %s", device_id, data)
        for cap_type, instance, value in light_command_to_capabilities(data):
            try:
                api.control_device(device, capability_type=cap_type, instance=instance, value=value)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Light command failed for %s (%s): %s",
                    device.name,
                    device.sku,
                    exc.response.status_code,
                )
    elif entity == "switch":
        logger.debug("Handling switch command for %s: %s", device_id, payload)
        for cap_type, instance, value in switch_command_to_capabilities(payload):
            try:
                api.control_device(device, capability_type=cap_type, instance=instance, value=value)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Switch command failed for %s (%s): %s",
                    device.name,
                    device.sku,
                    exc.response.status_code,
                )
    elif entity.startswith("cap_"):
        instance = entity.removeprefix("cap_")
        cap_entities = capability_map.get(device.device, {})
        cap_entity = cap_entities.get(instance)
        if not cap_entity:
            logger.warning("Unknown capability instance %s for %s", instance, device.name)
            return

        entity_type = cap_entity["entity_type"]
        value: Any
        if entity_type == "switch":
            value = 1 if payload.strip().upper() == "ON" else 0
        elif entity_type == "number":
            try:
                value = int(payload)
            except ValueError:
                value = float(payload)
        elif entity_type == "select":
            options = capability_options.get(device.device, {}).get(instance, {})
            value = options.get("name_to_value", {}).get(payload)
            if value is None:
                logger.warning("Unknown option '%s' for %s", payload, instance)
                return
        elif entity_type == "text":
            try:
                value = json.loads(payload)
            except json.JSONDecodeError:
                value = payload
        else:
            logger.warning("Unsupported entity type %s for %s", entity_type, instance)
            return

        try:
            api.control_device(
                device,
                capability_type=cap_entity["capability_type"],
                instance=instance,
                value=value,
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Capability command failed for %s (%s): %s",
                device.name,
                device.sku,
                exc.response.status_code,
            )
    else:
        logger.debug("Unsupported command entity: %s", entity)
        return

    try:
        state = api.get_device_state(device)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "State refresh failed for %s (%s): %s",
            device.name,
            device.sku,
            exc.response.status_code,
        )
        logger.debug("State refresh error body for %s: %s", device.device, exc.response.text)
        return
    _publish_state(mqtt, base_topic, device, state, capability_map, capability_options)


def main() -> int:
    parser = argparse.ArgumentParser(description="Govee Platform API v2 to MQTT bridge")
    parser.add_argument("--dry-run", action="store_true", help="Print discovered devices and exit")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args()

    config = load_config(dry_run=args.dry_run)
    _setup_logging(config.log_level)
    logger.info(
        "Starting govee2mqtt-v2 dry_run=%s poll_interval=%ss mqtt_base=%s",
        args.dry_run,
        config.poll_interval_seconds,
        config.mqtt_base_topic,
    )

    api = GoveeApiClient(config.govee_api_key, base_url=config.api_base_url)
    try:
        devices = api.list_devices()
    except Exception:
        api.close()
        raise

    for device in devices:
        has_scene = any(
            cap.type
            in (
                "devices.capabilities.dynamic_scene",
                "devices.capabilities.dynamic_setting",
                "devices.capabilities.mode",
            )
            for cap in device.capabilities
        )
        if not has_scene:
            continue
        try:
            _merge_scene_options(device, api.get_device_scenes(device))
        except httpx.HTTPStatusError as exc:
            logger.debug("Scene fetch failed for %s: %s", device.name, exc.response.status_code)
        try:
            _merge_scene_options(device, api.get_device_diy_scenes(device))
        except httpx.HTTPStatusError as exc:
            logger.debug("DIY scene fetch failed for %s: %s", device.name, exc.response.status_code)

    capability_map, capability_options = _build_capability_maps(devices)
    total_caps = sum(len(items) for items in capability_map.values())
    if total_caps:
        logger.info(
            "Prepared %d capability entities across %d devices",
            total_caps,
            len(devices),
        )
    else:
        logger.warning("No capability entities discovered; check device capabilities/dataType")

    if args.dry_run:
        _print_dry_run(devices)
        api.close()
        return 0

    if not config.mqtt_host:
        raise ValueError("MQTT_HOST is required when not in --dry-run mode")

    mqtt = MqttClient(
        host=config.mqtt_host,
        port=config.mqtt_port,
        username=config.mqtt_username,
        password=config.mqtt_password,
        base_topic=config.mqtt_base_topic,
    )

    command_queue: queue.Queue[tuple[str, str, str]] = queue.Queue()

    def _enqueue_command(device_id: str, entity: str, payload: str) -> None:
        command_queue.put((device_id, entity, payload))

    mqtt.set_command_handler(_enqueue_command)
    mqtt.connect()

    device_map = {device_slug(device): device for device in devices}
    unsupported_state_devices: set[str] = set()
    for device in devices:
        if not _state_supported(device):
            unsupported_state_devices.add(device.device)
            logger.debug("Skipping state polling for %s (%s)", device.name, device.sku)
    logger.info("Discovered %d devices", len(devices))
    _publish_discovery(mqtt, config.mqtt_base_topic, devices, capability_map)

    try:
        while True:
            cycle_start = time.monotonic()
            for device in devices:
                while not command_queue.empty():
                    _handle_command(
                        api,
                        mqtt,
                        config.mqtt_base_topic,
                        device_map,
                        capability_map,
                        capability_options,
                        command_queue.get(),
                    )

                if device.device in unsupported_state_devices:
                    continue

                try:
                    state = api.get_device_state(device)
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "State fetch failed for %s (%s): %s",
                        device.name,
                        device.sku,
                        exc.response.status_code,
                    )
                    logger.debug("State error body for %s: %s", device.device, exc.response.text)
                    if exc.response.status_code == 400:
                        unsupported_state_devices.add(device.device)
                        logger.info(
                            "Skipping future state polls for %s (%s)",
                            device.name,
                            device.sku,
                        )
                    continue
                _publish_state(
                    mqtt,
                    config.mqtt_base_topic,
                    device,
                    state,
                    capability_map,
                    capability_options,
                )

                time.sleep(max(1.0, config.poll_interval_seconds / max(1, len(devices))))

            if args.once:
                break

            elapsed = time.monotonic() - cycle_start
            sleep_time = max(0.0, config.poll_interval_seconds - elapsed)
            if sleep_time:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        mqtt.disconnect()
        api.close()

    return 0
