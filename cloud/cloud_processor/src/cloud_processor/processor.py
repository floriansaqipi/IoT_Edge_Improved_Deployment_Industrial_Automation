from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from edge_study_common.messages import copy_record, json_payload, utc_now, validate_telemetry

from .detection import detect_anomaly


TELEMETRY_TABLE = "CloudTelemetry"
ALERTS_TABLE = "CloudAlerts"
INVALID_TABLE = "CloudInvalid"
CLOUD_DETECTION_SCENARIOS = {"S0_CLOUD_ONLY", "S1_EDGE_PASS_THROUGH"}


@dataclass(frozen=True)
class TableWrite:
    table_name: str
    entity: dict[str, Any]


@dataclass(frozen=True)
class ProcessedEvent:
    writes: tuple[TableWrite, ...]
    valid: bool
    message_type: str


def process_event_body(
    body: bytes | str | dict[str, Any],
    metadata: dict[str, Any] | None = None,
    cloud_received_timestamp: str | None = None,
) -> ProcessedEvent:
    metadata = metadata or {}
    received_at = cloud_received_timestamp or utc_now()
    try:
        record = _decode_body(body)
    except ValueError as exc:
        invalid = _invalid_entity(str(exc), body, metadata, received_at)
        return ProcessedEvent((TableWrite(INVALID_TABLE, invalid),), False, "invalid")

    if record.get("messageType") == "alert":
        alert = copy_record(record)
        alert["cloudReceivedTimestamp"] = received_at
        return ProcessedEvent(
            (TableWrite(ALERTS_TABLE, _entity_from_record(alert, metadata, received_at, table_hint="alert")),),
            True,
            "alert",
        )

    errors = validate_telemetry(record)
    if errors:
        invalid = _invalid_entity("; ".join(errors), record, metadata, received_at)
        return ProcessedEvent((TableWrite(INVALID_TABLE, invalid),), False, "invalid")

    telemetry = copy_record(record)
    telemetry["cloudReceivedTimestamp"] = received_at
    scenario = str(telemetry.get("scenario", ""))
    if scenario in CLOUD_DETECTION_SCENARIOS:
        telemetry["cloudDetection"] = detect_anomaly(telemetry).as_dict()
    else:
        telemetry.setdefault("cloudDetection", None)

    writes = [TableWrite(TELEMETRY_TABLE, _entity_from_record(telemetry, metadata, received_at))]
    if _is_alert_record(telemetry):
        writes.append(TableWrite(ALERTS_TABLE, _entity_from_record(_alert_from_telemetry(telemetry), metadata, received_at)))
    return ProcessedEvent(tuple(writes), True, "telemetry")


