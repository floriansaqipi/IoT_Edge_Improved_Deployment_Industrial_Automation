# Codex Project Brief: Azure IoT Edge Microservice Placement Study for Industrial Automation

## 0. Purpose of this Markdown file

This file is a complete project-context handoff for another AI coding agent, especially Codex. It summarizes the entire planning conversation for a scientific study titled:

**Albanian title:**  
**“Përmirësimi i vendosjes së mikroshërbimeve në Azure IoT Edge për Automatizim Industrial”**

**English meaning:**  
**“Improving the Placement of Microservices in Azure IoT Edge for Industrial Automation.”**

The goal is to help Codex understand the research context, implementation target, simulator design, Azure IoT Edge architecture, experiment scenarios, metrics, and repo structure so it can help implement the project.

The project should produce an experimental system and results for a scientific paper. It should not remain conceptual only.

---

## 1. Scientific study overview

### 1.1 Main research idea

The study investigates whether placing selected industrial IoT microservices at the edge using **Azure IoT Edge** improves performance compared to a cloud-only architecture.

The core comparison is between:

1. **Cloud-only processing**
2. **Azure IoT Edge pass-through processing**
3. **Hybrid edge-cloud processing**
4. **Edge-heavy processing with local storage and cloud sync**

The study focuses on industrial automation workloads, not generic IoT temperature examples.

The central idea is:

> Critical and data-reducing microservices should run close to industrial devices on Azure IoT Edge, while storage, dashboards, and long-term analytics should remain in the cloud.

---

### 1.2 What makes the study original/publishable

The general idea of edge/cloud placement is not entirely new. The publishable part should be a **practical experimental evaluation** in an industrial automation context.

The proposed contribution is:

> A measurement-driven microservice placement approach for Azure IoT Edge in industrial automation, evaluated against cloud-only, edge-pass-through, hybrid edge-cloud, and edge-heavy deployments under normal, high-load, weak-network, packet-loss, and cloud-outage conditions.

The paper should not claim simply:

> “Azure IoT Edge is better than cloud.”

Instead, it should prove more specific claims:

- Which microservices benefit from edge placement?
- Under what network/load conditions does edge placement help?
- What performance trade-offs appear in latency, bandwidth, CPU/RAM usage, throughput, message loss, and outage recovery?

---

## 2. Research questions and hypotheses

### 2.1 Research questions

**RQ1:** How does microservice placement across Azure IoT Edge and cloud affect latency, throughput, bandwidth usage, resource consumption, and reliability in industrial automation workloads?

**RQ2:** Which placement strategy gives the best trade-off between local responsiveness and cloud scalability?

**RQ3:** Do hybrid edge-cloud and edge-heavy placement maintain critical functionality better than cloud-only placement during weak network conditions and cloud disconnection?

---

### 2.2 Hypotheses

**H1:** Hybrid edge-cloud placement reduces p95/p99 alert latency compared to cloud-only processing.

**H2:** Hybrid placement reduces cloud-bound traffic compared to cloud-only and edge-pass-through configurations.

**H3:** Edge-local anomaly detection and alerting maintain service availability during cloud outages.

**H4:** Edge-heavy processing may reduce latency but increases edge CPU/RAM usage, so hybrid placement is expected to be the best practical trade-off.

**H5:** S3 edge-heavy deployment should provide the strongest cloud-outage autonomy, but it should also create the highest edge CPU/RAM/disk load and synchronization backlog after reconnect.

---

## 3. Key architecture concept

The system has four major layers:

```text
Industrial Data Creation Layer
        ↓
Azure IoT Edge Layer
        ↓
Cloud Layer
        ↓
Metrics and Results Layer
```

Full architecture:

```text
+--------------------------------------------------+
| Industrial Data Creation Layer                    |
| - Simulated industrial machines                   |
| - Virtual PLCs / OPC UA server                    |
| - Motors, pumps, conveyors, tanks, compressors    |
| - Controlled faults/anomalies                     |
| - Ground-truth logger                             |
+-----------------------+--------------------------+
                        |
                        | OPC UA for S1/S2/S3
                        | Direct cloud output for S0
                        v
+--------------------------------------------------+
| Azure IoT Edge Layer                              |
| - OPC UA collector / OPC Publisher or custom      |
| - normalizer-validator                            |
| - filter-aggregator                               |
| - anomaly-detector                                |
| - local-alert-service                             |
| - edge-local-storage for S3                        |
| - cloud-sync-service for S3                        |
| - $edgeHub / $edgeAgent                           |
+-----------------------+--------------------------+
                        |
                        v
+--------------------------------------------------+
| Cloud Layer                                       |
| - Azure IoT Hub                                   |
| - cloud ingestion service                         |
| - cloud anomaly detector for S0/S1                |
| - cloud sync receiver for S3                       |
| - storage                                         |
| - dashboard / results API                         |
+-----------------------+--------------------------+
                        |
                        v
+--------------------------------------------------+
| Metrics and Results                               |
| - latency                                         |
| - throughput                                      |
| - bandwidth / cloud traffic                       |
| - edge CPU/RAM                                    |
| - message loss                                    |
| - outage recovery                                 |
+--------------------------------------------------+
```

---

## 4. Important architectural decision: no Microsoft temperature simulator

The project should **not** use Microsoft’s simple simulated temperature sensor as the main workload.

Reason:

- The paper is about industrial automation.
- A simple temperature sensor is too generic and weak scientifically.
- The data layer should simulate industrial machines, PLC-like behavior, correlated sensor values, faults, and OPC UA exposure.

Microsoft samples may be used only as references for understanding Azure IoT Edge and OPC UA integration, not as the main scientific workload.

---

## 5. OPC UA explanation and role

### 5.1 What is OPC UA?

OPC UA means **Open Platform Communications Unified Architecture**.

In simple terms:

> OPC UA is an industrial communication protocol that allows PLCs, machines, sensors, and industrial software systems to expose and exchange structured data.

In this project:

```text
Virtual industrial machine / PLC simulator = OPC UA Server
Azure IoT Edge collector / OPC Publisher   = OPC UA Client
```

The OPC UA server exposes values such as:

```text
Factory.Line1.Motor001.Temperature
Factory.Line1.Motor001.Vibration
Factory.Line1.Motor001.RPM
Factory.Line1.Pump001.Pressure
Factory.Line1.Conveyor001.Speed
```

