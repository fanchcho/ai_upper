"""Feishu long connection protocol, matching the original SDK Frame wire schema."""
import asyncio,json,threading,time
from urllib.parse import urlsplit,parse_qs
from mvvm.services.provider_setup import build_transport


def varint(n):
 out=bytearray()
 while n>127:out.append((n&127)|128);n>>=7
 out.append(n);return bytes(out)

def encode(rows):
 return b''.join(varint((k<<3)|(2 if isinstance(v,bytes) else 0))+(varint(len(v))+v if isinstance(v,bytes) else varint(v)) for k,v in rows)

def decode(raw):
 raw=bytes(raw);i=0;rows=[]
 def number():
  nonlocal i
  n=0
  for shift in range(0,70,7):
   b=raw[i];i+=1;n|=(b&127)<<shift
   if not b&128:return n
  raise ValueError('invalid protobuf varint')
 while i<len(raw):
  tag=number();wire=tag&7
  if wire==0:value=number()
  elif wire==2:
   size=number();value=raw[i:i+size];i+=size
   if i>len(raw):raise ValueError('truncated protobuf frame')
  else:raise ValueError('unsupported protobuf wire type '+str(wire))
  rows.append((tag>>3,value))
 return rows

def connection(parent,bot,vault,on_state,on_event):
 from utils.qt_compat import QtCore,QtWebSockets,Signal
 QObject,QTimer,QUrl=QtCore.QObject,QtCore.QTimer,QtCore.QUrl
 QWebSocket=QtWebSockets.QWebSocket
 class Link(QObject):
  discovered=Signal(object)
  def __init__(self):
   super().__init__(parent);self.stopped=False;self.fragments={};self.seen=[];self.socket=QWebSocket(parent=self)
   self.timer=QTimer(self);self.timer.timeout.connect(self.ping)
   self.retry=QTimer(self);self.retry.setSingleShot(True);self.retry.timeout.connect(self.discover)
   self.discovered.connect(self.open)
   self.socket.connected.connect(lambda:on_state('connected'))
   self.socket.disconnected.connect(self.disconnected)
   self.socket.errorOccurred.connect(lambda e:on_state('error: '+self.socket.errorString()))
   self.socket.binaryMessageReceived.connect(self.message);self.service=0
   self.discover()
  def set(self):
   self.stopped=True;self.timer.stop();self.retry.stop();self.socket.close()
  def discover(self):
   if self.stopped:return
   settings=bot.get('settings',{});secret=vault.get_secret('remote:'+bot['id']+':appSecret')
   if not settings.get('appId') or not secret:on_state('未验证：飞书 App ID 或 App Secret 未配置');return
   on_state('connecting')
   def work():
    async def request():
     transport=build_transport()
     try:
      base='https://open.larksuite.com' if settings.get('domain')=='lark' else 'https://open.feishu.cn'
      response=await transport.post(base+'/callback/ws/endpoint',headers={'Content-Type':'application/json','locale':'zh'},body=json.dumps({'AppID':settings['appId'],'AppSecret':secret}).encode())
      data=json.loads(await response.text())
      if data.get('code')!=0:raise ValueError('pullConnectConfig failed: code='+str(data.get('code'))+', msg='+str(data.get('msg')))
      return data['data']
     finally:await transport.aclose()
    async def bounded():return await asyncio.wait_for(request(),15)
    try:self.discovered.emit(asyncio.run(bounded()))
    except Exception as e:self.discovered.emit({'error':str(e).replace(secret,'[redacted]') or type(e).__name__})
   threading.Thread(target=work,daemon=True).start()
  def open(self,data):
   if self.stopped:return
   if 'error' in data:on_state('未验证：'+data['error']);return
   url=data['URL']
   if urlsplit(url).scheme!='wss':on_state('error: 飞书长连接地址必须为 wss');return
   self.service=int(parse_qs(urlsplit(url).query)['service_id'][0]);self.timer.start(max(1000,int(data['ClientConfig']['PingInterval']*1000)));self.socket.open(QUrl(url))
  def disconnected(self):
   self.timer.stop()
   if not self.stopped:on_state('reconnecting');self.retry.start(10000)
  def ping(self):
   self.socket.sendBinaryMessage(encode([(1,0),(2,0),(3,self.service),(4,0),(5,encode([(1,b'type'),(2,b'ping')]))]))
  def message(self,raw):
   try:
    rows=decode(raw);fields=dict(rows);headers={dict(decode(v))[1].decode():dict(decode(v))[2].decode() for k,v in rows if k==5}
    if fields.get(4)!=1 or headers.get('type')!='event':return
    identity=headers['message_id'];total=int(headers.get('sum','1'));seq=int(headers.get('seq','0'))
    if not 0<=seq<total<=1024:raise ValueError('invalid fragment sequence')
    now=time.monotonic();self.fragments={k:v for k,v in self.fragments.items() if now-v[0]<30}
    _,parts=self.fragments.setdefault(identity,(now,{}));parts[seq]=fields.get(8,b'')
    if len(parts)!=total:return
    payload=json.loads(b''.join(parts[n] for n in range(total)));self.fragments.pop(identity,None)
    if identity not in self.seen:on_event(payload);self.seen=(self.seen+[identity])[-1000:]
    reply=[(k,v) for k,v in rows if k!=8]+[(8,b'{"code":200}')];self.socket.sendBinaryMessage(encode(reply))
   except Exception as e:on_state('error: '+str(e))
 return Link()
