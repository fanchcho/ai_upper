"""Per-data-directory process lock and activation (deva main/index.ts:276)."""
from pathlib import Path
import hashlib
from PySide6.QtCore import QObject, QLockFile
from PySide6.QtNetwork import QLocalServer, QLocalSocket

class SingleInstance(QObject):
    def __init__(self, home, parent=None):
        super().__init__(parent)
        home = Path(home).resolve()
        home.mkdir(parents=True, exist_ok=True)
        self.lock = QLockFile(str(home / 'instance.lock'))
        self.name = 'ai-upper-' + hashlib.sha256(str(home).encode()).hexdigest()[:24]
        self.server = QLocalServer(self)
        self.window = None
        self.pending = False

    def acquire(self):
        if not self.lock.tryLock(0):
            client = QLocalSocket(self)
            client.connectToServer(self.name)
            if not client.waitForConnected(2000):
                raise RuntimeError('Existing instance activation failed: ' + client.errorString())
            client.write(b'activate\n')
            if not client.waitForBytesWritten(2000):
                raise RuntimeError('Activation write failed: ' + client.errorString())
            client.disconnectFromServer()
            return False
        # The lock proves no live owner remains; remove a socket left by a crash.
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.lock.unlock()
            raise RuntimeError(self.server.errorString())
        self.server.newConnection.connect(self._activate)
        return True

    def _activate(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.close()
            socket.deleteLater()
            self.pending = True
        if self.window is not None and self.pending:
            self.pending = False
            print("SINGLE INSTANCE ACTIVATE", flush=True)
            if self.window.isMinimized():
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
