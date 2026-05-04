# Azure IoT Edge Study: Actual Implementation Context

## 0. Purpose Of This File

This file is a self-contained context document for the actual implemented
Azure IoT Edge microservice placement study in this repository.

It is meant to be copied into ChatGPT or another analysis tool when generating
architecture diagrams, experiment graphs, paper text, or interpretation notes.
It summarizes what was actually built in the repository, how the scenarios work,
where data is generated and stored, and how the budgeted experiment controller
runs the study.

This file does not replace the original long-term design file:

```text
azure_iot_edge_study_context_for_codex_with_s3_two_laptop_architecture.md
```

That original file describes the broader S0/S1/S2/S3 research idea. The active
implemented study is the budgeted S0/S1/S2 version described here and in:

```text
azure_iot_edge_study_context_800k_daily_budget.md
```

Important safety note: this file intentionally contains no secret values. It may
name Azure resources, devices, modules, paths, and architecture choices, but it
does not contain runtime credentials or connection strings.

## 1. Project Story

The scientific goal is to study how the placement of microservices across cloud
and edge layers affects an industrial automation telemetry pipeline. The project
simulates industrial devices, exposes their live values over OPC UA, ingests the
data through different cloud/edge paths, and compares latency, throughput,
cloud traffic, message loss, anomaly behavior, and edge resource use.

The original research design contained four scenario families:

| Scenario | Original meaning | Current implementation status |
|---|---|---|
| S0 | Cloud-only baseline | Implemented |
| S1 | Azure IoT Edge pass-through | Implemented |
| S2 | Hybrid edge-cloud microservice placement | Implemented |
| S3 | Edge-heavy processing with local storage and cloud sync | Deferred |

S3 is intentionally not part of the first active experiment matrix. It remains
future work because the first full run was redesigned around an Azure IoT Hub
daily message budget.

The active study compares S0, S1, and S2 under a controlled two-machine lab
layout:

```text
Machine A -> Machine B -> Azure
```

Machine A creates industrial telemetry and exposes it through OPC UA. Machine B
runs Azure IoT Edge or the S0 direct publisher. Azure receives cloud-bound
messages through IoT Hub and processes them with a single Azure Function.

## 2. Physical And Cloud Architecture

### Machine A: Data Creation And OPC UA Simulator

Machine A is the Windows simulator laptop. In the lab setup it is expected to
use LAN IP:

```text
192.168.1.5
```

Machine A runs the Python industrial simulator from:

```text
simulator/industrial-opcua-simulator/
```

It is responsible for:

- generating virtual industrial telemetry;
- injecting controlled faults;
- writing local JSONL and CSV ground truth;
- exposing live OPC UA nodes at:

```text
opc.tcp://192.168.1.5:4840/factory/server
```

The OPC UA server binds to:

```text
opc.tcp://0.0.0.0:4840/factory/server
```

Machine B connects to Machine A through the LAN endpoint.

### Machine B: Edge Host And Cloud-Bound Publisher Host

Machine B is the Ubuntu Server VM used as the edge host. In the lab setup it is
expected to use LAN IP:

```text
192.168.1.3
```

Machine B runs:

- Azure IoT Edge runtime;
- Docker/Moby container runtime;
- S1 and S2 IoT Edge modules;
- the S0 non-Edge publisher container;
- network shaping commands for delay and cloud outage tests.

Machine B is also where cloud-bound network conditions are applied. The project
shapes only Machine B to Azure IoT Hub traffic, not the Machine A to Machine B
OPC UA link. This keeps the OPC UA industrial LAN path separate from the
cloud-bound path being studied.

### Azure Cloud Layer

The Azure cloud layer receives and processes cloud-bound telemetry. The actual
resource names used in this implementation are:

| Resource | Name |
|---|---|
| Resource group | `rg-iot-edge-placement-study` |
| IoT Hub | `iothub-edge-study-florian01` |
| IoT Edge device identity | `edge-gateway-b-ubuntu` |
| S0 non-Edge device identity | `s0-cloud-publisher-b` |
| ACR login server | `acredgestudyflorian01.azurecr.io` |
| Storage account | `stedgecloudflorian01` |
| Function App | `func-edge-study-cloudproc-florian01` |
| IoT Hub consumer group for cloud processor | `cloudproc` |

The cloud path uses:

