"""Local browser pairing: original remote-crypto.ts transcript and ordered frames."""
import json,os,time,hashlib,hmac,secrets,threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import quote
from pathlib import Path
from mvvm.services.channel_push import encode,decode

def start(controller,bot):
 from utils.qt_compat import QtCore,QtNetwork,QtWebSockets
 QObject,QTimer=QtCore.QObject,QtCore.QTimer
 QHostAddress,QWebSocketServer=QtNetwork.QHostAddress,QtWebSockets.QWebSocketServer
 from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey,X25519PublicKey
 from cryptography.hazmat.primitives.kdf.hkdf import HKDF
 from cryptography.hazmat.primitives import hashes,serialization
 from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
 class Server(QObject):
  def __init__(self):
   super().__init__(controller);self.ticket=None;self.connections={};self.server=QWebSocketServer('ai_upper pairing',QWebSocketServer.NonSecureMode,self)
   if not self.server.listen(QHostAddress.LocalHost,0):raise RuntimeError(self.server.errorString())
   self.server.newConnection.connect(self.accept)
   directory=Path(__file__).resolve().parents[2]/'web_pair'
   class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kw):super().__init__(*args,directory=str(directory),**kw)
    def log_message(self,*args):pass
   self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start()
  def set(self):
   for socket in list(self.connections):socket.close()
   self.server.close();self.ticket=None;self.http.shutdown();self.http.server_close()
  def issue(self):
   self.ticket={'id':secrets.token_urlsafe(9),'key':os.urandom(32),'expires':time.time()+120,'failures':0}
   data={'port':self.server.serverPort(),'id':self.ticket['id'],'secret':encode(self.ticket['key'])}
   return 'http://127.0.0.1:'+str(self.http.server_port)+'/index.html#'+quote(json.dumps(data))
  def visible(self,did):return any(c.get('proven') and c.get('device')==did and c.get('visible',True) for c in self.connections.values())
  def revoke(self,did):
   for socket,state in list(self.connections.items()):
    if state.get('device')==did:socket.close()
  def accept(self):
   socket=self.server.nextPendingConnection();state={'send':0,'recv':0,'visible':True};self.connections[socket]=state
   timer=QTimer(socket);timer.setSingleShot(True);timer.timeout.connect(socket.close);timer.start(15000)
   socket.disconnected.connect(lambda:self.connections.pop(socket,None))
   socket.disconnected.connect(socket.deleteLater)
   def send(value):
    box=state['tx'].encrypt(b'\0'*4+state['send'].to_bytes(8,'big'),json.dumps(value).encode(),None);state['send']+=1
    socket.sendTextMessage(json.dumps({'t':'x','d':encode(box)}))
   def receive(raw):
    try:
     if len(raw)>1024*1024:raise ValueError('frame too large')
     frame=json.loads(raw)
     if frame.get('t')=='hi':
      if 'tx' in state or frame.get('v')!=1:raise ValueError('invalid handshake')
      kind=frame.get('k');identity=frame.get('id');ticket=self.ticket
      if kind=='pair':
       if not ticket or ticket['id']!=identity or time.time()>ticket['expires']:raise ValueError('配对票据已过期或已使用')
       secret=ticket['key'];state['ticket']=ticket
      elif kind=='resume':
       row=next(b for b in controller.list() if b['id']==bot['id'])
       if not any(u['id']==identity for u in row['users']):raise ValueError('设备已移除')
       secret=decode(controller.shell._vault.get_secret('remote:'+bot['id']+':dev:'+identity) or '');state['device']=identity
      else:raise ValueError('不支持的握手类型')
      pub=decode(frame['e']);nonce=decode(frame['n'])
      if len(pub)!=32 or len(nonce)!=16 or len(secret)!=32:raise ValueError('invalid key')
      private=X25519PrivateKey.generate();public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
      digest=hashlib.sha256(('deva-e2e/1|'+kind+'|'+identity+'|').encode()+pub+nonce+public).digest()
      keys=HKDF(algorithm=hashes.SHA256(),length=64,salt=secret,info=digest).derive(private.exchange(X25519PublicKey.from_public_bytes(pub)))
      state['rx']=ChaCha20Poly1305(keys[:32]);state['tx']=ChaCha20Poly1305(keys[32:])
      socket.sendTextMessage(json.dumps({'t':'hi','e':encode(public),'m':encode(hmac.new(secret,b'desk'+digest,hashlib.sha256).digest())}));return
     if frame.get('t')!='x' or 'rx' not in state:raise ValueError('encrypted frame required')
     body=json.loads(state['rx'].decrypt(b'\0'*4+state['recv'].to_bytes(8,'big'),decode(frame['d']),None));state['recv']+=1
     if not state.get('proven'):
      if state.get('ticket'):
       if self.ticket is not state['ticket']:raise ValueError('配对票据已使用')
       self.ticket=None;did='d_'+secrets.token_hex(8);key=os.urandom(32)
       if not controller.shell._vault.set_secret('remote:'+bot['id']+':dev:'+did,encode(key)).get('ok'):raise ValueError('设备密钥保存失败')
       rows=controller.list();row=next(b for b in rows if b['id']==bot['id']);row['users'].append({'id':did,'chatId':did,'name':str(body.get('name') or '浏览器')[:40],'pairedAt':int(time.time()*1000)});controller.save(rows);state['device']=did
       send({'t':'paired','id':did,'key':encode(key)})
      state['proven']=True;timer.stop()
      from cryptography.hazmat.primitives.asymmetric import ec
      saved=controller.shell._vault.get_secret('remote:'+bot['id']+':vapid')
      if not saved:
       key=ec.generate_private_key(ec.SECP256R1());n=key.private_numbers();saved=json.dumps({'d':encode(n.private_value.to_bytes(32,'big'))})
       if not controller.shell._vault.set_secret('remote:'+bot['id']+':vapid',saved).get('ok'):raise ValueError('VAPID保存失败')
      key=ec.derive_private_key(int.from_bytes(decode(json.loads(saved)['d']),'big'),ec.SECP256R1())
      send({'t':'ready','publicKey':encode(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint))})
     if body.get('t')=='visible':state['visible']=body.get('visible') is True
     if body.get('t')=='push':
      sub=body.get('subscription')
      if sub is not None and (not isinstance(sub,dict) or not str(sub.get('endpoint','')).startswith('https://') or len(sub['endpoint'])>1000 or len(decode(sub.get('keys',{}).get('p256dh','')))!=65 or len(decode(sub.get('keys',{}).get('auth','')))<16):raise ValueError('推送订阅无效')
      rows=controller.list();row=next(b for b in rows if b['id']==bot['id']);user=next(u for u in row['users'] if u['id']==state['device'])
      if sub is None:user.pop('push',None)
      else:user['push']=sub
      controller.save(rows);send({'t':'result','ok':True})
    except Exception as exc:
     if state.get('ticket') and not state.get('proven'):
      state['ticket']['failures']+=1
      if state['ticket']['failures']>=3:self.ticket=None
     controller.status.emit('未验证：'+(str(exc) or type(exc).__name__),'');socket.close()
   socket.textMessageReceived.connect(receive)
 return Server()
