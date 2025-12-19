from govee2mqtt_v2.discovery import (
    capability_discovery_payloads,
    light_discovery_payload,
    sensor_discovery_payloads,
)
from govee2mqtt_v2.hass import capability_entities
from govee2mqtt_v2.models import Capability, Device


def _cap(cap_type: str, instance: str) -> Capability:
    return Capability(type=cap_type, instance=instance)


def test_light_discovery_payload_rgb() -> None:
    device = Device(
        sku="H6072",
        device="AA:BB:CC:DD:AA:BB:CC:DD",
        name="Floor Lamp",
        device_type="devices.types.light",
        capabilities=[
            _cap("devices.capabilities.on_off", "powerSwitch"),
            _cap("devices.capabilities.range", "brightness"),
            _cap("devices.capabilities.color_setting", "colorRgb"),
            _cap("devices.capabilities.color_setting", "colorTemperatureK"),
        ],
    )
    topic, payload = light_discovery_payload(device, "govee2mqtt")
    assert topic.endswith("/config")
    assert payload["schema"] == "json"
    assert payload["brightness"] is True
    assert payload["rgb"] is True
    assert payload["color_temp"] is True


def test_sensor_discovery_payload_temp_humidity() -> None:
    device = Device(
        sku="H7143",
        device="11:22:33:44:55:66:77:88",
        name="Air Monitor",
        device_type="devices.types.sensor",
        capabilities=[
            _cap("devices.capabilities.range", "temperature"),
            _cap("devices.capabilities.range", "humidity"),
        ],
    )
    payloads = sensor_discovery_payloads(device, "govee2mqtt")
    assert len(payloads) == 2
    topics = [topic for topic, _ in payloads]
    assert any("sensor" in topic for topic in topics)


def test_capability_discovery_payloads() -> None:
    device = Device(
        sku="H6072",
        device="AA:BB:CC:DD:AA:BB:CC:DD",
        name="Floor Lamp",
        device_type="devices.types.light",
        capabilities=[
            Capability(
                type="devices.capabilities.toggle",
                instance="gradientToggle",
                parameters={"dataType": "ENUM"},
            ),
            Capability(
                type="devices.capabilities.range",
                instance="brightness",
                parameters={"dataType": "INTEGER", "range": {"min": 1, "max": 100, "precision": 1}},
            ),
            Capability(
                type="devices.capabilities.dynamic_scene",
                instance="lightScene",
                parameters={
                    "dataType": "ENUM",
                    "options": [{"name": "Sunrise", "value": {"id": 1}}],
                },
            ),
            Capability(
                type="devices.capabilities.music_setting",
                instance="musicMode",
                parameters={"dataType": "STRUCT", "fields": []},
            ),
        ],
    )
    entities = capability_entities(device)
    payloads = capability_discovery_payloads(device, "govee2mqtt_v2", entities)
    topics = [item["topic"] for item in payloads]
    assert any("/switch/" in topic for topic in topics)
    assert any("/number/" in topic for topic in topics)
    assert any("/select/" in topic for topic in topics)
    assert any("/text/" in topic for topic in topics)
    assert all(item["payload"].get("object_id") for item in payloads)


def test_capability_entities_unknown_datatype_defaults_to_text() -> None:
    device = Device(
        sku="H0001",
        device="AA:BB:CC:DD:EE:FF:00:11",
        name="Test Device",
        device_type="devices.types.other",
        capabilities=[
            Capability(
                type="devices.capabilities.work_mode",
                instance="workMode",
                parameters={},
            )
        ],
    )
    entities = capability_entities(device)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "text"
