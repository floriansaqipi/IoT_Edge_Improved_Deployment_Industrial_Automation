from __future__ import annotations

import argparse
import asyncio
import json
import time
from contextlib import nullcontext
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np

from config_loader import ConfigError, OpcUaConfig, OutputConfig, SimulationConfig, load_config
from devices import DEVICE_CLASS_BY_TYPE
from devices.base_device import BaseDevice
from ground_truth_logger import MultiGroundTruthLogger
from opcua_server import IndustrialOpcUaServer


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

    outputs = tuple((output.path, output.format) for output in config.all_outputs)
    with MultiGroundTruthLogger(outputs) as logger:
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
        "runMode": config.run_mode,
        "deviceCount": config.device_count,
        "targetMessagesPerSecond": config.target_messages_per_second,
        "messagesPerDevicePerSecond": config.messages_per_device_per_second,
        "durationSeconds": config.duration_seconds,
        "expectedMessages": total_messages,
        "writtenMessages": total_messages,
        "groundTruthAnomalyMessages": anomaly_count,
        "outputPath": str(config.output.path),
        "outputFormat": config.output.format,
        "outputPaths": [str(output.path) for output in config.all_outputs],
        "outputFormats": [output.format for output in config.all_outputs],
        "paceRealtime": config.pace_realtime,
        "wallClockMessagesPerSecond": round(total_messages / wall_duration, 2),
    }


async def run_opcua_simulation(config: SimulationConfig) -> dict[str, Any]:
    devices = build_devices(config)
    total_messages = config.expected_message_count
    anomaly_count = 0
    message_index = 0
    wall_start = time.perf_counter()
    writes_ground_truth = config.run_mode == "both"
    outputs = tuple((output.path, output.format) for output in config.all_outputs) if writes_ground_truth else ()

    experiment_metadata = {
        "ExperimentId": config.experiment_id,
        "Scenario": config.scenario,
        "RunId": config.run_id,
    }
    async with IndustrialOpcUaServer(config.opcua, devices, experiment_metadata) as opcua_server:
        logger_context = MultiGroundTruthLogger(outputs) if writes_ground_truth else nullcontext(None)
        with logger_context as logger:
            while config.until_stopped or message_index < total_messages:
                elapsed_seconds = message_index / config.target_messages_per_second
                if config.pace_realtime or config.until_stopped:
                    await _async_sleep_until(wall_start + elapsed_seconds)

                device = devices[message_index % len(devices)]
                sensor_timestamp = config.start_time + timedelta(seconds=elapsed_seconds)
                record = device.emit(sensor_timestamp, elapsed_seconds)
                if record["groundTruth"]["isAnomaly"]:
                    anomaly_count += 1
                if logger is not None:
                    logger.write(record)
                await opcua_server.update_record(record)
                message_index += 1

    wall_duration = max(time.perf_counter() - wall_start, 0.000001)
    return {
        "experimentId": config.experiment_id,
        "scenario": config.scenario,
        "runId": config.run_id,
        "runMode": config.run_mode,
        "deviceCount": config.device_count,
        "targetMessagesPerSecond": config.target_messages_per_second,
        "messagesPerDevicePerSecond": config.messages_per_device_per_second,
        "durationSeconds": config.duration_seconds,
        "expectedMessages": total_messages,
        "writtenMessages": message_index,
        "groundTruthAnomalyMessages": anomaly_count,
        "outputPath": str(config.output.path) if writes_ground_truth else None,
        "outputFormat": config.output.format if writes_ground_truth else None,
        "outputPaths": [str(output.path) for output in config.all_outputs] if writes_ground_truth else [],
        "outputFormats": [output.format for output in config.all_outputs] if writes_ground_truth else [],
        "paceRealtime": config.pace_realtime,
        "untilStopped": config.until_stopped,
        "opcuaEndpoint": config.opcua.endpoint,
        "opcuaNamespaceUri": config.opcua.namespace_uri,
        "wallClockMessagesPerSecond": round(message_index / wall_duration, 2),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the industrial telemetry simulator.")
    parser.add_argument("config", type=Path, help="Path to an experiment YAML config.")
    parser.add_argument("--mode", choices=("file", "opcua", "both"), help="Override runMode from the config.")
    parser.add_argument("--opcua-endpoint", help="Override opcua.endpoint from the config.")
    parser.add_argument("--until-stopped", action="store_true", help="Run OPC UA mode until interrupted.")
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
    if args.output is not None or args.format is not None:
        replacements["outputs"] = ()
    if args.duration is not None:
        replacements["duration_seconds"] = args.duration
    if args.mode is not None:
        replacements["run_mode"] = args.mode
    if args.opcua_endpoint is not None:
        replacements["opcua"] = OpcUaConfig(
            endpoint=args.opcua_endpoint,
            namespace_uri=config.opcua.namespace_uri,
        )
    if args.until_stopped:
        replacements["until_stopped"] = True
    if args.realtime:
        replacements["pace_realtime"] = True
    if args.no_realtime:
        replacements["pace_realtime"] = False

    overridden = replace(config, **replacements)
    if overridden.duration_seconds <= 0:
        raise ConfigError("--duration must be greater than zero.")
    if overridden.until_stopped and overridden.run_mode == "file":
        raise ConfigError("--until-stopped is only valid for opcua or both mode.")
    if not overridden.opcua.endpoint.startswith("opc.tcp://"):
        raise ConfigError("--opcua-endpoint must start with opc.tcp://.")
    return overridden


def main() -> int:
    args = parse_args()
    try:
        config = apply_overrides(load_config(args.config), args)
        if config.run_mode == "file":
            summary = run_simulation(config)
        else:
            summary = asyncio.run(run_opcua_simulation(config))
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2
    except KeyboardInterrupt:
        print("Simulation stopped by user.")
        return 130

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _sleep_until(target: float) -> None:
    remaining = target - time.perf_counter()
    if remaining > 0:
        time.sleep(remaining)


async def _async_sleep_until(target: float) -> None:
    remaining = target - time.perf_counter()
    if remaining > 0:
        await asyncio.sleep(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
