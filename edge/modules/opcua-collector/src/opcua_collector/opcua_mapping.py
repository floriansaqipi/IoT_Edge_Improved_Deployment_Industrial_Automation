from __future__ import annotations

import re


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

_PREFIX_TO_DEVICE_TYPE = {prefix: device_type for device_type, prefix in DEVICE_TYPE_PREFIX.items()}
_DEVICE_RE = re.compile(r"^(Motor|Pump|Conveyor|Tank|Compressor)(\d{3,})$")


def device_type_from_name(device_name: str) -> str:
    match = _DEVICE_RE.match(device_name)
    if match is None:
        raise ValueError(f"Unsupported OPC UA device object name: {device_name}.")
    return _PREFIX_TO_DEVICE_TYPE[match.group(1)]


def is_known_device_name(device_name: str) -> bool:
    return _DEVICE_RE.match(device_name) is not None


def device_name_to_id(device_name: str) -> str:
    match = _DEVICE_RE.match(device_name)
    if match is None:
        raise ValueError(f"Unsupported OPC UA device object name: {device_name}.")
    device_type = _PREFIX_TO_DEVICE_TYPE[match.group(1)]
    return f"{device_type}-{match.group(2)}"


def device_sort_key(device_name: str) -> tuple[int, int]:
    match = _DEVICE_RE.match(device_name)
    if match is None:
        return (len(DEVICE_TYPE_PREFIX), 0)
    order = tuple(DEVICE_TYPE_PREFIX.values()).index(match.group(1))
    return (order, int(match.group(2)))


def value_keys_for_device_name(device_name: str) -> tuple[str, ...]:
    return DEVICE_VALUE_KEYS[device_type_from_name(device_name)]


def node_string_id(device_name: str, node_name: str) -> str:
    return f"Factory.Line1.{device_name}.{node_name}"


def experiment_node_string_id(node_name: str) -> str:
    return f"Factory.Experiment.{node_name}"


def node_id_text(namespace_index: int, string_id: str) -> str:
    return f"ns={namespace_index};s={string_id}"
