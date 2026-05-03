from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEVICE_TYPES = ("motor", "pump", "conveyor", "tank", "compressor")
RUN_MODES = ("file", "opcua", "both")
DEFAULT_OPCUA_ENDPOINT = "opc.tcp://0.0.0.0:4840/factory/server"
DEFAULT_OPCUA_NAMESPACE_URI = "urn:industrial-automation:azure-iot-edge-study"


class ConfigError(ValueError):
    """Raised when an experiment YAML file is missing required simulator settings."""


@dataclass(frozen=True)
class OutputConfig:
    format: str
    path: Path


@dataclass(frozen=True)
class FaultSchedule:
    device_id: str
    anomaly_type: str
    start_second: float
    warning_duration_seconds: float
    fault_duration_seconds: float
    recovery_duration_seconds: float

    @property
    def end_second(self) -> float:
        return (
            self.start_second
            + self.warning_duration_seconds
            + self.fault_duration_seconds
            + self.recovery_duration_seconds
        )

    def phase_at(self, elapsed_seconds: float) -> str:
        if elapsed_seconds < self.start_second or elapsed_seconds >= self.end_second:
            return "NORMAL"

        warning_end = self.start_second + self.warning_duration_seconds
        fault_end = warning_end + self.fault_duration_seconds

        if elapsed_seconds < warning_end:
            return "WARNING"
        if elapsed_seconds < fault_end:
            return "FAULT"
        return "RECOVERY"

    def intensity_at(self, elapsed_seconds: float) -> float:
        phase = self.phase_at(elapsed_seconds)
        if phase == "NORMAL":
            return 0.0

        if phase == "WARNING":
            span = max(self.warning_duration_seconds, 0.001)
            progress = (elapsed_seconds - self.start_second) / span
            return 0.25 + 0.4 * min(max(progress, 0.0), 1.0)

        if phase == "FAULT":
            return 1.0

        recovery_start = self.start_second + self.warning_duration_seconds + self.fault_duration_seconds
        span = max(self.recovery_duration_seconds, 0.001)
        progress = (elapsed_seconds - recovery_start) / span
        return 0.7 * (1.0 - min(max(progress, 0.0), 1.0))


@dataclass(frozen=True)
class FaultConfig:
    enabled: bool
    schedules: tuple[FaultSchedule, ...]


@dataclass(frozen=True)
class OpcUaConfig:
    endpoint: str
    namespace_uri: str


@dataclass(frozen=True)
class SimulationConfig:
    experiment_id: str
    scenario: str
    run_id: str
    run_mode: str
    device_count: int
    target_messages_per_second: int
    duration_seconds: float
    seed: int
    start_time: datetime
    pace_realtime: bool
    until_stopped: bool
    device_mix: dict[str, int]
    output: OutputConfig
    outputs: tuple[OutputConfig, ...]
    opcua: OpcUaConfig
    faults: FaultConfig

    @property
    def messages_per_device_per_second(self) -> float:
        return self.target_messages_per_second / self.device_count

    @property
    def expected_message_count(self) -> int:
        return int(round(self.target_messages_per_second * self.duration_seconds))

    @property
    def all_outputs(self) -> tuple[OutputConfig, ...]:
        return self.outputs or (self.output,)


def load_config(path: str | Path) -> SimulationConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a mapping.")

    output, outputs = _parse_outputs(raw, config_path.parent)
    device_count = _required_int(raw, "deviceCount")
    target_mps = _required_int(raw, "targetMessagesPerSecond")
    duration = _required_float(raw, "durationSeconds")
    device_mix = _parse_device_mix(raw.get("deviceMix"), device_count)

    config = SimulationConfig(
        experiment_id=_required_str(raw, "experimentId"),
        scenario=_required_str(raw, "scenario"),
        run_id=_required_str(raw, "runId"),
        run_mode=_parse_run_mode(raw.get("runMode", "file")),
        device_count=device_count,
        target_messages_per_second=target_mps,
        duration_seconds=duration,
        seed=_required_int(raw, "seed"),
        start_time=_parse_start_time(raw.get("startTime")),
        pace_realtime=bool(raw.get("paceRealtime", False)),
        until_stopped=bool(raw.get("untilStopped", False)),
        device_mix=device_mix,
        output=output,
        outputs=outputs,
        opcua=_parse_opcua(raw.get("opcua")),
        faults=_parse_faults(raw.get("faults")),
    )
    _validate_config(config)
    return config


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string.")
    return value.strip()


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise ConfigError(f"{key} must be an integer.")
    return value


def _required_float(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)):
        raise ConfigError(f"{key} must be numeric.")
    return float(value)


def _parse_outputs(raw: dict[str, Any], config_dir: Path) -> tuple[OutputConfig, tuple[OutputConfig, ...]]:
    if "outputs" in raw:
        outputs_raw = raw.get("outputs")
        if not isinstance(outputs_raw, list) or not outputs_raw:
            raise ConfigError("outputs must be a non-empty list.")
        outputs = tuple(_parse_output_item(item, config_dir, "outputs") for item in outputs_raw)
        paths = [output.path for output in outputs]
        if len(paths) != len(set(paths)):
            raise ConfigError("outputs must not contain duplicate paths.")
        return outputs[0], outputs

    output = _parse_output_item(raw.get("output"), config_dir, "output")
    return output, ()


