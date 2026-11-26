"""LaunchServices and CLI share a single Unix lock in a disposable Mac session."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import socket
from PySide6.QtCore import QCoreApplication, QSettings
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from macos_runtime import runtime_directory
from unix_instance import instance_busy

directory = runtime_directory()
app = Path.home() / 'Applications/Miga.app'
cli = Path.home() / '.local/bin/miga'


def server():
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(2)
        client.connect(str(directory / 'control.sock'))
        client.sendall(b'ping\n')
        assert client.recv(16).strip() == b'OK'
    return (directory / 'control.sock').stat().st_ino


if __name__ == '__main__':
    assert not instance_busy(directory), 'Use a disposable session without Miga running'
    disposable = os.environ.get('GITHUB_ACTIONS') == 'true'
    if disposable:
        qapp = QCoreApplication([])
        qapp.setOrganizationName('desktop-pet')
        qapp.setOrganizationDomain('camilo477.github.io')
        qapp.setApplicationName('mascota')
        settings = QSettings()
        settings.setValue('size', 201)  # The app normalizes this to 200 on close.
        settings.setValue('appearance/coat', 'calico')
        settings.setValue('keyboard/format', '65')
        settings.sync()
    try:
        subprocess.run(['open', '-g', app], check=True)
        for _ in range(150):
            try:
                first = server()
                break
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(.1)
        else:
            raise AssertionError('The Finder bundle did not answer ping')
        with ThreadPoolExecutor(3) as pool:
            list(pool.map(lambda _: subprocess.run([cli], cwd='/', check=True, timeout=15), range(3)))
        assert server() == first and instance_busy(directory)
        subprocess.run([cli, 'off'], check=True, timeout=12)
        subprocess.run([cli, 'off'], check=True, timeout=12)
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _: subprocess.run([cli], cwd='/', check=True, timeout=18), range(2)))
        assert server() and instance_busy(directory)
    finally:
        subprocess.run([cli, 'off'], check=True, timeout=12)
    assert not instance_busy(directory)
    if disposable:
        settings.sync()
        assert settings.value('size', type=int) == 200
        assert settings.value('appearance/coat') == 'calico' and settings.value('keyboard/format') == '65'
    print('PASS: Finder, concurrent detached terminal starts, ping, off and released lock.')
