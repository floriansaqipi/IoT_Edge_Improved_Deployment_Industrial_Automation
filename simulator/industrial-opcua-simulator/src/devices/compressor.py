from __future__ import annotations

from typing import Any

import numpy as np

from devices.base_device import BaseDevice


class Compressor(BaseDevice):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pressure_base = float(self.rng.uniform(5.5, 7.5))
        self.temperature = float(self.rng.uniform(58.0, 68.0))
        self.vibration_base = float(self.rng.uniform(0.18, 0.34))

    def _next_values(
        self,
        elapsed_seconds: float,
        delta_seconds: float,
        state: str,
        anomaly_type: str | None,
        intensity: float,
    ) -> dict[str, Any]:
        pressure_wave = 0.28 * np.sin(elapsed_seconds / 4.0)
        instability = 0.0
        if anomaly_type == "pressure_instability":
            instability = intensity * (1.6 * np.sin(elapsed_seconds * 7.0) + 0.7 * np.sin(elapsed_seconds * 13.0))

        pressure = self.pressure_base + pressure_wave + instability + self._noise(0.08)
        current = 4.8 + 0.52 * max(pressure, 0.0) + 1.4 * intensity + self._noise(0.14)
        self.temperature += (0.025 * current + 0.45 * intensity - 0.045 * (self.temperature - 24.0)) * delta_seconds
        self.temperature += self._noise(0.06)
        self.temperature = self._clamp(self.temperature, 40.0, 110.0)
        vibration = self.vibration_base + 0.025 * max(current - 7.0, 0.0) + 0.55 * intensity + self._noise(0.025)

        return {
            "pressure": self._clamp(pressure, 2.0, 11.0),
            "temperature": self._clamp(self.temperature, 40.0, 110.0),
            "vibration": self._clamp(vibration, 0.02, 2.0),
            "current": self._clamp(current, 2.0, 18.0),
        }
