# UI Build Stage
FROM node:24 AS ui-build

# Add Caldera
ADD https://github.com/apache/caldera.git /app

# Remove git submodule folders
RUN rm -rf /app/plugins/*

# Add desired plugins
ADD https://github.com/mitre/magma.git /app/plugins/magma
ADD https://github.com/mitre/manx.git /app/plugins/manx
ADD https://github.com/mitre/fieldmanual.git /app/plugins/fieldmanual
ADD https://github.com/mitre/stockpile.git /app/plugins/stockpile
ADD https://github.com/mitre/sandcat.git /app/plugins/sandcat
ADD https://github.com/mitre/modbus.git /app/plugins/modbus
ADD https://github.com/mitre/bacnet.git /app/plugins/bacnet

# Build VueJS front-end
WORKDIR /app/plugins/magma
RUN npm install --omit=dev --loglevel verbose && \
    npm run build

# Payload Build Stage
FROM golang:1.25-bookworm AS payload-build

RUN apt update; \
    apt install -y --no-install-recommends \
    git \
    cmake \
    build-essential

COPY --from=ui-build /app /app

# Update sandcat agents
RUN cd /app/plugins/sandcat/gocat; \
    go mod tidy; \
    go mod download; \
    go build; \
    cd /app/plugins/sandcat; \
    ./update-agents.sh; \
    cp /app/plugins/sandcat/gocat/gocat /app/plugins/sandcat/payloads/sandcat

# Runtime stage
FROM python:3.13-slim-bookworm AS runtime

# Set timezone (default to UTC)
ARG TZ="UTC"
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

COPY --from=payload-build /app /app

# Install pip requirements, ignoring lxml
RUN sed -i '/^lxml.*/d' /app/requirements.txt; \
    pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt;

# Default HTTP port for web interface and agent beacons over HTTP
EXPOSE 8888

# Default HTTPS port for web interface and agent beacons over HTTPS (requires SSL plugin to be enabled)
# EXPOSE 8443

STOPSIGNAL SIGINT

ADD entrypoint.sh .
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