- Azure IoT Hub Standard S1 with 2 units for the budgeted experiment;
- Azure Container Registry Basic for module/container images;
- Azure Function runtime 4 with Python 3.12;
- Azure Table Storage tables for processed outputs;
- Azure Monitor metrics for IoT Hub usage and throttling checks.

## 3. Repository Map

The main implemented areas are:

```text
simulator/industrial-opcua-simulator/   Python simulator and OPC UA server
edge/modules/                           IoT Edge module source code
edge/deployments/                       S1, S2, and idle deployment templates
cloud/s0-cloud-publisher/               S0 direct cloud publisher container
cloud/azure-function/                   Azure Function app package
cloud/cloud_processor/                  Cloud validation, detection, table mapping
cloud/tools/                            Cloud result export tooling
experiments/                            Budget matrix and budget preflight logic
experiments/controller/                 Experiment controller
infrastructure/                         Azure, firewall, and network setup notes
scripts/                                PowerShell helper scripts
tests/                                  Unit and integration tests
results/                                Local experiment evidence and generated files
```

Generated data and local runtime files are ignored by git. Important ignored
locations include:

```text
simulator/industrial-opcua-simulator/results/
cloud/results/
results/experiments/
.env.experiment.local
edge/deployments/*.generated.json
```

## 4. Data Creation Layer

The data creation layer is a Python 3.12 simulator. It was built first as a
local-only simulator and later extended with OPC UA server mode.

Main entrypoint:

```text
simulator/industrial-opcua-simulator/src/main.py
```

Configuration loading:

```text
simulator/industrial-opcua-simulator/src/config_loader.py
```

Ground truth logging:

```text
simulator/industrial-opcua-simulator/src/ground_truth_logger.py
```

OPC UA server implementation:

```text
simulator/industrial-opcua-simulator/src/opcua_server.py
```

Device models:

```text
simulator/industrial-opcua-simulator/src/devices/
```

### Device Types

The simulator models five industrial device categories:

| Device type | Example ID | Typical values |
|---|---|---|
| Motor | `motor-001` | temperature, vibration, rpm, current, load, status |
| Pump | `pump-001` | pressure, flowRate, temperature, vibration, current, status |
| Conveyor | `conveyor-001` | speed, load, motorCurrent, vibration, status |
| Tank | `tank-001` | level, pressure, inletFlow, outletFlow, valveState, status |
| Compressor | `compressor-001` | pressure, temperature, vibration, current, status |

The simulator does not generate purely independent random values. It generates
correlated signals. Examples:

- motor load affects current, rpm, vibration, and temperature;
- pump blockage raises pressure/current and lowers flow;
- conveyor jam lowers speed and raises load/current/vibration;
- tank overflow risk raises level while outlet flow is restricted;
- compressor pressure instability creates abnormal pressure oscillation.

### Device States And Faults

Each device can move through:

```text
NORMAL -> WARNING -> FAULT -> RECOVERY -> NORMAL
```

Faults are configured through YAML schedules. Ground truth is generated before
any edge or cloud processing, so it can later be used to evaluate anomaly
detection and message loss.

Implemented anomaly types include:

| Device | Example anomaly types |
|---|---|
| Motor | `overload`, `overheating`, `bearing_fault` |
| Pump | `blockage`, `pressure_drop`, `leak` |
| Conveyor | `jam` |
| Tank | `overflow_risk` |
| Compressor | `pressure_instability` |

### Simulator Message Shape

Each generated JSONL record is one full device update. It contains metadata,
timestamps, sensor values, and ground truth:

```json
{
  "experimentId": "budgeted_800k_s0_s1_s2",
  "scenario": "S1_EDGE_PASS_THROUGH",
  "runId": "s1_90_normal_rep1_campaign_id",
  "deviceId": "motor-001",
  "deviceType": "motor",
  "sequence": 1,
  "sensorTimestamp": "2026-05-04T00:00:00.000000Z",
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

CSV output flattens common metadata, ground truth fields, and known sensor
columns. JSONL and CSV are both used as local ground-truth evidence.

### Simulator Modes

The simulator supports these run modes:

| Mode | Meaning |
|---|---|
| `file` | Generate local JSONL/CSV only |
| `opcua` | Expose live OPC UA values only |
| `both` | Expose OPC UA values and write local JSONL/CSV ground truth |

Useful commands:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps.yaml
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps_opcua.yaml --mode both --realtime
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps_opcua.yaml --until-stopped
```

