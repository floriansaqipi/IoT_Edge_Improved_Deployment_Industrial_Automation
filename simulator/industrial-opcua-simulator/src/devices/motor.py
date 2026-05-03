from __future__ import annotations

from typing import Any

import numpy as np

from devices.base_device import BaseDevice


class Motor(BaseDevice):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_load = float(self.rng.uniform(45.0, 68.0))
        self.temperature = float(self.rng.uniform(58.0, 66.0))
        self.vibration_base = float(self.rng.uniform(0.18, 0.34))
        self.rpm_base = float(self.rng.uniform(1460.0, 1490.0))

    def _next_values(
        self,
        elapsed_seconds: float,
        delta_seconds: float,
        state: str,
        anomaly_type: str | None,
        intensity: float,
    ) -> dict[str, Any]:
        load_wave = 5.0 * np.sin(elapsed_seconds / 9.0)
        load = self.base_load + load_wave + self._noise(1.4)
        fault_heat = 0.0
        vibration_fault = 0.0

        if anomaly_type == "overload":
            load += 25.0 * intensity
            fault_heat += 0.8 * intensity
        elif anomaly_type == "overheating":
            fault_heat += 1.4 * intensity
        elif anomaly_type == "bearing_fault":
            vibration_fault += 1.05 * intensity
            fault_heat += 0.55 * intensity

        load = self._clamp(load, 25.0, 115.0)
        current = 4.7 + 0.065 * load + 1.1 * intensity + self._noise(0.18)
        cooling = 0.035 * (self.temperature - 24.0)
        thermal_gain = 0.018 * max(load - 45.0, 0.0) + fault_heat
        self.temperature += (thermal_gain - cooling) * delta_seconds + self._noise(0.08)
        self.temperature = self._clamp(self.temperature, 35.0, 115.0)
        vibration = self.vibration_base + 0.0025 * max(load - 55.0, 0.0) + vibration_fault + self._noise(0.025)
        rpm = self.rpm_base - 0.42 * load - 6.0 * intensity + self._noise(4.0)

        return {
            "temperature": self._clamp(self.temperature, 35.0, 115.0),
            "vibration": self._clamp(vibration, 0.02, 2.5),
            "rpm": self._clamp(rpm, 1200.0, 1520.0),
            "current": self._clamp(current, 2.0, 18.0),
            "load": self._clamp(load, 0.0, 120.0),
        }
