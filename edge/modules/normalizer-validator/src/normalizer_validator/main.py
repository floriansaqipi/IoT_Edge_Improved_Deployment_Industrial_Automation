from __future__ import annotations

import logging

from edge_study_common.messages import OutputMessage, copy_record, utc_now, validate_telemetry
from edge_study_common.runtime import run_main


logger = logging.getLogger(__name__)


def process_record(record: dict) -> list[OutputMessage]:
    errors = validate_telemetry(record)
    if errors:
        logger.warning("Dropping invalid telemetry from %s: %s", record.get("deviceId", "<unknown>"), "; ".join(errors))
        return []

    normalized = copy_record(record)
    normalized["normalizedTimestamp"] = utc_now()
    normalized.setdefault("filteredTimestamp", None)
    normalized.setdefault("anomalyTimestamp", None)
    normalized.setdefault("cloudReceivedTimestamp", None)
    return [OutputMessage("normalized", normalized)]


def main() -> int:
    return run_main("input1", process_record)


if __name__ == "__main__":
    raise SystemExit(main())
