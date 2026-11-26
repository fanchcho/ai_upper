import subprocess,os,json
from pathlib import Path
results=[]
for name,files in [('related',['app/tests/test_display_cache.py','app/tests/test_qml_shell.py','app/tests/test_markdown_body.py','app/tests/test_markdown_document.py','app/tests/test_markdown_highlight.py']),('full',[])]:
 env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-arch-retained-{name}',QT_QPA_PLATFORM='offscreen',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
 with open(f'.tmp/architecture/pytest-{name}.log','w') as f:p=subprocess.run(['.venv/bin/python','-m','pytest',*files,'-q',f'--basetemp=/tmp/ai-upper-arch-retained-{name}-base'],env=env,stdout=f,stderr=subprocess.STDOUT)
 results.append(dict(name=name,exit_code=p.returncode));print(results[-1],flush=True)
 if p.returncode:break
Path('.tmp/architecture/test-exits.json').write_text(json.dumps(results,indent=2))
