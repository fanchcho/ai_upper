const {app,BrowserWindow,session,nativeTheme}=require('electron');
const fs=require('fs'),path=require('path');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
app.setPath('userData','/tmp/ai-upper-web-browser-electron-'+Date.now());
app.whenReady().then(async()=>{
 const input=JSON.parse(fs.readFileSync('.tmp/remaining-three/browser-url.json'));
 const win=new BrowserWindow({width:1000,height:720,webPreferences:{nodeIntegration:false,contextIsolation:true}});
 // No synthetic permission grant or PushManager: exercise the host's real API.
 session.defaultSession.setPermissionRequestHandler((wc,p,cb)=>cb(false));
 const status=()=>win.webContents.executeJavaScript('document.querySelector("#status").textContent');
 async function ready(){for(let i=0;i<100;i++){if((await status()).includes('安全连接'))return;await delay(100)}throw Error(await status())}
 async function visibility(expected){for(let i=0;i<100;i++){try{const s=JSON.parse(fs.readFileSync('.tmp/remaining-three/browser-state.json'));if(s.devices.some(d=>d.proven&&d.visible===expected))return}catch(e){}await delay(100)}throw Error('server visibility mismatch '+expected)}
 async function font(){await win.webContents.executeJavaScript(`(async()=>{const f=new FontFace('EvidenceCJK','url(data:font/otf;base64,${fs.readFileSync('.tmp/theme-settings/NotoSansCJKsc-Regular.otf').toString('base64')})');await f.load();document.fonts.add(f);document.body.style.fontFamily='EvidenceCJK,sans-serif'})()`)}
 async function capture(prefix){for(const theme of ['dark','light']){nativeTheme.themeSource=theme;await delay(150);fs.writeFileSync('out/remaining-three/'+prefix+'-'+theme+'.png',(await win.webContents.capturePage()).toPNG())}}
 await win.loadURL(input.url);await ready();await font();await visibility(true);await capture('browser');
 win.hide();await visibility(false);win.show();await visibility(true);
 await win.loadURL(win.webContents.getURL());await ready();await font();
 win.focus();const pos=await win.webContents.executeJavaScript('(()=>{const r=document.querySelector("#subscribe").getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}})()');
 win.webContents.sendInputEvent({type:'mouseDown',button:'left',clickCount:1,...pos});win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...pos});
 let result;for(let i=0;i<100;i++){result=await status();if(result.startsWith('未验证：')||result.startsWith('订阅已保存'))break;await delay(100)}
 if(result.startsWith('正在申请'))throw Error('subscription still pending');await capture('browser-subscribe');
 const config=JSON.parse(fs.readFileSync(path.join(input.home,'config.json')));if(config.remote.bots[0].users.length!==1)throw Error('resume added a duplicate device');
 fs.writeFileSync('.tmp/remaining-three/browser-revoke','remove');
 for(let i=0;i<100;i++){if((await status()).includes('连接已关闭'))break;await delay(100)}
 if(!(await status()).includes('连接已关闭'))throw Error('revoked socket still open');
 const revoked=JSON.parse(fs.readFileSync('.tmp/remaining-three/browser-revoked.json'));
 const evidence={status:result,users:config.remote.bots[0].users,reloadResumed:true,foreground:true,background:true,revoked};
 fs.writeFileSync('docs/audit/remaining-three/browser.json',JSON.stringify(evidence,null,2));console.log(evidence);
 fs.writeFileSync('.tmp/remaining-three/browser-done','done');app.quit();
}).catch(e=>{console.error(e);fs.writeFileSync('.tmp/remaining-three/browser-done','failed');app.exit(1)});