Phase 1 paired outputs can be regenerated with:

```powershell
.\scripts\run_phase1_outputs.ps1
```

## 5. OPC UA Layer

The OPC UA server exposes the simulated factory address space under:

```text
Objects/Factory/Line1
```

Example device paths:

```text
Objects/Factory/Line1/Motor001
Objects/Factory/Line1/Pump001
Objects/Factory/Line1/Conveyor001
Objects/Factory/Line1/Tank001
Objects/Factory/Line1/Compressor001
```

Stable string NodeIds are used. Examples:

```text
ns=<study>;s=Factory.Line1.Motor001.Temperature
ns=<study>;s=Factory.Line1.Motor001.Sequence
ns=<study>;s=Factory.Line1.Motor001.IsAnomaly
```

Run metadata is exposed under:

```text
Objects/Factory/Experiment
```

with nodes:

```text
Factory.Experiment.ExperimentId
Factory.Experiment.Scenario
Factory.Experiment.RunId
```

The namespace URI is:

```text
urn:industrial-automation:azure-iot-edge-study
```

Phase 2 lab testing uses anonymous NoSecurity OPC UA. Security certificates are
not the focus of the current experiment.

## 6. Active Scenario Implementations

The active implemented scenarios are S0, S1, and S2.

### S0: Direct Cloud Baseline

S0 bypasses Azure IoT Edge processing. It still runs on Machine B so that
network delay and outage can be applied on the same cloud-bound path as S1 and
S2.

Flow:

```text
Machine A OPC UA simulator
  -> Machine B s0-cloud-publisher Docker container
  -> Azure IoT Hub
  -> Azure Function ProcessIoTHubTelemetry
  -> Azure Table Storage
```

Implementation:

```text
cloud/s0-cloud-publisher/
```

S0 uses `IoTHubDeviceClient.create_from_connection_string()` through the Azure
IoT Python SDK. The S0 publisher reads OPC UA snapshots with the same discovery
logic used by the Edge collector, adds direct publisher timestamps, and sends
device-to-cloud messages as a normal IoT Hub device identity:

```text
s0-cloud-publisher-b
```

S0 timestamp additions:

```text
directPublisherReceivedTimestamp
cloudPublishTimestamp
edgeReceivedTimestamp: null
```

Before S0 runs, the controller deploys an idle Edge manifest so S1/S2 modules do
not also publish the same OPC UA stream.

### S1: Azure IoT Edge Pass-Through

S1 measures the overhead of using Azure IoT Edge as a gateway without deep local
processing.

Flow:

```text
Machine A OPC UA simulator
  -> Machine B IoT Edge opcua-collector
  -> $edgeHub
  -> Azure IoT Hub
  -> Azure Function ProcessIoTHubTelemetry
  -> Azure Table Storage
```

Implementation:

```text
edge/modules/opcua-collector/
edge/deployments/s1-edge-pass-through.template.json
```

The collector:

- connects to `opc.tcp://192.168.1.5:4840/factory/server`;
- discovers devices under `Factory/Line1`;
- subscribes to each device `Sequence` node;
- reads a full device snapshot whenever sequence changes;
- adds `edgeReceivedTimestamp`;
- forwards one JSON telemetry message to Edge Hub output `telemetry`.

The S1 Edge route is:

```text
FROM /messages/modules/opcua-collector/outputs/telemetry INTO $upstream
```

### S2: Hybrid Edge-Cloud Microservice Pipeline

S2 is the main proposed edge-cloud placement strategy. Full telemetry is
processed locally on Machine B, but only sampled telemetry plus alerts are sent
to Azure.

Flow:

```text
Machine A OPC UA simulator
  -> opcua-collector
  -> normalizer-validator
  -> filter-aggregator
  -> anomaly-detector
  -> sampled telemetry -> Azure IoT Hub -> Azure Function -> Table Storage
  -> alerts -> local-alert-service -> Azure IoT Hub -> Azure Function -> Table Storage
```

Implementation:

```text
edge/modules/normalizer-validator/
edge/modules/filter-aggregator/
edge/modules/anomaly-detector/
edge/modules/local-alert-service/
edge/deployments/s2-hybrid.template.json
```

