# Firewall Changes

This file records planned or executed firewall changes for the Azure IoT Edge
microservice placement study.

## Current Status

As of 2026-05-03, Codex has not added, removed, or modified any Windows Firewall
rules for this project.

## Planned OPC UA Rule

Use this rule only when Machine B cannot reach the OPC UA simulator on Machine A.

- Machine A, Windows simulator laptop: `192.168.1.5`
- Machine B, Ubuntu Server VM edge host: `192.168.1.3`
- OPC UA endpoint from Machine B: `opc.tcp://192.168.1.5:4840/factory/server`
- Rule name: `AzureIoTEdgeStudy-OPCUA-TCP-4840`
- Display name: `Azure IoT Edge Study OPC UA Simulator TCP 4840`
- Direction: inbound
- Protocol: TCP
- Local port: `4840`
- Remote address: `192.168.1.3`
- Profile: `Private`
- Action: allow

Preview the exact command without changing the firewall:

```powershell
.\infrastructure\host-vm-setup\windows-firewall-opcua.ps1 -Action Show
```

Add the rule:

```powershell
.\infrastructure\host-vm-setup\windows-firewall-opcua.ps1 -Action Add
```

Revert the rule:

```powershell
.\infrastructure\host-vm-setup\windows-firewall-opcua.ps1 -Action Remove
```

Equivalent raw add command:

```powershell
New-NetFirewallRule -Name 'AzureIoTEdgeStudy-OPCUA-TCP-4840' -DisplayName 'Azure IoT Edge Study OPC UA Simulator TCP 4840' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 4840 -RemoteAddress '192.168.1.3' -Profile Private
```

Equivalent raw revert command:

```powershell
Remove-NetFirewallRule -Name 'AzureIoTEdgeStudy-OPCUA-TCP-4840'
```

## Change Log

- 2026-05-03: Added reversible script and documentation only. No firewall rule was applied.
