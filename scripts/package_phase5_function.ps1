param(
    [string]$OutputPath = "cloud\azure-function\dist\phase5-cloud-function.zip"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$FunctionDir = Join-Path $Root "cloud\azure-function"
$CloudProcessorSrc = Join-Path $Root "cloud\cloud_processor\src\cloud_processor"
$CommonSrc = Join-Path $Root "edge\modules\common\src\edge_study_common"
$OutputFullPath = Join-Path $Root $OutputPath
$Stage = Join-Path $env:TEMP ("phase5-function-package-" + [guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Path $Stage | Out-Null
try {
    Copy-Item (Join-Path $FunctionDir "host.json") $Stage
    Copy-Item (Join-Path $FunctionDir "requirements.txt") $Stage
    Copy-Item (Join-Path $FunctionDir ".deployment") $Stage
    Copy-Item (Join-Path $FunctionDir "ProcessIoTHubTelemetry") (Join-Path $Stage "ProcessIoTHubTelemetry") -Recurse
    robocopy $CloudProcessorSrc (Join-Path $Stage "cloud_processor") /E /XD __pycache__ | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Failed to copy cloud_processor package." }
    robocopy $CommonSrc (Join-Path $Stage "edge_study_common") /E /XD __pycache__ | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Failed to copy edge_study_common package." }

    New-Item -ItemType Directory -Path (Split-Path $OutputFullPath) -Force | Out-Null
    if (Test-Path $OutputFullPath) {
        Remove-Item $OutputFullPath -Force
    }
    $env:PHASE5_PACKAGE_STAGE = $Stage
    $env:PHASE5_PACKAGE_OUTPUT = $OutputFullPath
    try {
        @'
import os
import zipfile
from pathlib import Path

stage = Path(os.environ["PHASE5_PACKAGE_STAGE"])
output = Path(os.environ["PHASE5_PACKAGE_OUTPUT"])
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(stage).as_posix())
'@ | .\.venv\Scripts\python.exe -
    }
    finally {
        Remove-Item Env:\PHASE5_PACKAGE_STAGE -ErrorAction SilentlyContinue
        Remove-Item Env:\PHASE5_PACKAGE_OUTPUT -ErrorAction SilentlyContinue
    }
    Write-Output "Packaged Phase 5 Azure Function: $OutputFullPath"
    Write-Output "Generated function packages are ignored by git."
}
finally {
    Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
}
