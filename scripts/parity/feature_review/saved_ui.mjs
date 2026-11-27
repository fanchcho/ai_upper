import fs from 'node:fs';
const pages=await (await fetch('http://127.0.0.1:9344/json/list')).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);let seq=0;const pending=new Map();ws.onmessage=e=>{let m=JSON.parse(e.data);if(m.id){pending.get(m.id)?.(m);pending.delete(m.id)}};
async function call(method,params={}){return new Promise(r=>{let id=++seq;pending.set(id,r);ws.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.result.exceptionDetails)throw Error(JSON.stringify(r));return r.result.result.value;}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
await call('Emulation.setDeviceMetricsOverride',{width:1280,height:820,deviceScaleFactor:1,mobile:false});
for(const theme of ['dark','light']){
 await evaluate(`window.deva.config.set({theme:'${theme}',mcp:{enabled:{echo:false}}}).then(()=>location.reload())`);await wait(1200);
 await evaluate(`document.querySelector('button[title=Settings]').click()`);await wait(400);
 await evaluate(`[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Extensions').click()`);await wait(400);
 console.log('ROWS',await evaluate(`JSON.stringify([...document.querySelectorAll('.cf-setrow__open')].map(x=>x.textContent))`));
 await evaluate(`[...document.querySelectorAll('.cf-setrow__open')].find(x=>x.textContent.includes('Echo')).click()`);await wait(500);
 console.log('INPUTS',await evaluate(`JSON.stringify([...document.querySelectorAll('input')].map(x=>({type:x.type,placeholder:x.placeholder})))`));
 const pt=await evaluate(`(()=>{const el=[...document.querySelectorAll('input')].find(x=>x.type==='password');el.scrollIntoView();const r=el.getBoundingClientRect();return {x:r.x+20,y:r.y+r.height/2}})()`);
 await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...pt});await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...pt});
 await call('Input.insertText',{text:'fixture'});await wait(850);
 console.log('SAVED',theme,await evaluate(`document.body.innerText.includes('Saved')`));
 const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(`out/feature-review/deva-saved-${theme}.png`,Buffer.from(shot.result.data,'base64'));
}
ws.close();process.exit(0);
