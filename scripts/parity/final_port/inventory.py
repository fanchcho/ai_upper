"""Reproducible source inventory: all IPC registrations, bridge calls, UI hooks."""
import json,re,subprocess,hashlib
from pathlib import Path
root=Path('/home/agent/shared_workspace/deva');base=root/'apps/desktop/src';out=Path('docs/audit/evidence')
rows=[];ipc=[];bridge=[];files=[]
main_re=re.compile(r'ipcMain\.(handle|on)\s*\(\s*[\'\"]([^\'\"]+)')
pre_re=re.compile(r'ipcRenderer\.(invoke|send|sendSync|on|once)\s*\(\s*[\'\"]([^\'\"]+)')
hook=re.compile(r'\bon[A-Z][\w]*\s*=|addEventListener\s*\(|\b(?:Menu|Tray|Notification|autoUpdater|safeStorage|clipboard|dialog|shell|globalShortcut)\.|\.on\s*\(\s*[\'\"]|\bon(?:Drop|Paste|KeyDown|CompositionStart|CompositionEnd)\b')
paths=subprocess.check_output(['rg','--files',str(base)],text=True).splitlines()
for file in sorted(paths):
 p=Path(file)
 if p.suffix not in ('.ts','.tsx','.js'):continue
 text=p.read_text();rel=str(p.relative_to(root));files.append(rel)
 for match in main_re.finditer(text):ipc.append({'channel':match[2],'kind':match[1],'source':rel+':'+str(text.count('\n',0,match.start())+1)})
 if '/preload/' in file:
  for match in pre_re.finditer(text):bridge.append({'channel':match[2],'kind':match[1],'source':rel+':'+str(text.count('\n',0,match.start())+1)})
 for i,line in enumerate(text.splitlines(),1):
  if hook.search(line):rows.append({'source':rel+':'+str(i),'code':line.strip()})
result={'scope':'all .ts/.tsx/.js under deva/apps/desktop/src; source only, no modification','files':files,'source_sha256':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files},'ipc':ipc,'preload':bridge,'non_ipc_hook_index':rows,'counts':{'source_files':len(files),'ipc_registrations':len(ipc),'preload_calls':len(bridge),'non_ipc_hook_lines':len(rows)}}
(out/'source-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result['counts']))
