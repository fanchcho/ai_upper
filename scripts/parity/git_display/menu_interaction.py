import os, sys, json, subprocess, tempfile
from pathlib import Path
ROOT=Path.cwd(); sys.path[:0]=[str(ROOT/'app/src'),str(ROOT/'app/tests'),str(ROOT/'scripts/parity')]
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, QPointF, QPoint, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from feature_parity_evidence import build, find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QImage
os.environ['GIT_AUTHOR_DATE']='2026-01-01T00:00:00Z'; os.environ['GIT_COMMITTER_DATE']='2026-01-01T00:00:00Z'
phase='menu';theme=sys.argv[1]; out=ROOT/(sys.argv[2] if len(sys.argv)>2 else 'docs/audit/git-version'); out.mkdir(parents=True,exist_ok=True)
app=QApplication([])
QFontDatabase.addApplicationFont(str(ROOT/'.tmp/theme-settings/NotoSansCJKsc-Regular.otf'))
tmp=Path(tempfile.mkdtemp(prefix='ai-upper-git-display-',dir='/tmp'))
w,b,store,t,e,home=build(tmp,theme,text_stream('unused fixture: no model turn performed'))
w.resize(1280,1060)
def pump(): _pump(app,lambda:False,.35)
def git(*args): return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.STDOUT,text=True).strip()
repo=home/'repo'; repo.mkdir(); git('init','-b','main'); git('config','user.name','Display Fixture'); git('config','user.email','fixture@example.invalid')
(repo/'note.txt').write_text('real fixture commit\n'); git('add','.'); git('commit','-m','Display fixture initial commit')
remote=home/'remote.git'; subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
git('remote','add','origin',str(remote)); git('push','-u','origin','main'); (repo/'note.txt').write_text('real fixture change\n')
s=store.load_session('s-1'); s.focusRoot=str(repo); store.save('s-1'); b.openSession('s-1'); b._publish(); pump()
def item(name): return find_item(w.contentItem(),name) or w.findChild(QObject,name)
def click(name):
 o=item(name); assert o is not None,name
 p=o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint(); QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,p); pump()
def typein(name,text):
 click(name); QTest.keyClick(w,Qt.Key_A,Qt.ControlModifier); [QTest.keyClick(w,ch) for ch in text]; pump(); assert item(name).property('text')==text

def snap(name):
 pump(); w.grabWindow().save(str(out/f'{theme}-{name}.png'))
click('gitChip');snap('menu')
m=item('gitMenu');c=m.property('contentItem');pos=c.mapToScene(QPointF(0,0));menu_rect=[pos.x()-6,pos.y()-6,m.property('width'),m.property('height')]
click('gitMenu_fetch');fetch=(repo/'.git/FETCH_HEAD').read_text();notice=item('gitMenuNotice').property('text')
click('gitMenu_branches');snap('branches')
click('gitMenu_create');typein('gitNewBranchName','new-menu-branch');click('gitBranchConfirm');branch=git('branch','--show-current');snap('created')
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(100,100));pump();click('gitChip');click('gitMenu_commit');snap('commit')
geometry={n:{'width':item(n).property('width'),'height':item(n).property('height')} for n in ('gitCommitDialog','gitNewCommitMessage','gitNewGenerate','gitNewSubmit')}
typein('gitNewCommitMessage','Commit through original-style modal');click('gitNewSubmit');pump();latest=git('log','-1','--format=%h %s');assert 'Commit through original-style modal' in latest
(out/f'{theme}-interaction.json').write_text(json.dumps({'menu_rect':menu_rect,'geometry':geometry,'home':str(home),'branch':branch,'fetch_head':fetch,'notice':notice,'commit':latest,'status':git('status','--porcelain')},ensure_ascii=False,indent=2))
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(100,100));pump()
b._vault.delete_secret('p1');w.setProperty('page','settings-models-provider');pump();snap('warning')
t.stop();w.close();e.deleteLater();pump()