Azure IoT Edge reads/subscribes to those values.

---

### 5.2 Why OPC UA is used here

OPC UA makes the simulator look more like an industrial automation environment.

Compared with plain MQTT, OPC UA is more appropriate for a PLC/SCADA-style industrial context.

Recommended decision:

```text
Primary protocol: OPC UA
Optional fallback / secondary mode: MQTT or direct JSON publisher
```

---

## 6. Industrial data creation layer

### 6.1 What this layer must do

The data creation layer is everything before Azure IoT Edge.

It must:

1. Simulate industrial machines.
2. Generate realistic sensor values.
3. Expose the values through OPC UA.
4. Inject controlled anomalies/faults.
5. Log ground-truth data for later evaluation.
6. Support configurable device counts and message rates.
7. Support all experimental scenarios and repetitions.

---

### 6.2 What “simulated machines” means

A simulated machine is a fake industrial asset created in software.

Examples:

- motor
- pump
- conveyor
- tank
- compressor

When the plan says:

```text
10, 50, 100 simulated machines
```

It does **not** mean buying real machines.

It means creating 10, 50, or 100 virtual industrial assets that generate telemetry.

Example:

```text
100 total machines:
40 motors
25 pumps
20 conveyors
10 tanks
5 compressors
```

Each machine produces realistic telemetry.

---

### 6.3 Recommended implementation style

Start with:

```text
1 OPC UA server simulating many devices
```

Do **not** start with 100 separate OPC UA servers.

Recommended initial architecture:

```text
industrial-opcua-simulator
    ├── motor-001 ... motor-040
    ├── pump-001 ... pump-025
    ├── conveyor-001 ... conveyor-020
    ├── tank-001 ... tank-010
    └── compressor-001 ... compressor-005
```

Later, if more realism is needed, split into multiple OPC UA servers:

```text
opcua-line-1: 20 devices
opcua-line-2: 20 devices
opcua-line-3: 20 devices
opcua-line-4: 20 devices
opcua-line-5: 20 devices
```

---

## 7. Device and sensor modeling

### 7.1 Device categories

Use these industrial device types:

| Device type | Sensor variables |
|---|---|
| Motor | temperature, vibration, rpm, current, load, status |
| Pump | pressure, flowRate, temperature, vibration, current, status |
| Conveyor | speed, load, motorCurrent, vibration, status |
| Tank | level, pressure, inletFlow, outletFlow, valveState, status |
| Compressor | pressure, temperature, vibration, current, status |

---

### 7.2 Normal value ranges

These ranges do not need to be perfect real-world engineering values. They need to be plausible and internally consistent.

#### Motor

| Sensor | Normal range |
|---|---:|
| temperature | 55–75 °C |
| vibration | 0.1–0.6 mm/s |
| rpm | 1400–1500 |
| current | 6–10 A |
| load | 40–80% |

#### Pump

| Sensor | Normal range |
|---|---:|
| pressure | 2.5–4.5 bar |
| flowRate | 20–40 L/min |
| temperature | 45–65 °C |
| vibration | 0.1–0.5 mm/s |
| current | 5–9 A |

#### Conveyor

| Sensor | Normal range |
|---|---:|
| speed | 1.0–2.0 m/s |
| load | 30–85% |
| current | 4–11 A |
| vibration | 0.1–0.7 mm/s |

#### Tank

| Sensor | Normal range |
|---|---:|
| level | 20–90% |
| pressure | 1.0–3.0 bar |
| inletFlow | 10–30 L/min |
| outletFlow | 10–30 L/min |

---

### 7.3 Data should be correlated, not random

Bad simulator design:

```python
temperature = random(50, 100)
vibration = random(0, 2)
current = random(0, 20)
```

Better simulator design:

```text
If load increases:
    current increases
    temperature slowly increases

If bearing fault starts:
    vibration increases first
    temperature increases later

If pump blockage happens:
    pressure increases
    flow rate decreases
    current increases
```

Example motor logic:

```python
load = base_load + noise
current = 5.0 + 0.06 * load + noise

temperature = previous_temperature \
              + 0.02 * load \
              + 0.3 * fault_heat \
              - cooling_effect \
              + noise

vibration = base_vibration + bearing_wear_effect + noise
```

---

## 8. Fault/anomaly modeling

### 8.1 Required fault types

| Device | Fault type | Expected signal behavior |
|---|---|---|
| Motor | overheating | temperature slowly rises above threshold |
| Motor | bearing_fault | vibration rises first, then temperature rises |
| Motor | overload | load/current rise, temperature rises |
| Pump | pressure_drop / leak | pressure decreases, flow decreases |
| Pump | blockage | pressure increases, flow decreases, current increases |
| Conveyor | jam | speed decreases, current and load increase |
| Tank | overflow_risk | level keeps increasing, outlet flow low |
| Compressor | pressure_instability | pressure oscillates abnormally |

---

### 8.2 Fault injection modes

Each device should support states:

```text
NORMAL
WARNING
FAULT
RECOVERY
```

Each generated record should include the ground truth:

```json
{
  "isAnomaly": true,
  "anomalyType": "bearing_fault"
}
```

The anomaly detector should normally not rely on the `groundTruth` field during detection. Ground truth is for evaluation and logging.

---

### 8.3 Example anomaly message

```json
{
  "experimentId": "exp001",
  "scenario": "S2_HYBRID",
  "deviceId": "motor-014",
  "deviceType": "motor",
  "sequence": 3910,
  "sensorTimestamp": "2026-04-28T20:05:00.000Z",
  "values": {
    "temperature": 91.2,
    "vibration": 1.34,
    "rpm": 1420,
    "current": 12.8,
    "load": 88.4
  },
  "groundTruth": {
    "isAnomaly": true,
    "anomalyType": "bearing_fault"
  }
}
```

---

## 9. Message rate and load design

### 9.1 Main message-rate rule

The simulator must support target total message rates:

```text
10 msg/s
100 msg/s
500 msg/s
```

Message rate should be computed as:

```text
messages per device per second = targetMessagesPerSecond / deviceCount
```

Examples:

| Devices | Target msg/s | Messages/device/second |
|---:|---:|---:|
| 10 | 10 | 1 |
| 10 | 100 | 10 |
| 50 | 100 | 2 |
| 100 | 100 | 1 |
| 100 | 500 | 5 |

