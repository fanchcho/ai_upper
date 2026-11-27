import os,sys,json,time,subprocess,uuid
from pathlib import Path
home=Path('/tmp/ai-upper-startup-gc-'+uuid.uuid4().hex);directory=home/'data'/'rewind';directory.mkdir(parents=True)
records=[{'turn':n,'kind':'write_file','path':'unused','pre':'QQ==','post':'Qg==','recordedAt':time.time()} for n in range(105)]
records.append({'turn':105,'kind':'write_file','path':'expired','pre':'QQ==','post':'Qg==','recordedAt':time.time()-31*86400})
path=directory/'fixture.json';path.write_text(json.dumps({'turn':106,'records':records}))
env=dict(os.environ,AI_UPPER_HOME=str(home),QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
# Real application startup, no direct GC invocation.
p=subprocess.Popen([sys.executable,'app/src/main.py'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
try:
 deadline=time.monotonic()+15
 while time.monotonic()<deadline:
  current=json.loads(path.read_text())
  if current['records'][0].get('released'):break
  time.sleep(.1)
 assert current['records'][0]['released'] and current['records'][-1]['released']
 assert len(current['records'])==106
 assert sum(isinstance(r.get('pre'),str) for r in current['records'])<=100
 print(json.dumps({'home':str(home),'metadata':len(current['records']),'released':sum(bool(r.get('released')) for r in current['records'])}))
finally:
 p.terminate()
 try:output=p.communicate(timeout=5)[0]
 except subprocess.TimeoutExpired:p.kill();output=p.communicate()[0]
 print(output.decode(errors='replace'))
