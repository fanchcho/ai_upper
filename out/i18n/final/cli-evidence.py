"""Safe actual CLI invocations, captured separately from this evidence runner."""
import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
commands=[
 [sys.executable,'tools/build.py','--help'],
 [sys.executable,'tools/build.py','--invalid-option'],
 [sys.executable,'tools/build.py','--verify'],
 [sys.executable,'-c',"import sys;sys.path.insert(0,'tools');from ai_upper.egg_loader import _key_bytes;\ntry:_key_bytes('invalid!')\nexcept ValueError as e:print(e,file=sys.stderr);sys.exit(2)"],
 [sys.executable,'-c',"import sys;sys.path.insert(0,'app/src');from mvvm.services.greeting import GreetingService;print(GreetingService().message())"],
 [sys.executable,'tools/ci_tail.py','--help'],
]
results=[]
for lang in ('en','zh-CN'):
 for i,cmd in enumerate(commands):
  env=dict(os.environ,AI_UPPER_HOME='/tmp/ai-upper-final-cli',LANG='zh_CN.UTF-8' if lang=='zh-CN' else 'en_US.UTF-8',LC_ALL='zh_CN.UTF-8' if lang=='zh-CN' else 'en_US.UTF-8')
  env.pop('AI_UPPER_LANG',None)
  r=subprocess.run(cmd,cwd=root,env=env,text=True,capture_output=True)
  p=root/f'out/i18n/final/cli-{lang}-{i}.txt'
  p.write_text('$ '+repr(cmd)+'\nLANG='+env['LANG']+'\nstdout:\n'+r.stdout+'\nstderr:\n'+r.stderr+'\nexit='+str(r.returncode)+'\n')
  results.append(dict(language=lang,command=cmd,exit=r.returncode,path=str(p)))
(root/'out/i18n/final/cli-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False,indent=2))
