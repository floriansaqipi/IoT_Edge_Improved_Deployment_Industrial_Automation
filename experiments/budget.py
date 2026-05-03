from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ALLOWED_CLOUD_OUTPUT_POLICIES = {"full", "sampled_10_percent", "capped"}
RAW_CLOUD_SCENARIOS = {"S0_CLOUD_ONLY", "S1_EDGE_PASS_THROUGH"}


class BudgetError(ValueError):
    """Raised when an experiment matrix would violate the daily cloud budget."""


@dataclass(frozen=True)
class BudgetLimits:
    daily_cloud_message_hard_limit: int
    planned_cloud_message_limit: int
    cloud_rate_limit_messages_per_second: float
    billable_message_chunk_bytes: int = 4096


@dataclass(frozen=True)
class ExperimentBudgetRow:
    id: str
    block: str
    scenario: str
    network_condition: str
    target_messages_per_second: float
    cloud_messages_per_second: float
    duration_seconds: float
    repetitions: int
    cloud_output_policy: str
    estimated_payload_bytes: int
    estimated_billable_messages: int

    @property
    def generated_messages(self) -> int:
        return math.ceil(self.target_messages_per_second * self.duration_seconds) * self.repetitions

    @property
    def cloud_events(self) -> int:
        return math.ceil(self.cloud_messages_per_second * self.duration_seconds) * self.repetitions


@dataclass(frozen=True)
class ExperimentBudgetMatrix:
    id: str
    description: str
    limits: BudgetLimits
    rows: tuple[ExperimentBudgetRow, ...]


@dataclass(frozen=True)
class BudgetReport:
    matrix_id: str
    row_count: int
    generated_messages: int
    planned_cloud_events: int
    estimated_billable_messages: int
    planned_cloud_message_limit: int
    daily_cloud_message_hard_limit: int
    cloud_rate_limit_messages_per_second: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "matrixId": self.matrix_id,
            "rowCount": self.row_count,
            "generatedMessages": self.generated_messages,
            "plannedCloudEvents": self.planned_cloud_events,
            "estimatedBillableMessages": self.estimated_billable_messages,
            "plannedCloudMessageLimit": self.planned_cloud_message_limit,
            "dailyCloudMessageHardLimit": self.daily_cloud_message_hard_limit,
            "cloudRateLimitMessagesPerSecond": self.cloud_rate_limit_messages_per_second,
        }


def billable_messages_for_payload(payload_bytes: int, chunk_bytes: int = 4096) -> int:
    if payload_bytes <= 0:
        raise BudgetError("payload_bytes must be greater than zero.")
    if chunk_bytes <= 0:
        raise BudgetError("chunk_bytes must be greater than zero.")
    return math.ceil(payload_bytes / chunk_bytes)


def estimate_row_billable_messages(row: ExperimentBudgetRow, limits: BudgetLimits) -> int:
    chunks_per_event = billable_messages_for_payload(
        row.estimated_payload_bytes,
        limits.billable_message_chunk_bytes,
    )
    return row.cloud_events * chunks_per_event


def load_budget_matrix(path: str | Path) -> ExperimentBudgetMatrix:
    matrix_path = Path(path)
    with matrix_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    if not isinstance(raw, dict):
        raise BudgetError("Matrix root must be a mapping.")

    limits = _parse_limits(raw)
    rows_raw = raw.get("experiments")
    if not isinstance(rows_raw, list) or not rows_raw:
        raise BudgetError("experiments must be a non-empty list.")

    rows = tuple(_parse_row(item) for item in rows_raw)
    return ExperimentBudgetMatrix(
        id=_required_str(raw, "id"),
        description=str(raw.get("description", "")).strip(),
        limits=limits,
        rows=rows,
    )


def preflight_budget_matrix(matrix: ExperimentBudgetMatrix) -> BudgetReport:
    errors: list[str] = []
    for row in matrix.rows:
        _validate_row(row, matrix.limits, errors)

    report = build_budget_report(matrix)
    if report.estimated_billable_messages > matrix.limits.planned_cloud_message_limit:
        errors.append(
            "Estimated billable messages "
            f"({report.estimated_billable_messages}) exceed plannedCloudMessageLimit "
            f"({matrix.limits.planned_cloud_message_limit})."
        )
    if report.estimated_billable_messages > matrix.limits.daily_cloud_message_hard_limit:
        errors.append(
            "Estimated billable messages "
            f"({report.estimated_billable_messages}) exceed dailyCloudMessageHardLimit "
            f"({matrix.limits.daily_cloud_message_hard_limit})."
        )

    if errors:
        raise BudgetError("\n".join(errors))
    return report


