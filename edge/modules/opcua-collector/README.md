# OPC UA Collector Edge Module

`opcua-collector` is the Phase 3 S1 pass-through Azure IoT Edge module.
It connects from Machine B to the Machine A OPC UA simulator, subscribes to
device `Sequence` nodes, reads the full device snapshot on each update, and
sends one JSON message to the `telemetry` output.

Default OPC UA endpoint:

```text
opc.tcp://192.168.1.5:4840/factory/server
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `OPCUA_ENDPOINT` | `opc.tcp://192.168.1.5:4840/factory/server` | Machine A simulator endpoint |
| `OPCUA_NAMESPACE_URI` | `urn:industrial-automation:azure-iot-edge-study` | Simulator namespace |
| `OUTPUT_NAME` | `telemetry` | Azure IoT Edge output name |
| `EXPERIMENT_ID_FALLBACK` | `phase3_s1` | Used if OPC UA experiment metadata is absent |
| `SCENARIO_FALLBACK` | `S1_EDGE_PASS_THROUGH` | Used if OPC UA experiment metadata is absent |
| `RUN_ID_FALLBACK` | `phase3_s1_rep1` | Used if OPC UA experiment metadata is absent |
| `RECONNECT_SECONDS` | `5` | Retry delay after OPC UA or send failures |
| `COLLECTOR_OUTPUT_MODE` | `edgehub` | `edgehub`, `stdout`, or `jsonl` |
| `LOCAL_OUTPUT_PATH` | unset | Required for `COLLECTOR_OUTPUT_MODE=jsonl` |

## Local Smoke Test

Start the simulator on Machine A:

```powershell
.\.venv\Scripts\python.exe simulator\industrial-opcua-simulator\src\main.py simulator\industrial-opcua-simulator\configs\exp_10_devices_10mps_opcua.yaml --until-stopped
```

Then run the collector locally in stdout mode:

```powershell
$env:COLLECTOR_OUTPUT_MODE = "stdout"
$env:OPCUA_ENDPOINT = "opc.tcp://127.0.0.1:4840/factory/server"
.\.venv\Scripts\python.exe -m pip install -r edge\modules\opcua-collector\requirements.txt
$env:PYTHONPATH = "edge\modules\opcua-collector\src"
.\.venv\Scripts\python.exe -m opcua_collector.main
```

Inside Azure IoT Edge, leave `COLLECTOR_OUTPUT_MODE` unset so the module uses
`IoTHubModuleClient.create_from_edge_environment()` and sends to `$edgeHub`.
