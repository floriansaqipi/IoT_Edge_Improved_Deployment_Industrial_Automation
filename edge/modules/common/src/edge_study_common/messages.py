from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


REQUIRED_TELEMETRY_FIELDS = {
    "experimentId",
    "scenario",
    "runId",
    "deviceId",
    "deviceType",
    "sequence",
    "sensorTimestamp",
    "edgeReceivedTimestamp",
    "values",
    "groundTruth",
}

DEVICE_VALUE_KEYS = {
    "motor": {"temperature", "vibration", "rpm", "current", "load", "status"},
    "pump": {"pressure", "flowRate", "temperature", "vibration", "current", "status"},
    "conveyor": {"speed", "load", "motorCurrent", "vibration", "status"},
    "tank": {"level", "pressure", "inletFlow", "outletFlow", "valveState", "status"},
    "compressor": {"pressure", "temperature", "vibration", "current", "status"},
}


@dataclass(frozen=True)
class OutputMessage:
    output_name: str
    payload: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def json_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def decode_message_data(message: Any) -> dict[str, Any]:
    data = getattr(message, "data", message)
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    if isinstance(data, str):
        decoded = json.loads(data)
    elif isinstance(data, dict):
        decoded = data
    else:
        raise ValueError(f"Unsupported message data type: {type(data).__name__}.")
    if not isinstance(decoded, dict):
        raise ValueError("Message body must decode to a JSON object.")
    return decoded


def validate_telemetry(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_TELEMETRY_FIELDS - set(record))
    if missing:
        errors.append(f"missing required field(s): {', '.join(missing)}")

    _require_str(record, "experimentId", errors)
    _require_str(record, "scenario", errors)
    _require_str(record, "runId", errors)
    _require_str(record, "deviceId", errors)
    device_type = _require_str(record, "deviceType", errors)
    _require_int(record, "sequence", errors)
    _require_str(record, "sensorTimestamp", errors)

    values = record.get("values")
    if not isinstance(values, dict):
        errors.append("values must be an object")
    elif device_type in DEVICE_VALUE_KEYS:
        missing_values = sorted(DEVICE_VALUE_KEYS[device_type] - set(values))
        if missing_values:
            errors.append(f"values missing required sensor(s): {', '.join(missing_values)}")
        for key, value in values.items():
            if key in {"status", "valveState"}:
                if not isinstance(value, str):
                    errors.append(f"values.{key} must be a string")
            elif not isinstance(value, (int, float)):
                errors.append(f"values.{key} must be numeric")
    elif device_type:
        errors.append(f"unsupported deviceType: {device_type}")

    ground_truth = record.get("groundTruth")
    if not isinstance(ground_truth, dict):
        errors.append("groundTruth must be an object")
    elif not isinstance(ground_truth.get("isAnomaly"), bool):
        errors.append("groundTruth.isAnomaly must be a boolean")

    return errors


def copy_record(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json_payload(record))


def _require_str(record: dict[str, Any], key: str, errors: list[str]) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key} must be a non-empty string")
        return ""
    return value


def _require_int(record: dict[str, Any], key: str, errors: list[str]) -> int:
    value = record.get(key)
    if not isinstance(value, int):
        errors.append(f"{key} must be an integer")
        return 0
    return value
