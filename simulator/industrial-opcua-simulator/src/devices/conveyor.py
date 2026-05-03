from __future__ import annotations

from typing import Any

import numpy as np

from devices.base_device import BaseDevice


class Conveyor(BaseDevice):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.speed_base = float(self.rng.uniform(1.25, 1.85))
        self.load_base = float(self.rng.uniform(42.0, 70.0))
        self.vibration_base = float(self.rng.uniform(0.18, 0.36))

    def _next_values(
        self,
        elapsed_seconds: float,
        delta_seconds: float,
        state: str,
        anomaly_type: str | None,
        intensity: float,
    ) -> dict[str, Any]:
        load = self.load_base + 8.0 * np.sin(elapsed_seconds / 7.0) + self._noise(1.5)
        speed = self.speed_base + 0.08 * np.sin(elapsed_seconds / 5.0) + self._noise(0.025)
        vibration_extra = 0.0

        if anomaly_type == "jam":
            speed -= 0.95 * intensity
            load += 38.0 * intensity
            vibration_extra += 0.75 * intensity

        load = self._clamp(load, 10.0, 120.0)
        speed = self._clamp(speed, 0.0, 2.3)
        motor_current = 2.8 + 0.085 * load + 2.5 * intensity + self._noise(0.16)
        vibration = self.vibration_base + 0.003 * load + vibration_extra + self._noise(0.025)

        return {
            "speed": self._clamp(speed, 0.0, 2.3),
            "load": self._clamp(load, 0.0, 120.0),
            "motorCurrent": self._clamp(motor_current, 1.0, 18.0),
            "vibration": self._clamp(vibration, 0.02, 2.0),
        }
