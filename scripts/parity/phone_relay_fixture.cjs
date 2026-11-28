// Local opaque relay fixture. Never decrypts phone payloads.
const http=require('http'),fs=require('fs'),path=require('path'),{WebSocketServer}=require('ws');
const sockets=new WebSocketServer({noServer:true});let desk;const peers=new Map(),log=[];let seq=0;
const server=http.createServer((req,res)=>{let file=req.url==='/'?'index.html':req.url.slice(1);if(!['index.html','client.js','sw.js'].includes(file)){res.writeHead(404);return res.end()}res.setHeader('content-type',file.endsWith('.js')?'text/javascript':'text/html');res.end(fs.readFileSync(path.join('app/src/web_pair',file)))});
server.on('upgrade',(req,socket,head)=>sockets.handleUpgrade(req,socket,head,ws=>{
 if(req.url.startsWith('/desk/')){if(!req.headers.authorization?.startsWith('Bearer '))return ws.close();desk=ws;log.push({t:'desk-authenticated',path:req.url});ws.on('message',raw=>{if(raw.toString()==='ping')return ws.send('pong');const env=JSON.parse(raw);log.push({t:env.t,direction:'outbound',c:env.c});const peer=peers.get(env.c);if(env.t==='msg'&&peer)peer.send(env.d);if(env.t==='close'&&peer)peer.close()});ws.on('close',()=>{if(desk===ws)desk=null})}
 else if(/^\/d\/[^/]+\/ws$/.test(req.url)){const c=String(++seq);peers.set(c,ws);if(!desk)return ws.close();desk.send(JSON.stringify({t:'open',c}));ws.on('message',raw=>{log.push({t:'msg',direction:'inbound',c});desk?.send(JSON.stringify({t:'msg',c,d:raw.toString()}))});ws.on('close',()=>{peers.delete(c);desk?.send(JSON.stringify({t:'close',c}))})}else ws.close();
 fs.writeFileSync('.tmp/phone-evidence/relay-log.json',JSON.stringify(log));
}));
setInterval(()=>fs.writeFileSync('.tmp/phone-evidence/relay-log.json',JSON.stringify(log)),100);
server.listen(0,'127.0.0.1',()=>fs.writeFileSync('.tmp/phone-evidence/relay-port',String(server.address().port)));