Best stress-test configuration:

```text
100 devices × 5 messages/second/device = 500 messages/second
```

---

### 9.2 Preferred message definition

Use one telemetry message per device update, containing all sensor values for that device.

Preferred:

```text
100 devices × 5 full telemetry messages/second = 500 messages/second
```

Avoid defining each individual sensor value as a separate message unless needed later.

---

## 10. OPC UA address-space design

Use a structured OPC UA address space:

```text
Objects
└── Factory
    └── Line1
        ├── Motor001
        │   ├── Temperature
        │   ├── Vibration
        │   ├── RPM
        │   ├── Current
        │   ├── Load
        │   ├── Status
        │   └── IsAnomaly
        ├── Pump001
        │   ├── Pressure
        │   ├── FlowRate
        │   ├── Temperature
        │   ├── Current
        │   └── IsAnomaly
        └── Conveyor001
            ├── Speed
            ├── Load
            ├── Current
            ├── Vibration
            └── IsAnomaly
```

Example node IDs:

```text
ns=2;s=Factory.Line1.Motor001.Temperature
ns=2;s=Factory.Line1.Motor001.Vibration
ns=2;s=Factory.Line1.Motor001.RPM
ns=2;s=Factory.Line1.Motor001.Current
ns=2;s=Factory.Line1.Motor001.IsAnomaly
```

---

## 11. Deployment scenarios

### 11.1 Scenario S0: cloud-only baseline

```text
Industrial simulator
        ↓
Direct cloud publisher
        ↓
IoT Hub / cloud ingestion
        ↓
Cloud normalizer
        ↓
Cloud filter
        ↓
Cloud anomaly detector
        ↓
Cloud alert/storage
```

Important design point:

S0 should bypass Azure IoT Edge completely.

Because OPC UA is normally local/industrial, the simulator should support two output modes:

```text
OPC UA output mode       -> used by S1, S2, and S3
Direct cloud output mode -> used by S0
```

The same data generation engine should be used in every scenario. Only the output path changes.

---

### 11.2 Scenario S1: edge pass-through

```text
Industrial OPC UA simulator
        ↓
Azure IoT Edge OPC UA collector
        ↓
$edgeHub
        ↓
IoT Hub
        ↓
Cloud processing
```

Purpose:

> Measure overhead of adding Azure IoT Edge as a gateway when it does little or no processing.

---

### 11.3 Scenario S2: hybrid proposed architecture

```text
Industrial OPC UA simulator
        ↓
Azure IoT Edge OPC UA collector
        ↓
Edge normalizer-validator
        ↓
Edge filter-aggregator
        ↓
Edge anomaly-detector
        ↓
Edge local-alert-service
        ↓
IoT Hub receives filtered data / summaries / alerts
        ↓
Cloud storage / dashboard / long-term analytics
```

Purpose:

> Test the proposed improved microservice placement.

---

### 11.4 Scenario S3: edge-heavy with local storage and cloud sync

```text
Industrial OPC UA simulator
        ↓
Azure IoT Edge OPC UA collector
        ↓
Edge normalizer-validator
        ↓
Edge filter-aggregator
        ↓
Edge anomaly-detector
        ↓
Edge local-alert-service
        ↓
Edge local-storage / buffer
        ↓
Cloud sync only: summaries, alerts, and periodic batches
```

Purpose:

> Test maximum local autonomy and determine whether moving almost all runtime processing to Azure IoT Edge gives better local latency and outage behavior, and what CPU/RAM/disk cost this creates on the edge device.

S3 is now part of the full study plan. If the implementation timeline becomes tight, S0/S1/S2 can be implemented first, but the codebase and experiment controller should be designed so S3 is supported without redesigning the system.

---

## 12. Proposed microservice placement

| Microservice | Proposed location | Reason |
|---|---|---|
| data collector | Edge | closest to industrial machines |
| OPC UA/protocol adapter | Edge | local industrial protocol handling |
| normalizer-validator | Edge | clean data early |
| filter-aggregator | Edge | reduce cloud traffic |
| anomaly-detector | Edge in S2/S3; Cloud in S0/S1 | low-latency detection |
| local-alert-service | Edge | should work during cloud outage |
| historical storage | Cloud in S0/S1/S2; Edge local storage + cloud sync in S3 | scalable cloud storage, but S3 tests local autonomy |
| dashboard/API | Cloud | remote user access |
| long-term analytics/model training | Cloud | requires history and compute |
| local-storage/buffer | Edge in S3; optional buffer in S2 | required for edge-heavy operation and outage experiments |
| cloud-sync-service | Edge in S3 | periodically sends summaries, alerts, and batches upstream |

---

## 13. Experimental matrix

### 13.1 Core scenario matrix

| Scenario | Load | Network | Goal |
|---|---:|---|---|
| S0 cloud-only | 100 msg/s | normal | baseline |
| S1 edge pass-through | 100 msg/s | normal | edge overhead |
| S2 hybrid | 100 msg/s | normal | proposed architecture |
| S3 edge-heavy | 100 msg/s | normal | maximum edge autonomy baseline |
| S0 cloud-only | 500 msg/s | normal | stress baseline |
| S2 hybrid | 500 msg/s | normal | stress proposed |
| S3 edge-heavy | 500 msg/s | normal | stress edge autonomy / edge resource cost |
| S0 cloud-only | 100 msg/s | 200 ms delay | weak network baseline |
| S2 hybrid | 100 msg/s | 200 ms delay | weak network proposed |
| S3 edge-heavy | 100 msg/s | 200 ms delay | weak network with mostly local processing |
| S0 cloud-only | 100 msg/s | cloud outage | failure behavior |
| S2 hybrid | 100 msg/s | cloud outage | local autonomy |
| S3 edge-heavy | 100 msg/s | cloud outage | maximum local autonomy and later sync |

---

### 13.2 Experiment factors

| Experiment factor | Values |
|---|---|
| Number of simulated machines | 10, 50, 100 |
| Message rate | 10 msg/s, 100 msg/s, 500 msg/s |
| Network condition | normal, 100 ms delay, 200 ms delay |
| Packet loss | 0%, 2%, 5% |
| Cloud outage | 2 minutes, 5 minutes |
| Run duration | 10 minutes/test |
| Repetitions | 3 runs/scenario |

