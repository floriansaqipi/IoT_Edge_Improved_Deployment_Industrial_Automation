# Machine B Ubuntu IoT Edge Notes

Machine B is the Ubuntu Server VM edge gateway at `192.168.1.3`. It runs Azure
IoT Edge and the Phase 3 `opcua-collector` module. Machine A remains the Windows
OPC UA simulator at `192.168.1.5`.

## Network Checks

Use bridged networking for the Ubuntu VM when possible.

```bash
ip addr
ping 192.168.1.5
nc -vz 192.168.1.5 4840
```

If `nc` cannot reach port `4840`, check the Machine A simulator is bound to
`0.0.0.0:4840`, then inspect the documented Windows firewall rules before
changing anything.

## Install Azure IoT Edge Runtime

The Microsoft docs currently mark IoT Edge `1.5` as the supported LTS release.
Use the commands below as the lab baseline, but check the linked Microsoft Learn
page if Ubuntu package support changes for your exact Ubuntu version.

```bash
source /etc/os-release
wget https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install -y moby-engine aziot-edge netcat-openbsd
```

Provision the lab device with the symmetric-key connection string from IoT Hub:

```bash
sudo iotedge config mp --connection-string '<EDGE_DEVICE_CONNECTION_STRING>'
sudo iotedge config apply
sudo iotedge check
sudo iotedge system status
sudo iotedge list
```

## Useful Runtime Commands

```bash
sudo iotedge list
sudo iotedge logs opcua-collector -f
sudo iotedge check
sudo systemctl status aziot-edged
```

No firewall rules should be added from this Ubuntu side for Phase 3 unless a
specific connectivity test proves they are needed.
