param(
    [string]$Campaign = "latest"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Push-Location $RepoRoot
try {
    & $Python -m experiments.controller status --campaign $Campaign
} finally {
    Pop-Location
}
