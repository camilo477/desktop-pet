"""Exercise detached Windows startup and shutdown in a disposable user session."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QCoreApplication
from windows_runtime import endpoint, instance_busy, request, runtime_directory


def main():
    app = QCoreApplication([])
    directory = runtime_directory()
    assert not instance_busy(directory), 'Use a disposable session without Miga running'
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
