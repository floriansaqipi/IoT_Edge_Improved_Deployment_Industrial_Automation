from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_MODULES = ROOT / "edge" / "modules"
MODULE_SRCS = (
    EDGE_MODULES / "common" / "src",
    EDGE_MODULES / "normalizer-validator" / "src",
    EDGE_MODULES / "filter-aggregator" / "src",
    EDGE_MODULES / "anomaly-detector" / "src",
    EDGE_MODULES / "local-alert-service" / "src",
)

for module_src in MODULE_SRCS:
    if str(module_src) not in sys.path:
        sys.path.insert(0, str(module_src))

from anomaly_detector.main import detect_anomaly, process_record as detect_record  # noqa: E402
from filter_aggregator.main import FilterAggregator  # noqa: E402
from local_alert_service.main import LocalAlertService  # noqa: E402
from normalizer_validator.main import process_record as normalize_record  # noqa: E402


def test_phase4_normalizer_accepts_valid_and_rejects_invalid_records() -> None:
    valid_outputs = normalize_record(_record("motor", sequence=1))
    invalid_outputs = normalize_record({"deviceId": "motor-001"})

    assert len(valid_outputs) == 1
    assert valid_outputs[0].output_name == "normalized"
    assert valid_outputs[0].payload["normalizedTimestamp"].endswith("Z")
    assert valid_outputs[0].payload["filteredTimestamp"] is None
    assert invalid_outputs == []


def test_phase4_filter_sampling_and_rate_cap() -> None:
    filter_aggregator = FilterAggregator(sample_every=10, max_messages_per_second=9)

    candidates = []
    for sequence in range(1, 101):
        payload = filter_aggregator.process_record(_record("motor", sequence=sequence), elapsed_seconds=0.0)[0].payload
        if payload["edgeRouting"]["cloudCandidate"]:
            candidates.append(sequence)

    assert candidates == [10, 20, 30, 40, 50, 60, 70, 80, 90]


def test_phase4_filter_does_not_use_ground_truth_to_bypass_sampling() -> None:
    filter_aggregator = FilterAggregator(sample_every=10, max_messages_per_second=9)
    record = _record("motor", sequence=7)
    record["groundTruth"] = {"isAnomaly": True, "anomalyType": "overheating"}

    payload = filter_aggregator.process_record(record, elapsed_seconds=0.0)[0].payload

    assert payload["edgeRouting"]["cloudCandidate"] is False


def test_phase4_anomaly_rules_cover_device_types() -> None:
    cases = {
        "motor": ("overheating", {"temperature": 91.0}),
        "pump": ("blockage", {"pressure": 5.8, "flowRate": 12.0}),
        "conveyor": ("jam", {"speed": 0.4, "motorCurrent": 13.0}),
        "tank": ("overflow_risk", {"level": 96.0, "outletFlow": 6.0}),
        "compressor": ("pressure_instability", {"pressure": 9.2}),
    }

    for device_type, (expected_type, overrides) in cases.items():
        record = _record(device_type, sequence=1, value_overrides=overrides)
        result = detect_anomaly(record)

        assert result.is_anomaly
        assert result.anomaly_type == expected_type
        assert result.score > 0
        assert result.matched_rules


def test_phase4_detector_ignores_ground_truth_labels() -> None:
    record = _record("motor", sequence=1)
    record["groundTruth"] = {"isAnomaly": True, "anomalyType": "overheating"}
    record["edgeRouting"] = {"cloudCandidate": False}

    result = detect_anomaly(record)
    outputs = detect_record(record)

    assert not result.is_anomaly
    assert outputs == []


def test_phase4_detector_routes_sampled_telemetry_and_alerts() -> None:
    sampled = _record("motor", sequence=10)
    sampled["edgeRouting"] = {"cloudCandidate": True}
    normal_outputs = detect_record(sampled)

    anomalous = _record("pump", sequence=1, value_overrides={"pressure": 5.8, "flowRate": 12.0})
    anomalous["edgeRouting"] = {"cloudCandidate": False}
    anomaly_outputs = detect_record(anomalous)

    assert [output.output_name for output in normal_outputs] == ["telemetry"]
    assert {output.output_name for output in anomaly_outputs} == {"telemetry", "alerts"}
    alert_payload = next(output.payload for output in anomaly_outputs if output.output_name == "alerts")
    assert alert_payload["edgeDetection"]["anomalyType"] == "blockage"
    assert alert_payload["anomalyTimestamp"].endswith("Z")


def test_phase4_alert_service_writes_compact_alert(tmp_path: Path) -> None:
    log_path = tmp_path / "alerts" / "s2_alerts.jsonl"
    service = LocalAlertService(log_path)
    record = _record("pump", sequence=3, value_overrides={"pressure": 5.8, "flowRate": 12.0})
    record["edgeDetection"] = {
        "isAnomaly": True,
        "anomalyType": "blockage",
        "severity": "critical",
        "score": 0.93,
        "matchedRules": ["pump.blockage"],
    }
    record["anomalyTimestamp"] = "2026-05-03T12:00:00.000000Z"

    outputs = service.process_record(record)
    written = json.loads(log_path.read_text(encoding="utf-8").strip())

    assert outputs[0].output_name == "alerts"
    assert outputs[0].payload["messageType"] == "alert"
    assert written["messageType"] == "alert"
    assert written["edgeDetection"]["anomalyType"] == "blockage"
    assert written["alertTimestamp"].endswith("Z")