The full factorial combination may become large. Start with the core matrix above, then expand selectively.

---

## 14. Metrics to collect

### 14.1 Latency metrics

Collect:

- sensor-to-cloud latency
- sensor-to-alert latency
- edge processing latency
- p50 latency
- p95 latency
- p99 latency
- jitter

Important: Do not report only averages. p95 and p99 are important for industrial workloads.

---

### 14.2 Throughput metrics

Collect:

- generated messages/second
- received messages/second at edge
- received messages/second at cloud
- processed messages/second per module

---

### 14.3 Bandwidth/cloud traffic metrics

Collect:

- cloud messages/minute
- cloud bytes/minute
- reduction ratio from filtering/aggregation

Example formula:

```text
bandwidthReduction = 1 - (hybridCloudBytes / cloudOnlyCloudBytes)
```

---

### 14.4 Edge resource metrics

Collect per module:

- CPU %
- memory MB
- container restarts
- queue length if available
- disk/buffer usage during outage

Can use:

```bash
docker stats
```

or Prometheus/cAdvisor if implemented.

---

### 14.5 Reliability metrics

Collect:

- message loss rate
- duplicate message rate
- local alert success during cloud outage
- outage recovery time
- backlog drain time after reconnect

Example:

```text
messageLossRate = (generatedMessages - receivedMessages) / generatedMessages
```

---

## 15. Timestamp and message schema

Each message should carry timestamps for latency calculations.

Recommended telemetry schema:

```json
{
  "experimentId": "exp001",
  "scenario": "S2_HYBRID",
  "runId": "s2_100_normal_rep1",
  "deviceId": "motor-001",
  "deviceType": "motor",
  "sequence": 5819,
  "sensorTimestamp": "2026-04-28T20:10:15.200Z",
  "edgeReceivedTimestamp": null,
  "normalizedTimestamp": null,
  "filteredTimestamp": null,
  "anomalyTimestamp": null,
  "cloudReceivedTimestamp": null,
  "values": {
    "temperature": 73.4,
    "vibration": 0.44,
    "rpm": 1450,
    "current": 8.8,
    "load": 68.0
  },
  "groundTruth": {
    "isAnomaly": false,
    "anomalyType": null
  }
}
```

Each microservice should append its timestamp before forwarding.

---

## 16. Ground-truth logging

The simulator must save ground-truth CSV or JSONL before any edge/cloud processing happens.

Example CSV columns:

```csv
experimentId,scenario,runId,deviceId,deviceType,sequence,sensorTimestamp,temperature,vibration,rpm,current,load,isAnomaly,anomalyType
```

Why this matters:

- Enables anomaly detection evaluation.
- Enables message loss measurement.
- Enables latency calculation.
- Gives the paper trustworthy experimental data.

Example claim enabled by this:

```text
The simulator injected 120 anomaly events.
The edge detector detected 114.
The cloud detector detected 116.
Average edge alert latency was lower under weak network conditions.
```

---

## 17. Experiment controller/orchestrator

The previous architecture supports all experimental configurations only if there is an **experiment controller**.

The experiment controller should:

1. Load an experiment matrix YAML file.
2. Start the simulator with the correct device count and message rate.
3. Select scenario S0/S1/S2/S3.
4. Deploy correct Azure IoT Edge deployment manifest for S1/S2/S3.
5. Start cloud services for S0/S1/S2/S3.
6. Apply network delay and packet loss.
7. Trigger cloud outage if configured.
8. Run for 10 minutes.
9. Collect metrics.
10. Stop services and clear network rules.
11. Repeat 3 times.
12. Save all results with run IDs.

---

## 18. Network emulation

### 18.1 Delay and packet loss

Use Linux `tc netem`.

Normal network:

```bash
sudo tc qdisc del dev eth0 root || true
```

Add 100 ms latency:

```bash
sudo tc qdisc add dev eth0 root netem delay 100ms
```

Add 200 ms latency:

```bash
sudo tc qdisc add dev eth0 root netem delay 200ms
```

Add 100 ms latency and 2% packet loss:

```bash
sudo tc qdisc add dev eth0 root netem delay 100ms loss 2%
```

Add 200 ms latency and 5% packet loss:

```bash
sudo tc qdisc add dev eth0 root netem delay 200ms loss 5%
```

Clear:

```bash
sudo tc qdisc del dev eth0 root || true
```

---

### 18.2 Cloud outage simulation

Simulate cloud outage by blocking outgoing traffic to the cloud.

Simple method:

```bash
sudo iptables -A OUTPUT -p tcp --dport 443 -j DROP
```

Restore:

```bash
sudo iptables -D OUTPUT -p tcp --dport 443 -j DROP
```

Expected behavior:

- S0 cloud-only: processing fails or stops during cloud outage.
- S2 hybrid: edge still receives OPC UA data, processes locally, detects anomalies, and queues/syncs cloud-bound messages later.
- S3 edge-heavy: edge continues full local processing, stores records locally, generates local alerts, and syncs batches/summaries after cloud connectivity returns.

---

## 19. Example experiment matrix YAML

```yaml
experiments:
  - id: s0_100_normal
    scenario: S0_CLOUD_ONLY
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s1_100_normal
    scenario: S1_EDGE_PASS_THROUGH
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s2_100_normal
    scenario: S2_HYBRID
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s3_100_normal
    scenario: S3_EDGE_HEAVY
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s0_500_normal
    scenario: S0_CLOUD_ONLY
    deviceCount: 100
    targetMessagesPerSecond: 500
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s2_500_normal
    scenario: S2_HYBRID
    deviceCount: 100
    targetMessagesPerSecond: 500
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s3_500_normal
    scenario: S3_EDGE_HEAVY
    deviceCount: 100
    targetMessagesPerSecond: 500
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s0_100_delay_200
    scenario: S0_CLOUD_ONLY
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 200
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s2_100_delay_200
    scenario: S2_HYBRID
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 200
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s3_100_delay_200
    scenario: S3_EDGE_HEAVY
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 200
    packetLossPercent: 0
    cloudOutageSeconds: 0
    durationSeconds: 600
    repetitions: 3

  - id: s0_100_outage_300
    scenario: S0_CLOUD_ONLY
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 300
    durationSeconds: 600
    repetitions: 3

  - id: s2_100_outage_300
    scenario: S2_HYBRID
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 300
    durationSeconds: 600
    repetitions: 3

  - id: s3_100_outage_300
    scenario: S3_EDGE_HEAVY
    deviceCount: 100
    targetMessagesPerSecond: 100
    delayMs: 0
    packetLossPercent: 0
    cloudOutageSeconds: 300
    durationSeconds: 600
    repetitions: 3
```

