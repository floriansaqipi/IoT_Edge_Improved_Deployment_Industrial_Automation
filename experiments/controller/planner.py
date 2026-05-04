from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import yaml

from experiments.budget import ExperimentBudgetMatrix, load_budget_matrix, preflight_budget_matrix

from .models import SCENARIO_S0, SCENARIO_S1, SCENARIO_S2, SUPPORTED_SCENARIOS, ControllerSettings, PlannedRun
from .network import build_network_plan


SIMULATOR_WARMUP_SECONDS = 45


class ControllerPlanError(ValueError):
    """Raised when the controller refuses an unsafe experiment plan."""


def load_and_validate_matrix(path: Path) -> ExperimentBudgetMatrix:
    matrix = load_budget_matrix(path)
    preflight_budget_matrix(matrix)
    errors: list[str] = []
    for row in matrix.rows:
        if row.scenario not in SUPPORTED_SCENARIOS:
            errors.append(f"{row.id}: unsupported scenario {row.scenario!r}; S3 is not part of the 800k plan.")
        if row.scenario in {SCENARIO_S0, SCENARIO_S1} and row.cloud_messages_per_second > 90:
            errors.append(f"{row.id}: S0/S1 cloud rate must be <= 90 msg/s.")
    if errors:
        raise ControllerPlanError("\n".join(errors))
    return matrix


def expand_runs(
    matrix: ExperimentBudgetMatrix,
    campaign_id: str,
    row_filter: str | None = None,
    block_filter: str | None = None,
    scenario_filter: str | None = None,
    repetition_filter: int | None = None,
) -> tuple[PlannedRun, ...]:
    runs: list[PlannedRun] = []
    for row in matrix.rows:
        if row_filter and row.id != row_filter:
            continue
        if block_filter and row.block != block_filter:
            continue
        if scenario_filter and row.scenario != scenario_filter:
            continue
        repetitions = [repetition_filter] if repetition_filter is not None else range(1, row.repetitions + 1)
        for repetition in repetitions:
            if repetition is None or repetition < 1 or repetition > row.repetitions:
                raise ControllerPlanError(f"{row.id}: repetition {repetition} is outside 1..{row.repetitions}.")
            runs.append(
                PlannedRun(
                    campaign_id=campaign_id,
                    matrix_id=matrix.id,
                    row_id=row.id,
                    block=row.block,
                    scenario=row.scenario,
                    network_condition=row.network_condition,
                    target_messages_per_second=row.target_messages_per_second,
                    cloud_messages_per_second=row.cloud_messages_per_second,
                    duration_seconds=row.duration_seconds,
                    repetition=repetition,
                    repetitions=row.repetitions,
                    cloud_output_policy=row.cloud_output_policy,
                    estimated_billable_messages=math.ceil(row.estimated_billable_messages / row.repetitions),
                )
            )
    return tuple(runs)


def build_run_manifest(run: PlannedRun, settings: ControllerSettings, run_dir: Path) -> dict[str, Any]:
    network_plan = build_network_plan(run.network_condition, settings.iot_hub_host, run.duration_seconds)
    return {
        "run": run.as_dict(),
        "paths": {
            "runDir": str(run_dir),
            "simulatorConfig": str(run_dir / "simulator_config.yaml"),
            "simulatorJsonl": str(run_dir / "simulator.jsonl"),
            "simulatorCsv": str(run_dir / "simulator.csv"),
            "events": str(run_dir / "events.jsonl"),
        },
        "settings": {
            "machineA": settings.machine_a_ip,
            "machineB": settings.machine_b_host,
            "opcuaEndpoint": settings.opcua_endpoint,
            "iotHubName": settings.iot_hub_name,
            "edgeDeviceId": settings.edge_device_id,
            "s0DeviceId": settings.s0_device_id,
            "acrLoginServer": settings.acr_login_server,
            "collectorImageTag": settings.collector_image_tag,
            "phase4ImageTag": settings.phase4_image_tag,
            "s0ImageTag": settings.s0_image_tag,
        },
        "network": network_plan.as_dict(),
        "actions": scenario_actions(run),
    }


