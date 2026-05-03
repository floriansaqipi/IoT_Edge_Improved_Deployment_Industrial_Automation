from __future__ import annotations

from typing import Any

import numpy as np

from devices.base_device import BaseDevice


class Pump(BaseDevice):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pressure_base = float(self.rng.uniform(3.0, 4.0))
        self.flow_base = float(self.rng.uniform(26.0, 36.0))
        self.temperature = float(self.rng.uniform(48.0, 56.0))
        self.vibration_base = float(self.rng.uniform(0.15, 0.28))

    def _next_values(
        self,
        elapsed_seconds: float,
        delta_seconds: float,
        state: str,
        anomaly_type: str | None,
        intensity: float,
    ) -> dict[str, Any]:
        demand = 1.0 + 0.08 * np.sin(elapsed_seconds / 8.0)
        pressure = self.pressure_base * demand + self._noise(0.05)
        flow_rate = self.flow_base * demand + self._noise(0.45)
        current_extra = 0.0
        heat_extra = 0.0

        if anomaly_type == "blockage":
            pressure += 2.1 * intensity
            flow_rate -= 17.0 * intensity
            current_extra += 3.4 * intensity
            heat_extra += 0.7 * intensity
        elif anomaly_type in {"pressure_drop", "leak"}:
            pressure -= 1.5 * intensity
            flow_rate -= 11.5 * intensity
            current_extra += 0.7 * intensity

        current = 3.8 + 0.42 * max(pressure, 0.0) + 0.035 * max(flow_rate, 0.0) + current_extra + self._noise(0.12)
        self.temperature += (0.02 * current + heat_extra - 0.055 * (self.temperature - 24.0)) * delta_seconds
        self.temperature += self._noise(0.06)
        self.temperature = self._clamp(self.temperature, 35.0, 95.0)
        vibration = self.vibration_base + 0.025 * max(current - 6.0, 0.0) + 0.25 * intensity + self._noise(0.02)

        return {
            "pressure": self._clamp(pressure, 0.2, 7.5),
            "flowRate": self._clamp(flow_rate, 0.0, 50.0),
            "temperature": self._clamp(self.temperature, 35.0, 95.0),
            "vibration": self._clamp(vibration, 0.02, 1.8),
            "current": self._clamp(current, 1.0, 16.0),
        }