---

## 20. Recommended repository structure

```text
azure-iot-edge-placement-study/
├── README.md
├── docker-compose.local.yml
├── .env.example
│
├── infrastructure/
│   └── host-vm-setup/
│       ├── windows-host-notes.md
│       ├── ubuntu-vm-notes.md
│       ├── network-topology.md
│       └── vm-resource-profile.md
│
├── simulator/
│   └── industrial-opcua-simulator/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── src/
│       │   ├── main.py
│       │   ├── config_loader.py
│       │   ├── opcua_server.py
│       │   ├── direct_cloud_publisher.py
│       │   ├── scenario_controller.py
│       │   ├── ground_truth_logger.py
│       │   └── devices/
│       │       ├── __init__.py
│       │       ├── base_device.py
│       │       ├── motor.py
│       │       ├── pump.py
│       │       ├── conveyor.py
│       │       ├── tank.py
│       │       └── compressor.py
│       ├── configs/
│       │   ├── exp_10_devices_10mps.yaml
│       │   ├── exp_50_devices_100mps.yaml
│       │   └── exp_100_devices_500mps.yaml
│       └── results/
│
├── edge/
│   ├── modules/
│   │   ├── opcua-collector/
│   │   │   ├── Dockerfile
│   │   │   └── src/
│   │   ├── normalizer-validator/
│   │   │   ├── Dockerfile
│   │   │   └── src/
│   │   ├── filter-aggregator/
│   │   │   ├── Dockerfile
│   │   │   └── src/
│   │   ├── anomaly-detector/
│   │   │   ├── Dockerfile
│   │   │   └── src/
│   │   ├── local-alert-service/
│   │   │   ├── Dockerfile
│   │   │   └── src/
│   │   ├── edge-local-storage/
│   │   │   ├── Dockerfile
│   │   │   └── src/
│   │   └── cloud-sync-service/
│   │       ├── Dockerfile
│   │       └── src/
│   └── deployments/
│       ├── s1-edge-pass-through.json
│       ├── s2-hybrid.json
│       └── s3-edge-heavy.json
│
├── cloud/
│   ├── cloud-ingestion-service/
│   │   ├── Dockerfile
│   │   └── src/
│   ├── cloud-anomaly-detector/
│   │   ├── Dockerfile
│   │   └── src/
│   └── storage/
│
├── experiments/
│   ├── experiment_matrix.yaml
│   ├── run_experiment.py
│   ├── apply_network.sh
│   ├── clear_network.sh
│   ├── trigger_outage.sh
│   ├── restore_cloud.sh
│   └── analyze_results.py
│
└── results/
    ├── raw/
    ├── processed/
    └── graphs/
```

---

## 21. Suggested implementation phases

### Phase 1: Local-only simulator

Implement:

- industrial device classes
- realistic telemetry generation
- fault injection
- ground-truth logging
- configurable device count and message rate

Output can be JSONL/CSV first.

Goal:

```text
Generate repeatable industrial telemetry at 10, 100, and 500 msg/s.
```

---

### Phase 2: OPC UA simulator

Implement:

- OPC UA server
- OPC UA address space
- node updates for all simulated devices

Goal:

```text
Expose simulated industrial machines through OPC UA.
```

---

### Phase 3: Azure IoT Edge ingestion

Implement one of these:

1. Custom OPC UA collector module, or
2. OPC Publisher integration.

Recommended for more control:

```text
Custom OPC UA collector module
```

Goal:

```text
Azure IoT Edge receives telemetry from OPC UA simulator.
```

---

### Phase 4: Edge microservices

Implement:

- normalizer-validator
- filter-aggregator
- anomaly-detector
- local-alert-service
- edge-local-storage
- cloud-sync-service

Goal:

```text
Hybrid edge pipeline works locally before sending selected data to cloud, and S3 edge-heavy mode can store/process locally before syncing summaries or batches.
```

---

### Phase 5: Cloud path

Implement:

- direct cloud publisher for S0
- cloud ingestion
- cloud normalizer/filter/anomaly detector for S0/S1
- cloud sync receiver for S3
- storage of received telemetry and metrics

Goal:

```text
S0 cloud-only and S1 pass-through are runnable baselines, and S3 has a cloud endpoint for synchronized batches/summaries.
```

---

### Phase 6: Experiment controller

Implement:

- scenario selection
- experiment matrix loading
- run duration control
- repetitions
- network delay/loss application
- cloud outage simulation
- results folder creation

Goal:

```text
All experiment matrix rows can run repeatably.
```

---

### Phase 7: Analysis

Implement:

- latency calculation
- throughput calculation
- bandwidth calculation
- message loss calculation
- CPU/RAM summary
- anomaly detection evaluation
- graphs

Goal:

```text
Generate paper-ready result tables and charts.
```

---

## 22. Local development recommendation

Before using real Azure resources, implement a local mode.

Local test pipeline:

```text
Simulator -> local OPC UA collector -> local microservices -> local results files
```

Then add Azure IoT Hub integration.

This reduces cost and debugging difficulty.

---

### 22.1 Planned physical deployment: two-laptop Windows/Ubuntu architecture

The current intended implementation is **not a single-laptop host + VM setup**. It should be treated as a **two-physical-machine local lab**:

```text
Machine A: Windows 11 simulator laptop
- Windows 11
- AMD Ryzen 7 4800H processor
- 8 CPU cores / 16 logical threads
- DDR5 RAM, currently expected around 8 GB
- Runs the industrial data creation layer
- Runs the virtual factory / OPC UA simulator
- Represents the external industrial machines, sensors, and PLC layer
```

```text
Machine B: Edge gateway laptop
- Physical laptop with Intel Core i7-4900MQ processor
- Runs an Ubuntu Server virtual machine
- The Ubuntu Server VM runs Azure IoT Edge
- Runs the edge microservices and edge-local storage/sync logic
- Connects to Azure cloud over the internet
```

Codex should therefore assume that the simulator/device layer and Azure IoT Edge layer are separated across **two different physical laptops** on the same local network.

