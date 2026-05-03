# Phase 3 Azure Setup

Phase 3 implements S1 edge pass-through ingestion:

```text
Machine A OPC UA simulator -> Machine B Azure IoT Edge opcua-collector -> $edgeHub -> IoT Hub
```

Defaults:

- Resource group: `rg-iot-edge-placement-study`
- Region: `westeurope`
- IoT Hub SKU: `S1`
- IoT Hub units for the budgeted one-day study: `2`
- Edge device ID: `edge-gateway-b-ubuntu`
- Collector image tag: `opcua-collector:0.1.0-amd64`

## Azure Resources

Use globally unique names for IoT Hub and ACR.

```bash
az login
az extension add --name azure-iot
az group create --name rg-iot-edge-placement-study --location westeurope
az iot hub create --resource-group rg-iot-edge-placement-study --name <unique-iot-hub-name> --sku S1 --unit 2
az acr create --resource-group rg-iot-edge-placement-study --name <uniqueacrname> --sku Basic --admin-enabled true
az iot hub device-identity create --hub-name <unique-iot-hub-name> --device-id edge-gateway-b-ubuntu --edge-enabled
az iot hub device-identity connection-string show --hub-name <unique-iot-hub-name> --device-id edge-gateway-b-ubuntu
```

Before running the full experiment matrix, validate the budget:

```powershell
.\scripts\check_experiment_budget.ps1
```

The budgeted matrix is documented in
`azure_iot_edge_study_context_800k_daily_budget.md` and stored in
`experiments/budgeted_800k_matrix.yaml`.

## Build Collector Image

From the repository root:

```bash
az acr build \
  --registry <uniqueacrname> \
  --image opcua-collector:0.1.0-amd64 \
  edge/modules/opcua-collector
```

Get ACR values for the deployment manifest:

```bash
az acr show --name <uniqueacrname> --query loginServer -o tsv
az acr credential show --name <uniqueacrname>
```

Render the local deployment manifest on Machine A:

```powershell
.\scripts\render_s1_deployment.ps1 `
  -AcrLoginServer "<uniqueacrname>.azurecr.io" `
  -AcrUsername "<acr-username>" `
  -AcrPassword "<acr-password>"
```

The generated file is ignored by git because it contains local registry
credentials.

## Deploy S1 Modules

```bash
az iot edge set-modules \
  --hub-name <unique-iot-hub-name> \
  --device-id edge-gateway-b-ubuntu \
  --content edge/deployments/s1-edge-pass-through.generated.json
```

## Validate Cloud Ingestion

Start the simulator on Machine A:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps_opcua.yaml --until-stopped
```

From Machine B:

```bash
ping 192.168.1.5
nc -vz 192.168.1.5 4840
sudo iotedge list
sudo iotedge logs opcua-collector -f
```

Monitor IoT Hub:

```bash
az iot hub monitor-events --hub-name <unique-iot-hub-name> --device-id edge-gateway-b-ubuntu
```

Acceptance criteria:

- `opcua-collector` stays `running`.
- Logs show an OPC UA connection to `192.168.1.5:4840`.
- IoT Hub receives messages with `deviceId`, `deviceType`, `sequence`,
  `sensorTimestamp`, `edgeReceivedTimestamp`, `values`, and `groundTruth`.
- No normalizer/filter/anomaly detector runs in this phase.

References:

- Azure IoT Edge Linux symmetric-key provisioning:
  https://learn.microsoft.com/en-us/azure/iot-edge/how-to-provision-single-device-linux-symmetric
- IoT Edge deployment manifests and routes:
  https://learn.microsoft.com/en-us/azure/iot-edge/module-composition
- `az iot edge set-modules`:
  https://learn.microsoft.com/en-us/cli/azure/iot/edge
