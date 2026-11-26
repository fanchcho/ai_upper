import subprocess,os,json
from pathlib import Path
root=Path.cwd();env=dict(os.environ,AI_UPPER_HOME='/tmp/ai-upper-i18n-close',LD_LIBRARY_PATH=str(root/'.tmp/wm/usr/lib/aarch64-linux-gnu'),QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',TMPDIR=str(root/'.tmp'))
commands=[['tools/build.py','--help'],['tools/build.py','--target','not-a-target'],['tools/build.py','--doctor'],['tools/ci_tail.py','--help'],['tools/ci_tail.py'],['tools/ci_tail.py','--log',str(root/'.tmp/i18n-close/absent.log'),'--title','test'],['app/src/main.py','--help']]
records=[]
for lang in ['en','zh-CN']:
 for i,args in enumerate(commands):
  e=dict(env,LANG=lang,LC_ALL=lang);e.pop('AI_UPPER_LANG',None)
  r=subprocess.run(['.venv/bin/python']+args,env=e,text=True,capture_output=True,timeout=40)
  path=root/f'out/i18n/close/cli-{lang}-{i}.txt';path.write_text('$ LANG='+lang+' LC_ALL='+lang+' .venv/bin/python '+' '.join(args)+'\n'+r.stdout+r.stderr+'\nexit='+str(r.returncode)+'\n');records.append(dict(language=lang,command=args,exit=r.returncode,file=str(path)))
(root/'out/i18n/close/cli-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
with open(root/'out/i18n/close/full-tests.txt','w') as f:
 p=subprocess.Popen(['.venv/bin/python','-m','pytest','app/tests','-q','--basetemp=/tmp/ai-upper-i18n-close/final'],env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('full pytest pid',p.pid)
