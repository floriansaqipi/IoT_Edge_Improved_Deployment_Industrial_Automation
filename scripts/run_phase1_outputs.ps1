param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Simulator = Join-Path $RepoRoot "simulator\industrial-opcua-simulator\src\main.py"
$ConfigDir = Join-Path $RepoRoot "simulator\industrial-opcua-simulator\configs"
$ResultDir = Join-Path $RepoRoot "simulator\industrial-opcua-simulator\results"
$PythonPath = Join-Path $RepoRoot $Python

$Experiments = @(
    "exp_10_devices_10mps",
    "exp_50_devices_100mps",
    "exp_100_devices_500mps"
)

New-Item -ItemType Directory -Force -Path $ResultDir | Out-Null

foreach ($Experiment in $Experiments) {
    $Config = Join-Path $ConfigDir "$Experiment.yaml"
    $JsonlOutput = Join-Path $ResultDir "$Experiment.jsonl"
    $CsvOutput = Join-Path $ResultDir "$Experiment.csv"

    Write-Host "Generating $Experiment JSONL..."
    & $PythonPath $Simulator $Config --format jsonl --output $JsonlOutput

    Write-Host "Generating $Experiment CSV..."
    & $PythonPath $Simulator $Config --format csv --output $CsvOutput
}

Write-Host "Phase 1 JSONL/CSV outputs regenerated in $ResultDir"
