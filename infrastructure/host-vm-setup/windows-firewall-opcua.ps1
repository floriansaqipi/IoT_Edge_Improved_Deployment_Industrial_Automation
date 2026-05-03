param(
    [ValidateSet("Show", "Add", "Remove")]
    [string]$Action = "Show",

    [string[]]$RemoteAddress = @("192.168.1.3", "192.168.1.9"),
    [int]$LocalPort = 4840
)

$ErrorActionPreference = "Stop"

$RuleName = "AzureIoTEdgeStudy-OPCUA-TCP-4840"
$DisplayName = "Azure IoT Edge Study OPC UA Simulator TCP 4840"
$PingRuleName = "AzureIoTEdgeStudy-ICMPv4-Ping-From-MachineB"
$PingDisplayName = "Azure IoT Edge Study ICMPv4 Ping From Machine B"

$RemoteAddressText = $RemoteAddress -join ", "
$RemoteAddressLiteral = "@('" + ($RemoteAddress -join "','") + "')"
$AddCommand = "New-NetFirewallRule -Name '$RuleName' -DisplayName '$DisplayName' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $LocalPort -RemoteAddress $RemoteAddressLiteral -Profile Any"
$AddPingCommand = "New-NetFirewallRule -Name '$PingRuleName' -DisplayName '$PingDisplayName' -Direction Inbound -Action Allow -Protocol ICMPv4 -IcmpType 8 -RemoteAddress $RemoteAddressLiteral -Profile Any"
$RemoveCommand = "Remove-NetFirewallRule -Name '$RuleName'; Remove-NetFirewallRule -Name '$PingRuleName'"

if ($Action -eq "Show") {
    Write-Host "No firewall changes were made."
    Write-Host "OPC UA rule name: $RuleName"
    Write-Host "OPC UA display name: $DisplayName"
    Write-Host "OPC UA protocol/port: TCP/$LocalPort"
    Write-Host "Ping rule name: $PingRuleName"
    Write-Host "Ping display name: $PingDisplayName"
    Write-Host "Ping protocol/type: ICMPv4 echo request"
    Write-Host "Allowed remote IPs: $RemoteAddressText"
    Write-Host "Add OPC UA command: $AddCommand"
    Write-Host "Add ping command: $AddPingCommand"
    Write-Host "Revert command: $RemoveCommand"
    exit 0
}

if ($Action -eq "Add") {
    Write-Host "Adding firewall rules:"
    Write-Host "- $DisplayName"
    Write-Host "- $PingDisplayName"
    Write-Host "Allowed remote IPs: $RemoteAddressText"
    Write-Host "Revert with: .\infrastructure\host-vm-setup\windows-firewall-opcua.ps1 -Action Remove"
    Remove-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
    Remove-NetFirewallRule -Name $PingRuleName -ErrorAction SilentlyContinue
    New-NetFirewallRule `
        -Name $RuleName `
        -DisplayName $DisplayName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $LocalPort `
        -RemoteAddress $RemoteAddress `
        -Profile Any `
        -ErrorAction Stop | Out-Null
    New-NetFirewallRule `
        -Name $PingRuleName `
        -DisplayName $PingDisplayName `
        -Direction Inbound `
        -Action Allow `
        -Protocol ICMPv4 `
        -IcmpType 8 `
        -RemoteAddress $RemoteAddress `
        -Profile Any `
        -ErrorAction Stop | Out-Null
    Write-Host "Firewall rules added."
    exit 0
}

Write-Host "Removing firewall rules:"
Write-Host "- $DisplayName"
Write-Host "- $PingDisplayName"
Remove-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
Remove-NetFirewallRule -Name $PingRuleName -ErrorAction SilentlyContinue
Write-Host "Firewall rules removed if they existed."
