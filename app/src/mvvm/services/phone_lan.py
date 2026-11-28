"""Serve mobile assets and /ws on one LAN TCP port, using Qt's WS upgrade."""
from pathlib import Path


def start(parent, websocket_server, port):
    from utils.qt_compat import QtCore, QtNetwork
    directory=Path(__file__).resolve().parents[2]/'web_pair'
    class Lan(QtCore.QObject):
        def __init__(self):
            super().__init__(parent);self.server=QtNetwork.QTcpServer(self);self.sockets=set()
            if not self.server.listen(QtNetwork.QHostAddress.AnyIPv4,port):raise RuntimeError(self.server.errorString())
            self.server.newConnection.connect(self.accept)
        def port(self):return self.server.serverPort()
        def accept(self):
            socket=self.server.nextPendingConnection();self.sockets.add(socket)
            timer=QtCore.QTimer(socket);timer.setSingleShot(True);timer.timeout.connect(lambda:socket.abort());timer.start(15000)
            socket.disconnected.connect(lambda:self.sockets.discard(socket))
            def read():
                raw=bytes(socket.peek(16385))
                if len(raw)>16384:socket.abort();return
                if b'\r\n\r\n' not in raw:return
                socket.readyRead.disconnect(read);timer.stop()
                first=raw.split(b'\r\n')[0].split();path=first[1].split(b'?')[0] if len(first)==3 else b''
                if path==b'/ws' and b'upgrade: websocket' in raw.lower():
                    websocket_server.handleConnection(socket);return
                socket.readAll()
                socket.disconnected.connect(socket.deleteLater)
                assets={b'/':('index.html','text/html'),b'/index.html':('index.html','text/html'),b'/client.js':('client.js','text/javascript'),b'/sw.js':('sw.js','text/javascript')}
                asset=assets.get(path);code=b'200 OK' if asset else b'404 Not Found'
                body=(directory/asset[0]).read_bytes() if asset else b'Not found'
                mime=asset[1] if asset else 'text/plain'
                socket.write(b'HTTP/1.1 '+code+b'\r\nConnection: close\r\nCache-Control: no-store\r\nContent-Type: '+mime.encode()+b'; charset=utf-8\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body);socket.disconnectFromHost()
            socket.readyRead.connect(read)
        def set(self):
            self.server.close()
            for socket in list(self.sockets):socket.abort()
    return Lan()
