"""Per-user, per-session Windows launcher and private pipe discovery."""

import ctypes
import errno
import msvcrt
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

from PySide6.QtCore import QStandardPaths

from instance_control import request, run_pet


def runtime_directory():
    session = ctypes.c_uint32()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
        raise ctypes.WinError()
    local = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    if not local:
        raise RuntimeError('No se pudo localizar la carpeta privada del usuario.')
    directory = Path(local) / 'desktop-pet' / 'runtime' / str(session.value)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def try_lock(directory):
    # Windows releases a byte-range lock on last handle close, including after a crash.
    # Locking one byte past EOF is supported. Never unlink or replace this file.
    stream = (directory / 'instance.lock').open('a+b')
    try:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as error:
        stream.close()
        if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            return None
        raise
    return stream


def instance_busy(directory):
    lock = try_lock(directory)
    if lock is None:
        return True
    lock.close()
    return False


def endpoint(directory):
    try:
        name = (directory / 'endpoint').read_text(encoding='ascii')
    except FileNotFoundError:
        return None
    return name if re.fullmatch(r'miga-[0-9a-f]{32}', name) else None


def serve(directory, ready_fd=None):
    lock = try_lock(directory)
    if lock is None:
        return 0
    with lock:
        marker = directory / 'endpoint'
        marker.unlink(missing_ok=True)
        name = 'miga-' + secrets.token_hex(16)
        pending = directory / 'endpoint.tmp'

        def ready():
            pending.write_text(name, encoding='ascii')
            os.replace(pending, marker)

        try:
            return run_pet(name, ready)
        finally:
            marker.unlink(missing_ok=True)
            pending.unlink(missing_ok=True)


def launch(directory):
    name = endpoint(directory) if instance_busy(directory) else None
    if name and request(name, b'ping'):
        print('Miga ya está en ejecución.')
        return 0
    if getattr(sys, 'frozen', False):
        command = [sys.executable, '--run']
    else:
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        command = [str(pythonw), str(Path(__file__).with_name('main.py')), '--run']
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True,
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        name = endpoint(directory) if instance_busy(directory) else None
        if name and request(name, b'ping'):
            print('Miga iniciada.')
            return 0
        if child.poll() is not None and (child.returncode or not instance_busy(directory)):
            break
        time.sleep(.06)
    raise RuntimeError('Miga no confirmó el inicio. Comprueba la instalación de Qt y la sesión gráfica.')


def stop_instance(directory):
    deadline = time.monotonic() + 15
    while instance_busy(directory):
        name = endpoint(directory)
        if name and request(name, b'off'):
            while instance_busy(directory) and endpoint(directory) == name:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Miga todavía está cerrando.')
                time.sleep(.05)
            print('Miga cerrada.')
            return 0
        if time.monotonic() >= deadline:
            raise RuntimeError('La instancia de Miga no responde.')
        time.sleep(.06)
    print('Miga no está en ejecución.')
    return 0
