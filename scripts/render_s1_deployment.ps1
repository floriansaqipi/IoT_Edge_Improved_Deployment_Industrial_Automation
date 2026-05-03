param(
    [Parameter(Mandatory = $true)]
    [string]$AcrLoginServer,

    [Parameter(Mandatory = $true)]
    [string]$AcrUsername,

    [Parameter(Mandatory = $true)]
    [string]$AcrPassword,

    [string]$ImageTag = "0.1.0-amd64",

    [string]$OutputPath = "edge\deployments\s1-edge-pass-through.generated.json"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TemplatePath = Join-Path $RepoRoot "edge\deployments\s1-edge-pass-through.template.json"
$ResolvedOutputPath = Join-Path $RepoRoot $OutputPath

$Content = Get-Content -Path $TemplatePath -Raw -Encoding UTF8
$Content = $Content.Replace("__ACR_LOGIN_SERVER__", $AcrLoginServer)
$Content = $Content.Replace("__ACR_USERNAME__", $AcrUsername)
$Content = $Content.Replace("__ACR_PASSWORD__", $AcrPassword)
$Content = $Content.Replace("__COLLECTOR_IMAGE_TAG__", $ImageTag)

$OutputDirectory = Split-Path -Parent $ResolvedOutputPath
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
Set-Content -Path $ResolvedOutputPath -Value $Content -Encoding UTF8

Write-Host "Rendered deployment manifest: $ResolvedOutputPath"
Write-Host "Generated deployment manifests are ignored by git."
