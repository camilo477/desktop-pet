"""Exercise detached Windows startup and shutdown in a disposable user session."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QCoreApplication
from windows_runtime import endpoint, instance_busy, request, runtime_directory


def main():
    app = QCoreApplication([])
    directory = runtime_directory()
    assert not instance_busy(directory), 'Use a disposable session without Miga running'
    if not sys.argv[1:]:
        # Interrupt only this test's own child. A new owner must be able to
        # replace its stale endpoint after Windows releases the file lock.
        # A Windows venv's python.exe can be a redirector with a child of
        # its own. Keep a handle to the test GUI process itself.
        env = dict(os.environ, PYTHONPATH=sysconfig.get_path('purelib'))
        child = subprocess.Popen([str(Path(sys.base_prefix) / 'python.exe'),
                                  str(ROOT / 'main.py'), '--run'], env=env)
        try:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                name = endpoint(directory)
                if name and instance_busy(directory) and request(name, b'ping'):
                    break
                time.sleep(.05)
            else:
                raise AssertionError('Test instance never became ready')
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=8)
        assert not instance_busy(directory)
    if sys.argv[1:]:
        cli = [sys.argv[1]]
    else:
        cli = ['cmd.exe', '/d', '/c', 'miga']
    with tempfile.TemporaryDirectory(prefix='miga cli ') as cwd:
        def run(args):
            subprocess.run(cli + args, check=True, cwd=cwd, timeout=35)
        try:
            with ThreadPoolExecutor(3) as pool:
                list(pool.map(run, ([], [], [])))
            name = endpoint(directory)
            assert instance_busy(directory) and name and request(name, b'ping') == b'OK'
            run([])
            assert endpoint(directory) == name
        finally:
            run(['off'])
        assert not instance_busy(directory)
        run(['off'])
    print('PASS: concurrent launch, private pipe ping, stable instance, graceful and idempotent off.')


if __name__ == '__main__':
    main()