def _decode_body(body: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(body, dict):
        return body
    raw = body.decode("utf-8") if isinstance(body, bytes) else body
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ValueError("message body must be a JSON object")
    return decoded


def _entity_from_record(
    record: dict[str, Any],
    metadata: dict[str, Any],
    cloud_received_timestamp: str,
    table_hint: str = "telemetry",
) -> dict[str, Any]:
    partition_key = _safe_key(
        "|".join(
            [
                str(record.get("experimentId") or "unknown-experiment"),
                str(record.get("scenario") or "unknown-scenario"),
                str(record.get("runId") or "unknown-run"),
            ]
        )
    )
    origin_device = _metadata_value(metadata, "iothub-connection-device-id", "iothubConnectionDeviceId", "originDeviceId")
    origin_module = _metadata_value(metadata, "iothub-connection-module-id", "iothubConnectionModuleId", "originModuleId")
    event_sequence = _metadata_value(metadata, "SequenceNumber", "sequenceNumber", "x-opt-sequence-number", "offset")
    payload_hash = hashlib.sha1(json_payload(record).encode("utf-8")).hexdigest()[:12]
    row_key = _safe_key(
        "|".join(
            [
                table_hint,
                str(origin_device or record.get("deviceId") or "unknown-origin"),
                str(origin_module or "device"),
                str(record.get("deviceId") or "unknown-device"),
                f"{int(record.get('sequence') or 0):012d}",
                str(event_sequence or payload_hash),
            ]
        )
    )

    cloud_detection = record.get("cloudDetection")
    edge_detection = record.get("edgeDetection")
    ground_truth = record.get("groundTruth")
    values = record.get("values")
    entity = {
        "PartitionKey": partition_key,
        "RowKey": row_key,
        "experimentId": str(record.get("experimentId") or ""),
        "scenario": str(record.get("scenario") or ""),
        "runId": str(record.get("runId") or ""),
        "messageType": str(record.get("messageType") or "telemetry"),
        "deviceId": str(record.get("deviceId") or ""),
        "deviceType": str(record.get("deviceType") or ""),
        "sequence": int(record.get("sequence") or 0),
        "sensorTimestamp": _optional_str(record.get("sensorTimestamp")),
        "edgeReceivedTimestamp": _optional_str(record.get("edgeReceivedTimestamp")),
        "directPublisherReceivedTimestamp": _optional_str(record.get("directPublisherReceivedTimestamp")),
        "cloudPublishTimestamp": _optional_str(record.get("cloudPublishTimestamp")),
        "normalizedTimestamp": _optional_str(record.get("normalizedTimestamp")),
        "filteredTimestamp": _optional_str(record.get("filteredTimestamp")),
        "anomalyTimestamp": _optional_str(record.get("anomalyTimestamp")),
        "alertTimestamp": _optional_str(record.get("alertTimestamp")),
        "cloudReceivedTimestamp": cloud_received_timestamp,
        "iotHubEnqueuedTimestamp": _optional_str(
            _metadata_value(metadata, "EnqueuedTimeUtc", "iothub-enqueuedtime", "x-opt-enqueued-time")
        ),
        "originDeviceId": str(origin_device or ""),
        "originModuleId": str(origin_module or ""),
        "valuesJson": _json_or_none(values),
        "groundTruthJson": _json_or_none(ground_truth),
        "edgeDetectionJson": _json_or_none(edge_detection),
        "cloudDetectionJson": _json_or_none(cloud_detection),
        "payloadJson": json_payload(record),
    }
    if isinstance(cloud_detection, dict):
        entity["cloudIsAnomaly"] = bool(cloud_detection.get("isAnomaly"))
        entity["cloudAnomalyType"] = _optional_str(cloud_detection.get("anomalyType"))
    if isinstance(edge_detection, dict):
        entity["edgeIsAnomaly"] = bool(edge_detection.get("isAnomaly"))
        entity["edgeAnomalyType"] = _optional_str(edge_detection.get("anomalyType"))
    return entity


def _alert_from_telemetry(record: dict[str, Any]) -> dict[str, Any]:
    alert = {
        "messageType": "alert",
        "experimentId": record.get("experimentId"),
        "scenario": record.get("scenario"),
        "runId": record.get("runId"),
        "deviceId": record.get("deviceId"),
        "deviceType": record.get("deviceType"),
        "sequence": record.get("sequence"),
        "sensorTimestamp": record.get("sensorTimestamp"),
        "edgeReceivedTimestamp": record.get("edgeReceivedTimestamp"),
        "directPublisherReceivedTimestamp": record.get("directPublisherReceivedTimestamp"),
        "cloudPublishTimestamp": record.get("cloudPublishTimestamp"),
        "normalizedTimestamp": record.get("normalizedTimestamp"),
        "filteredTimestamp": record.get("filteredTimestamp"),
        "anomalyTimestamp": record.get("anomalyTimestamp"),
        "cloudReceivedTimestamp": record.get("cloudReceivedTimestamp"),
        "alertTimestamp": utc_now(),
        "groundTruth": record.get("groundTruth"),
    }
    if isinstance(record.get("edgeDetection"), dict) and record["edgeDetection"].get("isAnomaly"):
        alert["edgeDetection"] = record["edgeDetection"]
    if isinstance(record.get("cloudDetection"), dict) and record["cloudDetection"].get("isAnomaly"):
        alert["cloudDetection"] = record["cloudDetection"]
    return alert


def _is_alert_record(record: dict[str, Any]) -> bool:
    edge_detection = record.get("edgeDetection")
    cloud_detection = record.get("cloudDetection")
    return (
        isinstance(edge_detection, dict)
        and bool(edge_detection.get("isAnomaly"))
        or isinstance(cloud_detection, dict)
        and bool(cloud_detection.get("isAnomaly"))
    )


def _invalid_entity(
    error: str,
    body: bytes | str | dict[str, Any],
    metadata: dict[str, Any],
    cloud_received_timestamp: str,
) -> dict[str, Any]:
    raw = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    if not isinstance(raw, str):
        raw = json_payload(raw)
    payload_hash = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()
    return {
        "PartitionKey": "invalid",
        "RowKey": _safe_key(f"{cloud_received_timestamp}|{payload_hash[:16]}"),
        "messageType": "invalid",
        "cloudReceivedTimestamp": cloud_received_timestamp,
        "error": error,
        "originDeviceId": str(_metadata_value(metadata, "iothub-connection-device-id", "originDeviceId") or ""),
        "originModuleId": str(_metadata_value(metadata, "iothub-connection-module-id", "originModuleId") or ""),
        "payloadJson": raw[:32000],
    }


def _metadata_value(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata:
            return metadata[key]
    system_properties = metadata.get("SystemProperties")
    if isinstance(system_properties, dict):
        for key in keys:
            if key in system_properties:
                return system_properties[key]
    return None


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _safe_key(value: str) -> str:
    invalid = {'/', '\\', '#', '?'}
    return "".join("_" if char in invalid or ord(char) < 32 else char for char in value)
