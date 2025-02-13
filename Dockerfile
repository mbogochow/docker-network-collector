FROM python:3.9-slim

WORKDIR /app

# Install required packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script
COPY docker_network_collector.py .
RUN chmod +x docker_network_collector.py

# Environment variables with defaults
ENV COLLECTOR_MODE=prometheus
ENV PROMETHEUS_PORT=9090
ENV NETWORKS="bridge host"
ENV INFLUXDB_URL=http://localhost:8086
ENV INFLUXDB_TOKEN=""
ENV INFLUXDB_ORG=""
ENV INFLUXDB_BUCKET=""

# Create entrypoint script
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'if [ "$COLLECTOR_MODE" = "prometheus" ]; then' >> /entrypoint.sh && \
    echo '    exec python /app/docker_network_collector.py -n $NETWORKS -p $PROMETHEUS_PORT' >> /entrypoint.sh && \
    echo 'elif [ "$COLLECTOR_MODE" = "influxdb" ]; then' >> /entrypoint.sh && \
    echo '    exec python /app/docker_network_collector.py -n $NETWORKS -i' >> /entrypoint.sh && \
    echo 'else' >> /entrypoint.sh && \
    echo '    exec python /app/docker_network_collector.py -n $NETWORKS' >> /entrypoint.sh && \
    echo 'fi' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
