from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np

from config_loader import ConfigError, OutputConfig, SimulationConfig, load_config
from devices import DEVICE_CLASS_BY_TYPE
from devices.base_device import BaseDevice
from ground_truth_logger import GroundTruthLogger


def build_devices(config: SimulationConfig) -> list[BaseDevice]:
    fault_by_device = {schedule.device_id: schedule for schedule in config.faults.schedules}
    devices: list[BaseDevice] = []

    for device_type, count in config.device_mix.items():
        device_class = DEVICE_CLASS_BY_TYPE[device_type]
        for index in range(1, count + 1):
            device_id = f"{device_type}-{index:03d}"
            rng = np.random.default_rng(config.seed + len(devices) + 1)
            devices.append(
                device_class(
                    device_id=device_id,
                    device_type=device_type,
                    rng=rng,
                    experiment_id=config.experiment_id,
                    scenario=config.scenario,
                    run_id=config.run_id,
                    fault_schedule=fault_by_device.get(device_id),
                )
            )

    known_ids = {device.device_id for device in devices}
    missing_fault_devices = sorted(set(fault_by_device) - known_ids)
    if missing_fault_devices:
        missing = ", ".join(missing_fault_devices)
        raise ConfigError(f"Fault schedules reference unknown device(s): {missing}.")

    return devices


def run_simulation(config: SimulationConfig) -> dict[str, Any]:
    devices = build_devices(config)
    total_messages = config.expected_message_count
    anomaly_count = 0
    wall_start = time.perf_counter()

    with GroundTruthLogger(config.output.path, config.output.format) as logger:
        for message_index in range(total_messages):
            elapsed_seconds = message_index / config.target_messages_per_second
            if config.pace_realtime:
                _sleep_until(wall_start + elapsed_seconds)

            device = devices[message_index % len(devices)]
            sensor_timestamp = config.start_time + timedelta(seconds=elapsed_seconds)
            record = device.emit(sensor_timestamp, elapsed_seconds)
            if record["groundTruth"]["isAnomaly"]:
                anomaly_count += 1
            logger.write(record)

    wall_duration = max(time.perf_counter() - wall_start, 0.000001)
    return {
        "experimentId": config.experiment_id,
        "scenario": config.scenario,
        "runId": config.run_id,
        "deviceCount": config.device_count,
        "targetMessagesPerSecond": config.target_messages_per_second,
        "messagesPerDevicePerSecond": config.messages_per_device_per_second,
        "durationSeconds": config.duration_seconds,
        "expectedMessages": total_messages,
        "writtenMessages": total_messages,
        "groundTruthAnomalyMessages": anomaly_count,
        "outputPath": str(config.output.path),
        "outputFormat": config.output.format,
        "paceRealtime": config.pace_realtime,
        "wallClockMessagesPerSecond": round(total_messages / wall_duration, 2),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local-only industrial telemetry simulator.")
    parser.add_argument("config", type=Path, help="Path to an experiment YAML config.")
    parser.add_argument("--duration", type=float, help="Override durationSeconds from the config.")
    parser.add_argument("--output", type=Path, help="Override output.path from the config.")
    parser.add_argument("--format", choices=("jsonl", "csv"), help="Override output.format from the config.")

    pacing = parser.add_mutually_exclusive_group()
    pacing.add_argument("--realtime", action="store_true", help="Sleep between messages to match the target rate.")
    pacing.add_argument("--no-realtime", action="store_true", help="Generate as fast as possible.")
    return parser.parse_args()


def apply_overrides(config: SimulationConfig, args: argparse.Namespace) -> SimulationConfig:
    output = config.output
    if args.output is not None or args.format is not None:
        output = OutputConfig(
            format=args.format or output.format,
            path=(args.output.resolve() if args.output is not None else output.path),
        )

    replacements: dict[str, Any] = {"output": output}
    if args.duration is not None:
        replacements["duration_seconds"] = args.duration
    if args.realtime:
        replacements["pace_realtime"] = True
    if args.no_realtime:
        replacements["pace_realtime"] = False

    overridden = replace(config, **replacements)
    if overridden.duration_seconds <= 0:
        raise ConfigError("--duration must be greater than zero.")
    return overridden


def main() -> int:
    args = parse_args()
    try:
        config = apply_overrides(load_config(args.config), args)
        summary = run_simulation(config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _sleep_until(target: float) -> None:
    remaining = target - time.perf_counter()
    if remaining > 0:
        time.sleep(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
