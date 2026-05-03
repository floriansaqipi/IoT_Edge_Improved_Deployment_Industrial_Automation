param(
    [string]$ConnectionString = $env:CLOUD_RESULTS_STORAGE_CONNECTION_STRING,
    [string]$OutputDir = "cloud\results"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ConnectionString)) {
    throw "ConnectionString or CLOUD_RESULTS_STORAGE_CONNECTION_STRING is required."
}

.\.venv\Scripts\python.exe cloud\tools\export_cloud_results.py `
    --connection-string $ConnectionString `
    --output-dir $OutputDir
