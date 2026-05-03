# Azure IoT Edge Study Context: 800k/Day Budgeted Experiment Plan

## 0. Purpose

This file is the active budgeted project context for the first full experimental
run of the Azure IoT Edge microservice placement study for industrial
automation.

The original long-form context file,
`azure_iot_edge_study_context_for_codex_with_s3_two_laptop_architecture.md`,
remains the expanded long-term plan. This file keeps the same scientific idea,
but scales the first publishable experiment so all cloud-bound telemetry fits
inside an **800,000 Azure IoT Hub messages/day hard cap**.

The first quota-limited study compares:

1. **S0 cloud-only**
2. **S1 Azure IoT Edge pass-through**
3. **S2 hybrid edge-cloud processing**

**S3 edge-heavy processing is deferred** to a later expanded study.

## 1. Quota Constraint And Azure Resource Choice

The one-day experiment must stay below:

```text
dailyCloudMessageHardLimit: 800000
plannedCloudMessageLimit: 640000
cloudRateLimitMessagesPerSecond: 90
```

The planned ceiling of 640,000 leaves room for manual smoke tests, retries,
monitoring, payload-size rounding, and operator mistakes.

Use **Azure IoT Hub Standard S1 with 2 units** during the experiment window.
Azure documents size-1 IoT Hub capacity as 400,000 device-to-cloud messages per
day per unit, so two S1 units provide the 800,000/day hard limit. Standard tier
is used because Azure IoT Edge module/device features are part of the standard
feature set.

Azure IoT Hub meters message quota in chunks. For this plan, assume each
telemetry message is under 4 KB and therefore counts as one billable message.
The experiment controller must still calculate billable messages as:

```text
billableMessages = ceil(payloadBytes / 4096)
```

Relevant Microsoft documentation:

- IoT Hub tier/size capacity:
  https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-scaling
- IoT Hub quotas, throttling, and 4 KB metering:
  https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-devguide-quotas-throttling

## 2. Scientific Scope Under The Budget

The scientific question remains:

> How does Azure IoT Edge microservice placement affect latency, throughput,
> cloud traffic, edge resource use, message loss, and anomaly behavior for
> industrial automation telemetry?

For the first budgeted run, the study narrows the comparison:

| Scenario | Included now | Reason |
|---|---:|---|
| S0 cloud-only | Yes | Baseline without Azure IoT Edge processing |
| S1 edge pass-through | Yes | Measures gateway overhead |
| S2 hybrid edge-cloud | Yes | Main proposed placement strategy |
| S3 edge-heavy | No | Deferred because it adds storage/sync complexity and extra matrix rows |

This keeps the experiment publishable while avoiding a matrix that would exceed
the daily IoT Hub quota.

## 3. Budgeted Experiment Matrix

Local generated telemetry and cloud-bound telemetry are intentionally different
in this plan. The simulator and edge modules may generate/process more data
locally than is sent to IoT Hub. JSONL/CSV ground truth remains the reference
for generated count, anomaly labels, message loss, and latency matching.

Machine-readable matrix:

```text
experiments/budgeted_800k_matrix.yaml
```

Budgeted matrix summary:

| Block | Scenarios | Generated rate | Cloud policy | Duration | Reps | Planned cloud messages |
|---|---|---:|---|---:|---:|---:|
| Normal network | S0, S1, S2 | 90 msg/s | S0/S1 full, S2 10% | 300s | 3 | 170,100 |
| 200 ms delay | S0, S1, S2 | 90 msg/s | S0/S1 full, S2 10% | 300s | 3 | 170,100 |
| Cloud outage/recovery | S0, S1, S2 | 90 msg/s | S0/S1 full or queued, S2 10% + alerts | 300s | 3 | 170,100 |
| Local/edge stress | S0, S1, S2 | 500 msg/s | cloud capped at 90/9 msg/s | 60s | 3 | 34,020 |

Planned total cloud messages:

```text
544,320
```

The preflight validator must refuse any selected matrix that exceeds 640,000
planned billable messages or any S0/S1 cloud-bound row above 90 msg/s.

## 4. Scenario Behavior

### S0 cloud-only

S0 bypasses Azure IoT Edge processing. It is the cloud baseline. For the
budgeted run, S0 sends full telemetry at 90 msg/s for normal, delay, and outage
blocks. In the stress block, local generation may be 500 msg/s but cloud output
is capped at 90 msg/s.

### S1 edge pass-through

S1 uses the Phase 3 `opcua-collector` path:

```text
Machine A OPC UA simulator -> Machine B opcua-collector -> $edgeHub -> IoT Hub
```

For the budgeted run, S1 sends full pass-through telemetry at 90 msg/s for
normal, delay, and outage blocks. In the stress block, local OPC UA generation
may be 500 msg/s but cloud output is capped at 90 msg/s.

### S2 hybrid edge-cloud

S2 is the proposed edge-cloud placement. Edge modules should process full raw
telemetry locally, but cloud output must be reduced:

- forward every 10th normalized telemetry message;
- always forward anomaly/alert messages immediately;
- emit low-rate summaries if needed;
- never forward all raw S2 telemetry during the budgeted study.

For normal, delay, and outage blocks, S2 cloud output is planned at 9 msg/s when
local generation is 90 msg/s. In the stress block, S2 still caps cloud output at
9 msg/s even though local generation is 500 msg/s.

## 5. Metrics To Collect

Keep the original metric categories, but interpret them with the local/cloud
split:

- generated messages/second from simulator JSONL/CSV;
- cloud messages/second from IoT Hub metrics;
- p50/p95/p99 latency for cloud-received messages;
- edge resource use on Machine B;
- message loss by matching ground truth against cloud receipt;
- anomaly/alert latency for S2;
- backlog/recovery behavior during the outage block.

The first budgeted study should not claim that every local stress message was
sent to the cloud. It should claim that the system processed local/edge stress
while keeping cloud-bound traffic under the quota policy.

## 6. Implementation Rules For Agents

Before running a full Azure experiment:

1. Run the budget preflight:

   ```powershell
   .\scripts\check_experiment_budget.ps1
   ```

2. Confirm the preflight total stays under 640,000 planned billable messages.
3. Confirm IoT Hub daily usage is low enough before starting the matrix.
4. Stop the run if Azure metrics approach 800,000 daily messages.

Do not add S3 rows to the budgeted matrix. Add S3 only in a future expanded
context/matrix after the budgeted S0/S1/S2 study is complete.

Do not silently change firewall rules. Keep using the reversible firewall
documentation in `infrastructure/host-vm-setup/firewall-changes.md`.

## 7. Azure Resource Plan

Use these defaults for the budgeted run:

- Resource group: `rg-iot-edge-placement-study`
- Region: `westeurope`
- IoT Hub SKU: `S1`
- IoT Hub units: `2`
- IoT Edge device ID: `edge-gateway-b-ubuntu`
- ACR SKU: `Basic`

After the one-day experiment, scale down or delete Azure resources to control
cost.

## 8. Acceptance Criteria

The budgeted study is successful when:

- observed IoT Hub usage stays below 800,000 daily messages;
- no sustained `429` throttling occurs;
- S0/S1 cloud counts match expected full cloud output;
- S2 cloud traffic is substantially lower than S0/S1;
- full generated telemetry remains available locally in JSONL/CSV;
- latency, throughput, message loss, anomaly, CPU/RAM, and recovery metrics are
  still calculable.
