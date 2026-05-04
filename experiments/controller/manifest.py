from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import SCENARIO_S1, SCENARIO_S2, ControllerSettings, PlannedRun


def render_edge_manifest(run: PlannedRun, settings: ControllerSettings, output_path: Path) -> Path:
    if run.scenario == SCENARIO_S1:
        template = settings.repo_root / "edge" / "deployments" / "s1-edge-pass-through.template.json"
        manifest = _load_template(template, settings, {"__COLLECTOR_IMAGE_TAG__": settings.collector_image_tag})
        _set_module_env(
            manifest,
            "opcua-collector",
            {
                "EXPERIMENT_ID_OVERRIDE": run.matrix_id,
                "SCENARIO_OVERRIDE": run.scenario,
                "RUN_ID_OVERRIDE": run.run_id,
                "CLOUD_OUTPUT_POLICY": "full",
                "CLOUD_MAX_MESSAGES_PER_SECOND": str(int(run.cloud_messages_per_second)),
            },
        )
    elif run.scenario == SCENARIO_S2:
        template = settings.repo_root / "edge" / "deployments" / "s2-hybrid.template.json"
        manifest = _load_template(
            template,
            settings,
            {
                "__COLLECTOR_IMAGE_TAG__": settings.collector_image_tag,
                "__PHASE4_IMAGE_TAG__": settings.phase4_image_tag,
            },
        )
        _set_module_env(
            manifest,
            "opcua-collector",
            {
                "EXPERIMENT_ID_OVERRIDE": run.matrix_id,
                "SCENARIO_OVERRIDE": run.scenario,
                "RUN_ID_OVERRIDE": run.run_id,
            },
        )
        _set_module_env(
            manifest,
            "filter-aggregator",
            {
                "CLOUD_OUTPUT_POLICY": "sampled_10_percent" if run.cloud_output_policy != "capped" else "capped",
                "SAMPLE_EVERY": "10",
                "CLOUD_MAX_MESSAGES_PER_SECOND": str(int(run.cloud_messages_per_second)),
            },
        )
    else:
        template = settings.repo_root / "edge" / "deployments" / "idle-edge.template.json"
        manifest = json.loads(template.read_text(encoding="utf-8"))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _load_template(template: Path, settings: ControllerSettings, replacements: dict[str, str]) -> dict[str, Any]:
    if not settings.acr_username or not settings.acr_password:
        raise ValueError("ACR_USERNAME and ACR_PASSWORD are required to render Edge deployment manifests.")
    text = template.read_text(encoding="utf-8")
    base_replacements = {
        "__ACR_LOGIN_SERVER__": settings.acr_login_server,
        "__ACR_USERNAME__": settings.acr_username,
        "__ACR_PASSWORD__": settings.acr_password,
    }
    base_replacements.update(replacements)
    for old, new in base_replacements.items():
        text = text.replace(old, new)
    return json.loads(text)


def _set_module_env(manifest: dict[str, Any], module_name: str, env: dict[str, str]) -> None:
    modules = manifest["modulesContent"]["$edgeAgent"]["properties.desired"]["modules"]
    module = modules[module_name]
    module_env = module.setdefault("env", {})
    for key, value in env.items():
        module_env[key] = {"value": value}
