const {app,BrowserWindow}=require('electron');
app.setPath('userData',process.env.PROBE_PROFILE);
app.whenReady().then(async()=>{
  const w=new BrowserWindow({width:400,height:300});
  await w.loadURL('data:text/html,<h1>Shutdown probe</h1>');
  console.log('MINIMAL_WINDOW_READY');
  if (process.env.PROBE_GRACEFUL==='1') setTimeout(()=>app.quit(),500);
});
