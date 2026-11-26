"""LaunchServices and CLI share a single Unix lock in a disposable Mac session."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import socket
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
    print('PASS: Finder, concurrent detached terminal starts, ping, off and released lock.')
