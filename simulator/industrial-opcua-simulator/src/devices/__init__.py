from devices.compressor import Compressor
from devices.conveyor import Conveyor
from devices.motor import Motor
from devices.pump import Pump
from devices.tank import Tank

DEVICE_CLASS_BY_TYPE = {
    "motor": Motor,
    "pump": Pump,
    "conveyor": Conveyor,
    "tank": Tank,
    "compressor": Compressor,
}

__all__ = ["Compressor", "Conveyor", "Motor", "Pump", "Tank", "DEVICE_CLASS_BY_TYPE"]
