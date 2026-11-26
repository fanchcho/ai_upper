import os,subprocess,json
from pathlib import Path
bridge=Path('app/src/qml_shell.py'); viewport=Path('app/src/markdown/viewport.py')
b=bridge.read_text();v=viewport.read_text()
deferred=b.replace('                self._display_cache.activate(Display(self._body, target), self._document)', '''                target.setTextWidth(previous.textWidth())
                display = Display(self._body, target)
                class PendingDocument(QtCore.QObject):
                    def textDocument(inner):
                        return target
                pending_document = PendingDocument(self._document.parent())''').replace('self._body.attach(self._document, fragment=fragment, images=images)', '''self._body.attach(pending_document, fragment=fragment, images=images)
                self._display_cache.activate(display, self._document)
                pending_document.deleteLater()''')
batched=v.replace('    overlays = []\n    for table in _iter_tables', '    overlays = []\n    transaction = QtGui.QTextCursor(document)\n    transaction.beginEditBlock()\n    for table in _iter_tables').replace('    return overlays\n', '    return overlays\n')
pos=batched.rfind('    return overlays');batched=batched[:pos]+'    transaction.endEditBlock()\n'+batched[pos:]
Path('.tmp/cold-path/deferred.patch').write_text(__import__('difflib').unified_diff(b.splitlines(True),deferred.splitlines(True)).__str__() if False else ''.join(__import__('difflib').unified_diff(b.splitlines(True),deferred.splitlines(True))))
Path('.tmp/cold-path/batch.patch').write_text(''.join(__import__('difflib').unified_diff(v.splitlines(True),batched.splitlines(True))))
results=[]
try:
 for i in range(1,4):
  for mode in ['baseline','deferred','batch']:
   bridge.write_text(deferred if mode=='deferred' else b);viewport.write_text(batched if mode=='batch' else v)
   env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-cold-path-{mode}-{i}',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
   out=f'.tmp/cold-path/{mode}-{i}'
   with open(out+'.log','w') as f:p=subprocess.run(['.venv/bin/python','.tmp/cold-path/measure.py',out],env=env,stdout=f,stderr=subprocess.STDOUT)
   results.append(dict(mode=mode,group=i,exit_code=p.returncode));print(results[-1],flush=True)
finally:
 bridge.write_text(b);viewport.write_text(v)
 Path('.tmp/cold-path/exits.json').write_text(json.dumps(results,indent=2))
