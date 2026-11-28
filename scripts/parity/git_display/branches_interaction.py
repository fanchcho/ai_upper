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
phase,theme=sys.argv[1:];out=Path('docs/audit/git-upstream');app=QApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf')
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
click('gitChip');shot('main');click('gitMenu_branches');shot('branches')
data={'repo':str(repo),'rows':branches(str(repo))['branches']}
if phase=='after':
 click('gitMenu_branch_feature/a');click('gitMenu_checkout');data['checkout_readback']=git('branch','--show-current');assert data['checkout_readback']=='feature/a'
 QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(100,100));pump()
 for i in range(40):git('branch',f'long-list-{i:02}')
 click('gitChip');click('gitMenu_branches');shot('long-list')
 menu=item('gitMenu');data['menu_height']=menu.property('height');assert data['menu_height']<=w.height()-16
 flick=item('gitBranchScroll');data['content_height']=flick.property('contentHeight');assert data['content_height']>flick.property('height')
 # Scroll by actual wheel events delivered to the QQuick window.
 p=flick.mapToScene(QPointF(flick.width()/2,flick.height()/2)).toPoint()
 QTest.wheelEvent(w,p,QPoint(0,-1200));pump();data['scroll_y']=flick.property('contentY');assert data['scroll_y']>0;shot('scrolled')
 QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(100,100));pump()
 empty=home/'empty';empty.mkdir();subprocess.run(['git','init',str(empty)],check=True,capture_output=True);s=store.load_session('s-1');s.focusRoot=str(empty);store.save('s-1');b.openSession('s-1');b._publish();pump();click('gitChip');click('gitMenu_branches');shot('empty');assert branches(str(empty))['branches']==[]
 data['empty_ui']=item('gitBranchEmpty').property('text');assert data['empty_ui']=='暂无分支'
(out/f'{phase}-{theme}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));print(json.dumps(data,ensure_ascii=False))
t.stop();w.close();e.deleteLater();pump()
