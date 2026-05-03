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
- Machine B, physical host laptop: `192.168.1.9`
- OPC UA endpoint from Machine B: `opc.tcp://192.168.1.5:4840/factory/server`
- Rule name: `AzureIoTEdgeStudy-OPCUA-TCP-4840`
- Display name: `Azure IoT Edge Study OPC UA Simulator TCP 4840`
- Direction: inbound
- Protocol: TCP
- Local port: `4840`
- Remote addresses: `192.168.1.3`, `192.168.1.9`
- Profile: `Any`
- Action: allow

Machine B ping test rule:

- Rule name: `AzureIoTEdgeStudy-ICMPv4-Ping-From-MachineB`
- Display name: `Azure IoT Edge Study ICMPv4 Ping From Machine B`
- Direction: inbound
- Protocol: ICMPv4
- ICMP type: `8` echo request
- Remote addresses: `192.168.1.3`, `192.168.1.9`
- Profile: `Any`
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
New-NetFirewallRule -Name 'AzureIoTEdgeStudy-OPCUA-TCP-4840' -DisplayName 'Azure IoT Edge Study OPC UA Simulator TCP 4840' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 4840 -RemoteAddress @('192.168.1.3','192.168.1.9') -Profile Any
New-NetFirewallRule -Name 'AzureIoTEdgeStudy-ICMPv4-Ping-From-MachineB' -DisplayName 'Azure IoT Edge Study ICMPv4 Ping From Machine B' -Direction Inbound -Action Allow -Protocol ICMPv4 -IcmpType 8 -RemoteAddress @('192.168.1.3','192.168.1.9') -Profile Any
```

Equivalent raw revert command:

```powershell
Remove-NetFirewallRule -Name 'AzureIoTEdgeStudy-OPCUA-TCP-4840'
Remove-NetFirewallRule -Name 'AzureIoTEdgeStudy-ICMPv4-Ping-From-MachineB'
```

## Change Log

- 2026-05-03: Added reversible script and documentation only. No firewall rule was applied.
- 2026-05-03: Updated reversible script to also manage a scoped ICMPv4 ping rule for Machine B.
- 2026-05-03: Attempted to add both scoped rules from a non-elevated shell. Windows returned `Access is denied`; no rule was applied.
- 2026-05-03: Updated planned scoped rules to allow both Machine B addresses: Ubuntu VM `192.168.1.3` and physical host `192.168.1.9`. No rule was applied by this edit.
- 2026-05-03: Existing scoped rules were found installed for `192.168.1.3` only. Attempted to update them in place to include `192.168.1.9`; Windows returned `Access is denied`, so the installed rules were not changed.
