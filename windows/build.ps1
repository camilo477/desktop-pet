# Run on x64 Windows after installation. Build dependencies stay in a temporary venv.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $root '.venv-win\Scripts\python.exe'
if (!(Test-Path -LiteralPath $runtime)) { throw 'Install Miga first.' }
$work = Join-Path ([IO.Path]::GetTempPath()) ('miga-build-' + [guid]::NewGuid())
$out = Join-Path $root 'dist'
if (Test-Path -LiteralPath (Join-Path $out 'Miga')) { throw 'Move dist\Miga aside before rebuilding.' }
try {
    & $runtime -m venv $work
    if ($LASTEXITCODE) { throw 'Could not create the build environment.' }
    $python = Join-Path $work 'Scripts\python.exe'
    & $python -m pip install -r (Join-Path $root 'requirements.txt') 'pyinstaller>=6.15,<7'
    if ($LASTEXITCODE) { throw 'Could not install the build tools.' }
    & $python -m PyInstaller --windowed --onedir --noupx --name Miga --distpath $out --workpath (Join-Path $work 'work') --specpath $work --add-data ((Join-Path $root 'assets') + ';assets') --exclude-module macos_runtime --exclude-module macos_input --exclude-module macos_window --exclude-module linux_runtime --exclude-module x11_input --exclude-module pynput (Join-Path $root 'main.py')
    if ($LASTEXITCODE) { throw 'Miga packaging failed.' }
} finally {
    if (Test-Path -LiteralPath $work) { Remove-Item -Recurse -Force -LiteralPath $work }
}