def _parse_output_item(raw: Any, config_dir: Path, label: str) -> OutputConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"{label} must be configured.")

    output_format = str(raw.get("format", "")).lower()
    output_path = raw.get("path")
    if output_format not in {"jsonl", "csv"}:
        raise ConfigError(f"{label}.format must be either jsonl or csv.")
    if not isinstance(output_path, str) or not output_path.strip():
        raise ConfigError(f"{label}.path must be a non-empty string.")

    path = Path(output_path)
    if not path.is_absolute():
        path = (config_dir / path).resolve()
    return OutputConfig(format=output_format, path=path)


def _parse_run_mode(raw: Any) -> str:
    run_mode = str(raw).lower()
    if run_mode not in RUN_MODES:
        raise ConfigError("runMode must be one of: file, opcua, both.")
    return run_mode


def _parse_opcua(raw: Any) -> OpcUaConfig:
    if raw is None:
        return OpcUaConfig(endpoint=DEFAULT_OPCUA_ENDPOINT, namespace_uri=DEFAULT_OPCUA_NAMESPACE_URI)
    if not isinstance(raw, dict):
        raise ConfigError("opcua must be a mapping.")

    endpoint = str(raw.get("endpoint", DEFAULT_OPCUA_ENDPOINT)).strip()
    namespace_uri = str(raw.get("namespaceUri", DEFAULT_OPCUA_NAMESPACE_URI)).strip()
    if not endpoint:
        raise ConfigError("opcua.endpoint must be a non-empty string.")
    if not endpoint.startswith("opc.tcp://"):
        raise ConfigError("opcua.endpoint must start with opc.tcp://.")
    if not namespace_uri:
        raise ConfigError("opcua.namespaceUri must be a non-empty string.")
    return OpcUaConfig(endpoint=endpoint, namespace_uri=namespace_uri)


def _parse_device_mix(raw: Any, device_count: int) -> dict[str, int]:
    if raw is None:
        return _default_device_mix(device_count)
    if not isinstance(raw, dict):
        raise ConfigError("deviceMix must be a mapping.")

    mix: dict[str, int] = {}
    for device_type in DEVICE_TYPES:
        count = raw.get(device_type, 0)
        if not isinstance(count, int) or count < 0:
            raise ConfigError(f"deviceMix.{device_type} must be a non-negative integer.")
        mix[device_type] = count

    unknown = sorted(set(raw) - set(DEVICE_TYPES))
    if unknown:
        raise ConfigError(f"deviceMix has unknown device type(s): {', '.join(unknown)}.")
    if sum(mix.values()) != device_count:
        raise ConfigError("deviceMix counts must add up to deviceCount.")
    return mix


def _default_device_mix(device_count: int) -> dict[str, int]:
    proportions = {
        "motor": 0.40,
        "pump": 0.25,
        "conveyor": 0.20,
        "tank": 0.10,
        "compressor": 0.05,
    }
    mix = {device_type: int(device_count * ratio) for device_type, ratio in proportions.items()}
    while sum(mix.values()) < device_count:
        for device_type in DEVICE_TYPES:
            mix[device_type] += 1
            if sum(mix.values()) == device_count:
                break
    return mix


def _parse_faults(raw: Any) -> FaultConfig:
    if raw is None:
        return FaultConfig(enabled=False, schedules=())
    if not isinstance(raw, dict):
        raise ConfigError("faults must be a mapping.")

    enabled = bool(raw.get("enabled", False))
    schedules_raw = raw.get("schedules", [])
    if not isinstance(schedules_raw, list):
        raise ConfigError("faults.schedules must be a list.")

    schedules = tuple(_parse_fault_schedule(item) for item in schedules_raw)
    return FaultConfig(enabled=enabled, schedules=schedules if enabled else ())


def _parse_fault_schedule(raw: Any) -> FaultSchedule:
    if not isinstance(raw, dict):
        raise ConfigError("Each fault schedule must be a mapping.")

    schedule = FaultSchedule(
        device_id=_required_str(raw, "deviceId"),
        anomaly_type=_required_str(raw, "anomalyType"),
        start_second=_required_float(raw, "startSecond"),
        warning_duration_seconds=_required_float(raw, "warningDurationSeconds"),
        fault_duration_seconds=_required_float(raw, "faultDurationSeconds"),
        recovery_duration_seconds=_required_float(raw, "recoveryDurationSeconds"),
    )
    durations = (
        schedule.warning_duration_seconds,
        schedule.fault_duration_seconds,
        schedule.recovery_duration_seconds,
    )
    if schedule.start_second < 0 or any(duration < 0 for duration in durations):
        raise ConfigError("Fault schedule times must be non-negative.")
    if schedule.warning_duration_seconds + schedule.fault_duration_seconds <= 0:
        raise ConfigError("Fault schedule must include warning or fault duration.")
    return schedule


def _parse_start_time(raw: Any) -> datetime:
    if raw is None:
        return datetime.now(timezone.utc)
    if not isinstance(raw, str):
        raise ConfigError("startTime must be an ISO-8601 timestamp string.")

    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError("startTime must be a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_config(config: SimulationConfig) -> None:
    if config.device_count <= 0:
        raise ConfigError("deviceCount must be greater than zero.")
    if config.target_messages_per_second <= 0:
        raise ConfigError("targetMessagesPerSecond must be greater than zero.")
    if config.duration_seconds <= 0:
        raise ConfigError("durationSeconds must be greater than zero.")
    if config.expected_message_count <= 0:
        raise ConfigError("Experiment must produce at least one message.")
    if config.until_stopped and config.run_mode == "file":
        raise ConfigError("untilStopped is only valid for opcua or both run modes.")
