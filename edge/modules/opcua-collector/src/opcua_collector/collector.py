from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from asyncua import Client

from .config import CollectorConfig
from .opcua_mapping import (
    EXPERIMENT_NODE_NAMES,
    METADATA_NODE_NAMES,
    VALUE_NODE_NAMES,
    device_name_to_id,
    device_sort_key,
    device_type_from_name,
    experiment_node_string_id,
    is_known_device_name,
    node_id_text,
    node_string_id,
    value_keys_for_device_name,
)


logger = logging.getLogger(__name__)
RECONNECT_SIGNAL = "__opcua_reconnect__"
ALLOWED_CLOUD_POLICIES = {"full", "sampled_10_percent", "capped"}


class TelemetrySender(Protocol):
    async def send(self, message: dict[str, Any]) -> None:
        """Send one telemetry message."""


class SequenceSubscriptionHandler:
    def __init__(self, device_by_sequence_node: dict[str, str], queue: asyncio.Queue[str]) -> None:
        self.device_by_sequence_node = device_by_sequence_node
        self.queue = queue

    def datachange_notification(self, node: Any, value: Any, data: Any) -> None:
        _ = data
        device_name = self.device_by_sequence_node.get(_node_identifier(node))
        if device_name is None or _as_int(value) <= 0:
            return
        self.queue.put_nowait(device_name)

    def status_change_notification(self, status: Any) -> None:
        logger.warning("OPC UA subscription status changed: %s", status)
        self.queue.put_nowait(RECONNECT_SIGNAL)


class OpcUaSnapshotReader:
    def __init__(self, config: CollectorConfig) -> None:
        self.config = config
        self.client = Client(url=config.opcua_endpoint)
        self.namespace_index: int | None = None
        self.experiment_metadata: dict[str, str] = {}

    async def __aenter__(self) -> "OpcUaSnapshotReader":
        await self.client.connect()
        self.namespace_index = await self.client.get_namespace_index(self.config.namespace_uri)
        self.experiment_metadata = await self.read_experiment_metadata()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.client.disconnect()

    async def discover_devices(self) -> list[str]:
        line = self._node("Factory.Line1")
        children = await line.get_children()
        device_names: list[str] = []
        for child in children:
            browse_name = await child.read_browse_name()
            if is_known_device_name(browse_name.Name):
                device_names.append(browse_name.Name)
        return sorted(device_names, key=device_sort_key)

    async def read_experiment_metadata(self) -> dict[str, str]:
        fallback = {
            "ExperimentId": self.config.experiment_id_fallback,
            "Scenario": self.config.scenario_fallback,
            "RunId": self.config.run_id_fallback,
        }
        metadata: dict[str, str] = {}
        for node_name in EXPERIMENT_NODE_NAMES:
            raw_value = await self._read_optional(experiment_node_string_id(node_name))
            value = str(raw_value).strip() if raw_value is not None else ""
            metadata[node_name] = value or fallback[node_name]
        if self.config.experiment_id_override is not None:
            metadata["ExperimentId"] = self.config.experiment_id_override
        if self.config.scenario_override is not None:
            metadata["Scenario"] = self.config.scenario_override
        if self.config.run_id_override is not None:
            metadata["RunId"] = self.config.run_id_override
        return metadata

    async def subscribe_sequence_changes(
        self,
        device_names: list[str],
        queue: asyncio.Queue[str],
        period_ms: int = 100,
    ) -> Any:
        device_by_sequence_node = {
            node_string_id(device_name, "Sequence"): device_name for device_name in device_names
        }
        handler = SequenceSubscriptionHandler(device_by_sequence_node, queue)
        subscription = await self.client.create_subscription(period_ms, handler)
        sequence_nodes = [self._node(node_string_id(device_name, "Sequence")) for device_name in device_names]
        await subscription.subscribe_data_change(sequence_nodes)
        return subscription

    async def read_snapshot(self, device_name: str) -> dict[str, Any]:
        device_type = device_type_from_name(device_name)
        metadata_nodes = {node_name: self._node(node_string_id(device_name, node_name)) for node_name in METADATA_NODE_NAMES}
        value_nodes = {
            key: self._node(node_string_id(device_name, VALUE_NODE_NAMES[key]))
            for key in value_keys_for_device_name(device_name)
        }

        metadata_values, values = await _read_node_groups(self.client, metadata_nodes, value_nodes)

        anomaly_type = str(metadata_values.get("AnomalyType") or "").strip()
        device_id = str(metadata_values.get("DeviceId") or device_name_to_id(device_name))
        device_type_value = str(metadata_values.get("DeviceType") or device_type)

        return {
            "experimentId": self.experiment_metadata.get("ExperimentId", self.config.experiment_id_fallback),
            "scenario": self.experiment_metadata.get("Scenario", self.config.scenario_fallback),
            "runId": self.experiment_metadata.get("RunId", self.config.run_id_fallback),
            "deviceId": device_id,
            "deviceType": device_type_value,
            "sequence": _as_int(metadata_values.get("Sequence")),
            "sensorTimestamp": str(metadata_values.get("SensorTimestamp") or ""),
            "edgeReceivedTimestamp": _utc_now(),
            "normalizedTimestamp": None,
            "filteredTimestamp": None,
            "anomalyTimestamp": None,
            "cloudReceivedTimestamp": None,
            "values": values,
            "groundTruth": {
                "isAnomaly": _as_bool(metadata_values.get("IsAnomaly")),
                "anomalyType": anomaly_type or None,
            },
        }

    def _node(self, string_id: str) -> Any:
        if self.namespace_index is None:
            raise RuntimeError("OPC UA namespace index is not initialized.")
        return self.client.get_node(node_id_text(self.namespace_index, string_id))

    async def _read_optional(self, string_id: str) -> Any | None:
        try:
            return await self._node(string_id).read_value()
        except Exception:
            logger.debug("Optional OPC UA node is not available: %s", string_id, exc_info=True)
            return None


