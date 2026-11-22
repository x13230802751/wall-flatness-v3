param(
    [Parameter(Mandatory=$true)][string]$Cloud,
    [Parameter(Mandatory=$true)][string]$Roi,
    [Parameter(Mandatory=$true)][string]$Out
)
$taskPython = 'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1119-907-0_26.1119.907.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe'
$taskDependencies = Join-Path (Split-Path $PSScriptRoot -Parent) '_runtime'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Bundled Python not found; use README virtual environment instructions.' }
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = "$taskDependencies;$PSScriptRoot"
    & $taskPython -m wall_flatness --cloud $Cloud --roi $Roi --out $Out
    $taskExitCode = $LASTEXITCODE
} finally { $env:PYTHONPATH = $previousPythonPath }
exit $taskExitCode
