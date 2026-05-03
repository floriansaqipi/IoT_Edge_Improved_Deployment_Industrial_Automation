from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATHS = (
    ROOT / "edge" / "modules" / "common" / "src",
    ROOT / "edge" / "modules" / "opcua-collector" / "src",
    ROOT / "cloud" / "s0-cloud-publisher" / "src",
    ROOT / "cloud" / "cloud_processor" / "src",
)

for path in PATHS:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cloud_processor.processor import ALERTS_TABLE, INVALID_TABLE, TELEMETRY_TABLE, process_event_body  # noqa: E402
from s0_cloud_publisher.config import S0PublisherConfig  # noqa: E402
from s0_cloud_publisher.iothub_sender import IoTHubDirectTelemetrySender  # noqa: E402


def test_phase5_s0_config_requires_device_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IOTHUB_DEVICE_CONNECTION_STRING", raising=False)

    with pytest.raises(ValueError, match="IOTHUB_DEVICE_CONNECTION_STRING"):
        S0PublisherConfig.from_env()


def test_phase5_s0_config_maps_to_collector_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IOTHUB_DEVICE_CONNECTION_STRING", "HostName=example;DeviceId=s0;SharedAccessKey=abc")
    monkeypatch.setenv("SCENARIO_OVERRIDE", "S0_CLOUD_ONLY")
    monkeypatch.setenv("RUN_ID_OVERRIDE", "s0_smoke")

    config = S0PublisherConfig.from_env()
    collector_config = config.to_collector_config()

    assert collector_config.scenario_override == "S0_CLOUD_ONLY"
    assert collector_config.run_id_override == "s0_smoke"
    assert collector_config.output_mode == "stdout"


def test_phase5_s0_sender_prepares_direct_cloud_message() -> None:
    config = S0PublisherConfig(
        iothub_device_connection_string="HostName=example;DeviceId=s0;SharedAccessKey=abc",
        scenario_override="S0_CLOUD_ONLY",
        run_id_override="s0_smoke",
    )
    sender = IoTHubDirectTelemetrySender(config)

    prepared = sender.prepare_message(_record("motor", sequence=1, scenario="OPCUA_SIMULATOR"))

    assert prepared["scenario"] == "S0_CLOUD_ONLY"
    assert prepared["runId"] == "s0_smoke"
    assert prepared["edgeReceivedTimestamp"] is None
    assert prepared["directPublisherReceivedTimestamp"].endswith("Z")
    assert prepared["cloudPublishTimestamp"].endswith("Z")


def test_phase5_s0_rate_cap_is_strict_even_for_ground_truth_anomalies() -> None:
    config = S0PublisherConfig(
        iothub_device_connection_string="HostName=example;DeviceId=s0;SharedAccessKey=abc",
        cloud_output_policy="capped",
        cloud_max_messages_per_second=2,
    )
    sender = IoTHubDirectTelemetrySender(config)
    anomaly = _record("motor", sequence=3)
    anomaly["groundTruth"] = {"isAnomaly": True, "anomalyType": "bearing_fault"}

    assert sender.limiter.should_forward(_sampling_record(_record("motor", 1)), 0.0)
    assert sender.limiter.should_forward(_sampling_record(_record("motor", 2)), 0.1)
    assert not sender.limiter.should_forward(_sampling_record(anomaly), 0.2)


def test_phase5_cloud_processor_detects_s0_anomaly_without_ground_truth() -> None:
    record = _record("motor", sequence=1, scenario="S0_CLOUD_ONLY", value_overrides={"vibration": 1.3})
    record["groundTruth"] = {"isAnomaly": False, "anomalyType": None}

    result = process_event_body(record, _metadata(), cloud_received_timestamp="2026-05-03T12:00:10.000000Z")

    assert result.valid
    assert [write.table_name for write in result.writes] == [TELEMETRY_TABLE, ALERTS_TABLE]
    telemetry = result.writes[0].entity
    assert telemetry["cloudIsAnomaly"] is True
    assert telemetry["cloudAnomalyType"] == "bearing_fault"
    assert telemetry["cloudReceivedTimestamp"] == "2026-05-03T12:00:10.000000Z"
    assert telemetry["originDeviceId"] == "s0-cloud-publisher-b"


