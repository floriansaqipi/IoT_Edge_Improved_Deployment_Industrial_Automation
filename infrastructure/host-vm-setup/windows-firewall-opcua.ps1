param(
    [ValidateSet("Show", "Add", "Remove")]
    [string]$Action = "Show",

    [string]$RemoteAddress = "192.168.1.3",
    [int]$LocalPort = 4840
)

$ErrorActionPreference = "Stop"

$RuleName = "AzureIoTEdgeStudy-OPCUA-TCP-4840"
$DisplayName = "Azure IoT Edge Study OPC UA Simulator TCP 4840"
$Profile = "Private"

$AddCommand = "New-NetFirewallRule -Name '$RuleName' -DisplayName '$DisplayName' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $LocalPort -RemoteAddress '$RemoteAddress' -Profile $Profile"
$RemoveCommand = "Remove-NetFirewallRule -Name '$RuleName'"

if ($Action -eq "Show") {
    Write-Host "No firewall changes were made."
    Write-Host "Rule name: $RuleName"
    Write-Host "Display name: $DisplayName"
    Write-Host "Protocol/port: TCP/$LocalPort"
    Write-Host "Allowed remote IP: $RemoteAddress"
    Write-Host "Add command: $AddCommand"
    Write-Host "Revert command: $RemoveCommand"
    exit 0
}

if ($Action -eq "Add") {
    Write-Host "Adding firewall rule: $DisplayName"
    Write-Host "Allowed remote IP: $RemoteAddress"
    Write-Host "Revert with: .\infrastructure\host-vm-setup\windows-firewall-opcua.ps1 -Action Remove"
    Remove-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
    New-NetFirewallRule `
        -Name $RuleName `
        -DisplayName $DisplayName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $LocalPort `
        -RemoteAddress $RemoteAddress `
        -Profile $Profile | Out-Null
    Write-Host "Firewall rule added."
    exit 0
}

Write-Host "Removing firewall rule: $DisplayName"
Remove-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
Write-Host "Firewall rule removed if it existed."
