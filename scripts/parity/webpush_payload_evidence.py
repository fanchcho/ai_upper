import sys,json,struct,tempfile
from pathlib import Path
sys.path.insert(0,'app/src')
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from mvvm.services.channel_push import web_request,encode
from mvvm.services.secrets_vault import SecretsVault
home=Path(tempfile.mkdtemp(prefix='ai-upper-push-',dir='/tmp'));vault=SecretsVault(home)
vapid=ec.generate_private_key(ec.SECP256R1());numbers=vapid.private_numbers()
assert vault.set_secret('remote:evidence:vapid',json.dumps({'d':encode(numbers.private_value.to_bytes(32,'big'))}))['ok']
ua=ec.generate_private_key(ec.SECP256R1());public=ua.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint);auth=b'a'*16
message={'title':'test','body':'encrypted payload'}
url,headers,body=web_request(vault,'evidence',{'endpoint':'https://push.invalid/sub','keys':{'p256dh':encode(public),'auth':encode(auth)}},message)
salt=body[:16];size,keylen=struct.unpack('!IB',body[16:21]);ep=body[21:21+keylen];shared=ua.exchange(ec.ECDH(),ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),ep))
def kdf(key,salt,info,n):return HKDF(algorithm=hashes.SHA256(),length=n,salt=salt,info=info).derive(key)
ikm=kdf(shared,auth,b'WebPush: info\0'+public+ep,32);key=kdf(ikm,salt,b'Content-Encoding: aes128gcm\0',16);nonce=kdf(ikm,salt,b'Content-Encoding: nonce\0',12)
plain=AESGCM(key).decrypt(nonce,body[21+keylen:],None)
assert plain[-1:]==b'\x02' and json.loads(plain[:-1])==message
print('PASS native cryptography RFC8291 payload roundtrip; key persisted/read via vault; no external HTTP attempted')