async def collect_forever(config: CollectorConfig, sender: TelemetrySender) -> None:
    last_sequence_by_device: dict[str, int] = {}
    limiter = _CloudOutputLimiter(
        policy=config.cloud_output_policy,
        sample_every=config.sample_every,
        max_messages_per_second=config.cloud_max_messages_per_second,
    )
    started_at = time.monotonic()

    while True:
        try:
            logger.info("Connecting to OPC UA endpoint %s", config.opcua_endpoint)
            async with OpcUaSnapshotReader(config) as reader:
                device_names = await reader.discover_devices()
                if not device_names:
                    raise RuntimeError("No Factory/Line1 device objects were discovered.")

                logger.info("Discovered %d OPC UA devices", len(device_names))
                queue: asyncio.Queue[str] = asyncio.Queue()
                subscription = await reader.subscribe_sequence_changes(device_names, queue)
                try:
                    while True:
                        device_name = await queue.get()
                        if device_name == RECONNECT_SIGNAL:
                            raise ConnectionError("OPC UA subscription status changed; reconnecting.")
                        message = await reader.read_snapshot(device_name)
                        sequence = int(message["sequence"])
                        if sequence <= 0:
                            continue
                        device_id = str(message["deviceId"])
                        if last_sequence_by_device.get(device_id) == sequence:
                            continue
                        last_sequence_by_device[device_id] = sequence
                        elapsed = time.monotonic() - started_at
                        if not limiter.should_forward(message, elapsed):
                            continue
                        await sender.send(message)
                finally:
                    await subscription.delete()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Collector loop failed. Reconnecting in %.1f seconds.",
                config.reconnect_seconds,
            )
            await asyncio.sleep(config.reconnect_seconds)


async def _read_node_groups(
    client: Client,
    metadata_nodes: dict[str, Any],
    value_nodes: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata_keys = list(metadata_nodes)
    value_keys = list(value_nodes)
    nodes = [metadata_nodes[key] for key in metadata_keys]
    nodes.extend(value_nodes[key] for key in value_keys)
    raw_values = await client.read_values(nodes)
    metadata_end = len(metadata_keys)
    metadata_values = dict(zip(metadata_keys, raw_values[:metadata_end], strict=True))
    values = dict(zip(value_keys, raw_values[metadata_end:], strict=True))
    return metadata_values, values


class _CloudOutputLimiter:
    def __init__(
        self,
        policy: str,
        sample_every: int = 10,
        max_messages_per_second: int | None = None,
    ) -> None:
        if policy not in ALLOWED_CLOUD_POLICIES:
            raise ValueError(f"Unsupported cloud output policy: {policy}.")
        if sample_every <= 0:
            raise ValueError("sample_every must be greater than zero.")
        if max_messages_per_second is not None and max_messages_per_second <= 0:
            raise ValueError("max_messages_per_second must be greater than zero.")
        self.policy = policy
        self.sample_every = sample_every
        self.max_messages_per_second = max_messages_per_second
        self._window_second: int | None = None
        self._sent_in_window = 0

    def should_forward(self, message: dict[str, Any], elapsed_seconds: float) -> bool:
        if self.policy == "full":
            return self._under_rate_cap(elapsed_seconds)
        if self.policy == "sampled_10_percent":
            sequence = _as_int(message.get("sequence"))
            return sequence > 0 and sequence % self.sample_every == 0 and self._under_rate_cap(elapsed_seconds)
        return self._under_rate_cap(elapsed_seconds)

    def _under_rate_cap(self, elapsed_seconds: float) -> bool:
        if self.max_messages_per_second is None:
            return True
        current_window = int(max(elapsed_seconds, 0.0))
        if self._window_second != current_window:
            self._window_second = current_window
            self._sent_in_window = 0
        if self._sent_in_window >= self.max_messages_per_second:
            return False
        self._sent_in_window += 1
        return True


def _node_identifier(node: Any) -> str:
    node_id = getattr(node, "nodeid", None)
    identifier = getattr(node_id, "Identifier", None)
    if identifier is None:
        return str(node_id)
    return str(identifier)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
