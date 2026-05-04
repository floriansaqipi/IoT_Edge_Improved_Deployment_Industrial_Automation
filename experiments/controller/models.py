from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCENARIO_S0 = "S0_CLOUD_ONLY"
SCENARIO_S1 = "S1_EDGE_PASS_THROUGH"
SCENARIO_S2 = "S2_HYBRID"
SUPPORTED_SCENARIOS = {SCENARIO_S0, SCENARIO_S1, SCENARIO_S2}


@dataclass(frozen=True)
class ControllerSettings:
    repo_root: Path
    results_root: Path
    matrix_path: Path
    machine_a_ip: str = "192.168.1.5"
    machine_b_host: str = "192.168.1.3"
    machine_b_user: str | None = None
    machine_b_password: str | None = field(default=None, repr=False)
    opcua_endpoint: str = "opc.tcp://192.168.1.5:4840/factory/server"
    opcua_bind_endpoint: str = "opc.tcp://0.0.0.0:4840/factory/server"
    opcua_namespace_uri: str = "urn:industrial-automation:azure-iot-edge-study"
    iot_hub_name: str = "iothub-edge-study-florian01"
    edge_device_id: str = "edge-gateway-b-ubuntu"
    s0_device_id: str = "s0-cloud-publisher-b"
    acr_login_server: str = "acredgestudyflorian01.azurecr.io"
    acr_username: str | None = None
    acr_password: str | None = field(default=None, repr=False)
    s0_connection_string: str | None = field(default=None, repr=False)
    storage_connection_string: str | None = field(default=None, repr=False)
    azure_cli_path: str = "az"
    collector_image_tag: str = "0.1.2-amd64"
    phase4_image_tag: str = "0.1.0-amd64"
    s0_image_tag: str = "0.1.0-amd64"

    @property
    def iot_hub_host(self) -> str:
        return f"{self.iot_hub_name}.azure-devices.net"


@dataclass(frozen=True)
class PlannedRun:
    campaign_id: str
    matrix_id: str
    row_id: str
    block: str
    scenario: str
    network_condition: str
    target_messages_per_second: float
    cloud_messages_per_second: float
    duration_seconds: float
    repetition: int
    repetitions: int
    cloud_output_policy: str
    estimated_billable_messages: int

    @property
    def run_id(self) -> str:
        return f"{self.row_id}_rep{self.repetition}_{self.campaign_id}"

    @property
    def generated_message_estimate(self) -> int:
        return int(self.target_messages_per_second * self.duration_seconds)

    @property
    def planned_cloud_message_estimate(self) -> int:
        return int(self.cloud_messages_per_second * self.duration_seconds)

    def as_dict(self) -> dict[str, Any]:
        return {
            "campaignId": self.campaign_id,
            "matrixId": self.matrix_id,
            "rowId": self.row_id,
            "block": self.block,
            "scenario": self.scenario,
            "networkCondition": self.network_condition,
            "targetMessagesPerSecond": self.target_messages_per_second,
            "cloudMessagesPerSecond": self.cloud_messages_per_second,
            "durationSeconds": self.duration_seconds,
            "repetition": self.repetition,
            "repetitions": self.repetitions,
            "cloudOutputPolicy": self.cloud_output_policy,
            "estimatedBillableMessages": self.estimated_billable_messages,
            "runId": self.run_id,
            "generatedMessageEstimate": self.generated_message_estimate,
            "plannedCloudMessageEstimate": self.planned_cloud_message_estimate,
        }