def test_phase5_cloud_processor_ignores_ground_truth_for_cloud_detection() -> None:
    record = _record("motor", sequence=1, scenario="S0_CLOUD_ONLY")
    record["groundTruth"] = {"isAnomaly": True, "anomalyType": "bearing_fault"}

    result = process_event_body(record, _metadata())

    assert result.valid
    telemetry = result.writes[0].entity
    cloud_detection = json.loads(telemetry["cloudDetectionJson"])
    assert cloud_detection["isAnomaly"] is False
    assert len(result.writes) == 1


def test_phase5_cloud_processor_preserves_s2_edge_detection() -> None:
    record = _record("pump", sequence=44, scenario="S2_HYBRID", value_overrides={"pressure": 5.8, "flowRate": 12.0})
    record["edgeDetection"] = {
        "isAnomaly": True,
        "anomalyType": "blockage",
        "severity": "critical",
        "score": 0.93,
        "matchedRules": ["pump.blockage"],
    }

    result = process_event_body(record, _metadata(origin_module="anomaly-detector"))

    assert [write.table_name for write in result.writes] == [TELEMETRY_TABLE, ALERTS_TABLE]
    telemetry = result.writes[0].entity
    assert telemetry["edgeIsAnomaly"] is True
    assert telemetry["edgeAnomalyType"] == "blockage"
    assert telemetry["cloudDetectionJson"] is None


def test_phase5_cloud_processor_stores_compact_alerts() -> None:
    alert = {
        "messageType": "alert",
        "experimentId": "phase5",
        "scenario": "S2_HYBRID",
        "runId": "s2_smoke",
        "deviceId": "pump-001",
        "deviceType": "pump",
        "sequence": 44,
        "sensorTimestamp": "2026-05-03T12:00:00.000000Z",
        "edgeDetection": {"isAnomaly": True, "anomalyType": "blockage"},
    }

    result = process_event_body(alert, _metadata(origin_module="local-alert-service"))

    assert result.valid
    assert result.message_type == "alert"
    assert len(result.writes) == 1
    assert result.writes[0].table_name == ALERTS_TABLE
    assert result.writes[0].entity["messageType"] == "alert"


def test_phase5_cloud_processor_routes_invalid_records() -> None:
    result = process_event_body({"deviceId": "motor-001"}, _metadata())

    assert not result.valid
    assert result.writes[0].table_name == INVALID_TABLE
    assert "missing required field" in result.writes[0].entity["error"]


def test_phase5_manifests_include_scenario_overrides_and_idle_routes() -> None:
    s1 = json.loads((ROOT / "edge" / "deployments" / "s1-edge-pass-through.template.json").read_text())
    s2 = json.loads((ROOT / "edge" / "deployments" / "s2-hybrid.template.json").read_text())
    idle = json.loads((ROOT / "edge" / "deployments" / "idle-edge.template.json").read_text())

    s1_env = s1["modulesContent"]["$edgeAgent"]["properties.desired"]["modules"]["opcua-collector"]["env"]
    s2_env = s2["modulesContent"]["$edgeAgent"]["properties.desired"]["modules"]["opcua-collector"]["env"]
    idle_agent = idle["modulesContent"]["$edgeAgent"]["properties.desired"]

    assert s1_env["SCENARIO_OVERRIDE"]["value"] == "S1_EDGE_PASS_THROUGH"
    assert s2_env["SCENARIO_OVERRIDE"]["value"] == "S2_HYBRID"
    assert idle_agent["modules"] == {}
    assert idle["modulesContent"]["$edgeHub"]["properties.desired"]["routes"] == {}


def _sampling_record(record: dict) -> dict:
    sampled = dict(record)
    sampled["groundTruth"] = {"isAnomaly": False, "anomalyType": None}
    return sampled


def _metadata(origin_module: str = "") -> dict:
    return {
        "iothub-connection-device-id": "s0-cloud-publisher-b",
        "iothub-connection-module-id": origin_module,
        "SequenceNumber": 123,
    }


def _record(
    device_type: str,
    sequence: int,
    scenario: str = "S0_CLOUD_ONLY",
    value_overrides: dict | None = None,
) -> dict:
    values = _values(device_type)
    if value_overrides:
        values.update(value_overrides)
    return {
        "experimentId": "phase5",
        "scenario": scenario,
        "runId": "phase5_rep1",
        "deviceId": f"{device_type}-001",
        "deviceType": device_type,
        "sequence": sequence,
        "sensorTimestamp": "2026-05-03T12:00:00.000000Z",
        "edgeReceivedTimestamp": None,
        "normalizedTimestamp": None,
        "filteredTimestamp": None,
        "anomalyTimestamp": None,
        "cloudReceivedTimestamp": None,
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
    }
    return dict(values_by_type[device_type])
