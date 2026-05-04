# Azure IoT Edge Microservice Placement Study

This repository contains an experimental Azure IoT Edge study for industrial
automation. The goal is to compare where industrial telemetry microservices
should run: directly in the cloud, as a pass-through edge gateway, or as a
hybrid edge-cloud pipeline.

The implemented study uses a two-machine lab:

```text
Machine A: industrial simulator + OPC UA server
Machine B: Ubuntu Server VM with Azure IoT Edge, Docker/Moby, and network shaping
Azure: IoT Hub, Azure Function, Azure Table Storage, Azure Monitor, ACR
```

The active implementation compares three scenarios:

| Scenario | Name | Short meaning |
|---|---|---|
| S0 | Cloud-only baseline | OPC UA data is published from Machine B directly to IoT Hub without IoT Edge processing. |
| S1 | Edge pass-through | Azure IoT Edge collects OPC UA data and forwards full telemetry to IoT Hub. |
| S2 | Hybrid edge-cloud | Edge modules normalize, filter, detect anomalies, and send sampled telemetry plus alerts to cloud. |

S3 edge-heavy storage/sync was part of the original long-term idea, but it is
deferred from the current budgeted experiment.

## Active Experiment Matrix

The active matrix is `experiments/budgeted_800k_matrix.yaml`. It is designed to
fit within an 800,000 IoT Hub messages/day hard cap.

Summary:

| Property | Value |
|---|---:|
| Scenarios | S0, S1, S2 |
| Matrix rows | 12 |
| Repetitions per row | 3 |
| Planned runs | 36 |
| Simulated devices | 100 |
| Main generated rate | 90 msg/s |
| Stress generated rate | 500 msg/s |
| S0/S1 main cloud rate | 90 msg/s |
| S2 main cloud rate | 9 msg/s plus alerts |
| Main run duration | 300 s |
| Stress run duration | 60 s |
| Planned cloud messages | 544,320 |
| Daily hard cap | 800,000 |

Rows:

| Row ID | Scenario | Network block | Generated rate | Cloud rate | Duration | Cloud policy |
|---|---|---|---:|---:|---:|---|
| `s0_90_normal` | S0 | normal | 90 | 90 | 300s | full |
| `s1_90_normal` | S1 | normal | 90 | 90 | 300s | full |
| `s2_90_normal` | S2 | normal | 90 | 9 | 300s | sampled 10 percent |
| `s0_90_delay_200` | S0 | 200 ms delay | 90 | 90 | 300s | full |
| `s1_90_delay_200` | S1 | 200 ms delay | 90 | 90 | 300s | full |
| `s2_90_delay_200` | S2 | 200 ms delay | 90 | 9 | 300s | sampled 10 percent |
| `s0_90_outage_120` | S0 | 120 s cloud outage | 90 | 90 | 300s | full |
| `s1_90_outage_120` | S1 | 120 s cloud outage | 90 | 90 | 300s | full |
| `s2_90_outage_120` | S2 | 120 s cloud outage | 90 | 9 | 300s | sampled 10 percent |
| `s0_500_stress_capped` | S0 | local/edge stress | 500 | 90 | 60s | capped |
| `s1_500_stress_capped` | S1 | local/edge stress | 500 | 90 | 60s | capped |
| `s2_500_stress_capped` | S2 | local/edge stress | 500 | 9 | 60s | capped |

Packet-loss rows and S3 rows are not part of the first active matrix.

## Architecture

### Machine A: Data Creation Layer

Machine A is the Windows simulator laptop. It runs a Python 3.12 industrial
simulator under `simulator/industrial-opcua-simulator/`.

The simulator:

- generates correlated telemetry for motors, pumps, conveyors, tanks, and
  compressors;
- injects controlled faults and state transitions;
- writes local JSONL/CSV ground truth;
- exposes live values through OPC UA.

Default OPC UA endpoint for Machine B:

```text
opc.tcp://192.168.1.5:4840/factory/server
```

The OPC UA address space is under `Objects/Factory/Line1`, with stable NodeIds
such as:

```text
ns=<study>;s=Factory.Line1.Motor001.Temperature
ns=<study>;s=Factory.Line1.Motor001.Sequence
ns=<study>;s=Factory.Line1.Motor001.IsAnomaly
```

### Machine B: Edge And Cloud-Bound Host

Machine B is an Ubuntu Server VM at `192.168.1.3`. It runs Azure IoT Edge,
Docker/Moby, the S0 publisher container, and network emulation.

Network delay and outage are applied on Machine B to cloud-bound IoT Hub
traffic, not to the Machine A to Machine B OPC UA link.

### Azure Cloud Layer

Cloud-bound messages go through Azure IoT Hub and are processed by one Azure
Function:

```text
ProcessIoTHubTelemetry
```

The cloud processor writes to Azure Table Storage:

| Table | Purpose |
|---|---|
| `CloudTelemetry` | Valid processed telemetry |
| `CloudAlerts` | Edge or cloud anomaly alerts |
| `CloudInvalid` | Invalid JSON or invalid schema records |

## Scenario Data Flows

### S0: Cloud-Only Baseline

S0 uses a normal Docker container on Machine B, not an IoT Edge module.

```text
Machine A OPC UA simulator
  -> Machine B s0-cloud-publisher
  -> Azure IoT Hub
  -> Azure Function
  -> Azure Table Storage
```

The S0 publisher adds direct-cloud timestamps such as
`directPublisherReceivedTimestamp` and `cloudPublishTimestamp`.

### S1: Edge Pass-Through

S1 uses Azure IoT Edge as a gateway.

```text
Machine A OPC UA simulator
  -> opcua-collector
  -> edgeHub
  -> Azure IoT Hub
  -> Azure Function
  -> Azure Table Storage
```

