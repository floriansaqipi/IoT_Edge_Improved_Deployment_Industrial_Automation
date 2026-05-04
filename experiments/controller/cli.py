from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .config import load_controller_settings
from .planner import expand_runs, load_and_validate_matrix
from .runner import ExperimentRunner
from .status import read_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the budgeted Azure IoT Edge experiment controller.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one or more planned experiments.")
    _add_common_run_args(run_parser)
    run_parser.add_argument("--mode", choices=("full", "smoke"), default="full")
    run_parser.add_argument("--rerun-completed", action="store_true")
    run_parser.add_argument("--leave-scenario-running", action="store_true")

    dry_parser = subparsers.add_parser("dry-run", help="Print planned actions without mutating external systems.")
    _add_common_run_args(dry_parser)

    status_parser = subparsers.add_parser("status", help="Read campaign progress files.")
    status_parser.add_argument("--campaign", default="latest")
    status_parser.add_argument("--results-root", type=Path, default=Path("results") / "experiments")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    if args.command == "status":
        print(json.dumps(read_status(repo_root / args.results_root, args.campaign), indent=2, sort_keys=True))
        return 0

    matrix_path = repo_root / args.matrix
    campaign_id = args.campaign_id or _campaign_id()
    settings = load_controller_settings(
        repo_root=repo_root,
        matrix_path=matrix_path,
        results_root=repo_root / args.results_root,
        env_file=repo_root / args.env_file if args.env_file else None,
    )
    matrix = load_and_validate_matrix(matrix_path)
    runs = expand_runs(
        matrix,
        campaign_id=campaign_id,
        row_filter=args.row,
        block_filter=args.block,
        scenario_filter=args.scenario,
        repetition_filter=args.rep,
    )
    if args.command == "run" and args.mode == "smoke":
        runs = _smoke_runs(runs)

    runner = ExperimentRunner(settings, matrix, runs, campaign_id)
    if args.command == "dry-run":
        print(json.dumps(runner.dry_run(), indent=2, sort_keys=True))
        return 0
    return runner.run(
        rerun_completed=args.rerun_completed,
        leave_scenario_running=args.leave_scenario_running,
    )


def _add_common_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--matrix", type=Path, default=Path("experiments") / "budgeted_800k_matrix.yaml")
    parser.add_argument("--results-root", type=Path, default=Path("results") / "experiments")
    parser.add_argument("--env-file", type=Path, default=Path(".env.experiment.local"))
    parser.add_argument("--campaign-id")
    parser.add_argument("--row")
    parser.add_argument("--block")
    parser.add_argument("--scenario", choices=("S0_CLOUD_ONLY", "S1_EDGE_PASS_THROUGH", "S2_HYBRID"))
    parser.add_argument("--rep", type=int)


def _campaign_id() -> str:
    return "campaign_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _smoke_runs(runs: tuple) -> tuple:
    selected = []
    seen_scenarios = set()
    for run in runs:
        if run.network_condition != "normal" or run.repetition != 1 or run.scenario in seen_scenarios:
            continue
        selected.append(replace(run, duration_seconds=min(run.duration_seconds, 60)))
        seen_scenarios.add(run.scenario)
        if len(selected) == 3:
            break
    return tuple(selected)
