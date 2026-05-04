from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StatusStore:
    def __init__(self, results_root: Path, campaign_id: str) -> None:
        self.results_root = results_root
        self.campaign_id = campaign_id
        self.campaign_dir = results_root / campaign_id
        self.latest_path = results_root / "_latest.json"

    def write_latest(self, payload: dict[str, Any]) -> None:
        self.results_root.mkdir(parents=True, exist_ok=True)
        self._write_json(
            self.latest_path,
            {
                "campaignId": self.campaign_id,
                "campaignDir": str(self.campaign_dir),
                "updatedAt": utc_now(),
                **payload,
            },
        )

    def write_run_status(self, run_dir: Path, status: str, payload: dict[str, Any]) -> None:
        self._write_json(
            run_dir / "status.json",
            {
                "campaignId": self.campaign_id,
                "status": status,
                "updatedAt": utc_now(),
                **payload,
            },
        )

    def append_event(self, run_dir: Path, event: str, details: dict[str, Any] | None = None) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": utc_now(), "event": event, "details": details or {}}
        with (run_dir / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, sort_keys=True) + "\n")

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)


def read_status(results_root: Path, campaign: str) -> dict[str, Any]:
    if campaign == "latest":
        latest_path = results_root / "_latest.json"
        if not latest_path.exists():
            return {"status": "missing", "message": f"No latest campaign at {latest_path}"}
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        campaign_id = str(latest["campaignId"])
    else:
        latest = {}
        campaign_id = campaign

    campaign_dir = results_root / campaign_id
    run_statuses = sorted(campaign_dir.glob("*/rep_*/status.json"))
    statuses = [json.loads(path.read_text(encoding="utf-8")) for path in run_statuses]
    return {
        "latest": latest,
        "campaignId": campaign_id,
        "campaignDir": str(campaign_dir),
        "runCount": len(statuses),
        "completed": sum(1 for item in statuses if item.get("status") == "completed"),
        "failed": sum(1 for item in statuses if item.get("status") == "failed"),
        "running": sum(1 for item in statuses if item.get("status") == "running"),
        "statuses": statuses[-5:],
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