The `opcua-collector` module subscribes to device sequence updates, reads full
OPC UA snapshots, adds `edgeReceivedTimestamp`, and forwards full telemetry.

### S2: Hybrid Edge-Cloud

S2 is the implemented edge microservice pipeline.

```text
Machine A OPC UA simulator
  -> opcua-collector
  -> normalizer-validator
  -> filter-aggregator
  -> anomaly-detector
       -> sampled telemetry to cloud
       -> alerts to local-alert-service
            -> compact alerts to cloud
```

S2 processes the full local stream at the edge, but sends only sampled telemetry
and alerts to Azure. This is the main traffic-reduction scenario.

## Repository Layout

```text
simulator/industrial-opcua-simulator/   Python simulator and OPC UA server
edge/modules/                           Azure IoT Edge module source code
edge/deployments/                       S1, S2, and idle deployment templates
cloud/s0-cloud-publisher/               S0 direct publisher container
cloud/azure-function/                   Azure Function app
cloud/cloud_processor/                  Cloud validation, detection, and table mapping
cloud/tools/                            Cloud result export tooling
experiments/                            Budget matrix and budget preflight logic
experiments/controller/                 Experiment controller
infrastructure/                         Azure, firewall, Ubuntu, and network setup notes
scripts/                                PowerShell helper scripts
tests/                                  Unit and integration tests
results/                                Local generated experiment evidence
```

## Technologies Used

Main technologies:

- Python 3.12;
- `asyncua` for OPC UA server/client behavior;
- Azure IoT Edge 1.5;
- Docker/Moby;
- Azure IoT Hub;
- Azure Functions with Python;
- Azure Table Storage;
- Azure Container Registry;
- Azure Monitor metrics;
- PowerShell helper scripts;
- SSH/Paramiko orchestration;
- `tc netem` and `iptables` for cloud-bound network conditions;
- `pytest` and `ruff`.

Useful manual tools:

- UaExpert for OPC UA browsing;
- Wireshark or `tcpdump` for network inspection;
- Azure Portal log stream and metrics for cloud validation.

Not used in the current implemented pipeline:

- Microsoft OPC Publisher;
- Prometheus, Node Exporter, cAdvisor, Grafana;
- S3 edge-heavy local storage/cloud sync modules.

## Data And Evidence

Each generated telemetry message contains:

- experiment metadata: `experimentId`, `scenario`, `runId`;
- device identity: `deviceId`, `deviceType`, `sequence`;
- timestamps: `sensorTimestamp`, edge timestamps, publisher timestamps, and
  `cloudReceivedTimestamp`;
- sensor `values`;
- simulator `groundTruth`;
- optional `edgeDetection` or `cloudDetection`.

Local ground truth is written as JSONL and CSV. Cloud results are exported from
Azure Table Storage as JSONL and CSV.

Phase 7 analysis should match local ground truth to cloud rows using:

```text
experimentId, scenario, runId, deviceId, sequence
```

## Results And Metrics

Per-run evidence is written under:

```text
results/experiments/<campaignId>/<rowId>/rep_<n>/
```

Typical evidence files include:

- simulator JSONL/CSV;
- cloud table exports;
- module logs;
- S0 publisher logs;
- Docker and IoT Edge status samples;
- IoT Hub metric snapshots;
- network emulation logs;
- `events.jsonl`, `status.json`, and `run_summary.json`.

Metrics to compute in analysis:

- generated vs cloud-received message count;
- message loss;
- throughput;
- sensor-to-cloud latency;
- p50/p95/p99 latency;
- cloud reduction ratio for S2;
- anomaly/alert latency;
- invalid cloud rows;
- IoT Hub throttling and quota usage;
- edge CPU/RAM/module stability.

## Running The Project

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run a local simulator config:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps.yaml
```

Run the OPC UA simulator with JSONL/CSV ground truth:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps_opcua.yaml --mode both --realtime
```

Keep the OPC UA server running for manual Edge or UaExpert testing:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps_opcua.yaml --until-stopped
```

Validate the budgeted matrix:

```powershell
.\scripts\check_experiment_budget.ps1
```

Run an experiment controller dry run:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller dry-run --matrix experiments\budgeted_800k_matrix.yaml
```

Run a short S0/S1/S2 smoke campaign:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller run --matrix experiments\budgeted_800k_matrix.yaml --mode smoke
```

Run the full matrix:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller run --matrix experiments\budgeted_800k_matrix.yaml --mode full
```

Check campaign progress from another terminal or chat:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller status --campaign latest
```

Export cloud results:

```powershell
.\scripts\export_cloud_results.ps1
```

## Tests

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run lint checks:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
```

The tests cover simulator config and device behavior, OPC UA mapping, S1
collector behavior, S2 module routing and detection, S0 publisher/cloud
processor behavior, budget validation, and experiment controller planning.

## Current Status And Caveats

Implemented:

- Phase 1 local simulator;
- Phase 2 OPC UA simulator;
- Phase 3 S1 Azure IoT Edge ingestion;
- Phase 4 S2 edge microservices;
- Phase 5 S0 publisher and Azure cloud processor;
- Phase 6 budgeted experiment controller.

Still needed:

- Phase 7 run-quality validation and statistical analysis;
- final graphs and paper-ready tables;
- reruns for any repetitions that fail quality checks.

Do not treat raw campaign output as final scientific results until Phase 7
validates each repetition.

## Related Context Documents

For a deeper handoff document, read:

```text
azure_iot_edge_study_actual_implementation_context.md
```

For the active budgeted experiment plan, read:

```text
azure_iot_edge_study_context_800k_daily_budget.md
```

For the original expanded S3/two-laptop concept, read:

```text
azure_iot_edge_study_context_for_codex_with_s3_two_laptop_architecture.md
```
