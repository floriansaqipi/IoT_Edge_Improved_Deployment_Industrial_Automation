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
    reconnect_seconds: float = 5.0
    output_mode: str = "edgehub"
    local_output_path: Path | None = None
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

        return cls(
            opcua_endpoint=endpoint,
            namespace_uri=namespace_uri,
            output_name=os.getenv("OUTPUT_NAME", "telemetry").strip() or "telemetry",
            experiment_id_fallback=os.getenv("EXPERIMENT_ID_FALLBACK", "phase3_s1").strip() or "phase3_s1",
            scenario_fallback=os.getenv("SCENARIO_FALLBACK", "S1_EDGE_PASS_THROUGH").strip()
            or "S1_EDGE_PASS_THROUGH",
            run_id_fallback=os.getenv("RUN_ID_FALLBACK", "phase3_s1_rep1").strip() or "phase3_s1_rep1",
            reconnect_seconds=reconnect_seconds,
            output_mode=output_mode,
            local_output_path=local_output_path,
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
