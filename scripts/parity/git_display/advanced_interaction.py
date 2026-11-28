import os,sys,json,subprocess,tempfile
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Qt,QPointF,QPoint
from PySide6.QtTest import QTest
from feature_parity_evidence import build,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from mvvm.services.git_service import branches
phase,theme=sys.argv[1:];out=Path('docs/audit/git-advanced');app=QApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf')
w,b,store,t,e,home=build(Path(tempfile.mkdtemp(prefix='ai-upper-branches-',dir='/tmp')),theme,text_stream('unused'))
w.resize(1280,1060)
def pump():_pump(app,lambda:False,.3)
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.STDOUT,text=True).strip()
repo=home/'repo';repo.mkdir();git('init','-b','main');git('config','user.name','Branch Fixture');git('config','user.email','fixture@example.invalid');(repo/'a').write_text('base');git('add','.');git('commit','-m','base')
remote=home/'remote.git';subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True);git('remote','add','origin',str(remote));git('push','-u','origin','main');git('symbolic-ref','refs/remotes/origin/HEAD','refs/remotes/origin/main')
git('branch','feature/a');git('branch','feature/b');git('branch','behind');git('branch','--set-upstream-to=origin/main','behind');git('commit','--allow-empty','-m','upstream advance');git('push');git('commit','--allow-empty','-m','local ahead')
s=store.load_session('s-1');s.focusRoot=str(repo);store.save('s-1');b.openSession('s-1');b._publish();pump()
def item(n):return find_item(w.contentItem(),n) or w.findChild(__import__('PySide6.QtCore',fromlist=['QObject']).QObject,n)
def click(n):
 o=item(n);assert o is not None,n;QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint());pump()
def shot(n):QTest.mouseMove(w,QPoint(10,10));pump();w.grabWindow().save(str(out/f'{phase}-{theme}-{n}.png'))

data={"repo":str(repo)}
def open_branch(name):
 QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(100,100));pump();click('gitChip');click('gitMenu_branches');click('gitMenu_branch_'+name)
if phase=='reach':
 click('gitChip');shot('main');data['legacy_visible']=item('gitPanel').property('visible');assert not data['legacy_visible'];click('gitMenu_branches');shot('branches')
elif phase=='force':
 git('checkout','-b','unmerged');git('commit','--allow-empty','-m','unique');git('checkout','main')
 open_branch('unmerged');click('gitMenu_delete');click('gitBranchConfirm');shot('confirm')
 data['warning']=item('gitDeleteWarning').property('text');assert '1 个提交' in data['warning'];click('gitBranchCancel');data['after_cancel']=git('branch','--list','unmerged');assert data['after_cancel']
 open_branch('unmerged');click('gitMenu_delete');click('gitBranchConfirm');click('gitBranchConfirm');data['after_delete']=git('branch','--list','unmerged');assert not data['after_delete']
elif phase=='remote':
 git('branch','remote-delete');git('push','origin','remote-delete');data['before']=git('ls-remote','--heads','origin','remote-delete')
 open_branch('origin/remote-delete');click('gitMenu_delete');shot('confirm');click('gitBranchConfirm');data['after']=git('ls-remote','--heads','origin','remote-delete');assert data['before'] and not data['after']
 git('branch','remote-fail');git('push','origin','remote-fail');git('remote','set-url','origin',str(home/'missing.git'))
 open_branch('origin/remote-fail');click('gitMenu_delete');click('gitBranchConfirm');data['failure']=item('gitMenu').property('notice');assert data['failure'];shot('failure')
(out/f'{phase}-{theme}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));print(json.dumps(data,ensure_ascii=False));t.stop();w.close();e.deleteLater();pump()
