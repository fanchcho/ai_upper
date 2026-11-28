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
phase,theme=sys.argv[1:3]; out=ROOT/'docs/audit/git-display'; out.mkdir(exist_ok=True)
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
click('gitChip'); QTest.mouseMove(w,QPoint(10,10)); pump()
def shot(name):
 w.grabWindow().save(str(out/f'{phase}-{theme}-{name}-full.png'))
 im=QImage(str(out/f'{phase}-{theme}-{name}-full.png'))
 if name.startswith('git'):
  p=item('gitIdentityName').mapToScene(QPointF(0,0)); x=round(p.x()*2)-44; y=200
 else: x=936; y=200
 im.copy(x,y,1025,1746).save(str(out/f'{phase}-{theme}-{name}.png'))
 return [x,y]
origin=shot('git')
names=['gitIdentityName','gitIdentityEmail','gitBranchName','gitRemoteName','gitRemoteUrl','gitSetConfig','gitDiscardAll','gitFetch','gitGenerateMessage']
data={'phase':phase,'theme':theme,'home':str(home),'repo':str(repo),'commit':git('rev-parse','--short','HEAD'),'crop':origin,'devicePixelRatio':w.devicePixelRatio(),'items':{}}
for name in names:
 o=item(name); p=o.mapToScene(QPointF(0,0)); data['items'][name]={'rect':[p.x(),p.y(),o.width(),o.height()],'text':o.property('text')}
if phase=='after':
 typein('gitIdentityName','Verified User'); typein('gitIdentityEmail','verified@example.invalid'); click('gitSetConfig')
 data['identity_readback']={'name':git('config','--local','--get','user.name'),'email':git('config','--local','--get','user.email')}
 typein('gitBranchName','display-check'); click('gitCreateBranch'); data['branches_readback']=git('branch','--list')
 typein('gitRemoteName','mirror'); typein('gitRemoteUrl',str(remote)); click('gitAddRemote'); data['remotes_readback']=git('remote','-v')
 click('gitFetch'); data['fetch_head_readback']=(repo/'.git/FETCH_HEAD').read_text(); data['notice']=item('gitNotice').property('text')
 data['commits_text']=item('gitRecentCommits').property('text'); shot('git-interacted')
 # Cursor is photographed while the real input has keyboard focus.
 click('gitIdentityName'); shot('git-focused')
if phase=='after':
 panel=item('gitPanel'); panel.setProperty('width',560); pump()
 data['stretched_widths']={n:item(n).width() for n in ['gitIdentityName','gitIdentityEmail','gitBranchName','gitRemoteName','gitRemoteUrl']}
 panel.setProperty('width',480); pump()
 empty=home/'empty-repo'; empty.mkdir(); subprocess.run(['git','init',str(empty)],check=True,capture_output=True)
 session=store.load_session('s-1'); session.focusRoot=str(empty); store.save('s-1'); b.openSession('s-1'); b._publish(); click('gitRefresh')
 data['empty_text']=item('gitRecentCommits').property('text'); assert data['empty_text']=='最近提交：暂无提交'; shot('git-empty')
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(100,100)); pump(); assert not item("gitPanel").property("visible")
b._vault.delete_secret('p1'); w.setProperty('page','settings-models-provider'); pump()
data['warning_state']={'has_key':b._vault.has_secret('p1'),'models':b._settings.models_section()}
from mvvm.services.settings_service import SettingsService
from mvvm.services.secrets_vault import SecretsVault
assert not SecretsVault(home).has_secret('p1')
assert SettingsService(home).models_section()['providers'][0]['enabled']
if phase=='after':
 warn=item('providerMissingKeyWarning'); wp=warn.mapToScene(QPointF(0,0)); data['warning_rect']=[wp.x(),wp.y(),warn.width(),warn.height()]
shot('warning')
if phase=='after':
 w.setProperty('page','bots'); pump(); shot('bots-shared-buttons')
(out/f'{phase}-{theme}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
print(json.dumps(data,ensure_ascii=False))
t.stop(); w.close(); e.deleteLater(); pump()
