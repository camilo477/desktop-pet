"""Install this checkout for the current Windows user, or remove its integration."""

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import time
import venv

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / '.venv-win'
PYTHON = ENV / 'Scripts' / 'python.exe'
PYTHONW = PYTHON.with_name('pythonw.exe')
BIN = ROOT / 'windows' / 'bin'
OWNER = ENV / '.miga-install.json'


def save(state):
    pending = OWNER.with_suffix('.tmp')
    pending.write_text(json.dumps(state), encoding='utf-8')
    pending.replace(OWNER)


def load():
    if ENV.is_symlink() or (ENV.exists() and ENV.lstat().st_file_attributes & 0x400):
        raise RuntimeError('The installation directory must not be a link or junction.')
    if not ENV.exists():
        return None
    if OWNER.is_file():
        state = json.loads(OWNER.read_text(encoding='utf-8'))
        if state.get('project') == 'camilo477/desktop-pet' and Path(state['root']) == ROOT:
            return state
    raise RuntimeError('The existing .venv-win is not owned by this Miga installation.')


def update_path(state, install):
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'Environment', 0,
                            winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        try:
            value, kind = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            value, kind = '', winreg.REG_EXPAND_SZ
        entries = value.split(';') if value else []
        matches = [i for i, p in enumerate(entries) if p and
                   Path(os.path.expandvars(p.strip('"'))) == BIN]
        if install and not matches:
            entries.append(str(BIN))
        elif not install and state['path_added'] and str(BIN) in entries:
            entries.remove(str(BIN))
        else:
            return
        winreg.SetValueEx(key, 'Path', 0, kind, ';'.join(entries))
        if install:
            state['path_added'] = True
            try:
                save(state)
            except OSError:
                winreg.SetValueEx(key, 'Path', 0, kind, value)
                raise
    # Ask Explorer to refresh the environment inherited by new terminals.
    ctypes.windll.user32.SendMessageTimeoutW(0xffff, 0x1a, 0, 'Environment', 2, 1000, None)


def shortcut(install):
    # Use the user's redirected Start Menu, including non-ASCII profile paths.
    # Paths are data supplied via the environment, never interpolated into code.
    script = r"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$file = Join-Path ($shell.SpecialFolders.Item('Programs')) 'Miga Desktop Pet.lnk'
$exists = Test-Path -LiteralPath $file
$link = $shell.CreateShortcut($file)
$arg = '"' + (Join-Path $env:MIGA_INSTALL_ROOT 'main.py') + '"'
if ($exists -and (($link.TargetPath -ne $env:MIGA_INSTALL_PYTHONW) -or ($link.Arguments -ne $arg))) {
    if ($env:MIGA_INSTALL_ACTION -eq 'install') { throw 'A different Start Menu shortcut already exists.' }
    exit 0
}
if ($env:MIGA_INSTALL_ACTION -eq 'install') {
    $link.TargetPath = $env:MIGA_INSTALL_PYTHONW
    $link.Arguments = $arg
    $link.WorkingDirectory = $env:MIGA_INSTALL_ROOT
    $link.IconLocation = Join-Path $env:MIGA_INSTALL_ROOT 'assets\icons\miga.ico'
    $link.Save()
} elseif ($exists) { Remove-Item -LiteralPath $file }
"""
    env = dict(os.environ, MIGA_INSTALL_ROOT=str(ROOT), MIGA_INSTALL_PYTHONW=str(PYTHONW),
               MIGA_INSTALL_ACTION='install' if install else 'uninstall')
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', script],
                   check=True, env=env)


def install(state):
    if sys.version_info < (3, 10) or sysconfig.get_platform() != 'win-amd64':
        raise RuntimeError('Use 64-bit x86 Python 3.10 or newer (3.12 recommended).')
    other = shutil.which('miga')
    if other and Path(other).resolve() != (BIN / 'miga.cmd'):
        raise RuntimeError('Another miga command already exists on PATH. Its launcher was preserved.')
    if state is None:
        ENV.mkdir()
        state = {'project': 'camilo477/desktop-pet', 'root': str(ROOT), 'path_added': False}
        save(state)
    if not PYTHON.exists() or not (ENV / 'Scripts/pip.exe').exists():
        venv.EnvBuilder(with_pip=True).create(ENV)
    subprocess.run([str(PYTHON), '-m', 'pip', 'install', '--disable-pip-version-check',
                    '-r', str(ROOT / 'requirements.txt')], check=True)
    shortcut(True)
    update_path(state, True)
    print('Installed. Open Miga Desktop Pet in Start, or run miga in a new terminal.')


def uninstall(state):
    if state is None:
        print('No installation in this checkout.')
        return
    if PYTHON.exists() and (ENV / 'Lib/site-packages/PySide6').exists():
        subprocess.run([str(PYTHON), str(ROOT / 'main.py'), 'off'], check=True)
    shortcut(False)
    update_path(state, False)
    # A detached GUI may still be unloading Qt just after releasing its lock.
    for attempt in range(20):
        try:
            shutil.rmtree(ENV)
            break
        except PermissionError:
            if attempt == 19:
                save(state)  # Keep ownership verifiable if a DLL is still in use.
                raise
            time.sleep(.1)
    print('Uninstalled. Preferences and source files were kept.')


if __name__ == '__main__':
    try:
        if sys.platform != 'win32' or sys.argv[1:] not in (['install'], ['uninstall']):
            raise RuntimeError('Run on Windows with install or uninstall.')
        (install if sys.argv[1] == 'install' else uninstall)(load())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(f'Miga setup: {error}')
