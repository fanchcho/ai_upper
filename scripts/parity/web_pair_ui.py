import sys,json,uuid,hashlib,hmac
from pathlib import Path
from urllib.parse import urlsplit,unquote
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF,QUrl
from PySide6.QtWebSockets import QWebSocket
from cryptography.hazmat.primitives.asymmetric import x25519,ec
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from mvvm.services.channel_push import encode,decode
from PySide6.QtTest import QTest
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');out=Path('out/remaining-three');results=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-web-pair-'+uuid.uuid4().hex),theme,text_stream('unused'))
 def click(n):
  o=find_item(w.contentItem(),n);assert o,n
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint());_pump(app,lambda:False,.2)
 click('railBots');click('webPairTicket');shot(w,out/f'web-entry-{theme}.png')
 api=b.botsService();bot=next(r for r in api.list() if r['platform']=='web');server=api.workers[bot['id']]
 # The UI issued this ticket; derive its current connection data without replacing any receiver.
 ticket={'port':server.server.serverPort(),'id':server.ticket['id'],'secret':encode(server.ticket['key'])}
 sock=QWebSocket();received=[];sock.textMessageReceived.connect(received.append);sock.open(QUrl('ws://127.0.0.1:'+str(ticket['port'])))
 assert _pump(app,lambda:sock.state().value==3,5)
 private=x25519.X25519PrivateKey.generate();pub=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);nonce=b'1'*16
 hi={'t':'hi','v':1,'k':'pair','id':ticket['id'],'e':encode(pub),'n':encode(nonce)};sock.sendTextMessage(json.dumps(hi));assert _pump(app,lambda:bool(received),5)
 reply=json.loads(received.pop(0));desk=decode(reply['e']);secret=decode(ticket['secret']);digest=hashlib.sha256(('deva-e2e/1|pair|'+ticket['id']+'|').encode()+pub+nonce+desk).digest();assert hmac.compare_digest(decode(reply['m']),hmac.new(secret,b'desk'+digest,hashlib.sha256).digest())
 keys=HKDF(algorithm=hashes.SHA256(),length=64,salt=secret,info=digest).derive(private.exchange(x25519.X25519PublicKey.from_public_bytes(desk)));tx=ChaCha20Poly1305(keys[:32]);rx=ChaCha20Poly1305(keys[32:]);seq=0
 def send(body):
  global seq
  frame=json.dumps({'t':'x','d':encode(tx.encrypt(b'\0'*4+seq.to_bytes(8,'big'),json.dumps(body).encode(),None))});seq+=1;sock.sendTextMessage(frame);return frame
 send({'t':'visible','visible':True});assert _pump(app,lambda:len(received)>=2,5)
 paired=json.loads(rx.decrypt(b'\0'*12,decode(json.loads(received[0])['d']),None));assert paired['t']=='paired';did=paired['id'];assert server.visible(did)
 assert server.ticket is None
 assert api.publish_notice(b._active,'not sent','foreground test')['recipients']==0
 ua=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
 subscription={'endpoint':'https://push.invalid/unverified','keys':{'p256dh':encode(ua),'auth':encode(b'a'*16)}}
 send({'t':'push','subscription':subscription});assert _pump(app,lambda:api.list()[0]['users'][0].get('push')==subscription,5)
 frame=send({'t':'visible','visible':False});assert _pump(app,lambda:not server.visible(did),5)
 sock.sendTextMessage(frame);assert _pump(app,lambda:sock.state().value==0,5)
 disk=json.loads((h/'config.json').read_text());assert disk['remote']['bots'][0]['users'][0]['push']==subscription
 shot(w,out/f'web-paired-{theme}.png');results.append({'theme':theme,'device':did,'front_suppression':True,'replay_closed':True,'config':disk,'subscription_status':'synthetic endpoint, no external send attempted'})
 api.close();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
(out/'web-pair.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS real QML ticket click, real WebSocket crypto handshake and proof, persisted device/subscription, foreground suppression, replay closes connection; external subscription/dispatch unverified')
