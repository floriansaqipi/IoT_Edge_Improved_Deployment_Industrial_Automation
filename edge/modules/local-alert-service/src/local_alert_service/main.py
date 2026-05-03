from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from edge_study_common.messages import OutputMessage, json_payload, utc_now
from edge_study_common.runtime import run_main


DEFAULT_ALERT_LOG_PATH = Path("/var/lib/edge-study/alerts/s2_alerts.jsonl")


class LocalAlertService:
    def __init__(self, alert_log_path: Path = DEFAULT_ALERT_LOG_PATH) -> None:
        self.alert_log_path = alert_log_path

    @classmethod
    def from_env(cls) -> "LocalAlertService":
        return cls(Path(os.getenv("ALERT_LOG_PATH", str(DEFAULT_ALERT_LOG_PATH))))

    def process_record(self, record: dict[str, Any]) -> list[OutputMessage]:
        alert = build_alert(record)
        self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.alert_log_path.open("a", encoding="utf-8") as file:
            file.write(json_payload(alert) + "\n")
        return [OutputMessage("alerts", alert)]


def build_alert(record: dict[str, Any]) -> dict[str, Any]:
    detection = record.get("edgeDetection", {})
    return {
        "messageType": "alert",
        "experimentId": record.get("experimentId"),
        "scenario": record.get("scenario"),
        "runId": record.get("runId"),
        "deviceId": record.get("deviceId"),
        "deviceType": record.get("deviceType"),
        "sequence": record.get("sequence"),
        "sensorTimestamp": record.get("sensorTimestamp"),
        "edgeReceivedTimestamp": record.get("edgeReceivedTimestamp"),
        "normalizedTimestamp": record.get("normalizedTimestamp"),
        "filteredTimestamp": record.get("filteredTimestamp"),
        "anomalyTimestamp": record.get("anomalyTimestamp"),
        "alertTimestamp": utc_now(),
        "edgeDetection": detection,
        "groundTruth": record.get("groundTruth"),
    }


_SERVICE = LocalAlertService.from_env()


def process_record(record: dict[str, Any]) -> list[OutputMessage]:
    return _SERVICE.process_record(record)


def main() -> int:
    return run_main("input1", process_record)


if __name__ == "__main__":
    raise SystemExit(main())
