from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from experiments.budget import load_budget_matrix, preflight_budget_matrix
from experiments.controller.models import ControllerSettings, PlannedRun
from experiments.controller.network import build_network_plan, outage_schedule_seconds
from experiments.controller.planner import (
    build_run_manifest,
    build_simulator_config,
    expand_runs,
    load_and_validate_matrix,
    scenario_actions,
)
from experiments.controller.status import StatusStore, read_status


ROOT = Path(__file__).resolve().parents[1]
EDGE_SRC = ROOT / "edge" / "modules" / "opcua-collector" / "src"
MATRIX_PATH = ROOT / "experiments" / "budgeted_800k_matrix.yaml"

if str(EDGE_SRC) not in sys.path:
    sys.path.insert(0, str(EDGE_SRC))

from opcua_collector.collector import _CloudOutputLimiter  # noqa: E402


def test_phase6_matrix_expands_to_36_planned_runs() -> None:
    matrix = load_and_validate_matrix(MATRIX_PATH)
    runs = expand_runs(matrix, campaign_id="campaign_test")

    assert len(runs) == 36
    assert runs[0].run_id == "s0_90_normal_rep1_campaign_test"
    assert runs[-1].run_id == "s2_500_stress_capped_rep3_campaign_test"


def test_phase6_selected_row_and_repetition_are_deterministic() -> None:
    matrix = load_and_validate_matrix(MATRIX_PATH)
    runs = expand_runs(matrix, "campaign_x", row_filter="s1_90_delay_200", repetition_filter=2)

    assert [run.run_id for run in runs] == ["s1_90_delay_200_rep2_campaign_x"]


def test_phase6_smoke_mode_selects_one_short_normal_run_per_scenario() -> None:
    from experiments.controller.cli import _smoke_runs

    matrix = load_and_validate_matrix(MATRIX_PATH)
    smoke = _smoke_runs(expand_runs(matrix, "campaign_smoke"))

    assert [run.scenario for run in smoke] == ["S0_CLOUD_ONLY", "S1_EDGE_PASS_THROUGH", "S2_HYBRID"]
    assert [run.repetition for run in smoke] == [1, 1, 1]
    assert [run.duration_seconds for run in smoke] == [60, 60, 60]


def test_phase6_preflight_rejects_s3_rows() -> None:
    matrix = load_budget_matrix(MATRIX_PATH)
    invalid = matrix.rows[0].__class__(
        **{**matrix.rows[0].__dict__, "scenario": "S3_EDGE_HEAVY", "id": "bad_s3"}
    )
    invalid_matrix = matrix.__class__(id=matrix.id, description=matrix.description, limits=matrix.limits, rows=(invalid,))

    with pytest.raises(Exception, match="S3"):
        preflight_budget_matrix(invalid_matrix)


def test_phase6_scenario_actions_match_s0_s1_s2() -> None:
    assert "s0-cloud-publisher" in " ".join(scenario_actions(_run("S0_CLOUD_ONLY")))
    assert "S1 Edge" in " ".join(scenario_actions(_run("S1_EDGE_PASS_THROUGH")))
    assert "edge microservices" in " ".join(scenario_actions(_run("S2_HYBRID")))


def test_phase6_network_commands_are_cloud_bound_and_reversible() -> None:
    delay = build_network_plan("delay_200ms", "hub.azure-devices.net", 300)
    outage = build_network_plan("cloud_outage_120s", "hub.azure-devices.net", 300)
    loss = build_network_plan("packet_loss_2", "hub.azure-devices.net", 300)

    assert delay.apply_command is not None
    assert "hub.azure-devices.net" in delay.apply_command
    assert "4840" not in delay.apply_command
    assert "clear" in delay.clear_command
    assert outage.outage_start_second == 90
    assert outage.outage_duration_second == 120
    assert outage.recovery_duration_second == 90
    assert loss.apply_command is not None
    assert "packet_loss_2" in loss.apply_command


def test_phase6_outage_schedule_scales_for_short_smoke_runs() -> None:
    assert outage_schedule_seconds(300) == (90, 120, 90)
    assert outage_schedule_seconds(30) == (9, 12, 9)


def test_phase6_run_manifest_and_simulator_config_paths(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = _run("S2_HYBRID")
    run_dir = tmp_path / "campaign" / run.row_id / "rep_1"

    manifest = build_run_manifest(run, settings, run_dir)
    simulator = build_simulator_config(run, settings, run_dir)

    assert manifest["run"]["runId"] == run.run_id
    assert manifest["network"]["condition"] == "normal"
    assert simulator["runMode"] == "both"
    assert simulator["outputs"][0]["format"] == "jsonl"
    assert simulator["outputs"][1]["format"] == "csv"
    assert simulator["scenario"] == "S2_HYBRID"


def test_phase6_status_files_are_readable_from_another_process(tmp_path: Path) -> None:
    store = StatusStore(tmp_path, "campaign_status")
    run_dir = tmp_path / "campaign_status" / "row" / "rep_1"

    store.write_latest({"status": "running", "plannedRunCount": 1})
    store.write_run_status(run_dir, "completed", {"run": {"runId": "r1"}})
    store.append_event(run_dir, "completed")

    status = read_status(tmp_path, "latest")

    assert status["campaignId"] == "campaign_status"
    assert status["completed"] == 1
    assert status["runCount"] == 1
    assert (run_dir / "events.jsonl").exists()


def test_phase6_s1_collector_limiter_strictly_caps_cloud_output() -> None:
    limiter = _CloudOutputLimiter(policy="full", max_messages_per_second=2)
    normal = {"sequence": 1, "groundTruth": {"isAnomaly": False}}
    anomaly = {"sequence": 3, "groundTruth": {"isAnomaly": True}}

    assert limiter.should_forward(normal, 0.0)
    assert limiter.should_forward(normal, 0.1)
    assert not limiter.should_forward(normal, 0.2)
    assert not limiter.should_forward(anomaly, 0.3)
    assert limiter.should_forward(normal, 1.0)


def test_phase6_dry_run_shape_has_no_mutation_commands(tmp_path: Path) -> None:
    from experiments.controller.runner import ExperimentRunner

    matrix = load_and_validate_matrix(MATRIX_PATH)
    runs = expand_runs(matrix, "campaign_dry", row_filter="s0_90_normal", repetition_filter=1)
    dry = ExperimentRunner(_settings(tmp_path), matrix, runs, "campaign_dry").dry_run()

    assert dry["plannedRunCount"] == 1
    assert dry["plannedRuns"][0]["scenario"] == "S0_CLOUD_ONLY"
    assert dry["matrix"]["estimatedBillableMessages"] == 544_320
    json.dumps(dry)


def _run(scenario: str) -> PlannedRun:
    return PlannedRun(
        campaign_id="campaign_test",
        matrix_id="budgeted_800k_s0_s1_s2",
        row_id="row",
        block="normal_network",
        scenario=scenario,
        network_condition="normal",
        target_messages_per_second=90,
        cloud_messages_per_second=90 if scenario != "S2_HYBRID" else 9,
        duration_seconds=300,
        repetition=1,
        repetitions=3,
        cloud_output_policy="full" if scenario != "S2_HYBRID" else "sampled_10_percent",
        estimated_billable_messages=27_000,
    )


def _settings(tmp_path: Path) -> ControllerSettings:
    return ControllerSettings(
        repo_root=ROOT,
        results_root=tmp_path,
        matrix_path=MATRIX_PATH,
        acr_username="user",
        acr_password="password",
    )