This is closer to a real industrial architecture than the previous single-laptop VM setup:

```text
+------------------------------------------------------------+
| Machine A: Windows 11 simulator laptop                      |
| AMD Ryzen 7 4800H                                           |
|                                                            |
| Industrial data creation layer                              |
| - industrial OPC UA simulator                               |
| - virtual machines/devices: motors, pumps, conveyors, etc.  |
| - ground-truth logger                                       |
| - experiment configuration files                            |
| - optional direct-cloud publisher for S0                    |
|                                                            |
| OPC UA endpoint example:                                    |
| opc.tcp://<windows-simulator-ip>:4840/factory/server        |
+----------------------------+-------------------------------+
                             |
                             | local LAN / Wi-Fi / Ethernet
                             | OPC UA traffic
                             v
+------------------------------------------------------------+
| Machine B: edge gateway laptop                              |
| Intel Core i7-4900MQ                                        |
|                                                            |
| Ubuntu Server VM                                            |
| - Azure IoT Edge runtime                                    |
| - Docker / container runtime                                |
| - OPC UA collector / OPC Publisher or custom collector       |
| - normalizer-validator                                      |
| - filter-aggregator                                         |
| - anomaly-detector                                          |
| - local-alert-service                                       |
| - edge-local-storage for S3                                  |
| - cloud-sync-service for S3                                  |
| - network-delay / packet-loss / cloud-outage scripts         |
+----------------------------+-------------------------------+
                             |
                             | internet / cloud-bound link
                             v
+------------------------------------------------------------+
| Azure cloud                                                  |
| - Azure IoT Hub                                              |
| - cloud ingestion                                            |
| - cloud processing/storage/dashboard                         |
+------------------------------------------------------------+
```

This means the **industrial simulator and the edge node are both conceptually and physically separate**. Codex should not treat the simulator as an IoT Edge module by default. The simulator represents the factory/device/PLC layer that exists before the edge gateway.

---

### 22.2 What runs where

| Component | Preferred location | Reason |
|---|---|---|
| Industrial OPC UA simulator | Machine A, Windows 11 Ryzen 7 laptop | Represents the external factory/PLC/sensor layer |
| Virtual industrial devices | Machine A, Windows 11 Ryzen 7 laptop | Generates motors, pumps, conveyors, tanks, compressors |
| Ground-truth logger | Machine A, Windows 11 Ryzen 7 laptop | Captures generated data before edge/cloud processing |
| Optional S0 direct-cloud publisher | Machine A, or a non-edge publisher on Machine B VM | Used to bypass Azure IoT Edge for the cloud-only baseline |
| Experiment matrix/config files | Repo, shared/copied to both machines as needed | Central control of experiments |
| Azure IoT Edge runtime | Machine B, Ubuntu Server VM | Azure IoT Edge is Linux/container-oriented and easier to manage on Ubuntu |
| Edge microservices | Machine B, Ubuntu Server VM | These are the services being tested for edge placement |
| S3 edge-local storage | Machine B, Ubuntu Server VM | Stores local data during edge-heavy/autonomy experiments |
| Network emulation scripts | Primarily Machine B, Ubuntu Server VM | Linux `tc netem` and `iptables` are easiest here |
| Cloud services / IoT Hub | Azure cloud | Remote cloud baseline and storage |
| Analysis scripts | Either machine | Run wherever result files are collected |

---

### 22.3 Local networking assumptions

Machine A and Machine B must be on the same local network.

Recommended physical/local networking:

```text
Best option:
- Put both laptops on the same router/network.
- Prefer Ethernet if available, because it is more stable than Wi-Fi.
- If using Wi-Fi, keep both machines close to the router and avoid unstable networks.
```

Recommended VM network mode on Machine B:

```text
Option 1: Bridged network, recommended
- Ubuntu VM gets its own LAN IP address.
- Windows simulator exposes OPC UA on the Windows laptop LAN IP.
- Ubuntu IoT Edge collector connects to the Windows laptop IP.
- This most closely matches a real gateway connected to a factory network.
```

```text
Option 2: NAT + port forwarding, fallback
- Works, but is more annoying.
- Ubuntu VM must still be able to reach the Windows simulator IP and OPC UA port.
- Avoid this for first implementation if possible.
```

Important endpoint rule:

```text
The OPC UA simulator should bind to an address reachable from the Ubuntu VM, not only to localhost.
```

Recommended simulator bind address:

```text
0.0.0.0:4840
```

Example endpoint configured in the edge collector:

```text
opc.tcp://<windows-simulator-laptop-ip>:4840/factory/server
```

Important note for Codex:

```text
Do not hardcode localhost for OPC UA endpoints.
localhost inside the Ubuntu VM means the Ubuntu VM itself, not the Windows simulator laptop.
OPC UA endpoint URLs must be configurable through YAML/environment variables.
```

Also account for Windows firewall:

```text
The Windows simulator laptop must allow inbound traffic to the OPC UA port, usually 4840.
If the edge collector cannot connect, check Windows Defender Firewall and VM network mode first.
```

---

### 22.4 How scenarios map onto the two-laptop layout

#### S0 cloud-only

S0 should bypass Azure IoT Edge processing.

There are two acceptable implementations:

```text
Option A, simplest conceptual baseline:
Machine A Windows simulator -> direct cloud publisher -> Azure IoT Hub/cloud services
```

```text
Option B, better for controlled network experiments:
Machine A Windows simulator -> lightweight non-edge cloud publisher on Machine B Ubuntu VM -> Azure IoT Hub/cloud services
```

Option B is often cleaner for experiments because the same Ubuntu VM can apply `tc netem` delay/loss/outage rules to the cloud-bound link. It is still considered cloud-only as long as this publisher does **not** use Azure IoT Edge modules and does **not** do edge processing.

Recommended practical decision:

```text
Implement S0 Option A first for simplicity.
For strict fair comparison under delay/loss/outage, add S0 Option B later so all cloud-bound traffic can be shaped from the Ubuntu VM.
```

#### S1 edge pass-through

```text
Machine A Windows OPC UA simulator
        ↓ OPC UA over LAN
Machine B Ubuntu VM running Azure IoT Edge
        ↓
opcua-collector -> $upstream
        ↓
Azure IoT Hub/cloud processing
```

S1 measures the overhead of placing Azure IoT Edge between the industrial simulator and the cloud while doing little or no local processing.

