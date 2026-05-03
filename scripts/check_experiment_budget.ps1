param(
    [string]$MatrixPath = "experiments\budgeted_800k_matrix.yaml",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$ResolvedMatrixPath = Join-Path $RepoRoot $MatrixPath
$Arguments = @("-m", "experiments.budget", $ResolvedMatrixPath)
if ($Json) {
    $Arguments += "--json"
}

& $Python @Arguments
exit $LASTEXITCODE
