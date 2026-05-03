from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from config_loader import ConfigError, FaultSchedule, OutputConfig, load_config
from devices.motor import Motor
from main import build_devices, run_simulation


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "simulator" / "industrial-opcua-simulator" / "configs"


def test_starter_configs_load() -> None:
    for config_name in (
        "exp_10_devices_10mps.yaml",
        "exp_50_devices_100mps.yaml",
        "exp_100_devices_500mps.yaml",
    ):
        config = load_config(CONFIG_DIR / config_name)
        assert config.device_count > 0
        assert config.target_messages_per_second > 0
        assert sum(config.device_mix.values()) == config.device_count


def test_invalid_rate_is_rejected(tmp_path: Path) -> None:
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        """
experimentId: bad
scenario: LOCAL_ONLY
runId: bad_run
deviceCount: 1
targetMessagesPerSecond: 0
durationSeconds: 1
seed: 1
output:
  format: jsonl
  path: out.jsonl
deviceMix:
  motor: 1
  pump: 0
  conveyor: 0
  tank: 0
  compressor: 0
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(bad_config)


def test_devices_emit_required_fields_and_sensor_keys() -> None:
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps.yaml")
    devices = build_devices(config)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    required_fields = {
        "experimentId",
        "scenario",
        "runId",
        "deviceId",
        "deviceType",
        "sequence",
        "sensorTimestamp",
        "edgeReceivedTimestamp",
        "normalizedTimestamp",
        "filteredTimestamp",
        "anomalyTimestamp",
        "cloudReceivedTimestamp",
        "values",
        "groundTruth",
    }
    expected_value_keys = {
        "motor": {"temperature", "vibration", "rpm", "current", "load", "status"},
        "pump": {"pressure", "flowRate", "temperature", "vibration", "current", "status"},
        "conveyor": {"speed", "load", "motorCurrent", "vibration", "status"},
        "tank": {"level", "pressure", "inletFlow", "outletFlow", "valveState", "status"},
        "compressor": {"pressure", "temperature", "vibration", "current", "status"},
    }

    for device in devices:
        record = device.emit(timestamp, 0.0)
        assert required_fields <= set(record)
        assert expected_value_keys[device.device_type] <= set(record["values"])
        assert {"isAnomaly", "anomalyType"} <= set(record["groundTruth"])


def test_same_seed_produces_repeatable_jsonl(tmp_path: Path) -> None:
    base_config = load_config(CONFIG_DIR / "exp_10_devices_10mps.yaml")
    first = replace(
        base_config,
        duration_seconds=1.0,
        output=OutputConfig(format="jsonl", path=tmp_path / "first.jsonl"),
        outputs=(),
    )
    second = replace(
        base_config,
        duration_seconds=1.0,
        output=OutputConfig(format="jsonl", path=tmp_path / "second.jsonl"),
        outputs=(),
    )

    run_simulation(first)
    run_simulation(second)

    assert first.output.path.read_text(encoding="utf-8") == second.output.path.read_text(encoding="utf-8")


def test_fault_injection_changes_expected_motor_signal() -> None:
    schedule = FaultSchedule(
        device_id="motor-001",
        anomaly_type="bearing_fault",
        start_second=0.0,
        warning_duration_seconds=0.0,
        fault_duration_seconds=10.0,
        recovery_duration_seconds=0.0,
    )
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    normal_motor = Motor(
        device_id="motor-001",
        device_type="motor",
        rng=np.random.default_rng(10),
        experiment_id="exp",
        scenario="LOCAL_ONLY",
        run_id="normal",
    )
    faulted_motor = Motor(
        device_id="motor-001",
        device_type="motor",
        rng=np.random.default_rng(10),
        experiment_id="exp",
        scenario="LOCAL_ONLY",
        run_id="faulted",
        fault_schedule=schedule,
    )

    normal = normal_motor.emit(timestamp, 1.0)
    faulted = faulted_motor.emit(timestamp, 1.0)

    assert faulted["values"]["vibration"] > normal["values"]["vibration"]
    assert faulted["groundTruth"]["isAnomaly"] is True
    assert faulted["groundTruth"]["anomalyType"] == "bearing_fault"


def test_sequence_numbers_are_monotonic_per_device() -> None:
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps.yaml")
    device = build_devices(config)[0]
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    sequences = [device.emit(timestamp, elapsed)["sequence"] for elapsed in (0.0, 1.0, 2.0)]

    assert sequences == [1, 2, 3]


def test_smoke_10_devices_10_mps_jsonl_is_parseable(tmp_path: Path) -> None:
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps.yaml")
    run_config = replace(
        config,
        duration_seconds=1.0,
        output=OutputConfig(format="jsonl", path=tmp_path / "smoke.jsonl"),
        outputs=(),
    )

    summary = run_simulation(run_config)
    lines = run_config.output.path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]

    assert summary["writtenMessages"] == 10
    assert len(records) == 10
    assert records[0]["sensorTimestamp"] == "2026-01-01T00:00:00.000000Z"


def test_smoke_100_devices_500_mps_completes(tmp_path: Path) -> None:
    config = load_config(CONFIG_DIR / "exp_100_devices_500mps.yaml")
    run_config = replace(
        config,
        duration_seconds=0.1,
        output=OutputConfig(format="jsonl", path=tmp_path / "stress.jsonl"),
        outputs=(),
    )

    summary = run_simulation(run_config)

    assert summary["writtenMessages"] == 50
    assert run_config.output.path.exists()


def test_multi_output_writes_jsonl_and_csv(tmp_path: Path) -> None:
    config_path = tmp_path / "multi.yaml"
    config_path.write_text(
        f"""
experimentId: multi
scenario: LOCAL_ONLY
runId: multi_run
deviceCount: 10
targetMessagesPerSecond: 10
durationSeconds: 1
seed: 42
startTime: "2026-01-01T00:00:00Z"
deviceMix:
  motor: 4
  pump: 2
  conveyor: 2
  tank: 1
  compressor: 1
outputs:
  - format: jsonl
    path: {tmp_path / "multi.jsonl"}
  - format: csv
    path: {tmp_path / "multi.csv"}
faults:
  enabled: true
  schedules:
    - deviceId: motor-001
      anomalyType: bearing_fault
      startSecond: 0
      warningDurationSeconds: 0
      faultDurationSeconds: 1
      recoveryDurationSeconds: 0
""",
        encoding="utf-8",
    )
    config = load_config(config_path)

    summary = run_simulation(config)
    jsonl_lines = (tmp_path / "multi.jsonl").read_text(encoding="utf-8").splitlines()
    csv_lines = (tmp_path / "multi.csv").read_text(encoding="utf-8").splitlines()

    assert summary["writtenMessages"] == 10
    assert summary["outputFormats"] == ["jsonl", "csv"]
    assert len(jsonl_lines) == 10
    assert len(csv_lines) == 11
    assert "isAnomaly" in csv_lines[0]
