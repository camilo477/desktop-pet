"""Build a native app or manage Miga's per-user installation."""

import argparse
import filecmp
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import venv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APP = Path.home() / 'Applications/Miga.app'
CLI = Path.home() / '.local/bin/miga'
RECEIPT = Path.home() / 'Library/Application Support/io.github.camilo477.miga/install.json'
BUNDLE_ID = 'io.github.camilo477.miga'
PROJECT = 'camilo477/desktop-pet'


def run(*args):
    subprocess.run(args, check=True)


def check_bundle(app):
    if app.is_symlink() or not app.is_dir():
        raise ValueError('Expected a Miga.app directory.')
    with (app / 'Contents/Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    if info.get('CFBundleIdentifier') != BUNDLE_ID or info.get('MigaProject') != PROJECT:
        raise ValueError('The existing application does not belong to this project.')


def build(stage):
    with TemporaryDirectory(prefix='miga-build-') as tmp:
        env = Path(tmp) / 'venv'
        venv.EnvBuilder(with_pip=True).create(env)
        python = env / 'bin/python'
        run(python, '-m', 'pip', 'install', '--only-binary=:all:', '-r', ROOT / 'requirements.txt',
            'pyinstaller>=6.16,<7')
        run(python, '-m', 'PyInstaller', '--distpath', stage, '--workpath', Path(tmp) / 'work',
            HERE / 'Miga.spec')
    app = stage / 'Miga.app'
    check_bundle(app)
    return app


def owned():
    if not RECEIPT.exists():
        return False
    if RECEIPT.is_symlink() or json.loads(RECEIPT.read_text()) != {'project': PROJECT, 'bundle': BUNDLE_ID}:
        raise ValueError('Unrecognized installation receipt.')
    return True


def check_targets(installed):
    if os.path.lexists(APP):
        if not installed:
            raise ValueError('An application already occupies ~/Applications/Miga.app.')
        check_bundle(APP)
    if os.path.lexists(CLI) and (not installed or CLI.is_symlink() or not CLI.is_file()
                                 or not filecmp.cmp(CLI, HERE / 'miga', shallow=False)):
        raise ValueError('A different launcher occupies ~/.local/bin/miga.')


def install(source):
    installed = owned()
    check_targets(installed)
    APP.parent.mkdir(parents=True, exist_ok=True)
    CLI.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=APP.parent, prefix='.miga-install-') as tmp:
        stage = Path(tmp)
        if source:
            check_bundle(source)
            app = stage / 'Miga.app'
            run('/usr/bin/ditto', source, app)
        else:
            app = build(stage)
        run('/usr/bin/lipo', '-verify_arch', platform.machine(), app / 'Contents/MacOS/Miga')
        run('/usr/bin/codesign', '--verify', '--deep', '--strict', app)
        # Recheck after the build; another installer may have finished.
        check_targets(owned())
        backup = stage / 'previous.app'
        if APP.exists():
            run(APP / 'Contents/MacOS/Miga', 'off')
            APP.rename(backup)
        created_cli = False
        try:
            app.rename(APP)
            if not CLI.exists():
                with CLI.open('xb') as dst:
                    created_cli = True
                    dst.write((HERE / 'miga').read_bytes())
                CLI.chmod(0o755)
            RECEIPT.write_text(json.dumps({'project': PROJECT, 'bundle': BUNDLE_ID}))
        except BaseException:
            if created_cli:
                CLI.unlink(missing_ok=True)
            if APP.exists():
                APP.rename(app)
            if backup.exists():
                backup.rename(APP)
            raise
    print('Installed ~/Applications/Miga.app. Open it in Finder or run miga.')
    if str(CLI.parent) not in os.get_exec_path():
        print('For the terminal command, add to your shell PATH: export PATH="$HOME/.local/bin:$PATH"')


def uninstall():
    if not owned():
        print('No installation receipt found.')
        return
    check_targets(True)
    if APP.exists():
        run(APP / 'Contents/MacOS/Miga', 'off')
        shutil.rmtree(APP)
    CLI.unlink(missing_ok=True)
    RECEIPT.unlink()
    print('Miga removed. Preferences were kept.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('install', 'build', 'uninstall'))
    parser.add_argument('--app', type=Path, help='install an existing local bundle')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise ValueError('Run this installer on macOS.')
    if args.action == 'uninstall':
        uninstall()
        return
    if platform.machine() not in ('arm64', 'x86_64') or tuple(map(int, platform.mac_ver()[0].split('.'))) < (14, 4):
        raise ValueError('Miga requires macOS 14.4 or later on Apple Silicon or Intel.')
    translated = subprocess.run(['/usr/sbin/sysctl', '-in', 'sysctl.proc_translated'],
                                capture_output=True, text=True)
    if translated.stdout.strip() == '1':
        raise ValueError('Use native ARM64 Python on Apple Silicon.')
    if not args.app and sys.version_info < (3, 11):
        raise ValueError('Use native Python 3.11 or newer (3.12 recommended).')
    if args.action == 'install':
        install(args.app)
    else:
        destination = ROOT / 'dist' / platform.machine()
        destination.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(destination / 'Miga.app'):
            raise ValueError('Move the previous dist bundle aside before building.')
        with TemporaryDirectory(dir=destination) as tmp:
            build(Path(tmp)).rename(destination / 'Miga.app')
        print(destination / 'Miga.app')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f'Miga: {error}')
