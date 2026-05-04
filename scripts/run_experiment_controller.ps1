param(
    [ValidateSet("dry-run", "run", "status")]
    [string]$Command = "dry-run",

    [string]$Matrix = "experiments\budgeted_800k_matrix.yaml",
    [string]$Mode = "full",
    [string]$Campaign = "",
    [string]$Row = "",
    [string]$Block = "",
    [ValidateSet("", "S0_CLOUD_ONLY", "S1_EDGE_PASS_THROUGH", "S2_HYBRID")]
    [string]$Scenario = "",
    [int]$Rep = 0
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$ArgsList = @("-m", "experiments.controller", $Command)
if ($Command -eq "status") {
    if ($Campaign) {
        $ArgsList += @("--campaign", $Campaign)
    }
} else {
    $ArgsList += @("--matrix", $Matrix)
    if ($Command -eq "run") {
        $ArgsList += @("--mode", $Mode)
    }
    if ($Campaign) {
        $ArgsList += @("--campaign-id", $Campaign)
    }
    if ($Row) {
        $ArgsList += @("--row", $Row)
    }
    if ($Block) {
        $ArgsList += @("--block", $Block)
    }
    if ($Scenario) {
        $ArgsList += @("--scenario", $Scenario)
    }
    if ($Rep -gt 0) {
        $ArgsList += @("--rep", "$Rep")
    }
}

Push-Location $RepoRoot
try {
    & $Python @ArgsList
} finally {
    Pop-Location
}
