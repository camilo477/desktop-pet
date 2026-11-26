"""Qt GUI lifetime and the two-command, user-only local control channel."""

import sys
from PySide6.QtCore import QIODevice, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


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


def run_pet(server_name, on_ready):
    from PySide6.QtWidgets import QApplication
    from pet import PetWindow

    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    server = QLocalServer(app)
    pet = None
    try:
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
                timeout.timeout.connect(lambda socket=client: socket.abort())
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
        on_ready()
        return app.exec()
    finally:
        if pet is not None:
            pet.shutdown()
        for client in server.findChildren(QLocalSocket):
            client.abort()
        server.close()
