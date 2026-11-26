import fs from 'node:fs';
const pages=await (await fetch('http://127.0.0.1:9344/json/list')).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);let seq=0;const pending=new Map();ws.onmessage=e=>{let m=JSON.parse(e.data);if(m.id){pending.get(m.id)?.(m);pending.delete(m.id)}};
async function call(method,params={}){return new Promise(r=>{let id=++seq;pending.set(id,r);ws.send(JSON.stringify({id,method,params}))})}
const expr=process.argv[2]||'JSON.stringify({keys:Object.keys(window.deva),buttons:[...document.querySelectorAll("button")].map(x=>({text:x.textContent,title:x.title}))})';
console.log(JSON.stringify(await call('Runtime.evaluate',{expression:expr,awaitPromise:true,returnByValue:true})));if(process.argv[3]) {await new Promise(r=>setTimeout(r,700));await call('Emulation.setDeviceMetricsOverride',{width:1280,height:820,deviceScaleFactor:1,mobile:false});const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(process.argv[3],Buffer.from(shot.result.data,'base64'))}ws.close();process.exit(0);
