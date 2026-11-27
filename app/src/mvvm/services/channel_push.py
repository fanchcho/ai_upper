"""Outbound Feishu cards and encrypted RFC8291 Web Push (deva remote adapters)."""
import asyncio,base64,json,os,time,struct,re
from urllib.parse import urlsplit
from mvvm.services.provider_setup import build_transport


def encode(value):return base64.urlsafe_b64encode(value).rstrip(b'=').decode()
def decode(value):return base64.urlsafe_b64decode(value+'='*((-len(value))%4))


def web_request(vault,identity,subscription,message):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    endpoint=subscription['endpoint'];url=urlsplit(endpoint)
    if url.scheme!='https':raise ValueError('Web Push endpoint 必须为 HTTPS')
    saved=vault.get_secret('remote:'+identity+':vapid')
    if not saved:
        private=ec.generate_private_key(ec.SECP256R1());numbers=private.private_numbers();public=numbers.public_numbers
        saved=json.dumps({'kty':'EC','crv':'P-256','d':encode(numbers.private_value.to_bytes(32,'big')),'x':encode(public.x.to_bytes(32,'big')),'y':encode(public.y.to_bytes(32,'big'))})
        if not vault.set_secret('remote:'+identity+':vapid',saved).get('ok'):raise ValueError('Web Push VAPID 密钥无法保存')
    jwk=json.loads(saved);private=ec.derive_private_key(int.from_bytes(decode(jwk['d']),'big'),ec.SECP256R1())
    public=private.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    header=encode(b'{"typ":"JWT","alg":"ES256"}');payload=encode(json.dumps({'aud':url.scheme+'://'+url.netloc,'exp':int(time.time())+43200,'sub':'https://github.com/sqfcyily/deva'},separators=(',',':')).encode())
    signing=(header+'.'+payload).encode();r,s=decode_dss_signature(private.sign(signing,ec.ECDSA(hashes.SHA256())))
    auth='vapid t='+signing.decode()+'.'+encode(r.to_bytes(32,'big')+s.to_bytes(32,'big'))+', k='+encode(public)
    ua=decode(subscription['keys']['p256dh']);secret=decode(subscription['keys']['auth'])
    if len(ua)!=65 or len(secret)<16:raise ValueError('Web Push 订阅公钥或认证密钥无效')
    eph=ec.generate_private_key(ec.SECP256R1());ep=eph.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    shared=eph.exchange(ec.ECDH(),ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),ua))
    def hkdf(key,salt,info,n):return HKDF(algorithm=hashes.SHA256(),length=n,salt=salt,info=info).derive(key)
    ikm=hkdf(shared,secret,b'WebPush: info\0'+ua+ep,32);salt=os.urandom(16)
    key=hkdf(ikm,salt,b'Content-Encoding: aes128gcm\0',16);nonce=hkdf(ikm,salt,b'Content-Encoding: nonce\0',12)
    body=salt+struct.pack('!IB',4096,len(ep))+ep+AESGCM(key).encrypt(nonce,json.dumps(message,ensure_ascii=False).encode()+b'\x02',None)
    headers={'authorization':auth,'content-encoding':'aes128gcm','content-type':'application/octet-stream','ttl':'86400','urgency':'high'}
    if message.get('tag'):headers['topic']=re.sub('[^A-Za-z0-9_-]','',message['tag'])[:32]
    return endpoint,headers,body


def push(vault,bot,user,title,body,sid):
    async def request():
        transport=build_transport()
        try:
            if bot['platform']=='feishu':
                settings=bot.get('settings',{});app_id=settings.get('appId');secret=vault.get_secret('remote:'+bot['id']+':appSecret')
                if not app_id or not secret:raise ValueError('飞书 App ID 或 App Secret 未配置')
                base='https://open.larksuite.com' if settings.get('domain')=='lark' else 'https://open.feishu.cn'
                response=await transport.post(base+'/open-apis/auth/v3/tenant_access_token/internal',headers={'content-type':'application/json'},body=json.dumps({'app_id':app_id,'app_secret':secret}).encode())
                data=json.loads(await response.text())
                if data.get('code')!=0:raise ValueError('飞书认证失败：'+str(data.get('code'))+' '+str(data.get('msg')))
                card={'config':{'wide_screen_mode':True},'header':{'title':{'tag':'plain_text','content':title}},'elements':[{'tag':'markdown','content':body}]}
                payload={'receive_id':user['chatId'],'msg_type':'interactive','content':json.dumps(card,ensure_ascii=False)}
                response=await transport.post(base+'/open-apis/im/v1/messages?receive_id_type=chat_id',headers={'authorization':'Bearer '+data['tenant_access_token'],'content-type':'application/json'},body=json.dumps(payload).encode())
                data=json.loads(await response.text())
                if data.get('code')!=0:raise ValueError('飞书发送失败：'+str(data.get('code'))+' '+str(data.get('msg')))
            elif bot['platform']=='web':
                if not user.get('push'):raise ValueError('Web Push 浏览器订阅不存在；未完成配对')
                url,headers,data=web_request(vault,bot['id'],user['push'],{'title':title,'body':body,'sid':sid,'tag':sid,'deskId':bot.get('settings',{}).get('deskId','')})
                response=await transport.post(url,headers=headers,body=data)
                if response.status in (404,410):return {'status':'gone','reason':'订阅已失效'}
                if not 200<=response.status<300:raise ValueError('Web Push HTTP '+str(response.status))
            else:raise ValueError('未知渠道')
            return {'status':'sent'}
        finally:await transport.aclose()
    async def bounded():return await asyncio.wait_for(request(),15)
    try:return asyncio.run(bounded())
    except Exception as exc:return {'status':'unverified','reason':str(exc) or type(exc).__name__}
