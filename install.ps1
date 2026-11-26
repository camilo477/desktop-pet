param([string]$Python)
$ErrorActionPreference = 'Stop'
$setup = Join-Path $PSScriptRoot 'windows\setup.py'
if ($Python) {
    & $Python $setup install
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    & py.exe -3 $setup install
} else {
    & python.exe $setup install
}
exit $LASTEXITCODE
