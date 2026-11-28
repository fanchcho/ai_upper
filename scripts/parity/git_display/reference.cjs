const { app, BrowserWindow } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const root=process.cwd(), out=path.join(root,'docs/audit/git-display');
app.setPath('userData',process.env.AI_UPPER_HOME);
app.commandLine.appendSwitch('force-device-scale-factor','2');
app.disableHardwareAcceleration();
const base='/home/agent/shared_workspace/deva/apps/desktop/src/renderer/src/';
const css=['styles/tokens.css','styles/app.css'].map(p=>fs.readFileSync(base+p,'utf8')).join('\n');
app.whenReady().then(async()=>{
 const win=new BrowserWindow({width:512,height:873,show:true,frame:false,webPreferences:{sandbox:true}});
 for(const theme of ['dark','light']){
 const html=`<!doctype html><html data-theme="${theme}"><head><meta charset="utf-8"><style>${css} @font-face{font-family:FixtureCJK;src:url("file://${root}/.tmp/theme-settings/NotoSansCJKsc-Regular.otf")} body{font-family:FixtureCJK,sans-serif}</style></head><body><div style="padding:16px;background:var(--bg-panel);min-height:100vh"><h3>原版 CSS 控件样本（非原版完整窗口）</h3><div class="provider-warn">⚠ 已启用但未配置密钥，对话将失败</div><input class="input" placeholder="user.name"><hr style="border:0;border-top:1px solid var(--border)"><button class="btn">Fetch</button><button class="btn btn--primary">保存身份</button><button class="btn btn--danger">丢弃全部</button><button class="btn btn--ghost">AI 提交信息</button></div></body></html>`;
 const file=path.join(root,'.tmp/git-display',`specimen-${theme}.html`);fs.writeFileSync(file,html);await win.loadFile(file);await win.webContents.executeJavaScript('document.fonts.ready.then(()=>true)');
 const data=await win.webContents.executeJavaScript(`Object.fromEntries(['.provider-warn','.input','.btn','.btn--primary','.btn--danger','.btn--ghost'].map(sel=>{const e=document.querySelector(sel),s=getComputedStyle(e);return [sel,{background:s.backgroundColor,border:s.borderTopColor,text:s.color,height:s.height,padding:s.padding,borderWidth:s.borderTopWidth,placeholder:getComputedStyle(e,"::placeholder").color}]}))`);
 fs.writeFileSync(path.join(out,`original-css-${theme}.json`),JSON.stringify({boundary:'Read-only original CSS rendered in Electron component specimen, not original client state',electron:process.versions.electron,chrome:process.versions.chrome,styles:data},null,2));
 const im=await win.webContents.capturePage();fs.writeFileSync(path.join(out,`original-css-${theme}.png`),im.toPNG());
 }
 win.destroy();app.quit();
}).catch(e=>{console.error(e);app.exit(1)});
