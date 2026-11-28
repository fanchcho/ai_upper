"""Bounded first-level prefix split. Never interprets a passing half as root cause."""
import os,json,subprocess,time,resource
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CORE,(resource.RLIM_INFINITY,resource.RLIM_INFINITY))
root=Path.cwd();out=root/'docs/audit/order-bisection'
nodes=['app/'+l.strip() if l.startswith('tests/') else l.strip() for l in (root/'.tmp/migration/collection.log').read_text().splitlines() if l.startswith(('tests/','app/tests/')) and '::' in l]
targets=['app/tests/test_bot_roundtrip.py::test_telegram_roundtrip_local','app/tests/test_qml_links.py::test_clicking_a_rendered_link_opens_it']
plan=[]
for target in targets:
 i=nodes.index(target);prefix=nodes[:i];m=len(prefix)//2
 for name,group in [('first',prefix[:m]),('second',prefix[m:])]:
  label=('bot' if 'bot_roundtrip' in target else 'qml')+'-'+name
  plan.append({'label':label,'targetIndex':i,'prefixCount':len(group),'nodes':group+[target]})
(out/'plan.json').write_text(json.dumps(plan,indent=2))
results=[]
for p in plan:
 env=os.environ.copy();env.update(AI_UPPER_HOME='/tmp/ai-upper-prefix-'+p['label'],PYTHONFAULTHANDLER='1',QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',LD_LIBRARY_PATH=str(root/'.tmp/wm/usr/lib/aarch64-linux-gnu'))
 t=time.monotonic()
 with (out/(p['label']+'.log')).open('w') as f:r=subprocess.run([str(root/'.venv/bin/python'),'-m','pytest','-q',*p['nodes']],env=env,stdout=f,stderr=subprocess.STDOUT)
 row={'label':p['label'],'count':len(p['nodes']),'exit':r.returncode,'seconds':round(time.monotonic()-t,2)};results.append(row);print(row,flush=True)
 (out/'results.json').write_text(json.dumps(results,indent=2))
 if r.returncode<0:break
