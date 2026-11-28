import {phoneHello,phoneFinish,b64uDecode,b64uEncode,parseTicket} from './remote-crypto'
window.addEventListener('hashchange',()=>{if(location.hash)location.reload()})
const status=document.querySelector('#status')!; const button=document.querySelector('#subscribe') as HTMLButtonElement
const list=document.querySelector('#sessions') as HTMLSelectElement;const historyBox=document.querySelector('#history')!;const input=document.querySelector('#message') as HTMLTextAreaElement
let ticket:any;const hash=decodeURIComponent(location.hash.slice(1))
if(hash.startsWith('{'))ticket=JSON.parse(hash)
else if(hash){const q=new URLSearchParams(location.hash.slice(1));const p=parseTicket(q.get('p')||'');if(!p)throw Error('配对票据无效');ticket={id:p.id,secret:b64uEncode(p.secret),desk:q.get('d'),via:q.get('via')||'relay',kind:q.get('k')||'pair'}}
else ticket=JSON.parse(localStorage.getItem('connection')||'null')
if(!ticket)throw Error('请从桌面重新生成配对票据')
const connection={port:ticket.port,desk:ticket.desk,via:ticket.via};localStorage.setItem('connection',JSON.stringify(connection));history.replaceState(null,'',location.pathname)
const storageKey='device:'+(ticket.desk||ticket.port);const saved=ticket.secret?null:JSON.parse(localStorage.getItem(storageKey)||'null');const auth=saved||ticket
const {hi,priv}=phoneHello(saved?'resume':ticket.kind||'pair',auth.id);let channel:any;let publicKey:string;let selected=''
const wsUrl=ticket.port?'ws://127.0.0.1:'+ticket.port:(location.protocol==='https:'?'wss://':'ws://')+location.host+(ticket.via==='lan'?'/ws':'/d/'+encodeURIComponent(ticket.desk)+'/ws')
const ws=new WebSocket(wsUrl)
function send(body:any){if(channel&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(channel.seal(body)))}
function sessions(rows:any[]){list.replaceChildren();for(const row of rows){const o=document.createElement('option');o.value=row.id;o.textContent=(row.title||row.id)+(row.busy?' · 处理中':'');list.append(o)}if(rows.some(r=>r.id===selected))list.value=selected;else selected=list.value}
ws.onopen=()=>ws.send(JSON.stringify(hi))
ws.onmessage=event=>{try{const frame=JSON.parse(event.data);if(frame.t==='hi'){channel=phoneFinish(hi,priv,b64uDecode(auth.key||auth.secret)!,frame);if(!channel)throw Error('设备认证失败');send({t:'hello',v:1,name:navigator.platform+' 浏览器',kind:'browser'});send({t:'visible',visible:!document.hidden});return}
 if(frame.t==='offline')throw Error('电脑不在线')
 const body:any=channel.open(frame);if(!body)throw Error('密文验证失败')
 if(body.t==='paired'){localStorage.setItem(storageKey,JSON.stringify({id:body.device||body.id,key:body.key}));status.textContent='设备配对已保存'}
 if(body.t==='ready'){publicKey=body.publicKey;button.disabled=false;status.textContent='安全连接已建立；外部推送未验证'}
 if(body.t==='ok'){sessions(body.sessions);if(selected)send({t:'history',sid:selected})}
 if(body.t==='sessions')sessions(body.list)
 if(body.t==='history'&&body.sid===selected){if(body.messages.at(-1)?.role==='assistant')status.textContent='回复已写回主对话';historyBox.replaceChildren();for(const m of body.messages){const p=document.createElement('p');p.textContent=(m.role==='user'?'我：':'助手：')+(m.text||m.parts?.filter((p:any)=>p.k==='text').map((p:any)=>p.text).join('')||'');historyBox.append(p)}}
 if(body.t==='created'){if(body.error)status.textContent=body.error;else{selected=body.sid;send({t:'history',sid:selected})}}
 if(body.t==='sent')status.textContent=body.ok?'消息已送入主对话，等待回复':body.message
 if(body.t==='err')status.textContent=body.message
 if(body.t==='result')status.textContent='订阅已保存；外部送达未验证'
}catch(e){status.textContent=String(e);ws.close()}}
ws.onclose=()=>{status.textContent+=' · 连接已关闭';button.disabled=true}
ws.onerror=()=>status.textContent='连接失败；未验证'
list.onchange=()=>{selected=list.value;send({t:'history',sid:selected})}
document.querySelector('#new')!.addEventListener('click',()=>{const sid='sess_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,8);send({t:'new',rid:sid,sid})})
document.querySelector('#send')!.addEventListener('click',()=>{if(selected&&input.value.trim()){send({t:'send',sid:selected,text:input.value,cid:Date.now().toString()});input.value=''}})
document.querySelector('#refresh')!.addEventListener('click',()=>{send({t:'refresh'});if(selected)send({t:'history',sid:selected})})
document.addEventListener('visibilitychange',()=>send({t:'visible',visible:!document.hidden}))
button.onclick=async()=>{try{status.textContent='正在申请浏览器推送订阅…';const registration=await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;const subscription=await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64uDecode(publicKey)!});send({t:'push',subscription:subscription.toJSON()})}catch(e){status.textContent='未验证：'+String(e)}}