def build_budget_report(matrix: ExperimentBudgetMatrix) -> BudgetReport:
    return BudgetReport(
        matrix_id=matrix.id,
        row_count=len(matrix.rows),
        generated_messages=sum(row.generated_messages for row in matrix.rows),
        planned_cloud_events=sum(row.cloud_events for row in matrix.rows),
        estimated_billable_messages=sum(row.estimated_billable_messages for row in matrix.rows),
        planned_cloud_message_limit=matrix.limits.planned_cloud_message_limit,
        daily_cloud_message_hard_limit=matrix.limits.daily_cloud_message_hard_limit,
        cloud_rate_limit_messages_per_second=matrix.limits.cloud_rate_limit_messages_per_second,
    )


def _validate_row(row: ExperimentBudgetRow, limits: BudgetLimits, errors: list[str]) -> None:
    if row.cloud_output_policy not in ALLOWED_CLOUD_OUTPUT_POLICIES:
        errors.append(f"{row.id}: unsupported cloudOutputPolicy {row.cloud_output_policy!r}.")
    if row.scenario == "S3_EDGE_HEAVY":
        errors.append(f"{row.id}: S3 is deferred and must not appear in the budgeted matrix.")
    if row.scenario in RAW_CLOUD_SCENARIOS and row.cloud_messages_per_second > limits.cloud_rate_limit_messages_per_second:
        errors.append(
            f"{row.id}: {row.scenario} cloudMessagesPerSecond "
            f"({row.cloud_messages_per_second}) exceeds cloudRateLimitMessagesPerSecond "
            f"({limits.cloud_rate_limit_messages_per_second})."
        )
    calculated = estimate_row_billable_messages(row, limits)
    if row.estimated_billable_messages != calculated:
        errors.append(
            f"{row.id}: estimatedBillableMessages is {row.estimated_billable_messages}, "
            f"but calculated value is {calculated}."
        )


def _parse_limits(raw: dict[str, Any]) -> BudgetLimits:
    return BudgetLimits(
        daily_cloud_message_hard_limit=_required_int(raw, "dailyCloudMessageHardLimit"),
        planned_cloud_message_limit=_required_int(raw, "plannedCloudMessageLimit"),
        cloud_rate_limit_messages_per_second=_required_number(raw, "cloudRateLimitMessagesPerSecond"),
        billable_message_chunk_bytes=int(raw.get("billableMessageChunkBytes", 4096)),
    )


def _parse_row(raw: Any) -> ExperimentBudgetRow:
    if not isinstance(raw, dict):
        raise BudgetError("Each experiment row must be a mapping.")

    row = ExperimentBudgetRow(
        id=_required_str(raw, "id"),
        block=_required_str(raw, "block"),
        scenario=_required_str(raw, "scenario"),
        network_condition=_required_str(raw, "networkCondition"),
        target_messages_per_second=_required_number(raw, "targetMessagesPerSecond"),
        cloud_messages_per_second=_required_number(raw, "cloudMessagesPerSecond"),
        duration_seconds=_required_number(raw, "durationSeconds"),
        repetitions=_required_int(raw, "repetitions"),
        cloud_output_policy=_required_str(raw, "cloudOutputPolicy"),
        estimated_payload_bytes=_required_int(raw, "estimatedPayloadBytes"),
        estimated_billable_messages=_required_int(raw, "estimatedBillableMessages"),
    )
    if row.target_messages_per_second <= 0:
        raise BudgetError(f"{row.id}: targetMessagesPerSecond must be greater than zero.")
    if row.cloud_messages_per_second < 0:
        raise BudgetError(f"{row.id}: cloudMessagesPerSecond must not be negative.")
    if row.duration_seconds <= 0:
        raise BudgetError(f"{row.id}: durationSeconds must be greater than zero.")
    if row.repetitions <= 0:
        raise BudgetError(f"{row.id}: repetitions must be greater than zero.")
    if row.estimated_payload_bytes <= 0:
        raise BudgetError(f"{row.id}: estimatedPayloadBytes must be greater than zero.")
    return row


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BudgetError(f"{key} must be a non-empty string.")
    return value.strip()


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise BudgetError(f"{key} must be an integer.")
    return value


def _required_number(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)):
        raise BudgetError(f"{key} must be numeric.")
    return float(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the budgeted Azure IoT Edge experiment matrix.")
    parser.add_argument(
        "matrix",
        nargs="?",
        default=Path("experiments") / "budgeted_800k_matrix.yaml",
        type=Path,
        help="Path to the experiment matrix YAML file.",
    )
    parser.add_argument("--json", action="store_true", help="Print the preflight report as JSON.")
    args = parser.parse_args()

    try:
        report = preflight_budget_matrix(load_budget_matrix(args.matrix))
    except BudgetError as exc:
        print(f"Budget preflight failed:\n{exc}")
        return 2

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print("Budget preflight passed.")
        for key, value in report.as_dict().items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
