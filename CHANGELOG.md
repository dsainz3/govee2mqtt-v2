# Changelog

All notable changes to the Python v2 implementation and HAOS add-on are
documented here. This changelog is required to be updated for every change.

## 0.1.14

- Add hands-off GitHub Actions automation for syncing, version bumps, CI, releases, and GHCR images.
- Add local automation scripts and set pre-commit automation hooks to manual stage.

## 0.1.12

- Set `object_id` for capability entities so entity IDs include `cap_<instance>` for easy search.

## 0.1.11

- Default unknown capability data types to text entities so every capability is exposed.
- Log a summary count of capability entities discovered at startup.

## 0.1.10

- Publish capability entities for additional controls beyond base light/switch/sensor mappings.
- Expand capability handling for boolean/string/numeric data types and better scene metadata merging.
- Serialize structured capability state values as JSON for MQTT consumers.

## 0.1.9

- Add generic capability entities (select/number/switch/text) for all device capabilities.
- Load scene and DIY scene options from the Platform API and expose them in discovery.

## 0.1.8

- Default MQTT base topic to `govee2mqtt_v2` for side-by-side testing with v1.
- Remove MQTT host/user/password options from the add-on; always auto-detect broker.

## 0.1.7

- Wrap Platform API v2 control/state requests with requestId/payload to fix 400 responses.

## 0.1.6

- Skip state polling for group/scene-like devices and those that return HTTP 400.
- Log HTTP 400 response bodies at debug for easier API troubleshooting.

## 0.1.5

- Allow HAOS add-on to auto-detect MQTT service when `mqtt_host` is unset.
- Guard device state polling against HTTP 400 responses so one device does not crash the loop.
- Enforce changelog updates via pre-commit hook.

## 0.1.4

- Fix HAOS add-on init handling to avoid s6 PID1 errors.
- Vendor Python app sources into `addon-v2/app` for add-on builds.
- Add debug logging across API, MQTT, discovery, and command handling.

## 0.1.2

- Initial Python v2 scaffold, discovery, and polling loop.
- Add HAOS add-on scaffolding and Docker build.
