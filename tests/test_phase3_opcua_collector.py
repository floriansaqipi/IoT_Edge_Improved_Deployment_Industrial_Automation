from __future__ import annotations

import asyncio
import json
import socket
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from asyncua import Client

from config_loader import OpcUaConfig, load_config
from main import build_devices
from opcua_server import IndustrialOpcUaServer


ROOT = Path(__file__).resolve().parents[1]
EDGE_SRC = ROOT / "edge" / "modules" / "opcua-collector" / "src"
CONFIG_DIR = ROOT / "simulator" / "industrial-opcua-simulator" / "configs"

if str(EDGE_SRC) not in sys.path:
    sys.path.insert(0, str(EDGE_SRC))

from opcua_collector.config import CollectorConfig  # noqa: E402
from opcua_collector.opcua_mapping import (  # noqa: E402
    device_name_to_id,
    device_type_from_name,
    node_id_text,
    node_string_id,
    value_keys_for_device_name,
)
from opcua_collector.collector import RECONNECT_SIGNAL, OpcUaSnapshotReader, SequenceSubscriptionHandler  # noqa: E402


def test_phase3_device_name_and_node_mapping() -> None:
    assert device_name_to_id("Motor001") == "motor-001"
    assert device_name_to_id("Compressor017") == "compressor-017"
    assert device_type_from_name("Tank003") == "tank"
    assert node_string_id("Motor001", "Temperature") == "Factory.Line1.Motor001.Temperature"
    assert node_id_text(2, "Factory.Line1.Motor001.Sequence") == "ns=2;s=Factory.Line1.Motor001.Sequence"
    assert value_keys_for_device_name("Pump001") == (
        "pressure",
        "flowRate",
        "temperature",
        "vibration",
        "current",
        "status",
    )


def test_phase3_deployment_manifest_shape() -> None:
    manifest_path = ROOT / "edge" / "deployments" / "s1-edge-pass-through.template.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    modules_content = manifest["modulesContent"]
    edge_agent = modules_content["$edgeAgent"]["properties.desired"]
    edge_hub = modules_content["$edgeHub"]["properties.desired"]
    collector = edge_agent["modules"]["opcua-collector"]

    assert collector["settings"]["image"] == "__ACR_LOGIN_SERVER__/opcua-collector:__COLLECTOR_IMAGE_TAG__"
    assert collector["env"]["OPCUA_ENDPOINT"]["value"] == "opc.tcp://192.168.1.5:4840/factory/server"
    assert collector["env"]["OUTPUT_NAME"]["value"] == "telemetry"
    assert edge_hub["routes"]["collectorToCloud"] == (
        "FROM /messages/modules/opcua-collector/outputs/telemetry INTO $upstream"
    )
    assert edge_hub["storeAndForwardConfiguration"]["timeToLiveSecs"] == 7200


def test_phase3_simulator_exposes_experiment_metadata() -> None:
    asyncio.run(_assert_simulator_exposes_experiment_metadata())


def test_phase3_collector_reads_live_device_snapshot() -> None:
    asyncio.run(_assert_collector_reads_live_device_snapshot())


def test_phase3_sequence_subscription_queues_device_updates() -> None:
    asyncio.run(_assert_sequence_subscription_queues_device_updates())


def test_phase3_subscription_status_change_triggers_reconnect() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    handler = SequenceSubscriptionHandler({}, queue)

    handler.status_change_notification("BadTimeout")

    assert queue.get_nowait() == RECONNECT_SIGNAL


async def _assert_simulator_exposes_experiment_metadata() -> None:
    port = _free_port()
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps_opcua.yaml")
    config = replace(
        config,
        opcua=OpcUaConfig(
            endpoint=f"opc.tcp://127.0.0.1:{port}/factory/server",
            namespace_uri=config.opcua.namespace_uri,
        ),
    )
    devices = build_devices(config)
    metadata = {
        "ExperimentId": config.experiment_id,
        "Scenario": config.scenario,
        "RunId": config.run_id,
    }

    async with IndustrialOpcUaServer(config.opcua, devices, metadata):
        async with Client(url=config.opcua.endpoint) as client:
            namespace_index = await client.get_namespace_index(config.opcua.namespace_uri)
            experiment_id = client.get_node(f"ns={namespace_index};s=Factory.Experiment.ExperimentId")
            scenario = client.get_node(f"ns={namespace_index};s=Factory.Experiment.Scenario")

            assert await experiment_id.read_value() == config.experiment_id
            assert await scenario.read_value() == config.scenario


async def _assert_collector_reads_live_device_snapshot() -> None:
    port = _free_port()
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps_opcua.yaml")
    config = replace(
        config,
        opcua=OpcUaConfig(
            endpoint=f"opc.tcp://127.0.0.1:{port}/factory/server",
            namespace_uri=config.opcua.namespace_uri,
        ),
    )
    devices = build_devices(config)
    motor = devices[0]
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metadata = {
        "ExperimentId": config.experiment_id,
        "Scenario": config.scenario,
        "RunId": config.run_id,
    }

    async with IndustrialOpcUaServer(config.opcua, devices, metadata) as server:
        record = motor.emit(timestamp, 0.0)
        await server.update_record(record)

        reader_config = CollectorConfig(
            opcua_endpoint=config.opcua.endpoint,
            namespace_uri=config.opcua.namespace_uri,
            output_name="telemetry",
            experiment_id_fallback="fallback-exp",
            scenario_fallback="S1_EDGE_PASS_THROUGH",
            run_id_fallback="fallback-run",
        )
        async with OpcUaSnapshotReader(reader_config) as reader:
            device_names = await reader.discover_devices()
            message = await reader.read_snapshot("Motor001")

    assert "Motor001" in device_names
    assert message["experimentId"] == config.experiment_id
    assert message["scenario"] == config.scenario
    assert message["runId"] == config.run_id
    assert message["deviceId"] == record["deviceId"]
    assert message["deviceType"] == record["deviceType"]
    assert message["sequence"] == record["sequence"]
    assert message["sensorTimestamp"] == record["sensorTimestamp"]
    assert message["edgeReceivedTimestamp"].endswith("Z")
    assert message["values"]["temperature"] == record["values"]["temperature"]
    assert message["values"]["status"] == record["values"]["status"]
    assert message["groundTruth"] == record["groundTruth"]


async def _assert_sequence_subscription_queues_device_updates() -> None:
    port = _free_port()
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps_opcua.yaml")
    config = replace(
        config,
        opcua=OpcUaConfig(
            endpoint=f"opc.tcp://127.0.0.1:{port}/factory/server",
            namespace_uri=config.opcua.namespace_uri,
        ),
    )
    devices = build_devices(config)
    motor = devices[0]
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    reader_config = CollectorConfig(
        opcua_endpoint=config.opcua.endpoint,
        namespace_uri=config.opcua.namespace_uri,
    )

    async with IndustrialOpcUaServer(config.opcua, devices) as server:
        async with OpcUaSnapshotReader(reader_config) as reader:
            queue: asyncio.Queue[str] = asyncio.Queue()
            subscription = await reader.subscribe_sequence_changes(["Motor001"], queue, period_ms=50)
            try:
                await server.update_record(motor.emit(timestamp, 0.0))
                device_name = await asyncio.wait_for(queue.get(), timeout=2)
            finally:
                await subscription.delete()

    assert device_name == "Motor001"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
