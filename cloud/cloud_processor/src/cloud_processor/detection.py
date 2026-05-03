from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DetectionResult:
    is_anomaly: bool
    anomaly_type: str | None
    severity: str
    score: float
    matched_rules: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "isAnomaly": self.is_anomaly,
            "anomalyType": self.anomaly_type,
            "severity": self.severity,
            "score": self.score,
            "matchedRules": list(self.matched_rules),
        }


def detect_anomaly(record: dict[str, Any]) -> DetectionResult:
    device_type = str(record.get("deviceType", ""))
    values = record.get("values", {})
    if not isinstance(values, dict):
        return DetectionResult(False, None, "none", 0.0, ())

    matches: list[tuple[str, str, str, float]] = []
    if device_type == "motor":
        _add(matches, values.get("temperature", 0) >= 85, "motor.overheating", "overheating", "critical", 0.95)
        _add(matches, values.get("vibration", 0) >= 1.0, "motor.bearing_fault", "bearing_fault", "critical", 0.92)
        _add(
            matches,
            values.get("current", 0) >= 12 or values.get("load", 0) >= 90,
            "motor.overload",
            "overload",
            "warning",
            0.82,
        )
    elif device_type == "pump":
        _add(
            matches,
            values.get("pressure", 0) >= 5.0 and values.get("flowRate", 99) <= 20,
            "pump.blockage",
            "blockage",
            "critical",
            0.93,
        )
        _add(
            matches,
            values.get("pressure", 99) <= 2.0 or values.get("flowRate", 99) <= 15,
            "pump.pressure_drop",
            "pressure_drop",
            "warning",
            0.78,
        )
    elif device_type == "conveyor":
        _add(
            matches,
            values.get("speed", 99) <= 0.8 and (values.get("motorCurrent", 0) >= 10 or values.get("load", 0) >= 90),
            "conveyor.jam",
            "jam",
            "critical",
            0.91,
        )
    elif device_type == "tank":
        _add(
            matches,
            values.get("level", 0) >= 90 and values.get("outletFlow", 99) <= 12,
            "tank.overflow_risk",
            "overflow_risk",
            "critical",
            0.9,
        )
    elif device_type == "compressor":
        _add(
            matches,
            values.get("pressure", 0) >= 8.8 or values.get("vibration", 0) >= 1.0 or values.get("current", 0) >= 10.5,
            "compressor.pressure_instability",
            "pressure_instability",
            "warning",
            0.84,
        )

    if not matches:
        return DetectionResult(False, None, "none", 0.0, ())
    best = max(matches, key=lambda item: item[3])
    return DetectionResult(True, best[1], best[2], best[3], tuple(match[0] for match in matches))


def _add(
    matches: list[tuple[str, str, str, float]],
    condition: bool,
    rule_name: str,
    anomaly_type: str,
    severity: str,
    score: float,
) -> None:
    if condition:
        matches.append((rule_name, anomaly_type, severity, score))
