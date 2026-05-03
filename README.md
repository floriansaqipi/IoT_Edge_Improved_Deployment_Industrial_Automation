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

Phase 3 adds S1 Azure IoT Edge ingestion. Machine B runs a custom
`opcua-collector` module that subscribes to the Machine A OPC UA server and
forwards full pass-through telemetry to IoT Hub through `$edgeHub`.

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

The simulator also exposes run metadata for Phase 3 under
`Objects/Factory/Experiment`:

```text
ns=<study>;s=Factory.Experiment.ExperimentId
ns=<study>;s=Factory.Experiment.Scenario
ns=<study>;s=Factory.Experiment.RunId
```

## Run Phase 3 S1 Edge Ingestion

Build and deploy the collector from Machine A or a machine with Azure CLI access:

```bash
az acr build --registry <uniqueacrname> --image opcua-collector:0.1.0-amd64 edge/modules/opcua-collector
```

Render the local deployment manifest after creating ACR credentials:

```powershell
.\scripts\render_s1_deployment.ps1 -AcrLoginServer "<uniqueacrname>.azurecr.io" -AcrUsername "<acr-username>" -AcrPassword "<acr-password>"
```

Apply it to the Machine B Edge device:

```bash
az iot edge set-modules --hub-name <unique-iot-hub-name> --device-id edge-gateway-b-ubuntu --content edge/deployments/s1-edge-pass-through.generated.json
```

Detailed Azure and Ubuntu steps live in
`infrastructure/azure/phase3-azure-setup.md` and
`infrastructure/host-vm-setup/ubuntu-iotedge-notes.md`.

## Budgeted 800k/Day Study Plan

The active one-day scientific run is documented in
`azure_iot_edge_study_context_800k_daily_budget.md`. It keeps S0/S1/S2 and
defers S3 so the run fits an 800,000 IoT Hub messages/day hard cap.

Validate the machine-readable experiment matrix before any full Azure run:

```powershell
.\scripts\check_experiment_budget.ps1
```

The checked matrix is `experiments/budgeted_800k_matrix.yaml`; its planned cloud
total is 544,320 billable messages, below the 640,000 operational planning
ceiling.

## Run Phase 5 Cloud Path

Phase 5 adds the S0 cloud-only publisher and Azure cloud processor. S0 runs as a
plain Docker container on Machine B, not as an IoT Edge module:

```text
Machine A OPC UA simulator -> Machine B s0-cloud-publisher -> IoT Hub -> Azure Function -> Table Storage
```

Package the Function App:

```powershell
.\scripts\package_phase5_function.ps1
```

Export cloud results after a smoke or matrix run:

```powershell
$env:CLOUD_RESULTS_STORAGE_CONNECTION_STRING = "<storage-account-connection-string>"
.\scripts\export_cloud_results.ps1
Remove-Item Env:\CLOUD_RESULTS_STORAGE_CONNECTION_STRING
```

Detailed Azure commands live in `infrastructure/azure/phase5-cloud-path.md`.

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
