from __future__ import annotations

from typing import Any

import numpy as np

from devices.base_device import BaseDevice


class Tank(BaseDevice):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.level = float(self.rng.uniform(35.0, 65.0))
        self.pressure_base = float(self.rng.uniform(1.3, 2.0))
        self.inlet_base = float(self.rng.uniform(14.0, 24.0))
        self.outlet_base = float(self.rng.uniform(14.0, 24.0))

    def _next_values(
        self,
        elapsed_seconds: float,
        delta_seconds: float,
        state: str,
        anomaly_type: str | None,
        intensity: float,
    ) -> dict[str, Any]:
        inlet_flow = self.inlet_base + 2.5 * np.sin(elapsed_seconds / 11.0) + self._noise(0.35)
        outlet_flow = self.outlet_base + 2.0 * np.sin(elapsed_seconds / 13.0) + self._noise(0.35)
        valve_state = "OPEN"

        if anomaly_type == "overflow_risk":
            inlet_flow += 8.5 * intensity
            outlet_flow -= 11.0 * intensity
            valve_state = "RESTRICTED" if state != "FAULT" else "CLOSED"

        level_delta = (inlet_flow - outlet_flow) * 0.09 * delta_seconds
        self.level += level_delta + self._noise(0.03)
        self.level = self._clamp(self.level, 0.0, 105.0)
        pressure = self.pressure_base + 0.018 * self.level + 0.35 * intensity + self._noise(0.04)

        return {
            "level": self._clamp(self.level, 0.0, 105.0),
            "pressure": self._clamp(pressure, 0.4, 5.0),
            "inletFlow": self._clamp(inlet_flow, 0.0, 45.0),
            "outletFlow": self._clamp(outlet_flow, 0.0, 45.0),
            "valveState": valve_state,
        }
