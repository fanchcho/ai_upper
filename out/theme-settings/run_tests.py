import os, subprocess
from pathlib import Path
env=dict(os.environ)
env.pop('PYTHONPATH',None)
env.update(AI_UPPER_HOME='/tmp/ai-upper-theme-full',LD_LIBRARY_PATH=str(Path('.tmp/wm/usr/lib/aarch64-linux-gnu').resolve()),QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(Path('.tmp/theme-settings').resolve()))
with open('out/theme-settings/pytest.log','w') as log:
 result=subprocess.run(['.venv/bin/python','-m','pytest','app/tests','-q','-rs','--basetemp=/tmp/ai-upper-theme-tests'],env=env,stdout=log,stderr=subprocess.STDOUT)
 log.write('\nexit_code='+str(result.returncode)+'\n')
Path('out/theme-settings/pytest.exit').write_text(str(result.returncode)+'\n')
