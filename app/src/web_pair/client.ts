import {phoneHello,phoneFinish,b64uDecode} from './remote-crypto'
const status=document.querySelector('#status')!; const button=document.querySelector('#subscribe') as HTMLButtonElement
const ticket=JSON.parse(decodeURIComponent(location.hash.slice(1)));history.replaceState(null,'',location.pathname)
const saved=JSON.parse(localStorage.getItem('device:'+ticket.port)||'null');const auth=saved||ticket
const {hi,priv}=phoneHello(saved?'resume':'pair',auth.id);let channel:any;let publicKey:string
const ws=new WebSocket('ws://127.0.0.1:'+ticket.port)
function send(body:any){if(channel)ws.send(JSON.stringify(channel.seal(body)))}
ws.onopen=()=>ws.send(JSON.stringify(hi))
ws.onmessage=event=>{try{const frame=JSON.parse(event.data);if(frame.t==='hi'){channel=phoneFinish(hi,priv,b64uDecode(auth.key||auth.secret)!,frame);if(!channel)throw Error('设备认证失败');send({t:'visible',visible:!document.hidden});return}
 const body=channel.open(frame);if(!body)throw Error('密文验证失败');if(body.t==='paired'){localStorage.setItem('device:'+ticket.port,JSON.stringify(body));status.textContent='设备配对已保存；推送尚未订阅'}
 if(body.t==='ready'){publicKey=body.publicKey;button.disabled=false;status.textContent='安全连接已建立；外部推送未验证'}
 if(body.t==='result')status.textContent='订阅已保存；外部送达未验证'
}catch(e){status.textContent=String(e);ws.close()}}
ws.onclose=()=>{status.textContent+=' · 连接已关闭';button.disabled=true}
ws.onerror=()=>status.textContent='连接失败；未验证'
document.addEventListener('visibilitychange',()=>send({t:'visible',visible:!document.hidden}))
button.onclick=async()=>{try{const registration=await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;const subscription=await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64uDecode(publicKey)!});send({t:'push',subscription:subscription.toJSON()})}catch(e){status.textContent='未验证：'+String(e)}}