#### S2 hybrid proposed architecture

```text
Machine A Windows OPC UA simulator
        ↓ OPC UA over LAN
Machine B Ubuntu VM / Azure IoT Edge
        ↓
opcua-collector -> normalizer -> filter -> anomaly-detector -> local-alert-service
        ↓
Azure IoT Hub receives filtered telemetry, summaries, and alerts
```

S2 is the main proposed architecture.

#### S3 edge-heavy architecture

```text
Machine A Windows OPC UA simulator
        ↓ OPC UA over LAN
Machine B Ubuntu VM / Azure IoT Edge
        ↓
opcua-collector -> normalizer -> filter -> anomaly-detector -> local-alert-service -> edge-local-storage
        ↓
cloud-sync-service sends data to cloud when available
```

S3 is the strongest local-autonomy scenario but should be expected to consume the most CPU/RAM/disk on the Ubuntu VM laptop.

---

### 22.5 Resource constraints for the two laptops

Machine A, the Windows Ryzen 7 laptop, is strong enough to run the industrial simulator and ground-truth logger. It should not also run Azure IoT Edge in the current plan.

Machine B, the i7-4900MQ laptop, runs the Ubuntu Server VM and therefore carries the edge workload. Because this is an older CPU, Codex should keep the edge-side implementation modular and scalable through configuration.

Recommended starting allocation for the Ubuntu Server VM on Machine B:

```text
Ubuntu Server VM on i7-4900MQ laptop:
- 2 to 4 virtual CPU cores
- 4 GB RAM minimum if available
- 40+ GB disk if possible
```

Windows simulator laptop:

```text
Windows 11 Ryzen 7 laptop:
- run industrial OPC UA simulator
- run ground-truth logger
- run optional S0 direct-cloud publisher
- run config/orchestration scripts if convenient
```

Debugging profile:

```text
10 devices
10-100 msg/s
S0/S1/S2 only
shorter runs during debugging
```

Scale-up profile:

```text
100 devices
500 msg/s
10-minute runs
S2 hybrid and S3 edge-heavy
cloud outage experiments
```

Codex should make container memory/CPU limits configurable, especially for S3.

Example principle:

```text
Do not hardcode resource-heavy defaults. Start small, then scale through YAML configs.
```

---

### 22.6 Consequence for network-delay and cloud-outage experiments

Network delay, packet loss, and cloud outage should primarily apply to the **cloud-bound link** between the edge gateway and Azure cloud, not to the local OPC UA link between the simulator laptop and edge laptop.

Recommended approach for S1/S2/S3:

```text
- Apply `tc netem` and outage rules inside the Ubuntu VM on Machine B.
- Shape the interface/path used by the Ubuntu VM to reach Azure/cloud.
- Do not break the Machine A -> Machine B OPC UA connection unless a separate local-network experiment is intentionally being run.
```

For S0:

```text
If S0 uses direct cloud publishing from Machine A:
- Windows needs its own delay/outage mechanism, or
- S0 cloud traffic should be routed through a controlled proxy/gateway, or
- use the S0 Option B non-edge publisher on the Ubuntu VM.
```

For scientific fairness, Codex should prefer a design where all cloud-bound traffic can be affected by the same delay/loss/outage mechanism.

Most practical fair setup:

```text
S0 controlled baseline:
Machine A simulator -> non-edge cloud publisher on Machine B Ubuntu VM -> Azure cloud

S1/S2/S3 edge scenarios:
Machine A simulator -> Azure IoT Edge on Machine B Ubuntu VM -> Azure cloud
```

This keeps the same physical cloud-bound laptop/VM/network path for all scenarios. The difference is whether the Machine B Ubuntu VM uses plain non-edge cloud publishing, edge pass-through, hybrid edge processing, or edge-heavy processing.



## 23. S0/S1/S2/S3 routing details

### S0 cloud-only

Same simulator engine, direct cloud output:

```text
simulator --output direct-cloud
```

No IoT Edge modules used.

---

### S1 edge pass-through

OPC UA simulator exposes data.

Edge deployment contains:

```text
opcua-collector -> $upstream
```

No normalizer/filter/anomaly processing on edge.

---

### S2 hybrid

OPC UA simulator exposes data.

Edge deployment contains:

```text
opcua-collector
    -> normalizer-validator
    -> filter-aggregator
    -> anomaly-detector
    -> local-alert-service
    -> $upstream
```

Cloud receives filtered data, summaries, and alerts, not necessarily every raw message.

---

### S3 edge-heavy

OPC UA simulator exposes data.

Edge deployment contains:

```text
opcua-collector
    -> normalizer-validator
    -> filter-aggregator
    -> anomaly-detector
    -> local-alert-service
    -> edge-local-storage
    -> cloud-sync-service
    -> $upstream only for summaries, alerts, or periodic batches
```

S3 should minimize dependence on cloud during runtime. Cloud is used mainly for synchronization, long-term storage, and remote visibility after local processing has already completed.

---

## 24. Example Azure IoT Edge route patterns

### S1 pass-through route

```json
{
  "routes": {
    "collectorToCloud": "FROM /messages/modules/opcua-collector/outputs/telemetry INTO $upstream"
  }
}
```

### S2 hybrid routes

```json
{
  "routes": {
    "collectorToNormalizer": "FROM /messages/modules/opcua-collector/outputs/telemetry INTO BrokeredEndpoint(\"/modules/normalizer-validator/inputs/input1\")",
    "normalizerToFilter": "FROM /messages/modules/normalizer-validator/outputs/output1 INTO BrokeredEndpoint(\"/modules/filter-aggregator/inputs/input1\")",
    "filterToAnomaly": "FROM /messages/modules/filter-aggregator/outputs/output1 INTO BrokeredEndpoint(\"/modules/anomaly-detector/inputs/input1\")",
    "anomalyToAlert": "FROM /messages/modules/anomaly-detector/outputs/alerts INTO BrokeredEndpoint(\"/modules/local-alert-service/inputs/input1\")",
    "anomalyToCloud": "FROM /messages/modules/anomaly-detector/outputs/telemetry INTO $upstream"
  }
}
```

### S3 edge-heavy routes

