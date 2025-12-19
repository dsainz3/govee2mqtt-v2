ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.0.0
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8

WORKDIR /app

COPY app/pyproject.toml /app/pyproject.toml
COPY app/README.md /app/README.md
COPY app/src /app/src

RUN apk add --no-cache python3 py3-pip \
    && pip install --no-cache-dir .

COPY run.sh /etc/services.d/govee2mqtt/run
RUN chmod +x /etc/services.d/govee2mqtt/run

ENTRYPOINT ["/init"]
