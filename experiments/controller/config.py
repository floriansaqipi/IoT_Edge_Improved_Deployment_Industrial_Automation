from __future__ import annotations

import os
from pathlib import Path

from .models import ControllerSettings


def load_controller_settings(
    repo_root: Path,
    matrix_path: Path,
    results_root: Path | None = None,
    env_file: Path | None = None,
) -> ControllerSettings:
    env_values = _load_env_file(env_file or repo_root / ".env.experiment.local")

    def value(name: str, default: str | None = None) -> str | None:
        return os.getenv(name) or env_values.get(name) or default

    return ControllerSettings(
        repo_root=repo_root,
        results_root=results_root or repo_root / "results" / "experiments",
        matrix_path=matrix_path,
        machine_a_ip=value("MACHINE_A_IP", "192.168.1.5") or "192.168.1.5",
        machine_b_host=value("MACHINE_B_HOST", "192.168.1.3") or "192.168.1.3",
        machine_b_user=value("MACHINE_B_USER"),
        machine_b_password=value("MACHINE_B_PASSWORD"),
        opcua_endpoint=value("OPCUA_ENDPOINT", "opc.tcp://192.168.1.5:4840/factory/server")
        or "opc.tcp://192.168.1.5:4840/factory/server",
        opcua_bind_endpoint=value("OPCUA_BIND_ENDPOINT", "opc.tcp://0.0.0.0:4840/factory/server")
        or "opc.tcp://0.0.0.0:4840/factory/server",
        iot_hub_name=value("IOT_HUB_NAME", "iothub-edge-study-florian01") or "iothub-edge-study-florian01",
        edge_device_id=value("EDGE_DEVICE_ID", "edge-gateway-b-ubuntu") or "edge-gateway-b-ubuntu",
        s0_device_id=value("S0_DEVICE_ID", "s0-cloud-publisher-b") or "s0-cloud-publisher-b",
        acr_login_server=value("ACR_LOGIN_SERVER", "acredgestudyflorian01.azurecr.io")
        or "acredgestudyflorian01.azurecr.io",
        acr_username=value("ACR_USERNAME"),
        acr_password=value("ACR_PASSWORD"),
        s0_connection_string=value("S0_IOTHUB_DEVICE_CONNECTION_STRING"),
        storage_connection_string=value("CLOUD_RESULTS_STORAGE_CONNECTION_STRING"),
        azure_cli_path=value("AZURE_CLI_PATH", "az") or "az",
        collector_image_tag=value("COLLECTOR_IMAGE_TAG", "0.1.2-amd64") or "0.1.2-amd64",
        phase4_image_tag=value("PHASE4_IMAGE_TAG", "0.1.0-amd64") or "0.1.0-amd64",
        s0_image_tag=value("S0_IMAGE_TAG", "0.1.0-amd64") or "0.1.0-amd64",
    )


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        values[key.strip()] = raw_value.strip().strip('"').strip("'")
    return values
