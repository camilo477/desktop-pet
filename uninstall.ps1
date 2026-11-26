param([string]$Python)
$ErrorActionPreference = 'Stop'
$setup = Join-Path $PSScriptRoot 'windows\setup.py'
if ($Python) {
    & $Python $setup uninstall
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    & py.exe -3 $setup uninstall
} else {
    & python.exe $setup uninstall
}
exit $LASTEXITCODE