S2 module roles:

| Module | Role |
|---|---|
| `opcua-collector` | Reads OPC UA snapshots and emits collector-shaped telemetry |
| `normalizer-validator` | Validates required fields and adds `normalizedTimestamp` |
| `filter-aggregator` | Adds `filteredTimestamp` and `edgeRouting.cloudCandidate` |
| `anomaly-detector` | Runs edge anomaly rules without using `groundTruth` |
| `local-alert-service` | Writes compact local alert records and forwards compact alerts |

S2 cloud reduction policy:

```text
CLOUD_OUTPUT_POLICY=sampled_10_percent
SAMPLE_EVERY=10
CLOUD_MAX_MESSAGES_PER_SECOND=9
```

The filter marks roughly every 10th normal telemetry message as a cloud
candidate. The detector forwards cloud candidates and detected anomalies. Alerts
bypass normal telemetry sampling and are routed with higher priority.

S2 alert log on Machine B:

```text
/home/floriansaqipi/iot_edge_study/alerts/s2_alerts.jsonl
```

S2 route chain:

```text
opcua-collector -> normalizer-validator
normalizer-validator -> filter-aggregator
filter-aggregator -> anomaly-detector
anomaly-detector telemetry -> $upstream
anomaly-detector alerts -> local-alert-service
local-alert-service alerts -> $upstream
```

All S2 modules are Docker images deployed as Azure IoT Edge modules from ACR.

## 7. Cloud Processing Layer

All active scenarios use the same cloud processor. There is not one Function App
per scenario. S0, S1, and S2 messages all flow into the same Azure Function:

```text
ProcessIoTHubTelemetry
```

Implementation:

```text
cloud/azure-function/function_app.py
cloud/cloud_processor/src/cloud_processor/
```

The Function reads from the IoT Hub built-in Event Hubs-compatible endpoint
using consumer group:

```text
cloudproc
```

It writes to three Azure Table Storage tables:

| Table | Meaning |
|---|---|
| `CloudTelemetry` | Valid processed telemetry rows |
| `CloudAlerts` | Alert rows from edge or cloud detection |
| `CloudInvalid` | Invalid JSON or invalid schema rows |

For S0 and S1, the cloud processor runs cloud-side anomaly detection and adds:

```text
cloudDetection
```

For S2, the cloud processor preserves:

```text
edgeDetection
```

and does not overwrite it with cloud detection. This keeps S2 as an edge
anomaly-detection scenario.

Table partitioning is based on:

```text
experimentId|scenario|runId
```

The RowKey uses origin, device, sequence, and Event Hub metadata to avoid
overwrites.

Cloud results can be exported locally with:

```powershell
.\scripts\export_cloud_results.ps1
```

The exported files are written under:

```text
cloud/results/
```

## 8. Active Budgeted Experiment Matrix

The active machine-readable matrix is:

```text
experiments/budgeted_800k_matrix.yaml
```

Matrix limits:

| Limit | Value |
|---|---:|
| Daily IoT Hub hard cap | 800,000 messages/day |
| Planned operational ceiling | 640,000 messages |
| Main cloud rate limit | 90 msg/s |
| Billable chunk size | 4,096 bytes |
| Default device count | 100 |
| Estimated payload size | 2,048 bytes |
| Planned cloud messages | 544,320 |

The active matrix has 12 rows and 3 repetitions per row, producing 36 planned
runs.

| Row ID | Scenario | Block | Generated rate | Cloud rate | Duration | Reps | Cloud policy |
|---|---|---|---:|---:|---:|---:|---|
| `s0_90_normal` | S0 | normal network | 90 | 90 | 300s | 3 | full |
| `s1_90_normal` | S1 | normal network | 90 | 90 | 300s | 3 | full |
| `s2_90_normal` | S2 | normal network | 90 | 9 | 300s | 3 | sampled 10 percent |
| `s0_90_delay_200` | S0 | 200 ms delay | 90 | 90 | 300s | 3 | full |
| `s1_90_delay_200` | S1 | 200 ms delay | 90 | 90 | 300s | 3 | full |
| `s2_90_delay_200` | S2 | 200 ms delay | 90 | 9 | 300s | 3 | sampled 10 percent |
| `s0_90_outage_120` | S0 | cloud outage | 90 | 90 | 300s | 3 | full |
| `s1_90_outage_120` | S1 | cloud outage | 90 | 90 | 300s | 3 | full |
| `s2_90_outage_120` | S2 | cloud outage | 90 | 9 | 300s | 3 | sampled 10 percent |
| `s0_500_stress_capped` | S0 | local/edge stress | 500 | 90 | 60s | 3 | capped |
| `s1_500_stress_capped` | S1 | local/edge stress | 500 | 90 | 60s | 3 | capped |
| `s2_500_stress_capped` | S2 | local/edge stress | 500 | 9 | 60s | 3 | capped |

