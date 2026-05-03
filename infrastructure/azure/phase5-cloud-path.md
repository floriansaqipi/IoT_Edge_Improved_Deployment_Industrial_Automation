# Phase 5 Cloud Path Setup

Phase 5 adds the budgeted cloud path for S0/S1/S2:

```text
S0: Machine A OPC UA simulator -> Machine B non-Edge S0 publisher -> IoT Hub -> Azure Function -> Table Storage
S1: Machine A OPC UA simulator -> Machine B IoT Edge S1 -> IoT Hub -> Azure Function -> Table Storage
S2: Machine A OPC UA simulator -> Machine B IoT Edge S2 -> IoT Hub -> Azure Function -> Table Storage
```

S3 remains deferred for the 800k/day study.

## Azure Resources

Use the existing IoT Hub:

```text
iothub-edge-study-florian01
```

Create one non-Edge IoT device identity for S0:

```bash
az iot hub device-identity create \
  --hub-name iothub-edge-study-florian01 \
  --device-id s0-cloud-publisher-b
```

Create cloud processing resources:

```bash
az storage account create \
  --resource-group rg-iot-edge-placement-study \
  --name stedgecloudflorian01 \
  --location switzerlandnorth \
  --sku Standard_LRS

az functionapp create \
  --resource-group rg-iot-edge-placement-study \
  --name func-edge-study-cloudproc-florian01 \
  --storage-account stedgecloudflorian01 \
  --consumption-plan-location switzerlandnorth \
  --runtime python \
  --runtime-version 3.12 \
  --functions-version 4 \
  --os-type Linux

az iot hub consumer-group create \
  --hub-name iothub-edge-study-florian01 \
  --name cloudproc
```

Set Function App settings using runtime-only secrets:

```bash
az functionapp config appsettings set \
  --resource-group rg-iot-edge-placement-study \
  --name func-edge-study-cloudproc-florian01 \
  --settings \
    IOTHUB_EVENTHUB_CONNECTION="<event-hub-compatible-connection-string>" \
    IOTHUB_EVENTHUB_NAME="<event-hub-compatible-name>" \
    IOTHUB_CONSUMER_GROUP="cloudproc" \
    CLOUD_RESULTS_STORAGE_CONNECTION_STRING="<storage-account-connection-string>" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true" \
    ENABLE_ORYX_BUILD="true"
```

Package and deploy from Machine A:

```powershell
.\scripts\package_phase5_function.ps1
az functionapp deploy `
  --resource-group rg-iot-edge-placement-study `
  --name func-edge-study-cloudproc-florian01 `
  --src-path cloud\azure-function\dist\phase5-cloud-function.zip `
  --type zip
```

## S0 Publisher

Build the Docker image from the repo root:

```bash
docker build \
  -f cloud/s0-cloud-publisher/Dockerfile \
  -t s0-cloud-publisher:0.1.0-amd64 \
  .
```

Run it on Machine B, not as an IoT Edge module:

```bash
docker run --rm \
  --name s0-cloud-publisher \
  -e OPCUA_ENDPOINT="opc.tcp://192.168.1.5:4840/factory/server" \
  -e OPCUA_NAMESPACE_URI="urn:industrial-automation:azure-iot-edge-study" \
  -e IOTHUB_DEVICE_CONNECTION_STRING="<s0-device-connection-string>" \
  -e CLOUD_OUTPUT_POLICY="full" \
  -e CLOUD_MAX_MESSAGES_PER_SECOND="90" \
  -e SCENARIO_OVERRIDE="S0_CLOUD_ONLY" \
  s0-cloud-publisher:0.1.0-amd64
```

Before an S0 run, deploy `edge/deployments/idle-edge.template.json` to the Edge
device so S1/S2 modules do not also publish the same OPC UA stream.

## Export Results

Export Azure Table Storage rows to local ignored files:

```powershell
$env:CLOUD_RESULTS_STORAGE_CONNECTION_STRING = "<storage-account-connection-string>"
.\scripts\export_cloud_results.ps1
Remove-Item Env:\CLOUD_RESULTS_STORAGE_CONNECTION_STRING
```

Generated files go under `cloud/results/` and are ignored by git.
