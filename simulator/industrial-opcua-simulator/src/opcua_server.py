from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asyncua import Server, ua

from config_loader import OpcUaConfig
from devices.base_device import BaseDevice


DEVICE_TYPE_PREFIX = {
    "motor": "Motor",
    "pump": "Pump",
    "conveyor": "Conveyor",
    "tank": "Tank",
    "compressor": "Compressor",
}

VALUE_NODE_NAMES = {
    "temperature": "Temperature",
    "vibration": "Vibration",
    "rpm": "RPM",
    "current": "Current",
    "load": "Load",
    "pressure": "Pressure",
    "flowRate": "FlowRate",
    "speed": "Speed",
    "motorCurrent": "MotorCurrent",
    "level": "Level",
    "inletFlow": "InletFlow",
    "outletFlow": "OutletFlow",
    "valveState": "ValveState",
    "status": "Status",
}

DEVICE_VALUE_KEYS = {
    "motor": ("temperature", "vibration", "rpm", "current", "load", "status"),
    "pump": ("pressure", "flowRate", "temperature", "vibration", "current", "status"),
    "conveyor": ("speed", "load", "motorCurrent", "vibration", "status"),
    "tank": ("level", "pressure", "inletFlow", "outletFlow", "valveState", "status"),
    "compressor": ("pressure", "temperature", "vibration", "current", "status"),
}

METADATA_NODE_NAMES = ("DeviceId", "DeviceType", "Sequence", "SensorTimestamp", "IsAnomaly", "AnomalyType")
EXPERIMENT_NODE_NAMES = ("ExperimentId", "Scenario", "RunId")


@dataclass(frozen=True)
class OpcUaNodeReference:
    device_id: str
    node_name: str
    node_string_id: str


class IndustrialOpcUaServer:
    def __init__(
        self,
        config: OpcUaConfig,
        devices: list[BaseDevice],
        experiment_metadata: dict[str, str] | None = None,
    ) -> None:
        self.config = config
        self.devices = devices
        self.experiment_metadata = experiment_metadata or {}
        self.server = Server()
        self.namespace_index: int | None = None
        self.nodes_by_device: dict[str, dict[str, Any]] = {}

    async def __aenter__(self) -> "IndustrialOpcUaServer":
        await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.stop()

    async def start(self) -> None:
        await self.server.init()
        self.server.set_endpoint(self.config.endpoint)
        self.server.set_server_name("Industrial OPC UA Simulator")
        self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        self.namespace_index = await self.server.register_namespace(self.config.namespace_uri)
        await self._build_address_space()
        await self.server.start()

    async def stop(self) -> None:
        await self.server.stop()

    async def update_record(self, record: dict[str, Any]) -> None:
        device_nodes = self.nodes_by_device[record["deviceId"]]
        ground_truth = record["groundTruth"]
        values = record["values"]

        updates = {
            "DeviceId": record["deviceId"],
            "DeviceType": record["deviceType"],
            "Sequence": int(record["sequence"]),
            "SensorTimestamp": record["sensorTimestamp"],
            "IsAnomaly": bool(ground_truth["isAnomaly"]),
            "AnomalyType": ground_truth["anomalyType"] or "",
        }
        for key, value in values.items():
            updates[VALUE_NODE_NAMES[key]] = value

        for node_name, value in updates.items():
            await device_nodes[node_name].write_value(value)

    async def _build_address_space(self) -> None:
        if self.namespace_index is None:
            raise RuntimeError("OPC UA namespace is not registered.")

        objects = self.server.nodes.objects
        factory = await objects.add_object(self._node_id("Factory"), "Factory")
        await self._add_experiment_metadata(factory)
        line = await factory.add_object(self._node_id("Factory.Line1"), "Line1")

        for device in self.devices:
            device_name = opcua_device_name(device.device_id)
            device_path = f"Factory.Line1.{device_name}"
            device_object = await line.add_object(self._node_id(device_path), device_name)
            self.nodes_by_device[device.device_id] = {}

            for node_name in METADATA_NODE_NAMES:
                node = await device_object.add_variable(
                    self._node_id(f"{device_path}.{node_name}"),
                    node_name,
                    _initial_value_for_node(node_name),
                )
                self.nodes_by_device[device.device_id][node_name] = node

            for value_key in DEVICE_VALUE_KEYS[device.device_type]:
                node_name = VALUE_NODE_NAMES[value_key]
                if node_name in self.nodes_by_device[device.device_id]:
                    continue
                node = await device_object.add_variable(
                    self._node_id(f"{device_path}.{node_name}"),
                    node_name,
                    _initial_value_for_node(node_name),
                )
                self.nodes_by_device[device.device_id][node_name] = node

    async def _add_experiment_metadata(self, factory: Any) -> None:
        experiment = await factory.add_object(self._node_id("Factory.Experiment"), "Experiment")
        for node_name in EXPERIMENT_NODE_NAMES:
            await experiment.add_variable(
                self._node_id(f"Factory.Experiment.{node_name}"),
                node_name,
                self.experiment_metadata.get(node_name, ""),
            )

    def _node_id(self, string_id: str) -> ua.NodeId:
        if self.namespace_index is None:
            raise RuntimeError("OPC UA namespace is not registered.")
        return ua.NodeId(string_id, self.namespace_index)


def opcua_device_name(device_id: str) -> str:
    device_type, number = device_id.split("-", maxsplit=1)
    return f"{DEVICE_TYPE_PREFIX[device_type]}{number}"


def opcua_node_string_id(device_id: str, node_name: str) -> str:
    return f"Factory.Line1.{opcua_device_name(device_id)}.{node_name}"


def opcua_experiment_node_string_id(node_name: str) -> str:
    return f"Factory.Experiment.{node_name}"


def opcua_node_references(devices: list[BaseDevice]) -> list[OpcUaNodeReference]:
    references: list[OpcUaNodeReference] = []
    for device in devices:
        node_names = list(METADATA_NODE_NAMES)
        node_names.extend(VALUE_NODE_NAMES[key] for key in DEVICE_VALUE_KEYS[device.device_type])
        for node_name in dict.fromkeys(node_names):
            references.append(
                OpcUaNodeReference(
                    device_id=device.device_id,
                    node_name=node_name,
                    node_string_id=opcua_node_string_id(device.device_id, node_name),
                )
            )
    return references


def _initial_value_for_node(node_name: str) -> str | int | float | bool:
    if node_name in {"DeviceId", "DeviceType", "SensorTimestamp", "Status", "AnomalyType", "ValveState"}:
        return ""
    if node_name == "Sequence":
        return 0
    if node_name == "IsAnomaly":
        return False
    return 0.0
