"""
Prometheus Metrics Registry for the FullRays Indoor Wireless Twin rApp.
Includes EIAP API, polling, state tracking, and Kafka/message bus metrics.
"""

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    disable_created_metrics,
    generate_latest,
)
from .config import get_config
from .mtls_logging import logger

SERVICE_PREFIX = get_config()["container_name"].replace("-", "_")


def _create_metrics() -> dict[str, Counter | Gauge]:
    return {
        "topology_successful_requests": Counter(
            namespace=SERVICE_PREFIX,
            name="topology_successful_requests",
            documentation="Total successful Topology & Inventory requests",
        ),
        "topology_failed_requests": Counter(
            namespace=SERVICE_PREFIX,
            name="topology_failed_requests",
            documentation="Total failed Topology & Inventory requests",
        ),
        "network_configuration_successful_requests": Counter(
            namespace=SERVICE_PREFIX,
            name="network_configuration_successful_requests",
            documentation="Total successful Network Configuration requests",
        ),
        "network_configuration_failed_requests": Counter(
            namespace=SERVICE_PREFIX,
            name="network_configuration_failed_requests",
            documentation="Total failed Network Configuration requests",
        ),
        "topology_polls_completed": Counter(
            namespace=SERVICE_PREFIX,
            name="topology_polls_completed",
            documentation="Total topology poll cycles completed",
        ),
        "config_polls_completed": Counter(
            namespace=SERVICE_PREFIX,
            name="config_polls_completed",
            documentation="Total configuration poll cycles completed",
        ),
        "state_changes_detected": Counter(
            namespace=SERVICE_PREFIX,
            name="state_changes_detected",
            documentation="Total state change events detected",
        ),
        "cells_monitored": Gauge(
            namespace=SERVICE_PREFIX,
            name="cells_monitored",
            documentation="Current number of cells being monitored",
        ),
        # ─── Kafka / Message Bus Metrics ──────────────────────────
        "messages_consumed": Counter(
            namespace=SERVICE_PREFIX,
            name="messages_consumed",
            documentation="Total messages consumed from Message Bus",
        ),
        "filtered_messages_by_motype": Counter(
            namespace=SERVICE_PREFIX,
            name="filtered_messages_by_motype",
            documentation="Messages filtered by MO Type",
        ),
        "filtered_messages_by_fdn": Counter(
            namespace=SERVICE_PREFIX,
            name="filtered_messages_by_fdn",
            documentation="Messages relevant to collected cells",
        ),
        "complete_batch_of_messages_consumed": Counter(
            namespace=SERVICE_PREFIX,
            name="complete_batch_of_messages_consumed",
            documentation="Total complete batches consumed",
        ),
        "partial_batch_of_messages_consumed": Counter(
            namespace=SERVICE_PREFIX,
            name="partial_batch_of_messages_consumed",
            documentation="Total partially filled batches consumed",
        ),
        "empty_batch_of_messages_consumed": Counter(
            namespace=SERVICE_PREFIX,
            name="empty_batch_of_messages_consumed",
            documentation="Total empty batches consumed",
        ),
        "schema_registry_successful_requests": Counter(
            namespace=SERVICE_PREFIX,
            name="schema_registry_successful_requests",
            documentation="Total successful Schema Registry requests",
        ),
        "schema_registry_failed_requests": Counter(
            namespace=SERVICE_PREFIX,
            name="schema_registry_failed_requests",
            documentation="Total failed Schema Registry requests",
        ),
    }


class MetricsRegistry(CollectorRegistry):
    """Prometheus Client CollectorRegistry with pre-registered counters."""

    def __init__(self):
        super().__init__()
        disable_created_metrics()
        self.counters = _create_metrics()
        self._register_counters()

    def _register_counters(self) -> None:
        for counter in self.counters.values():
            self.register(counter)
        logger.debug(
            f"Created metrics registry in format:\n{generate_latest(self).decode('utf-8')}"
        )

    def _unregister_counters(self) -> None:
        for counter in self.counters.values():
            self.unregister(counter)
        self.counters = {}


metrics_registry = MetricsRegistry()
