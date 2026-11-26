"""Exercise the installed launcher with a private control socket and test preferences."""

import os
from pathlib import Path
import pty
import select
import socket
import struct
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def running_pid(directory):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(2)
        client.connect(str(directory / 'desktop-pet/control.sock'))
        client.sendall(b'ping\n')
        assert client.recv(64).strip() == b'OK'
        return struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]


if __name__ == '__main__':
    with TemporaryDirectory(prefix='miga-cli-') as tmp:
        runtime = Path(tmp)
        env = dict(os.environ, XDG_RUNTIME_DIR=tmp, XDG_CONFIG_HOME=str(runtime / 'config'),
                   QT_QPA_PLATFORM='offscreen')
        shell, terminal = pty.fork()
        if shell == 0:
            os.chdir(ROOT)
            os.execvpe('sh', ['sh', '-c', 'miga && echo READY && read answer'], env)
        try:
            output = b''
            while b'READY' not in output:
                assert select.select([terminal], [], [], 10)[0], 'Launcher did not return to the shell'
                output += os.read(terminal, 1024)
            pid = running_pid(runtime)
            os.close(terminal)
            terminal = None
            os.waitpid(shell, 0)
            assert os.getsid(pid) == pid
            subprocess.run(['miga'], cwd=tmp, env=env, check=True, timeout=10)
            assert running_pid(runtime) == pid
        finally:
            if terminal is not None:
                os.close(terminal)
                os.waitpid(shell, 0)
            subprocess.run(['miga', 'off'], cwd=tmp, env=env, check=True, timeout=10)
        stopped = subprocess.check_output(['miga', 'off'], cwd=ROOT, env=env, text=True, timeout=10)
        assert 'no está en ejecución' in stopped
    print('PASS: detached launch, terminal closure, one instance across directories and graceful shutdown.')
