"""Per-data-directory process lock and activation (deva main/index.ts:276)."""
from pathlib import Path
import hashlib

def SingleInstance(home, parent=None):
    """Create the native controller lazily after the Qt application starts."""
    from utils.qt_compat import QtCore, QtNetwork

    class Controller(QtCore.QObject):
        def __init__(self, home, parent=None):
            super().__init__(parent)
            home = Path(home).resolve()
            home.mkdir(parents=True, exist_ok=True)
            self.lock = QtCore.QLockFile(str(home / 'instance.lock'))
            self.name = 'ai-upper-' + hashlib.sha256(str(home).encode()).hexdigest()[:24]
            self.server = QtNetwork.QLocalServer(self)
            self.window = None
            self.pending = False
    
        def acquire(self):
            if not self.lock.tryLock(0):
                client = QtNetwork.QLocalSocket(self)
                client.connectToServer(self.name)
                if not client.waitForConnected(2000):
                    raise RuntimeError('Existing instance activation failed: ' + client.errorString())
                if client.write(b'activate\n') != len(b'activate\n'):
                    raise RuntimeError('Activation write failed: ' + client.errorString())
                client.flush()
                # A named pipe may finish writing before waitForBytesWritten()
                # starts. Confirm delivery with a reply, not a write notification.
                # The owner may still be loading QML before its event loop starts.
                if not client.canReadLine() and not client.waitForReadyRead(10000):
                    raise RuntimeError('Activation acknowledgement failed: ' + client.errorString())
                if bytes(client.readLine()) != b'activated\n':
                    raise RuntimeError('Invalid activation acknowledgement')
                client.disconnectFromServer()
                return False
            # The lock proves no live owner remains; remove a socket left by a crash.
            QtNetwork.QLocalServer.removeServer(self.name)
            if not self.server.listen(self.name):
                self.lock.unlock()
                raise RuntimeError(self.server.errorString())
            self.server.newConnection.connect(self._activate)
            return True
    
        def _activate(self):
            while self.server.hasPendingConnections():
                socket = self.server.nextPendingConnection()
                socket.disconnected.connect(socket.deleteLater)
                socket.readyRead.connect(lambda socket=socket: self._receive(socket))
                if socket.bytesAvailable():
                    self._receive(socket)
            self._show_window()

        def _receive(self, socket):
            if not socket.canReadLine():
                return
            if bytes(socket.readLine()) == b'activate\n':
                self.pending = True
                self._show_window()
                socket.write(b'activated\n')
                socket.flush()
            # disconnectFromServer drains queued replies before closing.
            socket.disconnectFromServer()

        def _show_window(self):
            if self.window is not None and self.pending:
                self.pending = False
                print("SINGLE INSTANCE ACTIVATE", flush=True)
                if self.window.windowState() == QtCore.Qt.WindowMinimized:
                    self.window.showNormal()
                else:
                    self.window.show()
                self.window.raise_()
                self.window.requestActivate()
    
        def attach(self, window):
            self.window = window
            self._activate()
    
        def close(self):
            self.server.close()
            self.lock.unlock()

    return Controller(home, parent)
