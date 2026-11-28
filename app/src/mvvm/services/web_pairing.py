"""Local browser pairing: original remote-crypto.ts transcript and ordered frames."""
import json,os,time,hashlib,hmac,secrets,threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import quote,urlencode
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
   super().__init__(controller);self.ticket=None;self.tickets={};self.connections={};self.relay=None;self.lan=None;self.links={'lan':'off','relay':'off'};self.server=QWebSocketServer('ai_upper pairing',QWebSocketServer.NonSecureMode,self)
   if not self.server.listen(QHostAddress.LocalHost,0):raise RuntimeError(self.server.errorString())
   self.server.newConnection.connect(self.accept)
   directory=Path(__file__).resolve().parents[2]/'web_pair'
   class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kw):super().__init__(*args,directory=str(directory),**kw)
    def log_message(self,*args):pass
   self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start()
   self.holds={'lan':{'qr':0,'link':0},'relay':{'qr':0,'link':0}};self.sweep=QTimer(self);self.sweep.setInterval(1000);self.sweep.timeout.connect(self.reconcile);self.sweep.start()
  def set(self):
   self.sweep.stop()
   if self.relay:self.relay.set()
   if self.lan:self.lan.set()
   for socket in list(self.connections):socket.close()
   self.server.close();self.ticket=None;self.tickets.clear();self.http.shutdown();self.http.server_close()
  def reconcile(self):
   now=time.time();self.tickets={k:t for k,t in self.tickets.items() if t['expires']>now}
   if self.ticket and self.ticket['expires']<=now:self.ticket=None
   row=next((b for b in controller.list() if b['id']==bot['id']),None)
   if not row:return
   from mvvm.services.phone_cards import prompts
   from mvvm.services.phone_sessions import session_list,history
   allowed={r['id'] for r in session_list(controller.shell,row)}
   from mvvm.services.phone_tasks import task_list
   tasks=task_list(controller.shell);task_signature=json.dumps(tasks,sort_keys=True)
   for state in list(self.connections.values()):
    if state.get('phone') and state.get('proven') and task_signature!=state.get('tasks'):
     state['tasks']=task_signature;state['send_frame']({'t':'tasks','list':tasks})
    sid=state.get('watch')
    if state.get('phone') and state.get('proven') and sid in allowed:
     pending=prompts(controller.shell,sid);signature=json.dumps(pending,sort_keys=True)
     if signature!=state.get('prompts'):
      state['prompts']=signature;state['send_frame'](history(controller.shell,sid))
   changed=False
   for via in ('lan','relay'):
    if max(self.holds[via].values())>now or any(u.get('via','relay')==via for u in row['users']):continue
    link=getattr(self,via)
    if link:
     link.set();setattr(self,via,None);self.links[via]='off';changed=True
   if changed:controller.changed.emit()
  def release_qr(self):
   for hold in self.holds.values():hold['qr']=min(hold['qr'],time.time()+5)
  def phone_issue(self,via,kind='pair'):
   from mvvm.services.qr_image import qr_image
   row=next(b for b in controller.list() if b['id']==bot['id']);settings=row['settings'];desk=settings['deskId']
   if via=='lan':
    if not self.lan:
     from mvvm.services.phone_lan import start
     self.lan=start(self,self.server,int(settings.get('port',17800)));self.links['lan']='on'
    addresses=[a.toString() for a in QtNetwork.QNetworkInterface.allAddresses() if a.protocol()==QtNetwork.QAbstractSocket.IPv4Protocol and not a.isLoopback()]
    if not addresses:raise ValueError('没有找到可用的局域网地址，请检查网络连接。')
    base='http://'+addresses[0]+':'+str(self.lan.port())+'/'
   else:
    base=settings.get('relayUrl') or 'https://m.deva.chat'
    if not self.relay:
     from mvvm.services.phone_relay import start
     saved=controller.shell._vault.get_secret('remote:'+bot['id']+':deskKey')
     if not saved:
      saved=secrets.token_urlsafe(32)
      if not controller.shell._vault.set_secret('remote:'+bot['id']+':deskKey',saved).get('ok'):raise ValueError('系统密钥存储不可用')
     def status(value):self.links['relay']=value;controller.changed.emit()
     self.relay=start(self,base,desk,saved,self.attach,status)
   now=time.time();self.tickets={k:t for k,t in self.tickets.items() if t['expires']>now}
   if kind=='pair':
    for old in self.tickets.values():
     if not old.get('sticky'):old['expires']=min(old['expires'],now+15)
   self.ticket={'id':secrets.token_urlsafe(9),'key':os.urandom(32),'expires':now+(600 if kind=='link' else 120),'failures':0,'kind':'pair','sticky':kind=='link'}
   self.tickets[self.ticket['id']]=self.ticket
   if kind=='pair':
    for hold in self.holds.values():hold['qr']=0
    self.holds[via]['qr']=self.ticket['expires']+30
   else:self.holds[via]['link']=max(self.holds[via]['link'],self.ticket['expires']+30)
   url=base.rstrip('/')+'/#'+urlencode({'d':desk,'p':self.ticket['id']+'.'+encode(self.ticket['key']),'n':__import__('socket').gethostname()[:40],'via':via})
   controller.changed.emit()
   return {'url':url,'qr':qr_image(url),'expiresAt':int(self.ticket['expires']*1000),'via':via}
  def devices(self):
   row=next(b for b in controller.list() if b['id']==bot['id'])
   return [dict(u,online=any(s.get('proven') and s.get('device')==u['id'] for s in self.connections.values())) for u in row['users']]
  def publish(self,sid):
   from mvvm.services.phone_sessions import history,session_list
   row=next(b for b in controller.list() if b['id']==bot['id']);rows=session_list(controller.shell,row)
   for state in list(self.connections.values()):
    if state.get('proven') and state.get('phone'):
     state['send_frame']({'t':'sessions','list':rows})
     if state.get('watch')==sid and any(r['id']==sid for r in rows):state['send_frame'](history(controller.shell,sid))
  def issue(self):
   self.ticket={'id':secrets.token_urlsafe(9),'key':os.urandom(32),'expires':time.time()+120,'failures':0}
   data={'port':self.server.serverPort(),'id':self.ticket['id'],'secret':encode(self.ticket['key'])}
   return 'http://127.0.0.1:'+str(self.http.server_port)+'/index.html#'+quote(json.dumps(data))
  def visible(self,did):return any(c.get('proven') and c.get('device')==did and c.get('visible',True) for c in self.connections.values())
  def revoke(self,did):
   for socket,state in list(self.connections.items()):
    if state.get('device')==did:socket.close()
  def accept(self):
   self.attach(self.server.nextPendingConnection(),'lan')
  def attach(self,socket,via):
   state={'send':0,'recv':0,'visible':True,'via':via};self.connections[socket]=state
   timer=QTimer(socket);timer.setSingleShot(True);timer.timeout.connect(socket.close);timer.start(15000)
   def disconnected():
    self.connections.pop(socket,None)
    if state.get('device'):
     rows=controller.list();row=next((b for b in rows if b['id']==bot['id']),None)
     if row:
      for u in row['users']:
       if u['id']==state['device']:u['lastSeen']=int(time.time()*1000)
      controller.save(rows)
    controller.changed.emit()
   socket.disconnected.connect(disconnected)
   socket.disconnected.connect(socket.deleteLater)
   def send(value):
    box=state['tx'].encrypt(b'\0'*4+state['send'].to_bytes(8,'big'),json.dumps(value).encode(),None);state['send']+=1
    socket.sendTextMessage(json.dumps({'t':'x','d':encode(box)}))
   state['send_frame']=send
   def receive(raw):
    try:
     if len(raw)>1024*1024:raise ValueError('frame too large')
     frame=json.loads(raw)
     if frame.get('t')=='hi':
      if 'tx' in state or frame.get('v')!=1:raise ValueError('invalid handshake')
      kind=frame.get('k');identity=frame.get('id');ticket=self.tickets.get(identity) or self.ticket
      if kind in ('pair','link'):
       if not ticket or ticket.get('kind','pair')!=kind or ticket['id']!=identity or time.time()>ticket['expires']:raise ValueError('配对票据已过期或已使用')
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
      if body.get('t')=='hello' and body.get('v')!=1:raise ValueError('手机网页与电脑版本不匹配')
      state['phone']=body.get('t')=='hello'
      if state.get('ticket'):
       ticket=state['ticket']
       if (self.ticket is not ticket and self.tickets.get(ticket['id']) is not ticket) or time.time()>ticket['expires']:raise ValueError('配对票据已使用或过期')
       self.tickets.pop(ticket['id'],None)
       if self.ticket is ticket:self.ticket=None
       did='d_'+secrets.token_hex(8);key=os.urandom(32)
       if not controller.shell._vault.set_secret('remote:'+bot['id']+':dev:'+did,encode(key)).get('ok'):raise ValueError('设备密钥保存失败')
       rows=controller.list();row=next(b for b in rows if b['id']==bot['id']);row['users'].append({'id':did,'chatId':did,'name':str(body.get('name') or '浏览器')[:40],'pairedAt':int(time.time()*1000),'lastSeen':int(time.time()*1000),'via':via,'kind':body.get('kind','browser')});controller.save(rows);state['device']=did
       send({'t':'paired','id':did,'device':did,'key':encode(key)})
      state['proven']=True;timer.stop()
      rows=controller.list();row=next(b for b in rows if b['id']==bot['id'])
      for user in row['users']:
       if user['id']==state['device']:user.update(lastSeen=int(time.time()*1000),via=via,kind=body.get('kind','browser'))
      controller.save(rows)
      from cryptography.hazmat.primitives.asymmetric import ec
      saved=controller.shell._vault.get_secret('remote:'+bot['id']+':vapid')
      if not saved:
       key=ec.generate_private_key(ec.SECP256R1());n=key.private_numbers();saved=json.dumps({'d':encode(n.private_value.to_bytes(32,'big'))})
       if not controller.shell._vault.set_secret('remote:'+bot['id']+':vapid',saved).get('ok'):raise ValueError('VAPID保存失败')
      key=ec.derive_private_key(int.from_bytes(decode(json.loads(saved)['d']),'big'),ec.SECP256R1())
      send({'t':'ready','publicKey':encode(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint))})
      if state['phone']:
       from mvvm.services.phone_sessions import session_list
       row=next(b for b in controller.list() if b['id']==bot['id'])
       send({'t':'ok','v':1,'desk':{'id':row['settings'].get('deskId'),'computer':__import__('socket').gethostname()},'device':{'id':state['device']},'sessions':session_list(controller.shell,row),'prompts':[],'vapid':encode(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint))})
      controller.changed.emit()
     if state.get('phone'):
      from mvvm.services.phone_sessions import handle
      handle(controller,bot['id'],state,body)
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
      if state['ticket']['failures']>=3:
       self.tickets.pop(state['ticket']['id'],None)
       if self.ticket is state['ticket']:self.ticket=None
     controller.status.emit('未验证：'+(str(exc) or type(exc).__name__),'');socket.close()
   socket.textMessageReceived.connect(receive)
 return Server()
