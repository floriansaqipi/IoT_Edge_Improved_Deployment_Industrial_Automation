from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from experiments.budget import build_budget_report

from .manifest import render_edge_manifest
from .models import SCENARIO_S0, SCENARIO_S1, SCENARIO_S2, ControllerSettings, PlannedRun
from .network import build_network_plan
from .planner import (
    SIMULATOR_WARMUP_SECONDS,
    build_run_manifest,
    build_simulator_config,
    scenario_actions,
    write_json,
    write_yaml,
)
from .status import StatusStore, utc_now


POST_RUN_CLOUD_SETTLE_SECONDS = 60


class ExperimentRunner:
    def __init__(
        self,
        settings: ControllerSettings,
        matrix: Any,
        runs: tuple[PlannedRun, ...],
        campaign_id: str,
    ) -> None:
        self.settings = settings
        self.matrix = matrix
        self.runs = runs
        self.campaign_id = campaign_id
        self.status = StatusStore(settings.results_root, campaign_id)

    def dry_run(self) -> dict[str, Any]:
        report = build_budget_report(self.matrix)
        return {
            "campaignId": self.campaign_id,
            "matrix": report.as_dict(),
            "plannedRunCount": len(self.runs),
            "plannedRuns": [
                {
                    **run.as_dict(),
                    "actions": scenario_actions(run),
                    "network": build_network_plan(
                        run.network_condition,
                        self.settings.iot_hub_host,
                        run.duration_seconds,
                    ).as_dict(),
                }
                for run in self.runs
            ],
        }

    def run(self, rerun_completed: bool = False, leave_scenario_running: bool = False) -> int:
        self._preflight()
        completed = 0
        self.status.write_latest({"status": "running", "plannedRunCount": len(self.runs), "completed": 0})
        for index, planned_run in enumerate(self.runs, start=1):
            run_dir = self._run_dir(planned_run)
            if (run_dir / "run_summary.json").exists() and not rerun_completed:
                completed += 1
                self.status.write_latest(
                    {
                        "status": "running",
                        "plannedRunCount": len(self.runs),
                        "completed": completed,
                        "currentRun": planned_run.as_dict(),
                    }
                )
                continue
            try:
                self._run_one(planned_run, run_dir, index, len(self.runs), leave_scenario_running)
                completed += 1
            except Exception as exc:
                self.status.write_run_status(run_dir, "failed", {"run": planned_run.as_dict(), "error": str(exc)})
                self.status.append_event(run_dir, "failed", {"error": str(exc)})
                self._cleanup_after_run(planned_run, run_dir, leave_scenario_running=False)
                raise
            self.status.write_latest(
                {
                    "status": "running",
                    "plannedRunCount": len(self.runs),
                    "completed": completed,
                    "currentRun": planned_run.as_dict(),
                }
            )
        self.status.write_latest({"status": "completed", "plannedRunCount": len(self.runs), "completed": completed})
        return 0

    def _preflight(self) -> None:
        preflight_dir = self.settings.results_root / self.campaign_id / "preflight"
        preflight_dir.mkdir(parents=True, exist_ok=True)
        self._run_local(["az", "account", "show"], check=False, capture=True)
        self._collect_preflight_iothub_metrics(preflight_dir)
        self._run_local(
            [
                sys.executable,
                str(self.settings.repo_root / "simulator" / "industrial-opcua-simulator" / "src" / "main.py"),
                "--help",
            ],
            check=True,
            capture=True,
        )
        if not self.settings.machine_b_user:
            raise RuntimeError("MACHINE_B_USER is required for real experiment runs.")
        self._install_remote_network_script()
        self._ssh("hostname", check=True)
        self._ssh(f"nc -vz -w 5 {self.settings.machine_a_ip} 4840", check=False)

    def _run_one(
        self,
        planned_run: PlannedRun,
        run_dir: Path,
        index: int,
        total: int,
        leave_scenario_running: bool,
    ) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        self.status.write_run_status(
            run_dir,
            "running",
            {"run": planned_run.as_dict(), "index": index, "total": total, "startedAt": utc_now()},
        )
        self.status.append_event(run_dir, "run_started", planned_run.as_dict())
        self._collect_iothub_metrics(run_dir / "iot_hub_metrics_before.json")

        write_json(run_dir / "run_manifest.json", build_run_manifest(planned_run, self.settings, run_dir))
        simulator_config_path = run_dir / "simulator_config.yaml"
        write_yaml(simulator_config_path, build_simulator_config(planned_run, self.settings, run_dir))

        edge_manifest_path = run_dir / f"{planned_run.scenario.lower()}_deployment.generated.json"
        render_edge_manifest(planned_run, self.settings, edge_manifest_path)

        self._start_scenario(planned_run, edge_manifest_path, run_dir)
        self._wait_for_scenario_ready(planned_run, run_dir)
        simulator, simulator_started_at = self._start_simulator(simulator_config_path, run_dir)
        try:
            self._ssh(
                f"nc -vz -w 5 {self.settings.machine_a_ip} 4840",
                check=True,
                log_path=run_dir / "opcua_reachability.log",
            )
            _sleep_until(simulator_started_at + SIMULATOR_WARMUP_SECONDS)
            self._apply_network_and_wait(planned_run, run_dir)
            time.sleep(POST_RUN_CLOUD_SETTLE_SECONDS)
            self._collect_iothub_metrics(run_dir / "iot_hub_metrics_after.json")
            self._collect_run_evidence(planned_run, run_dir)
        finally:
            self._stop_process(simulator)
            self._cleanup_after_run(planned_run, run_dir, leave_scenario_running)

        summary = self._build_summary(planned_run, run_dir)
        write_json(run_dir / "run_summary.json", summary)
        self.status.write_run_status(run_dir, "completed", {"run": planned_run.as_dict(), "summary": summary})
        self.status.append_event(run_dir, "run_completed", summary)

    def _start_simulator(self, config_path: Path, run_dir: Path) -> tuple[subprocess.Popen[Any], float]:
        stdout = (run_dir / "simulator.stdout.log").open("w", encoding="utf-8")
        stderr = (run_dir / "simulator.stderr.log").open("w", encoding="utf-8")
        command = [
            sys.executable,
            str(self.settings.repo_root / "simulator" / "industrial-opcua-simulator" / "src" / "main.py"),
            str(config_path),
            "--mode",
            "both",
            "--realtime",
        ]
        self.status.append_event(run_dir, "simulator_start", {"command": command})
        started_at = time.monotonic()
        process = subprocess.Popen(command, cwd=self.settings.repo_root, stdout=stdout, stderr=stderr)
        time.sleep(5)
        if process.poll() is not None:
            raise RuntimeError(f"Simulator exited early with code {process.returncode}.")
        return process, started_at

    def _start_scenario(self, planned_run: PlannedRun, manifest_path: Path, run_dir: Path) -> None:
        if planned_run.scenario == SCENARIO_S0:
            self._deploy_edge_manifest(manifest_path, run_dir)
            self._start_s0_container(planned_run, run_dir)
        elif planned_run.scenario in {SCENARIO_S1, SCENARIO_S2}:
            self._deploy_edge_manifest(manifest_path, run_dir)
        else:
            raise RuntimeError(f"Unsupported scenario: {planned_run.scenario}")

    def _wait_for_scenario_ready(self, planned_run: PlannedRun, run_dir: Path) -> None:
        deadline = time.monotonic() + 120
        while True:
            if planned_run.scenario == SCENARIO_S0:
                output = self._ssh("docker ps --format '{{.Names}} {{.Status}}' | grep '^s0-cloud-publisher ' || true", check=False)
                if "s0-cloud-publisher" in output:
                    self.status.append_event(run_dir, "scenario_ready", {"scenario": planned_run.scenario})
                    return
            else:
                output = self._ssh("iotedge list || sudo iotedge list", check=False)
                module_names = _module_names_for_scenario(planned_run.scenario)
                if all(name in output for name in module_names) and output.count("running") >= len(module_names):
                    self.status.append_event(run_dir, "scenario_ready", {"scenario": planned_run.scenario})
                    return
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timed out waiting for scenario to become ready: {planned_run.scenario}")
            time.sleep(5)

    def _deploy_edge_manifest(self, manifest_path: Path, run_dir: Path) -> None:
        command = [
            "az",
            "iot",
            "edge",
            "set-modules",
            "--hub-name",
            self.settings.iot_hub_name,
            "--device-id",
            self.settings.edge_device_id,
            "--content",
            str(manifest_path),
            "--only-show-errors",
            "--output",
            "none",
        ]
        self._run_local(command, check=True, capture=True, log_path=run_dir / "az_set_modules.log")

    def _start_s0_container(self, planned_run: PlannedRun, run_dir: Path) -> None:
        if not self.settings.s0_connection_string:
            raise RuntimeError("S0_IOTHUB_DEVICE_CONNECTION_STRING is required for S0 runs.")
        image = f"{self.settings.acr_login_server}/s0-cloud-publisher:{self.settings.s0_image_tag}"
        env = {
            "OPCUA_ENDPOINT": self.settings.opcua_endpoint,
            "OPCUA_NAMESPACE_URI": self.settings.opcua_namespace_uri,
            "IOTHUB_DEVICE_CONNECTION_STRING": self.settings.s0_connection_string,
            "CLOUD_OUTPUT_POLICY": planned_run.cloud_output_policy,
            "CLOUD_MAX_MESSAGES_PER_SECOND": str(int(planned_run.cloud_messages_per_second)),
            "EXPERIMENT_ID_OVERRIDE": planned_run.matrix_id,
            "SCENARIO_OVERRIDE": planned_run.scenario,
            "RUN_ID_OVERRIDE": planned_run.run_id,
            "SEND_WORKER_COUNT": "32",
            "SEND_QUEUE_MAXSIZE": "10000",
            "LOG_LEVEL": "WARNING",
        }
        env_args = " ".join(f"-e {key}={_shell_quote(value)}" for key, value in env.items())
        if self.settings.acr_username and self.settings.acr_password:
            self._ssh(
                "docker login "
                f"{self.settings.acr_login_server} "
                f"-u {_shell_quote(self.settings.acr_username)} "
                f"-p {_shell_quote(self.settings.acr_password)} || "
                "sudo docker login "
                f"{self.settings.acr_login_server} "
                f"-u {_shell_quote(self.settings.acr_username)} "
                f"-p {_shell_quote(self.settings.acr_password)}",
                check=True,
                log_path=run_dir / "machine_b_docker_login.log",
            )
        self._ssh(
            "docker rm -f s0-cloud-publisher >/dev/null 2>&1 || "
            "sudo docker rm -f s0-cloud-publisher >/dev/null 2>&1 || true",
            check=False,
        )
        self._ssh(
            f"docker run -d --name s0-cloud-publisher --restart no {env_args} {image} || "
            f"sudo docker run -d --name s0-cloud-publisher --restart no {env_args} {image}",
            check=True,
            log_path=run_dir / "machine_b_s0_start.log",
        )

    def _apply_network_and_wait(self, planned_run: PlannedRun, run_dir: Path) -> None:
        network_plan = build_network_plan(
            planned_run.network_condition,
            self.settings.iot_hub_host,
            planned_run.duration_seconds,
        )
        self._ssh(network_plan.show_command, check=False, log_path=run_dir / "network_before.log")
        if planned_run.network_condition == "normal":
            time.sleep(planned_run.duration_seconds)
            return
        if planned_run.network_condition == "cloud_outage_120s":
            time.sleep(network_plan.outage_start_second or 0)
            if network_plan.apply_command:
                self._ssh(network_plan.apply_command, check=True, log_path=run_dir / "network_apply.log")
            self.status.append_event(run_dir, "cloud_outage_started")
            time.sleep(network_plan.outage_duration_second or 0)
            self._ssh(network_plan.clear_command, check=False, log_path=run_dir / "network_clear.log")
            self.status.append_event(run_dir, "cloud_outage_cleared")
            time.sleep(network_plan.recovery_duration_second or 0)
            return
        if network_plan.apply_command:
            self._ssh(network_plan.apply_command, check=True, log_path=run_dir / "network_apply.log")
        time.sleep(planned_run.duration_seconds)

    def _collect_run_evidence(self, planned_run: PlannedRun, run_dir: Path) -> None:
        self._ssh("iotedge list || sudo iotedge list", check=False, log_path=run_dir / "machine_b_iotedge_list.log")
        self._ssh(
            "docker stats --no-stream || sudo docker stats --no-stream || true",
            check=False,
            log_path=run_dir / "machine_b_docker_stats.log",
        )
        self._ssh(
            "docker ps --format '{{json .}}' || sudo docker ps --format '{{json .}}' || true",
            check=False,
            log_path=run_dir / "machine_b_docker_ps.jsonl",
        )
        for module_name in _module_names_for_scenario(planned_run.scenario):
            self._ssh(
                f"iotedge logs {module_name} --tail 1000 || sudo iotedge logs {module_name} --tail 1000 || true",
                check=False,
                log_path=run_dir / f"module_{module_name}.log",
            )
        if planned_run.scenario == SCENARIO_S0:
            self._ssh(
                "docker logs --tail 1000 s0-cloud-publisher || sudo docker logs --tail 1000 s0-cloud-publisher || true",
                check=False,
                log_path=run_dir / "s0_cloud_publisher.log",
            )
        if planned_run.scenario == SCENARIO_S2:
            self._ssh(
                "test -f /home/floriansaqipi/iot_edge_study/alerts/s2_alerts.jsonl "
                "&& tail -n 1000 /home/floriansaqipi/iot_edge_study/alerts/s2_alerts.jsonl || true",
                check=False,
                log_path=run_dir / "s2_alerts_tail.jsonl",
            )
        self._export_cloud_tables(planned_run, run_dir)

    def _cleanup_after_run(self, planned_run: PlannedRun, run_dir: Path, leave_scenario_running: bool) -> None:
        network_plan = build_network_plan(
            planned_run.network_condition,
            self.settings.iot_hub_host,
            planned_run.duration_seconds,
        )
        self._ssh(network_plan.clear_command, check=False, log_path=run_dir / "network_cleanup.log")
        if planned_run.scenario == SCENARIO_S0:
            self._ssh(
                "docker rm -f s0-cloud-publisher >/dev/null 2>&1 || "
                "sudo docker rm -f s0-cloud-publisher >/dev/null 2>&1 || true",
                check=False,
            )
        if not leave_scenario_running:
            idle_manifest = run_dir / "idle_after_run.generated.json"
            idle_run = PlannedRun(
                campaign_id=planned_run.campaign_id,
                matrix_id=planned_run.matrix_id,
                row_id=planned_run.row_id,
                block=planned_run.block,
                scenario="IDLE",
                network_condition="normal",
                target_messages_per_second=planned_run.target_messages_per_second,
                cloud_messages_per_second=planned_run.cloud_messages_per_second,
                duration_seconds=planned_run.duration_seconds,
                repetition=planned_run.repetition,
                repetitions=planned_run.repetitions,
                cloud_output_policy=planned_run.cloud_output_policy,
                estimated_billable_messages=planned_run.estimated_billable_messages,
            )
            render_edge_manifest(idle_run, self.settings, idle_manifest)
            self._deploy_edge_manifest(idle_manifest, run_dir)

    def _export_cloud_tables(self, planned_run: PlannedRun, run_dir: Path) -> None:
        if not self.settings.storage_connection_string:
            (run_dir / "cloud_export_skipped.txt").write_text(
                "CLOUD_RESULTS_STORAGE_CONNECTION_STRING was not configured.\n",
                encoding="utf-8",
            )
            return
        from azure.data.tables import TableServiceClient

        partition_key = f"{planned_run.matrix_id}|{planned_run.scenario}|{planned_run.run_id}"
        service = TableServiceClient.from_connection_string(self.settings.storage_connection_string)
        for table_name in ("CloudTelemetry", "CloudAlerts", "CloudInvalid"):
            table = service.get_table_client(table_name)
            rows = list(table.query_entities(f"PartitionKey eq '{partition_key}'"))
            _write_jsonl(run_dir / f"{table_name}.jsonl", rows)
            _write_csv(run_dir / f"{table_name}.csv", rows)

    def _build_summary(self, planned_run: PlannedRun, run_dir: Path) -> dict[str, Any]:
        return {
            "runId": planned_run.run_id,
            "scenario": planned_run.scenario,
            "networkCondition": planned_run.network_condition,
            "completedAt": utc_now(),
            "simulatorJsonlRows": _count_lines(run_dir / "simulator.jsonl"),
            "simulatorCsvRows": max(0, _count_lines(run_dir / "simulator.csv") - 1),
            "cloudTelemetryRows": _count_lines(run_dir / "CloudTelemetry.jsonl"),
            "cloudAlertRows": _count_lines(run_dir / "CloudAlerts.jsonl"),
            "cloudInvalidRows": _count_lines(run_dir / "CloudInvalid.jsonl"),
            "plannedCloudMessages": planned_run.planned_cloud_message_estimate,
        }

    def _run_dir(self, planned_run: PlannedRun) -> Path:
        return self.settings.results_root / planned_run.campaign_id / planned_run.row_id / f"rep_{planned_run.repetition}"

    def _run_local(
        self,
        command: list[str],
        check: bool,
        capture: bool,
        log_path: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        actual_command = list(command)
        if actual_command[0] == "az":
            actual_command[0] = self._azure_cli_command()
        if (
            shutil.which(actual_command[0]) is None
            and actual_command[0] != sys.executable
            and not Path(actual_command[0]).exists()
        ):
            if check:
                raise RuntimeError(f"Required command is not available: {command[0]}")
            return subprocess.CompletedProcess(actual_command, 127, "", f"{command[0]} not found")
        result = subprocess.run(
            actual_command,
            cwd=self.settings.repo_root,
            capture_output=capture,
            text=True,
            check=False,
        )
        if log_path:
            log_path.write_text(self._redact((result.stdout or "") + (result.stderr or "")), encoding="utf-8")
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}")
        return result

    def _collect_preflight_iothub_metrics(self, preflight_dir: Path) -> None:
        self._collect_iothub_metrics(preflight_dir / "iot_hub_metrics.json")

    def _collect_iothub_metrics(self, output_path: Path) -> None:
        hub_id = self._run_local(
            [
                "az",
                "iot",
                "hub",
                "show",
                "--name",
                self.settings.iot_hub_name,
                "--query",
                "id",
                "-o",
                "tsv",
            ],
            check=False,
            capture=True,
            log_path=output_path.with_name(output_path.stem + "_resource.log"),
        ).stdout.strip()
        if not hub_id:
            return
        self._run_local(
            [
                "az",
                "monitor",
                "metrics",
                "list",
                "--resource",
                hub_id,
                "--metric",
                "d2c.telemetry.ingress.success,d2c.telemetry.ingress.allProtocol,d2c.telemetry.ingress.sendThrottle,dailyMessageQuotaUsed",
                "--interval",
                "PT1H",
            ],
            check=False,
            capture=True,
            log_path=output_path,
        )

    def _azure_cli_command(self) -> str:
        if self.settings.azure_cli_path != "az":
            return self.settings.azure_cli_path
        known_windows_path = Path("C:/Program Files/Microsoft SDKs/Azure/CLI2/wbin/az.cmd")
        if known_windows_path.exists():
            return str(known_windows_path)
        return "az"

    def _install_remote_network_script(self) -> None:
        import paramiko

        local_script = self.settings.repo_root / "infrastructure" / "host-vm-setup" / "ubuntu-network-emulation.sh"
        remote_dir = "/home/floriansaqipi/iot_edge_study"
        remote_script = f"{remote_dir}/ubuntu-network-emulation.sh"
        self._ssh(f"mkdir -p {remote_dir}", check=True)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.settings.machine_b_host,
            username=self.settings.machine_b_user,
            password=self.settings.machine_b_password,
            timeout=15,
        )
        try:
            sftp = client.open_sftp()
            try:
                sftp.put(str(local_script), remote_script)
            finally:
                sftp.close()
        finally:
            client.close()
        self._ssh(f"chmod +x {remote_script}", check=True)

    def _ssh(self, command: str, check: bool, log_path: Path | None = None) -> str:
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.settings.machine_b_host,
            username=self.settings.machine_b_user,
            password=self.settings.machine_b_password,
            timeout=15,
        )
        try:
            _, stdout, stderr = client.exec_command(command)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
        finally:
            client.close()
        if log_path:
            log_path.write_text(f"$ {self._redact(command)}\n{self._redact(out + err)}", encoding="utf-8")
        if check and code != 0:
            raise RuntimeError(f"SSH command failed ({code}): {command}\n{err}")
        return out + err

    @staticmethod
    def _stop_process(process: subprocess.Popen[Any]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()

    def _redact(self, text: str) -> str:
        redacted = text
        for secret in (self.settings.machine_b_password, self.settings.acr_password, self.settings.s0_connection_string):
            if secret:
                redacted = redacted.replace(secret, "***REDACTED***")
        return redacted


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(dict(row), default=str, separators=(",", ":"), sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in keys})


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as file:
        return sum(1 for _ in file)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _sleep_until(target: float) -> None:
    remaining = target - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)


def _module_names_for_scenario(scenario: str) -> tuple[str, ...]:
    if scenario == SCENARIO_S1:
        return ("opcua-collector",)
    if scenario == SCENARIO_S2:
        return (
            "opcua-collector",
            "normalizer-validator",
            "filter-aggregator",
            "anomaly-detector",
            "local-alert-service",
        )
    return ()
