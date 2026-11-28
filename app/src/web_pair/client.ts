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
const {hi,priv}=phoneHello(saved?'resume':ticket.kind||'pair',auth.id);let channel:any;let publicKey:string;let selected='';const uploads:string[]=[];const uploadWait=new Map<string,(body:any)=>void>()
const wsUrl=ticket.port?'ws://127.0.0.1:'+ticket.port:(location.protocol==='https:'?'wss://':'ws://')+location.host+(ticket.via==='lan'?'/ws':'/d/'+encodeURIComponent(ticket.desk)+'/ws')
const downloads=new Map<string,any>();const ws=new WebSocket(wsUrl)
function send(body:any){if(channel&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(channel.seal(body)))}
function sessions(rows:any[]){list.replaceChildren();for(const row of rows){const o=document.createElement('option');o.value=row.id;o.textContent=(row.title||row.id)+(row.busy?' · 处理中':'');list.append(o)}if(rows.some(r=>r.id===selected))list.value=selected;else selected=list.value}
ws.onopen=()=>ws.send(JSON.stringify(hi))
ws.onmessage=event=>{try{const frame=JSON.parse(event.data);if(frame.t==='hi'){channel=phoneFinish(hi,priv,b64uDecode(auth.key||auth.secret)!,frame);if(!channel)throw Error('设备认证失败');send({t:'hello',v:1,name:navigator.platform+' 浏览器',kind:'browser'});send({t:'visible',visible:!document.hidden});return}
 if(frame.t==='offline')throw Error('电脑不在线')
 const body:any=channel.open(frame);if(!body)throw Error('密文验证失败')
 if(body.t==='tasks')renderTasks(body.list)
 if(body.t==='file'){if(!body.ok){status.textContent=body.message}else if(body.text!==undefined){showFile(body,new Blob([body.text],{type:'text/plain'}));}else downloads.set(body.rid,{...body,parts:[]})}
 if(body.t==='file_chunk'){const file=downloads.get(body.rid);if(!file||body.seq!==file.parts.length)throw Error('文件块顺序错误');file.parts.push(b64uDecode(body.data));if(file.parts.length===file.chunks){showFile(file,new Blob(file.parts,{type:file.mime}));downloads.delete(body.rid)}}
 if(body.t==='upload'){uploadWait.get(body.uid)?.(body);status.textContent=body.state==='done'?'附件已上传，等待发送':body.message||'正在上传'}
 if(body.t==='paired'){localStorage.setItem(storageKey,JSON.stringify({id:body.device||body.id,key:body.key}));status.textContent='设备配对已保存'}
 if(body.t==='ready'){publicKey=body.publicKey;button.disabled=false;status.textContent='安全连接已建立；外部推送未验证'}
 if(body.t==='ok'){sessions(body.sessions);if(selected)send({t:'history',sid:selected})}
 if(body.t==='sessions')sessions(body.list)
 if(body.t==='history'&&body.sid===selected){renderPrompts(body.prompts||[]);if(body.messages.at(-1)?.role==='assistant')status.textContent='回复已写回主对话';historyBox.replaceChildren();for(const m of body.messages){const p=document.createElement('p');p.textContent=(m.role==='user'?'我：':'助手：')+(m.text||m.parts?.filter((p:any)=>p.k==='text').map((p:any)=>p.text).join('')||'');historyBox.append(p)}for(const f of body.files||[]){const b=document.createElement('button');b.className='delivered';b.textContent='查看 / 下载 '+f.name;b.onclick=()=>send({t:'file',sid:selected,tool:f.tool,index:f.index,rid:crypto.randomUUID()});historyBox.append(b)}}
 if(body.t==='created'){if(body.error)status.textContent=body.error;else{selected=body.sid;send({t:'history',sid:selected})}}
 if(body.t==='sent')status.textContent=body.ok?'消息已送入主对话，等待回复':body.message
 if(body.t==='err')status.textContent=body.message
 if(body.t==='result')status.textContent=body.message||'订阅已保存；外部送达未验证'
}catch(e){status.textContent=String(e);ws.close()}}
ws.onclose=()=>{status.textContent+=' · 连接已关闭';button.disabled=true}
ws.onerror=()=>status.textContent='连接失败；未验证'
list.onchange=()=>{selected=list.value;send({t:'history',sid:selected})}
document.querySelector('#new')!.addEventListener('click',()=>{const sid='sess_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,8);send({t:'new',rid:sid,sid})})
document.querySelector('#send')!.addEventListener('click',()=>{if(selected&&(input.value.trim()||uploads.length)){send({t:'send',sid:selected,text:input.value,files:uploads.splice(0),cid:Date.now().toString()});input.value=''}})
document.querySelector('#refresh')!.addEventListener('click',()=>{send({t:'refresh'});if(selected)send({t:'history',sid:selected})})
document.addEventListener('visibilitychange',()=>send({t:'visible',visible:!document.hidden}))
button.onclick=async()=>{try{status.textContent='正在申请浏览器推送订阅…';const registration=await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;const subscription=await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64uDecode(publicKey)!});send({t:'push',subscription:subscription.toJSON()})}catch(e){status.textContent='未验证：'+String(e)}}

