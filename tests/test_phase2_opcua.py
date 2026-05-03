from __future__ import annotations

import asyncio
import socket
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from asyncua import Client

from config_loader import OpcUaConfig, OutputConfig, load_config
from main import build_devices, run_opcua_simulation
from opcua_server import IndustrialOpcUaServer, opcua_device_name, opcua_node_references, opcua_node_string_id


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "simulator" / "industrial-opcua-simulator" / "configs"


def test_opcua_config_loads() -> None:
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps_opcua.yaml")

    assert config.run_mode == "both"
    assert config.pace_realtime is True
    assert config.opcua.endpoint == "opc.tcp://0.0.0.0:4840/factory/server"
    assert config.opcua.namespace_uri == "urn:industrial-automation:azure-iot-edge-study"
    assert [output.format for output in config.all_outputs] == ["jsonl", "csv"]


def test_deterministic_opcua_device_names_and_node_ids() -> None:
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps_opcua.yaml")
    references = opcua_node_references(build_devices(config))

    assert opcua_device_name("motor-001") == "Motor001"
    assert opcua_node_string_id("motor-001", "Temperature") == "Factory.Line1.Motor001.Temperature"
    assert any(reference.node_string_id == "Factory.Line1.Motor001.Sequence" for reference in references)
    assert any(reference.node_string_id == "Factory.Line1.Pump001.FlowRate" for reference in references)


def test_opcua_server_exposes_and_updates_nodes() -> None:
    asyncio.run(_assert_opcua_server_exposes_and_updates_nodes())


def test_opcua_run_writes_both_outputs(tmp_path: Path) -> None:
    asyncio.run(_assert_opcua_run_writes_both_outputs(tmp_path))


def test_opcua_only_run_does_not_write_outputs(tmp_path: Path) -> None:
    asyncio.run(_assert_opcua_only_run_does_not_write_outputs(tmp_path))


async def _assert_opcua_server_exposes_and_updates_nodes() -> None:
    port = _free_port()
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps_opcua.yaml")
    config = replace(
        config,
        duration_seconds=1.0,
        opcua=OpcUaConfig(
            endpoint=f"opc.tcp://127.0.0.1:{port}/factory/server",
            namespace_uri=config.opcua.namespace_uri,
        ),
    )
    devices = build_devices(config)
    motor = devices[0]
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async with IndustrialOpcUaServer(config.opcua, devices) as server:
        first = motor.emit(timestamp, 0.0)
        await server.update_record(first)

        async with Client(url=config.opcua.endpoint) as client:
            namespace_index = await client.get_namespace_index(config.opcua.namespace_uri)
            children = await client.nodes.objects.get_children()
            browse_names = [await child.read_browse_name() for child in children]
            assert any(name.Name == "Factory" for name in browse_names)

            sequence = client.get_node(f"ns={namespace_index};s=Factory.Line1.Motor001.Sequence")
            temperature = client.get_node(f"ns={namespace_index};s=Factory.Line1.Motor001.Temperature")
            is_anomaly = client.get_node(f"ns={namespace_index};s=Factory.Line1.Motor001.IsAnomaly")

            assert await sequence.read_value() == 1
            assert isinstance(await temperature.read_value(), float)
            assert await is_anomaly.read_value() is False

            second = motor.emit(timestamp, 1.0)
            await server.update_record(second)
            assert await sequence.read_value() == 2


async def _assert_opcua_run_writes_both_outputs(tmp_path: Path) -> None:
    port = _free_port()
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps_opcua.yaml")
    config = replace(
        config,
        duration_seconds=0.2,
        pace_realtime=False,
        opcua=OpcUaConfig(
            endpoint=f"opc.tcp://127.0.0.1:{port}/factory/server",
            namespace_uri=config.opcua.namespace_uri,
        ),
        output=OutputConfig(format="jsonl", path=tmp_path / "phase2.jsonl"),
        outputs=(
            OutputConfig(format="jsonl", path=tmp_path / "phase2.jsonl"),
            OutputConfig(format="csv", path=tmp_path / "phase2.csv"),
        ),
    )

    summary = await run_opcua_simulation(config)

    assert summary["runMode"] == "both"
    assert summary["writtenMessages"] == 2
    assert (tmp_path / "phase2.jsonl").read_text(encoding="utf-8").count("\n") == 2
    assert len((tmp_path / "phase2.csv").read_text(encoding="utf-8").splitlines()) == 3


async def _assert_opcua_only_run_does_not_write_outputs(tmp_path: Path) -> None:
    port = _free_port()
    config = load_config(CONFIG_DIR / "exp_10_devices_10mps_opcua.yaml")
    config = replace(
        config,
        run_mode="opcua",
        duration_seconds=0.2,
        pace_realtime=False,
        opcua=OpcUaConfig(
            endpoint=f"opc.tcp://127.0.0.1:{port}/factory/server",
            namespace_uri=config.opcua.namespace_uri,
        ),
        output=OutputConfig(format="jsonl", path=tmp_path / "server_only.jsonl"),
        outputs=(
            OutputConfig(format="jsonl", path=tmp_path / "server_only.jsonl"),
            OutputConfig(format="csv", path=tmp_path / "server_only.csv"),
        ),
    )

    summary = await run_opcua_simulation(config)

    assert summary["runMode"] == "opcua"
    assert summary["writtenMessages"] == 2
    assert summary["outputPaths"] == []
    assert not (tmp_path / "server_only.jsonl").exists()
    assert not (tmp_path / "server_only.csv").exists()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
