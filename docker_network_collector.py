#!/usr/bin/env python3

import docker
import argparse
import json
from typing import List, Dict
import sys
import os
import time


class DockerNetworkCollector:
    def __init__(self, network_names: List[str]):
        self.network_names = network_names
        self.client = docker.from_env()
        self.mode = "local"
        self.prometheus_port = None
        self.influx_config = None

    def get_container_network_interfaces(self) -> Dict:
        """Get internal ethernet interfaces for containers in specified networks."""
        container_interfaces = {}

        try:
            containers = self.client.containers.list()

            for container in containers:
                container_info = container.attrs
                networks_info = container_info.get("NetworkSettings", {}).get(
                    "Networks", {}
                )

                relevant_networks = {
                    net_name: net_info
                    for net_name, net_info in networks_info.items()
                    if net_name in self.network_names
                }

                if relevant_networks:
                    container_interfaces[container.name] = {
                        net_name: {
                            "eth_interface": f"eth{idx}",
                            "ip_address": net_info.get("IPAddress"),
                            "mac_address": net_info.get("MacAddress"),
                        }
                        for idx, (net_name, net_info) in enumerate(
                            relevant_networks.items()
                        )
                    }

        except docker.errors.APIError as e:
            print(f"Error accessing Docker API: {e}")
            return {}

        return container_interfaces

    def run_prometheus_exporter(self):
        """Run as a Prometheus exporter."""
        try:
            from prometheus_client import start_http_server, Gauge

            container_network_info = Gauge(
                'container_network_interface',
                'Container network interface information',
                ['container_name', 'network_name', 'eth_interface', 'ip_address',
                 'mac_address']
            )

            start_http_server(self.prometheus_port)
            print(f"Prometheus exporter started on port {self.prometheus_port}")

            while True:
                container_network_info._metrics.clear()
                interfaces = self.get_container_network_interfaces()

                for container_name, networks in interfaces.items():
                    for network_name, network_info in networks.items():
                        container_network_info.labels(
                            container_name=container_name,
                            network_name=network_name,
                            eth_interface=network_info["eth_interface"],
                            ip_address=network_info["ip_address"],
                            mac_address=network_info["mac_address"]
                        ).set(1)

                time.sleep(15)

        except ImportError:
            print("Error: prometheus_client package is required for exporter mode.")
            print("Please install it using: pip install prometheus_client")
            sys.exit(1)

    def run_influxdb_exporter(self):
        """Run as an InfluxDB exporter."""
        try:
            from influxdb_client import InfluxDBClient, Point
            from influxdb_client.client.write_api import SYNCHRONOUS

            client = InfluxDBClient(
                url=self.influx_config["url"],
                token=self.influx_config["token"],
                org=self.influx_config["org"]
            )
            write_api = client.write_api(write_options=SYNCHRONOUS)

            print(f"InfluxDB exporter started, writing to {self.influx_config['url']}")

            while True:
                interfaces = self.get_container_network_interfaces()

                for container_name, networks in interfaces.items():
                    for network_name, network_info in networks.items():
                        point = (
                            Point("container_network_interface")
                            .tag("container_name", container_name)
                            .tag("network_name", network_name)
                            .tag("eth_interface", network_info["eth_interface"])
                            .field("ip_address", network_info["ip_address"])
                            .field("mac_address", network_info["mac_address"])
                        )

                        write_api.write(
                            bucket=self.influx_config["bucket"],
                            org=self.influx_config["org"],
                            record=point
                        )

                time.sleep(15)

        except ImportError:
            print("Error: influxdb-client package is required for InfluxDB mode.")
            print("Please install it using: pip install influxdb-client")
            sys.exit(1)

    def run_local_output(self):
        """Run once and output to stdout."""
        interfaces = self.get_container_network_interfaces()
        if interfaces:
            print(json.dumps(interfaces, indent=2))
        else:
            print("No containers found in the specified networks.")

    def set_mode(self, mode: str, **kwargs):
        """Set the running mode and associated configuration."""
        self.mode = mode
        if mode == "prometheus":
            self.prometheus_port = kwargs.get("port")
        elif mode == "influxdb":
            self.influx_config = kwargs

    def run(self):
        """Run the collector in the configured mode."""
        if self.mode == "prometheus":
            self.run_prometheus_exporter()
        elif self.mode == "influxdb":
            self.run_influxdb_exporter()
        else:
            self.run_local_output()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Docker Network Interface Inspector"
    )
    parser.add_argument(
        "--networks",
        "-n",
        nargs="+",
        default=["bridge", "host"],
        help="List of network names to inspect (default: bridge host)"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--prometheus",
        "-p",
        type=int,
        metavar="PORT",
        help="Run as Prometheus exporter on specified port"
    )
    group.add_argument(
        "--influxdb",
        "-i",
        action="store_true",
        help="Run as InfluxDB exporter (requires environment variables)"
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    collector = DockerNetworkCollector(args.networks)

    if args.prometheus:
        collector.set_mode("prometheus", port=args.prometheus)
    elif args.influxdb:
        # Get InfluxDB configuration from environment variables
        influx_config = {
            "url": os.getenv("INFLUXDB_URL", "http://localhost:8086"),
            "token": os.getenv("INFLUXDB_TOKEN"),
            "org": os.getenv("INFLUXDB_ORG"),
            "bucket": os.getenv("INFLUXDB_BUCKET"),
        }

        # Verify all required variables are set
        missing_vars = [
            k for k, v in influx_config.items() if v is None
        ]
        if missing_vars:
            print(
                f"Error: Missing required environment variables: {', '.join(missing_vars)}"
            )
            sys.exit(1)

        collector.set_mode("influxdb", **influx_config)

    collector.run()


if __name__ == "__main__":
    main()