def scenario_actions(run: PlannedRun) -> list[str]:
    if run.scenario == SCENARIO_S0:
        return [
            "deploy idle Edge manifest",
            "start Machine A OPC UA simulator",
            "start s0-cloud-publisher Docker container on Machine B",
            "publish direct D2C telemetry to IoT Hub with S0 timestamps",
        ]
    if run.scenario == SCENARIO_S1:
        return [
            "deploy S1 Edge manifest",
            "start Machine A OPC UA simulator",
            "forward OPC UA collector output through Edge Hub",
            "cap S1 cloud output at 90 msg/s for stress rows",
        ]
    if run.scenario == SCENARIO_S2:
        return [
            "deploy S2 Edge manifest",
            "start Machine A OPC UA simulator",
            "process full local stream through edge microservices",
            "forward sampled telemetry plus compact alerts to IoT Hub",
        ]
    raise ControllerPlanError(f"Unsupported scenario: {run.scenario}")


def build_simulator_config(run: PlannedRun, settings: ControllerSettings, run_dir: Path) -> dict[str, Any]:
    device_count = 100
    return {
        "experimentId": run.matrix_id,
        "scenario": run.scenario,
        "runId": run.run_id,
        "runMode": "both",
        "deviceCount": device_count,
        "targetMessagesPerSecond": _yaml_number(run.target_messages_per_second),
        "durationSeconds": _yaml_number(run.duration_seconds),
        "seed": _stable_seed(run.run_id),
        "startTime": "2026-01-01T00:00:00Z",
        "paceRealtime": True,
        "warmupSeconds": SIMULATOR_WARMUP_SECONDS,
        "opcua": {
            "endpoint": settings.opcua_bind_endpoint,
            "namespaceUri": settings.opcua_namespace_uri,
        },
        "deviceMix": _device_mix(device_count),
        "outputs": [
            {"format": "jsonl", "path": str(run_dir / "simulator.jsonl")},
            {"format": "csv", "path": str(run_dir / "simulator.csv")},
        ],
        "faults": {
            "enabled": True,
            "schedules": _fault_schedules(),
        },
    }


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _fault_schedules() -> list[dict[str, Any]]:
    return [
        {
            "deviceId": "motor-014",
            "anomalyType": "bearing_fault",
            "startSecond": 30,
            "warningDurationSeconds": 20,
            "faultDurationSeconds": 90,
            "recoveryDurationSeconds": 30,
        },
        {
            "deviceId": "pump-011",
            "anomalyType": "blockage",
            "startSecond": 100,
            "warningDurationSeconds": 20,
            "faultDurationSeconds": 80,
            "recoveryDurationSeconds": 30,
        },
        {
            "deviceId": "conveyor-009",
            "anomalyType": "jam",
            "startSecond": 40,
            "warningDurationSeconds": 10,
            "faultDurationSeconds": 30,
            "recoveryDurationSeconds": 10,
        },
        {
            "deviceId": "tank-004",
            "anomalyType": "overflow_risk",
            "startSecond": 45,
            "warningDurationSeconds": 10,
            "faultDurationSeconds": 35,
            "recoveryDurationSeconds": 10,
        },
        {
            "deviceId": "compressor-002",
            "anomalyType": "pressure_instability",
            "startSecond": 20,
            "warningDurationSeconds": 10,
            "faultDurationSeconds": 35,
            "recoveryDurationSeconds": 10,
        },
    ]


def _device_mix(device_count: int) -> dict[str, int]:
    motor = round(device_count * 0.40)
    pump = round(device_count * 0.25)
    conveyor = round(device_count * 0.20)
    tank = round(device_count * 0.10)
    compressor = device_count - motor - pump - conveyor - tank
    return {
        "motor": motor,
        "pump": pump,
        "conveyor": conveyor,
        "tank": tank,
        "compressor": compressor,
    }


def _stable_seed(text: str) -> int:
    return 1000 + sum((index + 1) * ord(char) for index, char in enumerate(text)) % 900_000


def _yaml_number(value: float) -> int | float:
    if float(value).is_integer():
        return int(value)
    return value