Important interpretation:

- 90 msg/s is the main cloud-qualified load for normal, delay, and outage rows.
- 500 msg/s is only a short local/edge stress block.
- In stress rows, local generated messages can exceed cloud messages.
- S2 intentionally sends much less cloud traffic than S0/S1.
- Packet-loss rows and S3 rows are not in the first active matrix.

Budget preflight command:

```powershell
.\scripts\check_experiment_budget.ps1
```

## 9. Network Conditions

Network shaping is applied on Machine B to cloud-bound IoT Hub traffic. The
default script is:

```text
infrastructure/host-vm-setup/ubuntu-network-emulation.sh
```

Controller network helper:

```text
experiments/controller/network.py
```

Cloud-bound ports targeted by the controller:

```text
443,5671,8883
```

Active network conditions:

| Condition | Behavior |
|---|---|
| `normal` | No artificial cloud-bound impairment |
| `delay_200ms` | Apply 200 ms delay to IoT Hub-bound traffic |
| `cloud_outage_120s` | Block IoT Hub-bound traffic during the outage window |

For a 300 second outage run, the schedule is:

```text
90s pre-outage
120s cloud outage
90s recovery
```

Packet loss support exists in the network command builder, but packet-loss rows
are not part of the first active matrix.

## 10. Experiment Controller

The experiment controller runs from Machine A and orchestrates Machine B over
SSH. It is implemented under:

```text
experiments/controller/
```

Primary CLI:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller dry-run --matrix experiments\budgeted_800k_matrix.yaml
.\.venv\Scripts\python.exe -m experiments.controller run --matrix experiments\budgeted_800k_matrix.yaml --mode smoke
.\.venv\Scripts\python.exe -m experiments.controller run --matrix experiments\budgeted_800k_matrix.yaml --mode full
.\.venv\Scripts\python.exe -m experiments.controller status --campaign latest
```

Wrapper scripts:

```text
scripts/run_experiment_controller.ps1
scripts/query_experiment_status.ps1
```

The controller loads settings from environment variables or:

```text
.env.experiment.local
```

That file is intentionally ignored by git and must not be copied into paper or
context documents.

### Controller Responsibilities

For each planned run, the controller:

1. writes a deterministic run ID;
2. creates a per-run result folder;
3. writes `run_manifest.json`;
4. builds a temporary simulator config with JSONL and CSV outputs;
5. renders the correct Edge manifest or idle manifest;
6. starts the selected scenario;
7. starts the Machine A OPC UA simulator;
8. confirms Machine B can reach Machine A OPC UA;
9. applies network delay or outage if needed;
10. waits for the configured duration;
11. collects IoT Hub metrics before and after;
12. exports Azure Table rows for the run;
13. collects Edge/Docker logs and stats;
14. clears network shaping in cleanup;
15. restores idle Edge unless instructed otherwise;
16. writes `run_summary.json` and `status.json`.

### Result Folder Structure

Campaign results are stored under:

```text
results/experiments/<campaignId>/<rowId>/rep_<n>/
```

Typical per-run files:

```text
run_manifest.json
status.json
events.jsonl
run_summary.json
simulator_config.yaml
simulator.jsonl
simulator.csv
CloudTelemetry.jsonl
CloudTelemetry.csv
CloudAlerts.jsonl
CloudAlerts.csv
CloudInvalid.jsonl
CloudInvalid.csv
iot_hub_metrics_before.json
iot_hub_metrics_after.json
machine_b_iotedge_list.log
machine_b_docker_stats.log
machine_b_docker_ps.jsonl
module_<module-name>.log
s0_cloud_publisher.log
s2_alerts_tail.jsonl
network_before.log
network_apply.log
network_clear.log
network_cleanup.log
```

The controller also writes:

```text
results/experiments/_latest.json
```

That file is meant for progress checks from another chat or terminal while a
campaign is running.

### Campaign Status

A full experiment campaign was started with an ID shaped like:

```text
full_20260504_013601
```

Do not treat all campaign rows as final scientific results until Phase 7
validates run quality. The correct way to inspect the current campaign state is:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller status --campaign latest
```

