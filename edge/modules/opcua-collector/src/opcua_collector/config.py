from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OPCUA_ENDPOINT = "opc.tcp://192.168.1.5:4840/factory/server"
DEFAULT_NAMESPACE_URI = "urn:industrial-automation:azure-iot-edge-study"


@dataclass(frozen=True)
class CollectorConfig:
    opcua_endpoint: str = DEFAULT_OPCUA_ENDPOINT
    namespace_uri: str = DEFAULT_NAMESPACE_URI
    output_name: str = "telemetry"
    experiment_id_fallback: str = "phase3_s1"
    scenario_fallback: str = "S1_EDGE_PASS_THROUGH"
    run_id_fallback: str = "phase3_s1_rep1"
    experiment_id_override: str | None = None
    scenario_override: str | None = None
    run_id_override: str | None = None
    cloud_output_policy: str = "full"
    sample_every: int = 10
    cloud_max_messages_per_second: int | None = None
    reconnect_seconds: float = 5.0
    output_mode: str = "edgehub"
    local_output_path: Path | None = None
    send_worker_count: int = 16
    send_queue_maxsize: int = 10000
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "CollectorConfig":
        output_mode = os.getenv("COLLECTOR_OUTPUT_MODE", "edgehub").strip().lower()
        if output_mode not in {"edgehub", "stdout", "jsonl"}:
            raise ValueError("COLLECTOR_OUTPUT_MODE must be one of: edgehub, stdout, jsonl.")

        reconnect_seconds = _positive_float(os.getenv("RECONNECT_SECONDS", "5"), "RECONNECT_SECONDS")
        local_output_raw = os.getenv("LOCAL_OUTPUT_PATH")
        local_output_path = Path(local_output_raw) if local_output_raw else None
        if output_mode == "jsonl" and local_output_path is None:
            raise ValueError("LOCAL_OUTPUT_PATH is required when COLLECTOR_OUTPUT_MODE=jsonl.")

        endpoint = os.getenv("OPCUA_ENDPOINT", DEFAULT_OPCUA_ENDPOINT).strip()
        if not endpoint.startswith("opc.tcp://"):
            raise ValueError("OPCUA_ENDPOINT must start with opc.tcp://.")

        namespace_uri = os.getenv("OPCUA_NAMESPACE_URI", DEFAULT_NAMESPACE_URI).strip()
        if not namespace_uri:
            raise ValueError("OPCUA_NAMESPACE_URI must be non-empty.")

        max_mps_raw = os.getenv("CLOUD_MAX_MESSAGES_PER_SECOND", "").strip()
        max_mps = int(max_mps_raw) if max_mps_raw else None

        return cls(
            opcua_endpoint=endpoint,
            namespace_uri=namespace_uri,
            output_name=os.getenv("OUTPUT_NAME", "telemetry").strip() or "telemetry",
            experiment_id_fallback=os.getenv("EXPERIMENT_ID_FALLBACK", "phase3_s1").strip() or "phase3_s1",
            scenario_fallback=os.getenv("SCENARIO_FALLBACK", "S1_EDGE_PASS_THROUGH").strip()
            or "S1_EDGE_PASS_THROUGH",
            run_id_fallback=os.getenv("RUN_ID_FALLBACK", "phase3_s1_rep1").strip() or "phase3_s1_rep1",
            experiment_id_override=_optional_env("EXPERIMENT_ID_OVERRIDE"),
            scenario_override=_optional_env("SCENARIO_OVERRIDE"),
            run_id_override=_optional_env("RUN_ID_OVERRIDE"),
            cloud_output_policy=os.getenv("CLOUD_OUTPUT_POLICY", "full").strip().lower() or "full",
            sample_every=_positive_int(os.getenv("SAMPLE_EVERY", "10"), "SAMPLE_EVERY"),
            cloud_max_messages_per_second=max_mps,
            reconnect_seconds=reconnect_seconds,
            output_mode=output_mode,
            local_output_path=local_output_path,
            send_worker_count=_positive_int(os.getenv("SEND_WORKER_COUNT", "16"), "SEND_WORKER_COUNT"),
            send_queue_maxsize=_positive_int(os.getenv("SEND_QUEUE_MAXSIZE", "10000"), "SEND_QUEUE_MAXSIZE"),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )


def _positive_float(raw: str, name: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def _positive_int(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
