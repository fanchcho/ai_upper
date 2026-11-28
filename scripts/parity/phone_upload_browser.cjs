const {app,BrowserWindow,nativeTheme}=require('electron');const fs=require('fs');const delay=ms=>new Promise(r=>setTimeout(r,ms));
const [url,theme,via,out]=process.argv.slice(-4);app.setPath('userData',process.cwd()+'/.tmp/phone-evidence/browser-'+theme+'-'+via+'-'+Date.now());
app.whenReady().then(async()=>{
 const win=new BrowserWindow({width:900,height:820,webPreferences:{nodeIntegration:false,contextIsolation:true}});nativeTheme.themeSource=theme;
 async function waitJS(expr){for(let i=0;i<150;i++){try{if(await win.webContents.executeJavaScript(expr))return}catch{}await delay(100)}throw Error('timeout '+expr+' '+await win.webContents.executeJavaScript('document.body.innerText'))}
 async function click(selector){const pos=await win.webContents.executeJavaScript(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}})()`);win.webContents.sendInputEvent({type:'mouseDown',button:'left',clickCount:1,...pos});win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...pos});await delay(100)}
 await win.loadURL(url);await waitJS('document.querySelector("#sessions").options.length>0');
 await win.webContents.executeJavaScript(`(async()=>{const f=new FontFace('EvidenceCJK','url(data:font/otf;base64,${fs.readFileSync('.tmp/theme-settings/NotoSansCJKsc-Regular.otf').toString('base64')})');await f.load();document.fonts.add(f);document.body.style.fontFamily='EvidenceCJK,sans-serif'})()`);
 await click('#new');await waitJS('document.querySelector("#sessions").value.startsWith("sess_")');
 await win.webContents.debugger.attach('1.3');
 await win.webContents.debugger.sendCommand('Page.setInterceptFileChooserDialog',{enabled:true});
 // Native chooser fails on this host (GSettings); select real file through CDP.
 const {root}=await win.webContents.debugger.sendCommand('DOM.getDocument');
 const {nodeId}=await win.webContents.debugger.sendCommand('DOM.querySelector',{nodeId:root.nodeId,selector:'#attachment'});
 await win.webContents.debugger.sendCommand('DOM.setFileInputFiles',{nodeId,files:[process.cwd()+'/.tmp/phone-evidence/evidence.txt']});
 await waitJS('document.querySelector("#status").textContent.includes("附件已上传")');
 await click('#message');await win.webContents.insertText('PHONE_'+via+'_'+theme);await click('#send');
 await waitJS('document.querySelector("#history").textContent.includes("LOCAL_MODEL_REPLY")');
 const sid=await win.webContents.executeJavaScript('document.querySelector("#sessions").value');
 fs.writeFileSync(out+'-'+theme+'-'+via+'.png',(await win.webContents.capturePage()).toPNG());
 const state=await win.webContents.executeJavaScript('({body:document.querySelector("#history").textContent,device:JSON.parse(localStorage.getItem("device:"+JSON.parse(localStorage.getItem("connection")).desk))})');
 win.reload();await waitJS('document.querySelector("#sessions").options.length>0');
 await win.webContents.executeJavaScript(`document.querySelector('#sessions').value=${JSON.stringify(sid)};document.querySelector('#sessions').dispatchEvent(new Event('change'))`);
 await waitJS('document.querySelector("#history").textContent.includes("LOCAL_MODEL_REPLY")');
 fs.writeFileSync('.tmp/phone-evidence/result.json',JSON.stringify({sid,device:state.device.id,body:state.body,reload:true}));
 // Keep the socket alive for the desktop's real revoke click.
 await waitJS('document.querySelector("#status").textContent.includes("连接已关闭")');
 fs.writeFileSync('.tmp/phone-evidence/revoked','true');
 for(let i=0;i<150&&!fs.existsSync('.tmp/phone-evidence/repair-url');i++)await delay(100);
 await win.loadURL(fs.readFileSync('.tmp/phone-evidence/repair-url','utf8'));
 await waitJS('document.querySelector("#sessions").options.length>0');
 await waitJS('JSON.parse(localStorage.getItem("device:"+JSON.parse(localStorage.getItem("connection")).desk)).id!=='+JSON.stringify(state.device.id));
 const repaired=await win.webContents.executeJavaScript('JSON.parse(localStorage.getItem("device:"+JSON.parse(localStorage.getItem("connection")).desk)).id');
 if(repaired===state.device.id)throw Error('revoked credential reused');
 fs.writeFileSync('.tmp/phone-evidence/repaired',repaired);
 await waitJS('document.querySelector("#status").textContent.includes("连接已关闭")');app.quit();
}).catch(e=>{console.error(e);app.exit(1)});