## 11. Metrics And Evidence

The study intentionally keeps local generated telemetry separate from
cloud-received telemetry. This is critical for the budgeted experiment, because
S2 and stress rows may process more locally than they send to Azure.

### Primary Evidence Sources

| Evidence | Location |
|---|---|
| Local generated telemetry | per-run `simulator.jsonl` and `simulator.csv` |
| Cloud telemetry | `CloudTelemetry` table and per-run exports |
| Cloud/edge alerts | `CloudAlerts` table and S2 local alert log |
| Invalid cloud messages | `CloudInvalid` table |
| Edge module logs | per-run `module_<module-name>.log` |
| S0 publisher logs | per-run `s0_cloud_publisher.log` |
| Edge resource samples | `docker stats`, `docker ps`, `iotedge list` logs |
| IoT Hub metrics | per-run `iot_hub_metrics_before/after.json` |
| Network evidence | per-run network logs |

### Matching Keys

Phase 7 should match local ground truth to cloud rows using:

```text
experimentId
scenario
runId
deviceId
sequence
```

These keys connect local JSONL/CSV ground truth to cloud Table Storage rows.

### Metrics To Compute In Phase 7

Latency metrics:

- sensor to edge received;
- sensor to normalized;
- sensor to filtered;
- sensor to anomaly detection;
- sensor to cloud received;
- publisher to cloud;
- outage recovery latency.

For each latency category:

```text
mean, min, max, standard deviation, p50, p95, p99
```

Throughput metrics:

- generated messages per second;
- cloud received messages per second;
- S2 sampled telemetry rate;
- alert rate;
- local/edge stress handling.

Reliability and quality metrics:

- generated count vs expected count;
- cloud count vs planned cloud count;
- message loss by matching local and cloud rows;
- invalid cloud rows;
- IoT Hub throttling or quota issues;
- Edge module restarts;
- run-quality pass/fail flags.

Anomaly metrics:

- edge/cloud detection count;
- anomaly type distribution;
- alert latency;
- comparison against ground truth;
- false positives and false negatives where computable.

Resource metrics:

- Machine B module CPU/RAM samples from Docker/IoT Edge logs;
- cloud message reduction ratio for S2;
- Azure IoT Hub daily quota use;
- send throttle events.

## 12. Current Status And Caveats

Implemented phases:

| Phase | Status |
|---|---|
| Phase 1 local simulator | Implemented |
| Phase 2 OPC UA simulator | Implemented |
| Phase 3 S1 Edge ingestion | Implemented |
| Phase 4 S2 edge microservices | Implemented |
| Phase 5 S0 cloud path and Azure cloud processor | Implemented |
| Phase 6 budgeted experiment controller | Implemented |
| Phase 7 analysis | Still needed |

Important caveats:

- S3 edge-heavy storage/sync is not part of the active run.
- Packet-loss rows are not part of the active run.
- The full experiment campaign must be validated before final paper claims.
- Some repetitions may need reruns if cloud counts, module readiness, or export
  evidence show run-quality problems.
- Graphs should distinguish generated local messages from cloud-received
  messages, especially for S2 and 500 msg/s stress rows.
- S2 should be described as reducing cloud traffic by sampling/capping and
  alert forwarding, not as eliminating local raw telemetry.

## 13. Graph And Diagram Ideas

This file can be used to ask ChatGPT or a graphing tool to create these visuals.

### Physical Architecture Diagram

Show:

```text
Machine A Windows simulator laptop
  -> OPC UA over LAN
Machine B Ubuntu Server VM
  -> Azure IoT Hub
Azure Function
Azure Table Storage
```

Include Machine A IP `192.168.1.5`, Machine B IP `192.168.1.3`, and OPC UA
endpoint `opc.tcp://192.168.1.5:4840/factory/server`.

### Scenario Data Flow Diagrams

Create separate diagrams for:

