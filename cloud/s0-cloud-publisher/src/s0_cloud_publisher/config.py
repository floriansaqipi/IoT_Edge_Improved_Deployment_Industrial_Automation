from __future__ import annotations

import os
from dataclasses import dataclass, field

from opcua_collector.config import DEFAULT_NAMESPACE_URI, DEFAULT_OPCUA_ENDPOINT, CollectorConfig


@dataclass(frozen=True)
class S0PublisherConfig:
    opcua_endpoint: str = DEFAULT_OPCUA_ENDPOINT
    namespace_uri: str = DEFAULT_NAMESPACE_URI
    iothub_device_connection_string: str = field(repr=False, default="")
    cloud_output_policy: str = "full"
    sample_every: int = 10
    cloud_max_messages_per_second: int | None = 90
    send_worker_count: int = 32
    send_queue_maxsize: int = 10000
    experiment_id_fallback: str = "phase5_s0"
    scenario_fallback: str = "S0_CLOUD_ONLY"
    run_id_fallback: str = "phase5_s0_rep1"
    experiment_id_override: str | None = None
    scenario_override: str | None = "S0_CLOUD_ONLY"
    run_id_override: str | None = None
    reconnect_seconds: float = 5.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "S0PublisherConfig":
        endpoint = os.getenv("OPCUA_ENDPOINT", DEFAULT_OPCUA_ENDPOINT).strip()
        if not endpoint.startswith("opc.tcp://"):
            raise ValueError("OPCUA_ENDPOINT must start with opc.tcp://.")

        connection_string = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING", "").strip()
        if not connection_string:
            raise ValueError("IOTHUB_DEVICE_CONNECTION_STRING is required.")

        max_mps_raw = os.getenv("CLOUD_MAX_MESSAGES_PER_SECOND", "90").strip()
        max_mps = int(max_mps_raw) if max_mps_raw else None

        return cls(
            opcua_endpoint=endpoint,
            namespace_uri=os.getenv("OPCUA_NAMESPACE_URI", DEFAULT_NAMESPACE_URI).strip() or DEFAULT_NAMESPACE_URI,
            iothub_device_connection_string=connection_string,
            cloud_output_policy=os.getenv("CLOUD_OUTPUT_POLICY", "full").strip().lower() or "full",
            sample_every=_positive_int(os.getenv("SAMPLE_EVERY", "10"), "SAMPLE_EVERY"),
            cloud_max_messages_per_second=max_mps,
            send_worker_count=_positive_int(os.getenv("SEND_WORKER_COUNT", "32"), "SEND_WORKER_COUNT"),
            send_queue_maxsize=_positive_int(os.getenv("SEND_QUEUE_MAXSIZE", "10000"), "SEND_QUEUE_MAXSIZE"),
            experiment_id_fallback=os.getenv("EXPERIMENT_ID_FALLBACK", "phase5_s0").strip() or "phase5_s0",
            scenario_fallback=os.getenv("SCENARIO_FALLBACK", "S0_CLOUD_ONLY").strip() or "S0_CLOUD_ONLY",
            run_id_fallback=os.getenv("RUN_ID_FALLBACK", "phase5_s0_rep1").strip() or "phase5_s0_rep1",
            experiment_id_override=_optional_env("EXPERIMENT_ID_OVERRIDE"),
            scenario_override=_optional_env("SCENARIO_OVERRIDE", default="S0_CLOUD_ONLY"),
            run_id_override=_optional_env("RUN_ID_OVERRIDE"),
            reconnect_seconds=_positive_float(os.getenv("RECONNECT_SECONDS", "5"), "RECONNECT_SECONDS"),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )

    def to_collector_config(self) -> CollectorConfig:
        return CollectorConfig(
            opcua_endpoint=self.opcua_endpoint,
            namespace_uri=self.namespace_uri,
            output_name="telemetry",
            experiment_id_fallback=self.experiment_id_fallback,
            scenario_fallback=self.scenario_fallback,
            run_id_fallback=self.run_id_fallback,
            experiment_id_override=self.experiment_id_override,
            scenario_override=self.scenario_override,
            run_id_override=self.run_id_override,
            reconnect_seconds=self.reconnect_seconds,
            output_mode="stdout",
            local_output_path=None,
            log_level=self.log_level,
        )


def _optional_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or None


def _positive_int(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def _positive_float(raw: str, name: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value
