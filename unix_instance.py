"""Process lock, local control and detached startup shared by Linux and macOS."""

import fcntl
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import time

from PySide6.QtNetwork import QLocalServer

from instance_control import request, run_pet


def private_directory(directory: Path) -> Path:
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not (stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077):
        raise RuntimeError("La carpeta temporal de Miga debe ser privada y pertenecer al usuario.")
    if len(os.fsencode(directory / "control.sock")) >= 104:
        raise RuntimeError("La ruta temporal es demasiado larga para el canal de control local.")
    return directory


def instance_busy(directory: Path) -> bool:
    try:
        fd = os.open(directory / "instance.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False
    finally:
        os.close(fd)


def notify(fd: int | None, message: str) -> None:
    if fd is not None:
        try:
            os.write(fd, (message + "\n").encode("utf-8")[:512])
        except OSError:
            pass
        finally:
            os.close(fd)


def serve(directory: Path, ready_fd: int | None) -> int:
    background_start = ready_fd is not None
    lock_fd = os.open(directory / "instance.lock",
                      os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            notify(ready_fd, "ALREADY")
            ready_fd = None
            return 0

        server_name = str(directory / "control.sock")
        QLocalServer.removeServer(server_name)

        def ready():
            nonlocal ready_fd
            notify(ready_fd, "READY")
            ready_fd = None

        return run_pet(server_name, ready)
    except Exception as error:
        notify(ready_fd, f"ERROR: {error}")
        ready_fd = None
        if not background_start:
            raise
        return 1
    finally:
        if ready_fd is not None:
            notify(ready_fd, "ERROR: No se pudo iniciar Miga.")
        os.close(lock_fd)


def launch(directory: Path) -> int:
    server_name = str(directory / "control.sock")
    if request(server_name, b"ping") is not None:
        print("Miga ya está en ejecución.")
        return 0
    read_fd, write_fd = os.pipe()
    try:
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command.append(str(Path(__file__).with_name("main.py").resolve()))
        child = subprocess.Popen(
            [*command, "--run", "--ready-fd", str(write_fd)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True, pass_fds=(write_fd,),
        )
    finally:
        os.close(write_fd)
    try:
        readable, _, _ = select.select([read_fd], [], [], 8.0)
        message = os.read(read_fd, 512).decode("utf-8", errors="replace").strip() if readable else ""
    finally:
        os.close(read_fd)
    if message in ("READY", "ALREADY"):
        print("Miga iniciada." if message == "READY" else "Miga ya se está iniciando.")
        return 0
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    else:
        child.wait()
    raise RuntimeError(message.removeprefix("ERROR: ") or
                       "No se pudo iniciar Miga. Comprueba las dependencias y la sesión gráfica.")


def stop_instance(directory):
    server_name = str(directory / "control.sock")
    deadline = time.monotonic() + 8.0
    reply = request(server_name, b"off")
    # The GUI may own the lock while it is still preparing its window.
    while reply is None and instance_busy(directory):
        if time.monotonic() >= deadline:
            raise RuntimeError("Miga sigue iniciándose; no ha podido recibir la orden de cierre.")
        time.sleep(0.05)
        reply = request(server_name, b"off")
    print("Miga cerrada." if reply is not None else "Miga no está en ejecución.")
    return 0
