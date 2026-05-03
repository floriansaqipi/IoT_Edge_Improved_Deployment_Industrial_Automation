# Azure IoT Edge Microservice Placement Study

This repository contains the experimental implementation for an Azure IoT Edge
microservice placement study in industrial automation.

Phase 1 is a local-only industrial simulator. It does not require Azure, Docker,
OPC UA, or cloud resources yet. The simulator generates correlated telemetry for
virtual motors, pumps, conveyors, tanks, and compressors, injects controlled
faults, and writes ground-truth output to JSONL or CSV.

## Setup

Use the existing Python 3.12 virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run Phase 1

Run one of the starter experiment configs:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps.yaml
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_50_devices_100mps.yaml
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_100_devices_500mps.yaml
```

Override duration, output path, or output format when doing quick checks:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps.yaml --duration 3 --output simulator\industrial-opcua-simulator\results\quick.jsonl --format jsonl
```

Generated run files are written under
`simulator/industrial-opcua-simulator/results/` by default and are ignored by
git.

## Output Schema

Each JSONL row is one full device update:

```json
{
  "experimentId": "phase1_exp_10_10mps",
  "scenario": "LOCAL_ONLY",
  "runId": "exp_10_devices_10mps_rep1",
  "deviceId": "motor-001",
  "deviceType": "motor",
  "sequence": 1,
  "sensorTimestamp": "2026-01-01T00:00:00.000000Z",
  "edgeReceivedTimestamp": null,
  "normalizedTimestamp": null,
  "filteredTimestamp": null,
  "anomalyTimestamp": null,
  "cloudReceivedTimestamp": null,
  "values": {
    "temperature": 64.2,
    "vibration": 0.31,
    "rpm": 1464.5,
    "current": 8.3,
    "load": 59.8,
    "status": "NORMAL"
  },
  "groundTruth": {
    "isAnomaly": false,
    "anomalyType": null
  }
}
```

CSV output flattens common metadata, ground-truth fields, and all known sensor
columns.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```
