"""Detached launcher and a private local control socket for the desktop pet."""

import argparse
import fcntl
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import QCoreApplication, QIODevice, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def runtime_directory() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        try:
            info = Path(base).lstat()
            valid = (Path(base).is_absolute() and stat.S_ISDIR(info.st_mode)
                     and info.st_uid == os.getuid() and not info.st_mode & 0o077)
        except OSError:
            valid = False
        if not valid:
            base = None
    directory = (Path(base) / "desktop-pet" if base else
                 Path(tempfile.gettempdir()) / f"desktop-pet-{os.getuid()}")
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not (stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077):
        raise RuntimeError("La carpeta temporal de Miga debe ser privada y pertenecer al usuario.")
    if len(os.fsencode(directory / "control.sock")) >= 104:
        raise RuntimeError("La ruta temporal es demasiado larga para el canal de control local.")
    return directory


def request(server_name: str, command: bytes) -> bytes | None:
    client = QLocalSocket()
    client.connectToServer(server_name, QIODevice.OpenModeFlag.ReadWrite)
    if not client.waitForConnected(300):
        client.abort()
        return None
    client.write(command + b"\n")
    client.flush()
    if not client.canReadLine() and not client.waitForReadyRead(1500):
        client.abort()
        raise RuntimeError("La instancia de Miga no responde al comando.")
    reply = bytes(client.readLine(64)).strip()
    expected = b"BYE" if command == b"off" else b"OK"
    if reply != expected:
        client.abort()
        raise RuntimeError("El canal de control devolvió una respuesta inesperada.")
    if command == b"off" and client.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        if not client.waitForDisconnected(4000):
            client.abort()
            raise RuntimeError("Miga recibió la orden, pero todavía no ha terminado de cerrar.")
    client.abort()
    return reply


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
    lock_fd = os.open(directory / "instance.lock",
                      os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    server = None
    pet = None
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            notify(ready_fd, "ALREADY")
            ready_fd = None
            return 0

        from PySide6.QtWidgets import QApplication
        from pet import PetWindow

        app = QApplication([sys.argv[0]])
        app.setQuitOnLastWindowClosed(False)
        server_name = str(directory / "control.sock")
        # Only the lock owner may remove a socket left behind by a crashed instance.
        QLocalServer.removeServer(server_name)
        server = QLocalServer(app)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        server.setMaxPendingConnections(4)
        pet = PetWindow()
        app.aboutToQuit.connect(pet.shutdown)
        if not server.listen(server_name):
            raise RuntimeError("No se pudo abrir el canal de control local.")

        def accept_connections() -> None:
            while server.hasPendingConnections():
                client = server.nextPendingConnection()
                client.setParent(server)
                client.setReadBufferSize(64)
                client.disconnected.connect(client.deleteLater)
                timeout = QTimer(client)
                timeout.setSingleShot(True)
                timeout.timeout.connect(client.abort)
                timeout.start(2000)

                def read_command(socket=client, timer=timeout) -> None:
                    if not socket.canReadLine():
                        if socket.bytesAvailable() >= 64:
                            socket.abort()
                        return
                    command = bytes(socket.readLine(64))
                    timer.stop()
                    if command == b"ping\n":
                        socket.write(b"OK\n")
                        socket.disconnectFromServer()
                    elif command == b"off\n":
                        socket.write(b"BYE\n")
                        socket.flush()
                        QTimer.singleShot(0, pet.close)
                    else:
                        socket.abort()

                client.readyRead.connect(read_command)
                read_command()

        server.newConnection.connect(accept_connections)
        pet.show()
        notify(ready_fd, "READY")
        ready_fd = None
        return app.exec()
    except Exception as error:
        notify(ready_fd, f"ERROR: {error}")
        ready_fd = None
        return 1
    finally:
        if pet is not None:
            pet.shutdown()
        if server is not None:
            for client in server.findChildren(QLocalSocket):
                client.abort()
            server.close()
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
        child = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--run", "--ready-fd", str(write_fd)],
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="miga", description="Miga, tu pequeña compañía de escritorio.")
    parser.add_argument("command", nargs="?", choices=("off",), help="cerrar Miga")
    parser.add_argument("--run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ready-fd", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    QCoreApplication.setOrganizationName("desktop-pet")
    # Keep the original settings namespace across the launcher rename.
    QCoreApplication.setApplicationName("mascota")
    try:
        directory = runtime_directory()
        if args.run:
            return serve(directory, args.ready_fd)
        app = QCoreApplication([sys.argv[0]])
        if args.command == "off":
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
        return launch(directory)
    except (OSError, RuntimeError) as error:
        if args.run:
            notify(args.ready_fd, f"ERROR: {error}")
        else:
            print(f"miga: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