def test_phase4_in_memory_s2_pipeline_samples_and_alerts(tmp_path: Path) -> None:
    filter_aggregator = FilterAggregator(sample_every=10, max_messages_per_second=9)
    alert_service = LocalAlertService(tmp_path / "alerts.jsonl")

    normalized = normalize_record(_record("motor", sequence=10))[0].payload
    filtered = filter_aggregator.process_record(normalized, elapsed_seconds=0.0)[0].payload
    telemetry_outputs = detect_record(filtered)

    anomaly_normalized = normalize_record(
        _record("pump", sequence=1, value_overrides={"pressure": 5.8, "flowRate": 12.0})
    )[0].payload
    anomaly_filtered = filter_aggregator.process_record(anomaly_normalized, elapsed_seconds=0.1)[0].payload
    anomaly_outputs = detect_record(anomaly_filtered)
    raw_alert = next(output.payload for output in anomaly_outputs if output.output_name == "alerts")
    compact_alert = alert_service.process_record(raw_alert)[0].payload

    assert filtered["normalizedTimestamp"].endswith("Z")
    assert filtered["filteredTimestamp"].endswith("Z")
    assert [output.output_name for output in telemetry_outputs] == ["telemetry"]
    assert compact_alert["messageType"] == "alert"
    assert compact_alert["anomalyTimestamp"].endswith("Z")
    assert compact_alert["alertTimestamp"].endswith("Z")


def test_phase4_s2_manifest_contains_expected_routes_and_budget_env() -> None:
    manifest_path = ROOT / "edge" / "deployments" / "s2-hybrid.template.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    edge_agent = manifest["modulesContent"]["$edgeAgent"]["properties.desired"]
    edge_hub = manifest["modulesContent"]["$edgeHub"]["properties.desired"]

    modules = edge_agent["modules"]
    routes = edge_hub["routes"]

    assert set(modules) == {
        "opcua-collector",
        "normalizer-validator",
        "filter-aggregator",
        "anomaly-detector",
        "local-alert-service",
    }
    assert "collectorToCloud" not in routes
    assert set(routes) == {
        "collectorToNormalizer",
        "normalizerToFilter",
        "filterToAnomaly",
        "anomalyTelemetryToCloud",
        "anomalyToAlert",
        "alertToCloud",
    }
    assert routes["alertToCloud"]["priority"] < routes["anomalyTelemetryToCloud"]["priority"]
    assert routes["anomalyTelemetryToCloud"]["route"].endswith("INTO $upstream")
    assert routes["alertToCloud"]["route"].endswith("INTO $upstream")
    assert edge_hub["storeAndForwardConfiguration"]["timeToLiveSecs"] == 7200

    filter_env = modules["filter-aggregator"]["env"]
    assert filter_env["CLOUD_OUTPUT_POLICY"]["value"] == "sampled_10_percent"
    assert filter_env["SAMPLE_EVERY"]["value"] == "10"
    assert filter_env["CLOUD_MAX_MESSAGES_PER_SECOND"]["value"] == "9"
    assert not any("s3" in module_name.lower() for module_name in modules)


def _record(device_type: str, sequence: int, value_overrides: dict | None = None) -> dict:
    values = _values(device_type)
    if value_overrides:
        values.update(value_overrides)
    return {
        "experimentId": "exp-phase4",
        "scenario": "S2_HYBRID",
        "runId": "run-phase4",
        "deviceId": f"{device_type}-001",
        "deviceType": device_type,
        "sequence": sequence,
        "sensorTimestamp": "2026-05-03T12:00:00.000000Z",
        "edgeReceivedTimestamp": "2026-05-03T12:00:00.010000Z",
        "values": values,
        "groundTruth": {"isAnomaly": False, "anomalyType": None},
    }


def _values(device_type: str) -> dict:
    values_by_type = {
        "motor": {
            "temperature": 62.0,
            "vibration": 0.2,
            "rpm": 1450.0,
            "current": 8.0,
            "load": 65.0,
            "status": "NORMAL",
        },
        "pump": {
            "pressure": 3.2,
            "flowRate": 42.0,
            "temperature": 48.0,
            "vibration": 0.2,
            "current": 6.0,
            "status": "NORMAL",
        },
        "conveyor": {
            "speed": 1.6,
            "load": 55.0,
            "motorCurrent": 6.5,
            "vibration": 0.15,
            "status": "NORMAL",
        },
        "tank": {
            "level": 55.0,
            "pressure": 1.2,
            "inletFlow": 18.0,
            "outletFlow": 18.0,
            "valveState": "OPEN",
            "status": "NORMAL",
        },
        "compressor": {
            "pressure": 7.0,
            "temperature": 58.0,
            "vibration": 0.3,
            "current": 7.5,
            "status": "NORMAL",
        },
    }
    return dict(values_by_type[device_type])
