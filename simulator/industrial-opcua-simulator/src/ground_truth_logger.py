from __future__ import annotations

import csv
import json
from contextlib import ExitStack
from pathlib import Path
from typing import Any


CSV_COLUMNS = [
    "experimentId",
    "scenario",
    "runId",
    "deviceId",
    "deviceType",
    "sequence",
    "sensorTimestamp",
    "edgeReceivedTimestamp",
    "normalizedTimestamp",
    "filteredTimestamp",
    "anomalyTimestamp",
    "cloudReceivedTimestamp",
    "temperature",
    "vibration",
    "rpm",
    "current",
    "load",
    "pressure",
    "flowRate",
    "speed",
    "motorCurrent",
    "level",
    "inletFlow",
    "outletFlow",
    "valveState",
    "status",
    "isAnomaly",
    "anomalyType",
]


class GroundTruthLogger:
    def __init__(self, output_path: Path, output_format: str) -> None:
        self.output_path = output_path
        self.output_format = output_format
        self._file = None
        self._csv_writer: csv.DictWriter[str] | None = None

    def __enter__(self) -> "GroundTruthLogger":
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.output_path.open("w", encoding="utf-8", newline="")
        if self.output_format == "csv":
            self._csv_writer = csv.DictWriter(self._file, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            self._csv_writer.writeheader()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._file is not None:
            self._file.close()

    def write(self, record: dict[str, Any]) -> None:
        if self._file is None:
            raise RuntimeError("GroundTruthLogger must be used as a context manager.")

        if self.output_format == "jsonl":
            self._file.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
            return

        if self._csv_writer is None:
            raise RuntimeError("CSV writer was not initialized.")
        self._csv_writer.writerow(_flatten_record(record))


class MultiGroundTruthLogger:
    def __init__(self, outputs: tuple[tuple[Path, str], ...]) -> None:
        self.outputs = outputs
        self._stack = ExitStack()
        self._loggers: list[GroundTruthLogger] = []

    def __enter__(self) -> "MultiGroundTruthLogger":
        for output_path, output_format in self.outputs:
            logger = GroundTruthLogger(output_path, output_format)
            self._loggers.append(self._stack.enter_context(logger))
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._stack.close()

    def write(self, record: dict[str, Any]) -> None:
        for logger in self._loggers:
            logger.write(record)


def _flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    values = record.get("values", {})
    ground_truth = record.get("groundTruth", {})
    row = {key: record.get(key) for key in CSV_COLUMNS}
    row.update({key: values.get(key) for key in values})
    row["isAnomaly"] = ground_truth.get("isAnomaly")
    row["anomalyType"] = ground_truth.get("anomalyType")
    return row
