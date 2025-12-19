#!/usr/bin/with-contenv bashio

wait_for_mqtt() {
  local max_attempts=30
  local attempt=1

  bashio::log.info "Waiting for MQTT service..."

  while [ $attempt -le $max_attempts ]; do
    if bashio::services.available mqtt ; then
      if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$(bashio::services mqtt host)/$(bashio::services mqtt port)" 2>/dev/null; then
        bashio::log.info "MQTT broker is ready"
        return 0
      fi
    fi

    bashio::log.info "MQTT broker not ready yet (attempt ${attempt}/${max_attempts}), waiting 2 seconds..."
    sleep 2
    attempt=$((attempt + 1))
  done

  bashio::log.error "MQTT broker did not become available after ${max_attempts} attempts"
  return 1
}

if ! bashio::config.has_value govee_api_key ; then
  bashio::exit.nok "govee_api_key is required"
fi

export GOVEE_API_KEY="$(bashio::config 'govee_api_key')"

if ! wait_for_mqtt ; then
  bashio::exit.nok "MQTT broker is not available"
fi
export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USERNAME="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"

export MQTT_BASE_TOPIC="$(bashio::config 'mqtt_base_topic')"
export POLL_INTERVAL_SECONDS="$(bashio::config 'poll_interval_seconds')"
export LOG_LEVEL="$(bashio::config 'log_level')"

exec govee2mqtt-v2