```text
S0: simulator -> s0-cloud-publisher -> IoT Hub -> Function -> tables
S1: simulator -> opcua-collector -> edgeHub -> IoT Hub -> Function -> tables
S2: simulator -> collector -> normalizer -> filter -> detector -> alert service -> IoT Hub -> Function -> tables
```

### Edge Module Pipeline Diagram

For S2, show the five modules and route priorities:

```text
opcua-collector
  -> normalizer-validator
  -> filter-aggregator
  -> anomaly-detector
       -> telemetry to cloud
       -> alerts to local-alert-service
            -> alerts to cloud
```

### Budgeted Experiment Matrix Chart

Useful chart forms:

- bar chart of planned cloud messages per block;
- grouped bar chart by scenario and block;
- table heatmap of generated rate vs cloud rate;
- total planned cloud messages vs 800,000 hard cap.

### Cloud Reduction Chart

Compare S0, S1, and S2 cloud output:

```text
S0 normal/delay/outage: 90 msg/s cloud
S1 normal/delay/outage: 90 msg/s cloud
S2 normal/delay/outage: 9 msg/s cloud plus alerts
```

For stress:

```text
S0 stress: 500 msg/s generated, 90 msg/s cloud cap
S1 stress: 500 msg/s generated, 90 msg/s cloud cap
S2 stress: 500 msg/s generated, 9 msg/s cloud cap plus alerts
```

### Latency And Reliability Graphs

Useful Phase 7 graphs:

- p50/p95/p99 latency per scenario and network condition;
- CDF of sensor-to-cloud latency;
- generated vs cloud-received count per run;
- message loss percentage per run;
- outage timeline showing before/outage/recovery phases;
- anomaly alert latency by scenario;
- Edge CPU/RAM by module for S1 vs S2.

## 14. Tools And Libraries Actually Used

Main local/runtime tools:

- Python 3.12 virtual environment;
- `pyyaml`, `numpy`, `pytest`, `ruff`;
- `asyncua` for OPC UA server/client behavior;
- `azure-iot-device` for IoT Hub device and module clients;
- `azure-data-tables` for Table Storage;
- Azure CLI with `azure-iot` extension;
- Docker/Moby;
- Azure IoT Edge runtime 1.5;
- PowerShell helper scripts on Machine A;
- SSH/Paramiko for controller orchestration;
- `tc netem` and `iptables` on Machine B for network conditions.

Useful external/manual tools:

- UaExpert for browsing OPC UA nodes;
- Wireshark or `tcpdump` for packet inspection if needed;
- Azure Portal log stream and Azure Monitor metrics for cloud validation.

Not part of the current implemented pipeline unless added later:

- Microsoft OPC Publisher;
- Prometheus;
- Node Exporter;
- cAdvisor;
- Grafana;
- S3 local storage/cloud sync modules.

## 15. Common Commands

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Check budget:

```powershell
.\scripts\check_experiment_budget.ps1
```

Run controller dry run:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller dry-run --matrix experiments\budgeted_800k_matrix.yaml
```

Run controller smoke:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller run --matrix experiments\budgeted_800k_matrix.yaml --mode smoke
```

Check current campaign status:

```powershell
.\.venv\Scripts\python.exe -m experiments.controller status --campaign latest
```

Package Azure Function:

```powershell
.\scripts\package_phase5_function.ps1
```

Export cloud results:

```powershell
.\scripts\export_cloud_results.ps1
```

Render S1/S2 manifests:

```powershell
.\scripts\render_s1_deployment.ps1
.\scripts\render_s2_deployment.ps1
```

## 16. How To Interpret The Study

S0 answers: what happens if industrial telemetry is sent to cloud processing
without Azure IoT Edge microservice placement?

S1 answers: what overhead or resilience does Azure IoT Edge introduce when used
mainly as a gateway?

S2 answers: what changes when normalization, filtering, anomaly detection, and
local alerting are placed at the edge, while only sampled telemetry and alerts
go to the cloud?

The most important comparison is not just latency. It is the combination of:

- cloud traffic reduction;
- edge resource cost;
- anomaly/alert timeliness;
- reliability during cloud delay/outage;
- message loss and recovery;
- ability to compute metrics from local ground truth and cloud evidence.

The final scientific conclusions should be written only after Phase 7 validates
all repetitions and computes the statistics.
