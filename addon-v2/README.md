# Govee2MQTT v2 (Python) Add-on

Engineering notes for the optional Home Assistant add-on wrapper.

## Purpose

- Package the Python implementation for HAOS/Supervised installs.
- Map add-on options to environment variables consumed by `govee2mqtt-v2`.

## Options Mapping

- `govee_api_key` -> `GOVEE_API_KEY`
- `mqtt_base_topic` -> `MQTT_BASE_TOPIC`
- `poll_interval_seconds` -> `POLL_INTERVAL_SECONDS`
- `log_level` -> `LOG_LEVEL`

## Runtime

- `addon-v2/run.sh` reads config via `bashio` and auto-detects the MQTT service.
- The container builds from the Python `Dockerfile` contents for parity with standalone usage.
