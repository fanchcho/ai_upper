import hashlib,json,subprocess
from pathlib import Path
from PySide6.QtGui import QImage
root=Path('docs/audit/phone-extensions'); records=[]
for p in sorted(root.rglob('*')):
 if p.name in ('recovery-audit.json','recovery.md') or not p.is_file():continue
 raw=p.read_bytes();record={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
 if p.suffix=='.json':json.loads(raw)
 if p.suffix=='.png':
  im=QImage(str(p));assert not im.isNull();record['size']=[im.width(),im.height()]
 records.append(record)
runs=[]
for name in ('upload','download','cards','tasks','install'):
 d=root if name=='upload' else root/name
 data=json.loads((d/'phone-readback.json').read_text());assert len(data['results'])==4
 for r in data['results']:
  assert r['browser']['reload'];assert r['revoked_disk_and_key']
  if name=='upload':assert any('UPLOAD_EVIDENCE' in x for x in r['messages_reopened'])
  if name=='download':assert r['delivered_reopened']['deliver_test']
  if name=='cards':
   c=json.loads((d/f"cards-{r['theme']}-{r['via']}.json").read_text());assert {x['outcome'] for x in c['interactions_reopened']}=={'approve','skipped','approved','denied'}
  if name=='tasks':
   c=json.loads((d/f"tasks-{r['theme']}-{r['via']}.json").read_text());assert not c['task_store_reads'][-1]['tasks'];assert any(x['status']=='paused' for s in c['task_store_reads'] for x in s['tasks']);assert any(x.get('runs') for s in c['task_store_reads'] for x in s['tasks'])
  if name=='install':
   c=json.loads((d/f"install-{r['theme']}-{r['via']}.json").read_text());assert len(c['devices_reopened'])==2;assert '已过期或已使用' in c['browser']['rejection']
  runs.append({'feature':name,'theme':r['theme'],'via':r['via'],'session':r['session']})
for decision in ('keep','ignore'):
 d=root/('cards-'+decision)
 data=json.loads((d/'phone-readback.json').read_text());assert len(data['results'])==4
 for r in data['results']:
  c=json.loads((d/f"cards-{r['theme']}-{r['via']}.json").read_text())
  assert c['plans_reopened']['plan_test']['decision']==decision
  assert {x['outcome'] for x in c['interactions_reopened']}=={decision}
  runs.append({'feature':'cards-'+decision,'theme':r['theme'],'via':r['via'],'session':r['session']})
files={}
for ext in ('txt','bin'):
 a=Path('.tmp/phone-evidence/delivered.'+ext).read_bytes();b=Path('.tmp/phone-evidence/downloaded.'+ext).read_bytes();assert a==b;files[ext]={'bytes':len(a),'source_sha256':hashlib.sha256(a).hexdigest(),'download_sha256':hashlib.sha256(b).hexdigest(),'identical':True}
assert not subprocess.check_output(['git','diff','b53779c','HEAD','--','app/src','app/tests'])
result={'checked_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'files':records,'runs':runs,'download_byte_comparison':files,'app_tree':subprocess.check_output(['git','rev-parse','HEAD:app'],text=True).strip(),'baseline_app_tree':subprocess.check_output(['git','rev-parse','b53779c:app'],text=True).strip(),'full_log_last_line':(root/'full.log').read_text().splitlines()[-1]}
(root/'recovery-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(len(records),'files verified;',len(runs),'runs checked; downloaded bytes equal; app tree unchanged')
