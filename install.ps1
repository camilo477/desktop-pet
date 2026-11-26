$ErrorActionPreference = 'Stop'
$setup = Join-Path $PSScriptRoot 'windows\setup.py'
if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    & py.exe -3 $setup install
} else {
    & python.exe $setup install
}
exit $LASTEXITCODE