const fileInput=document.querySelector('#attachment') as HTMLInputElement
fileInput.onchange=async()=>{for(const file of Array.from(fileInput.files||[])){const uid='up_'+Math.random().toString(36).slice(2);try{await new Promise<void>((resolve,reject)=>{uploadWait.set(uid,b=>b.state==='ready'?resolve():reject(Error(b.message)));send({t:'up_begin',uid,name:file.name,size:file.size,mime:file.type})});const data=new Uint8Array(await file.arrayBuffer());for(let i=0;i<data.length;i+=192*1024)send({t:'up_chunk',uid,seq:i/(192*1024),data:b64uEncode(data.slice(i,i+192*1024))});await new Promise<void>((resolve,reject)=>{uploadWait.set(uid,b=>b.state==='done'?resolve():reject(Error(b.message)));send({t:'up_end',uid})});uploads.push(uid)}catch(e){status.textContent=String(e)}finally{uploadWait.delete(uid)}}}

function showFile(file:any,blob:Blob){const box=document.querySelector('#file')!;box.replaceChildren();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=file.name;a.textContent='保存 '+file.name;a.id='download';box.append(a);const pre=document.createElement('pre');pre.textContent=file.text||('已收到 '+blob.size+' 字节');box.append(pre);status.textContent=file.truncated?'预览已截断':'文件已接收'}

function renderPrompts(rows:any[]){const box=document.querySelector('#cards')!;box.replaceChildren();for(const row of rows){const card=document.createElement('fieldset');card.className='card';card.dataset.kind=row.kind;const text=document.createElement('pre');text.textContent=row.question;card.append(text);const feedback=document.createElement('textarea');feedback.placeholder='补充意见 / 回答';card.append(feedback);const choices=row.kind==='plan'?[['approve','批准计划'],['keep','继续完善'],['ignore','忽略计划']]:row.kind==='mount'?[['skipped','暂不挂载']]:row.kind==='approval'?[['approved','允许执行'],['denied','拒绝执行']]:[['answered','提交回答']];for(const [d,label] of choices){const b=document.createElement('button');b.textContent=label;b.dataset.decision=d;b.onclick=()=>send({t:'action',rid:crypto.randomUUID(),value:{k:row.kind==='question'?'ask':row.kind,key:row.key,d},form:{text:feedback.value}});card.append(b)}box.append(card)}}

function renderTasks(rows:any[]){const box=document.querySelector('#tasks')!;const opened=new Set(Array.from(box.querySelectorAll('details[open]')).map(e=>(e as HTMLElement).dataset.id));box.replaceChildren();for(const row of rows){const item=document.createElement('details');item.dataset.id=row.id;item.open=opened.has(row.id);const summary=document.createElement('summary');summary.textContent=row.title+' · '+row.status;item.append(summary);const pre=document.createElement('pre');pre.textContent='计划：'+row.schedule+'\n角色：'+(row.personaId||'默认')+'\n模型：'+(row.model||'跟随默认')+'\n下次运行：'+(row.nextRunAt?new Date(row.nextRunAt).toLocaleString():'无')+'\n上次运行：'+(row.lastRun?JSON.stringify(row.lastRun):'无')+'\n主对话：'+(row.owner?.title||'无');item.append(pre);for(const [action,label] of [['pause','暂停'],['resume','恢复'],['run','立即运行'],['delete','删除']]){const b=document.createElement('button');b.textContent=label;b.dataset.action=action;b.disabled=action==='resume'&&row.status==='completed';b.onclick=()=>send({t:'task',rid:crypto.randomUUID(),id:row.id,action});item.append(b)}if(row.sessionId){const b=document.createElement('button');b.textContent='查看任务对话';b.dataset.action='open';b.onclick=()=>{selected=row.sessionId;list.value=selected;send({t:'history',sid:selected})};item.append(b)}box.append(item)}}