```json
{
  "routes": {
    "collectorToNormalizer": "FROM /messages/modules/opcua-collector/outputs/telemetry INTO BrokeredEndpoint(\"/modules/normalizer-validator/inputs/input1\")",
    "normalizerToFilter": "FROM /messages/modules/normalizer-validator/outputs/output1 INTO BrokeredEndpoint(\"/modules/filter-aggregator/inputs/input1\")",
    "filterToAnomaly": "FROM /messages/modules/filter-aggregator/outputs/output1 INTO BrokeredEndpoint(\"/modules/anomaly-detector/inputs/input1\")",
    "anomalyToAlert": "FROM /messages/modules/anomaly-detector/outputs/alerts INTO BrokeredEndpoint(\"/modules/local-alert-service/inputs/input1\")",
    "anomalyToLocalStorage": "FROM /messages/modules/anomaly-detector/outputs/telemetry INTO BrokeredEndpoint(\"/modules/edge-local-storage/inputs/input1\")",
    "localStorageToCloudSync": "FROM /messages/modules/edge-local-storage/outputs/batches INTO BrokeredEndpoint(\"/modules/cloud-sync-service/inputs/input1\")",
    "cloudSyncToCloud": "FROM /messages/modules/cloud-sync-service/outputs/sync INTO $upstream"
  }
}
```

---

## 25. What Codex should implement first

Implement in this order:

1. `simulator/industrial-opcua-simulator/src/devices/base_device.py`
2. `motor.py`, `pump.py`, `conveyor.py`, `tank.py`, `compressor.py`
3. `ground_truth_logger.py`
4. config loader and YAML configs
5. JSONL/CSV-only simulation mode
6. OPC UA server mode
7. direct cloud publisher stub/local mock mode
8. edge collector/local mock consumer
9. edge microservices as local Python services
10. Dockerfiles and Docker Compose
11. two-laptop setup documentation for Windows simulator laptop + Ubuntu Server VM edge laptop
12. configurable OPC UA endpoint handling between the Windows simulator laptop and Ubuntu VM on the edge laptop
13. S0 direct-cloud mode that can run either from the Windows simulator laptop or through a non-edge publisher in the Ubuntu VM for fair network shaping
14. S3 edge-local-storage and cloud-sync-service modules
15. experiment controller
16. results analyzer

Codex should not begin with Azure-specific deployment manifests before the simulator works locally.

---

## 26. Minimal viable implementation target

A first working milestone should demonstrate:

```text
10 simulated devices
100 msg/s total
normal network
local output to CSV/JSONL
fault injection enabled
p50/p95 latency calculable locally
```

Then expand to:

```text
100 simulated devices
500 msg/s total
OPC UA endpoint
Azure IoT Edge collector
S1, S2, and S3 scenarios
```

---

## 27. Expected results and interpretation

Expected trends:

| Scenario | Expected behavior |
|---|---|
| S0 cloud-only | simplest baseline, higher latency under delay/outage, no local autonomy |
| S1 edge pass-through | measures gateway overhead, little performance improvement |
| S2 hybrid | best trade-off, lower alert latency, lower cloud traffic, works during outage |
| S3 edge-heavy | lowest local dependency on cloud, strong outage behavior, but highest edge CPU/RAM/disk usage |

The paper should be careful not to claim hard real-time control.

Correct phrasing:

> This study targets near-real-time monitoring, anomaly detection, alerting, and supervisory control in industrial automation, not deterministic millisecond-level PLC control loops.

---

## 28. Paper-oriented contribution statement

Use a statement like:

> This study implements and evaluates Azure IoT Edge microservice placement strategies for industrial automation. The architecture decomposes the industrial telemetry pipeline into containerized microservices and experimentally compares cloud-only, edge-pass-through, hybrid edge-cloud, and edge-heavy deployment placements. The evaluation measures latency, throughput, bandwidth usage, edge CPU/RAM/disk consumption, message loss, anomaly detection behavior, local autonomy, and recovery behavior during network degradation and cloud disconnection.

---

## 29. Important constraints and notes

1. Do not use the Microsoft temperature simulator as the main workload.
2. Use industrial device types and OPC UA.
3. Keep simulator configurable through YAML.
4. Keep S0, S1, S2, and S3 using the same generated data model for fairness.
5. Log ground truth before any edge/cloud processing.
6. Include sequence numbers in every message.
7. Include timestamps at every processing stage.
8. Use p95/p99 latency, not only average latency.
9. Use 3 repetitions per scenario.
10. Build local mode first before requiring Azure resources.
11. Make experiment runs reproducible with fixed random seeds where possible.
12. Separate generated raw data, processed metrics, and graphs.
13. Assume the practical development setup is two physical laptops: a Windows 11 Ryzen 7 laptop for the industrial simulator/data layer, and a separate i7-4900MQ laptop hosting an Ubuntu Server VM for Azure IoT Edge.
14. Keep simulator/device-layer code separate from IoT Edge modules; they run on different physical laptops in the intended lab setup.
15. Make OPC UA endpoints configurable because the Windows simulator laptop and Ubuntu VM edge gateway do not share the same `localhost`; use LAN IP addresses.
16. Design for limited RAM: start with small runs, then scale to 100 devices and 500 msg/s.

---

## 30. Uploaded/source files mentioned in the conversation

The conversation included these uploaded sources/files:

- `Përmirësimi i vendosjes së mikroshërbimeve në Azure IoT Edge për Automatizim Industrial (1).docx`
- `sensors-24-05320.pdf`
- `sensors-24-06771-v2.pdf`
- `Enabling_Industrial_Internet_of_Things_by_Leveragi.pdf`
- `s10270-022-01006-z.pdf`

Some older duplicate uploads may have expired in the chat environment. This Markdown file is designed to preserve the useful project context so Codex can continue implementation even if the uploaded files are unavailable.

---

## 31. Final one-sentence project summary for Codex

Build a configurable industrial OPC UA simulator and Azure IoT Edge experimental testbed, intended for a two-laptop setup where the Windows 11 Ryzen 7 laptop runs the industrial simulator/data layer and a separate i7-4900MQ laptop hosts an Ubuntu Server VM running Azure IoT Edge. The system compares cloud-only, edge-pass-through, hybrid, and edge-heavy microservice placement for industrial automation workloads under different load, network delay, packet loss, and cloud outage conditions, measuring latency, throughput, bandwidth, resource usage, message loss, anomaly detection, local autonomy, and recovery behavior.
