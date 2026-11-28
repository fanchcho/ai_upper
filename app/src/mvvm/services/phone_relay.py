"""Original relay open/msg/close envelopes; payloads stay end-to-end encrypted."""
import json
import time
from urllib.parse import urlsplit, urlunsplit, quote


def start(parent, url, desk_id, key, attach, status):
    from utils.qt_compat import QtCore, QtNetwork, QtWebSockets, Signal
    class Peer(QtCore.QObject):
        textMessageReceived = Signal(str)
        disconnected = Signal()
        def __init__(self, relay, identity):
            super().__init__(relay);self.relay=relay;self.identity=identity;self.closed=False
        def sendTextMessage(self, text):
            self.relay.envelope({'t':'msg','c':self.identity,'d':text})
        def close(self):
            if self.closed:return
            self.closed=True;self.relay.envelope({'t':'close','c':self.identity})
            self.relay.peers.pop(self.identity,None);self.disconnected.emit()
    class Relay(QtCore.QObject):
        def __init__(self):
            super().__init__(parent);self.peers={};self.stopped=False;self.attempt=0;self.error='';self.last_rx=time.monotonic()
            self.socket=QtWebSockets.QWebSocket(parent=self)
            self.retry=QtCore.QTimer(self);self.retry.setSingleShot(True);self.retry.timeout.connect(self.connect)
            self.beat=QtCore.QTimer(self);self.beat.setInterval(20000);self.beat.timeout.connect(self.heartbeat)
            self.socket.connected.connect(self.connected);self.socket.disconnected.connect(self.disconnected)
            self.socket.errorOccurred.connect(self.failed);self.socket.textMessageReceived.connect(self.receive)
            self.connect()
        def connect(self):
            parts=urlsplit(url.strip())
            if parts.scheme not in ('http','https','ws','wss') or not parts.hostname:
                status('error: 中转地址无效');return
            if parts.scheme in ('http','ws') and parts.hostname!='127.0.0.1':
                status('error: 公网中转必须使用 HTTPS/WSS');return
            scheme='wss' if parts.scheme in ('https','wss') else 'ws'
            target=urlunsplit((scheme,parts.netloc,parts.path.rstrip('/')+'/desk/'+quote(desk_id),'',''))
            request=QtNetwork.QNetworkRequest(QtCore.QUrl(target));request.setRawHeader(b'authorization',('Bearer '+key).encode())
            self.error='';status('connecting');self.socket.open(request)
        def connected(self):
            self.attempt=0;self.last_rx=time.monotonic();self.beat.start();status('on')
        def failed(self, *_):
            self.error=self.socket.errorString();status('error: '+self.error)
        def heartbeat(self):
            if time.monotonic()-self.last_rx>45:
                self.error='与中转的连接没有响应，正在重连';self.socket.abort()
            else:self.socket.sendTextMessage('ping')
        def envelope(self, value):
            if self.socket.isValid():self.socket.sendTextMessage(json.dumps(value))
        def receive(self, raw):
            self.last_rx=time.monotonic()
            if raw=='pong':return
            try:
                env=json.loads(raw);cid=env.get('c')
                if not isinstance(cid,str):return
                if env.get('t')=='open' and cid not in self.peers:
                    peer=Peer(self,cid);self.peers[cid]=peer;attach(peer,'relay')
                elif env.get('t')=='msg' and cid in self.peers and isinstance(env.get('d'),str):
                    self.peers[cid].textMessageReceived.emit(env['d'])
                elif env.get('t')=='close' and cid in self.peers:self.peers[cid].close()
            except (ValueError,TypeError):return
        def disconnected(self):
            self.beat.stop()
            for peer in list(self.peers.values()):peer.close()
            if self.stopped:return
            status('error: '+(self.error or '与中转断开，正在重连'));self.attempt+=1
            delay=60000 if '401' in self.error or '403' in self.error else min(30000,1000*2**min(self.attempt-1,5))
            self.retry.start(delay)
        def set(self):
            self.stopped=True;self.retry.stop();self.beat.stop()
            for peer in list(self.peers.values()):peer.close()
            self.socket.close()
    return Relay()
