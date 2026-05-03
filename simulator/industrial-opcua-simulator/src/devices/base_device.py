from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import numpy as np

from config_loader import FaultSchedule


class BaseDevice(ABC):
    def __init__(
        self,
        device_id: str,
        device_type: str,
        rng: np.random.Generator,
        experiment_id: str,
        scenario: str,
        run_id: str,
        fault_schedule: FaultSchedule | None = None,
    ) -> None:
        self.device_id = device_id
        self.device_type = device_type
        self.rng = rng
        self.experiment_id = experiment_id
        self.scenario = scenario
        self.run_id = run_id
        self.fault_schedule = fault_schedule
        self.sequence = 0
        self._last_elapsed_seconds: float | None = None

    def emit(self, sensor_timestamp: datetime, elapsed_seconds: float) -> dict[str, Any]:
        delta_seconds = self._delta_seconds(elapsed_seconds)
        state, anomaly_type, intensity = self._fault_context(elapsed_seconds)
        values = self._next_values(elapsed_seconds, delta_seconds, state, anomaly_type, intensity)
        values["status"] = state

        self.sequence += 1
        return {
            "experimentId": self.experiment_id,
            "scenario": self.scenario,
            "runId": self.run_id,
            "deviceId": self.device_id,
            "deviceType": self.device_type,
            "sequence": self.sequence,
            "sensorTimestamp": _format_timestamp(sensor_timestamp),
            "edgeReceivedTimestamp": None,
            "normalizedTimestamp": None,
            "filteredTimestamp": None,
            "anomalyTimestamp": None,
            "cloudReceivedTimestamp": None,
            "values": _round_values(values),
            "groundTruth": {
                "isAnomaly": state != "NORMAL",
                "anomalyType": anomaly_type if state != "NORMAL" else None,
            },
        }

    def _delta_seconds(self, elapsed_seconds: float) -> float:
        if self._last_elapsed_seconds is None:
            delta = 1.0
        else:
            delta = elapsed_seconds - self._last_elapsed_seconds
        self._last_elapsed_seconds = elapsed_seconds
        return min(max(delta, 0.001), 5.0)

    def _fault_context(self, elapsed_seconds: float) -> tuple[str, str | None, float]:
        if self.fault_schedule is None:
            return "NORMAL", None, 0.0
        state = self.fault_schedule.phase_at(elapsed_seconds)
        intensity = self.fault_schedule.intensity_at(elapsed_seconds)
        anomaly_type = self.fault_schedule.anomaly_type if state != "NORMAL" else None
        return state, anomaly_type, intensity

    def _noise(self, scale: float) -> float:
        return float(self.rng.normal(0.0, scale))

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    @abstractmethod
    def _next_values(
        self,
        elapsed_seconds: float,
        delta_seconds: float,
        state: str,
        anomaly_type: str | None,
        intensity: float,
    ) -> dict[str, Any]:
        raise NotImplementedError


def _format_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _round_values(values: dict[str, Any]) -> dict[str, Any]:
    rounded: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, float):
            rounded[key] = round(value, 4)
        else:
            rounded[key] = value
    return rounded
