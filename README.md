# Docker Network Collector

A Python utility for collecting and monitoring network interface information from Docker containers.

## Why

I found myself wanting to separate out network data from cAdvisor based on the internal Docker network but I could only do that based on the internal container ethernet adapter which I didn't have a way of identifying reliably which belonged to which Docker network.  So this collector bridges that gap by providing a mapping between containers, networks, and interfaces.

## Description

Docker Network Collector inspects Docker containers and their network interfaces, providing information such as:

- Container names
- Network names
- Ethernet interface names
- IP addresses
- MAC addresses

The tool can operate in three modes:

- Local output (default): Prints JSON to stdout
- Prometheus exporter: Exposes metrics for Prometheus scraping
- InfluxDB exporter: Writes metrics to an InfluxDB instance (untested)

## Installation

### Local

1. Clone this repository
2. Install the required dependencies:

```bash
# For all script capabilities
pip install -r requirements.txt
# Minimum requirement
pip install docker
# For Prometheus mode:
pip install prometheus_client
# For InfluxDB mode:
pip install influxdb-client
```

### Docker Compose

#### Prometheus Mode Example

```yaml
services:
  docker-network-collector:
    container_name: docker-network-collector
    build: .
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - COLLECTOR_MODE=prometheus
      - PROMETHEUS_PORT=9090
      - NETWORKS=external dev util media
    # Expose if you want access from the host
    # ports:
    #   - 9090:9090
    restart: unless-stopped
```

#### InfluxDB Mode Example

```yaml
services:
  docker-network-collector:
    container_name: docker-network-collector
    build: .
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment: 
      - COLLECTOR_MODE=influxdb
      - NETWORKS=bridge host custom_network
      - INFLUXDB_URL=http://influxdb:8086
      - INFLUXDB_TOKEN=your_token_here
      - INFLUXDB_ORG=your_org
      - INFLUXDB_BUCKET=docker_metrics
    restart: unless-stopped
```

## Usage

### Basic Usage

```bash
# Inspect default networks (bridge and host)
./docker_network_collector.py

# Inspect specific networks
./docker_network_collector.py --networks network1 network2
```

### Prometheus Exporter Mode

```bash
# Run as Prometheus exporter on port 9090
./docker_network_collector.py --prometheus 9090
```

### InfluxDB Exporter Mode

```bash
# Set required environment variables
export INFLUXDB_URL="http://localhost:8086"
export INFLUXDB_TOKEN="your-token"
export INFLUXDB_ORG="your-org"
export INFLUXDB_BUCKET="your-bucket"

# Run as InfluxDB exporter
./docker_network_collector.py --influxdb
```

## Prometheus

### Config

```yaml
scrape_configs:
  - job_name: 'docker_network_interfaces'
    static_configs:
      - targets: ['network-collector-prometheus:9090']
```

### Queries

```promql
# Get all stats
container_network_interface

# Get info for a specific container on a specific network
container_network_interface{container_name="$container", network_name="$network"}

# Get count of containers grouped by network
count(container_network_interface) by (network_name)
```

## Output Format

### Local Mode (JSON)

```json
{
  "container_name": {
    "network_name": {
      "eth_interface": "eth0",
      "ip_address": "172.17.0.2",
      "mac_address": "02:42:ac:11:00:02"
    }
  }
}
```

where `container_name` is the name of the container and `network_name` is the name of the network. If the container belongs to more than one of the queried networks then there will be an entry for each of those networks for the container.

### Prometheus Metrics

```
# HELP container_network_interface Container network interface information
# TYPE container_network_interface gauge
container_network_interface{container_name="container1",network_name="bridge",eth_interface="eth0",ip_address="172.17.0.2",mac_address="02:42:ac:11:00:02"} 1.0
```

## Environment Variables

When using InfluxDB mode, the following environment variables are required:

- `INFLUXDB_URL`: InfluxDB server URL (default: http://localhost:8086)
- `INFLUXDB_TOKEN`: Authentication token
- `INFLUXDB_ORG`: Organization name
- `INFLUXDB_BUCKET`: Bucket name

## Requirements

- Python 3.6+
- Docker Engine
- Docker SDK for Python
- Optional: prometheus_client (for Prometheus mode)
- Optional: influxdb-client (for InfluxDB mode)

