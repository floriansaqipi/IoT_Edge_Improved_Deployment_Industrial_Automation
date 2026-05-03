# Azure IoT Edge Microservice Placement Study

This repository contains the experimental implementation for an Azure IoT Edge
microservice placement study in industrial automation.

Phase 1 is a local-only industrial simulator. It does not require Azure, Docker,
OPC UA, or cloud resources yet. The simulator generates correlated telemetry for
virtual motors, pumps, conveyors, tanks, and compressors, injects controlled
faults, and writes ground-truth output to JSONL or CSV.

Phase 2 adds OPC UA server mode. The Windows simulator laptop is Machine A
(`192.168.1.5`) and the Ubuntu Server VM edge host is Machine B (`192.168.1.3`).
Machine B should connect to Machine A at:

```text
opc.tcp://192.168.1.5:4840/factory/server
```

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

Run a Phase 2 OPC UA profile:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps_opcua.yaml --mode both --realtime
```

For a longer live UaExpert or Machine B test, keep the server running until
interrupted:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps_opcua.yaml --until-stopped
```

Override duration, output path, or output format when doing quick checks:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps.yaml --duration 3 --output simulator\industrial-opcua-simulator\results\quick.jsonl --format jsonl
```

Generated run files are written under
`simulator/industrial-opcua-simulator/results/` by default and are ignored by
git.

Generate paired JSONL and CSV outputs for all Phase 1 starter configs:

```powershell
.\scripts\run_phase1_outputs.ps1
```

The current two-laptop lab default is Machine A at `192.168.1.5` and Machine B
at `192.168.1.3`. If OPC UA testing later needs a Windows Firewall exception,
preview the reversible rule first:

```powershell
.\infrastructure\host-vm-setup\windows-firewall-opcua.ps1 -Action Show
```

The OPC UA address space is exposed under `Objects/Factory/Line1` with stable
string NodeIds such as:

```text
ns=<study>;s=Factory.Line1.Motor001.Temperature
ns=<study>;s=Factory.Line1.Motor001.Sequence
ns=<study>;s=Factory.Line1.Motor001.IsAnomaly
```

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
