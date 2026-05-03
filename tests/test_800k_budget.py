from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from experiments.budget import (
    BudgetError,
    billable_messages_for_payload,
    load_budget_matrix,
    preflight_budget_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
COMMON_EDGE_SRC = ROOT / "edge" / "modules" / "common" / "src"
MATRIX_PATH = ROOT / "experiments" / "budgeted_800k_matrix.yaml"

if str(COMMON_EDGE_SRC) not in sys.path:
    sys.path.insert(0, str(COMMON_EDGE_SRC))

from edge_study_common.cloud_output_policy import CloudOutputLimiter  # noqa: E402


def test_budgeted_matrix_stays_under_800k_limits() -> None:
    report = preflight_budget_matrix(load_budget_matrix(MATRIX_PATH))

    assert report.estimated_billable_messages == 544_320
    assert report.estimated_billable_messages < 640_000
    assert report.estimated_billable_messages < 800_000
    assert report.planned_cloud_events == 544_320
    assert report.row_count == 12


def test_payload_metering_uses_4kb_chunks() -> None:
    assert billable_messages_for_payload(1) == 1
    assert billable_messages_for_payload(4096) == 1
    assert billable_messages_for_payload(4097) == 2
    assert billable_messages_for_payload(8192) == 2


def test_preflight_rejects_over_budget_matrix() -> None:
    matrix = load_budget_matrix(MATRIX_PATH)
    first_row = matrix.rows[0]
    over_budget_row = replace(first_row, estimated_billable_messages=700_000)
    over_budget_matrix = replace(matrix, rows=(over_budget_row, *matrix.rows[1:]))

    with pytest.raises(BudgetError, match="plannedCloudMessageLimit"):
        preflight_budget_matrix(over_budget_matrix)


def test_preflight_rejects_raw_cloud_rate_above_limit() -> None:
    matrix = load_budget_matrix(MATRIX_PATH)
    first_row = matrix.rows[0]
    invalid_row = replace(
        first_row,
        cloud_messages_per_second=91,
        estimated_billable_messages=81_900,
    )
    invalid_matrix = replace(matrix, rows=(invalid_row, *matrix.rows[1:]))

    with pytest.raises(BudgetError, match="cloudMessagesPerSecond"):
        preflight_budget_matrix(invalid_matrix)


def test_s2_sampling_keeps_every_tenth_message_and_alerts() -> None:
    limiter = CloudOutputLimiter(policy="sampled_10_percent")
    forwarded_sequences = [
        sequence
        for sequence in range(1, 31)
        if limiter.should_forward({"sequence": sequence, "groundTruth": {"isAnomaly": False}}, sequence / 90)
    ]

    assert forwarded_sequences == [10, 20, 30]
    assert limiter.should_forward(
        {"sequence": 31, "groundTruth": {"isAnomaly": True}},
        elapsed_seconds=1.0,
    )


def test_cloud_output_cap_limits_non_alerts_but_not_alerts() -> None:
    limiter = CloudOutputLimiter(policy="capped", max_messages_per_second=2)
    normal = {"sequence": 1, "groundTruth": {"isAnomaly": False}}
    alert = {"sequence": 4, "groundTruth": {"isAnomaly": True}}

    assert limiter.should_forward(normal, elapsed_seconds=0.0)
    assert limiter.should_forward(normal, elapsed_seconds=0.1)
    assert not limiter.should_forward(normal, elapsed_seconds=0.2)
    assert limiter.should_forward(alert, elapsed_seconds=0.3)
    assert limiter.should_forward(normal, elapsed_seconds=1.0)
