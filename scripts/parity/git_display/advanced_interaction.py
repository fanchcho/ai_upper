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
elif phase=='merge':
 git('checkout','-b','conflict');(repo/'a').write_text('branch');git('commit','-am','branch change');git('checkout','main');(repo/'a').write_text('main');git('commit','-am','main change')
 click('gitChip');click('gitMenu_branches');click('gitMenu_merge');click('gitMenu_branch_conflict');click('gitBranchConfirm');shot('conflict');data['files']=item('gitConflictFiles').property('text');assert '\na' in data['files']
 click('gitConflictAbort');data['status']=git('status','--porcelain');r=subprocess.run(['git','-C',str(repo),'rev-parse','--verify','MERGE_HEAD'],capture_output=True,text=True);data['merge_head']={'exit':r.returncode,'stderr':r.stderr};assert data['status']=='' and r.returncode!=0
elif phase=='identity':
 os.environ['GIT_CONFIG_GLOBAL']=str(home/'global.gitconfig');os.environ['GIT_CONFIG_NOSYSTEM']='1'
 git('config','--unset','user.name');git('config','--unset','user.email');git('config','user.useConfigOnly','true');(repo/'a').write_text('identity change')
 click('gitChip');click('gitMenu_commit');assert not item('gitNewIdentityName').property('visible')
 def typein(n,value):
  click(n);QTest.keyClick(w,Qt.Key_A,Qt.ControlModifier)
  for ch in value:QTest.keyClick(w,ch)
  pump()
 typein('gitNewCommitMessage','identity verified');click('gitNewSubmit');assert item('gitNewIdentityName').property('visible');shot('missing')
 typein('gitNewIdentityName','Scope User');typein('gitNewIdentityEmail','scope@example.invalid');click('gitIdentityScope');QTest.keyClick(w,Qt.Key_Down);QTest.keyClick(w,Qt.Key_Return);pump();data['scope']=item('gitIdentityScope').property('currentIndex');assert data['scope']==1;shot('scope');click('gitIdentitySave');data['name']=git('config','--global','--get','user.name');data['email']=git('config','--global','--get','user.email');assert data['name']=='Scope User';assert not item('gitNewIdentityName').property('visible');click('gitNewSubmit');data['commit']=git('log','-1','--format=%s');assert data['commit']=='identity verified'
elif phase=='ai':
 import threading,time
 from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
 requests=[];release=threading.Event()
 class Handler(BaseHTTPRequestHandler):
  def do_POST(self):
   requests.append({'path':self.path,'body':self.rfile.read(int(self.headers['Content-Length'])).decode()});release.wait(5);self.send_response(503);self.end_headers()
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 from test_qml_shell import MODELS
 import copy
 models=copy.deepcopy(MODELS);models['providers'][0]['apiHost']='http://127.0.0.1:'+str(server.server_port);b._settings.set_config({'models':models})
 (repo/'a').write_text('AI real diff');click('gitChip');click('gitMenu_commit');click('gitNewGenerate')
 for _ in range(30):
  pump()
  if requests:break
 assert requests;data['requests']=requests;data['before_stop']=item('gitNewGenerate').property('text');assert data['before_stop']=='停止生成';shot('running');click('gitNewGenerate');data['after_stop']=item('gitNewGenerate').property('text');assert data['after_stop']=='AI 生成';pump();data['pending']=len(b._commit_cancels);assert data['pending']==0;data['workers_after_stop']=[th.name for th in threading.enumerate() if '_generate_commit_worker' in th.name];assert data['workers_after_stop']==[];shot('stopped');release.set();server.shutdown();data['boundary']='本地HTTP阻塞端点；未返回模型文本，不算真实模型成功'
elif phase=='remote':
 git('branch','remote-delete');git('push','origin','remote-delete');data['before']=git('ls-remote','--heads','origin','remote-delete')
 open_branch('origin/remote-delete');click('gitMenu_delete');shot('confirm');click('gitBranchConfirm');data['after']=git('ls-remote','--heads','origin','remote-delete');assert data['before'] and not data['after']
 git('branch','remote-fail');git('push','origin','remote-fail');git('remote','set-url','origin',str(home/'missing.git'))
 open_branch('origin/remote-fail');click('gitMenu_delete');click('gitBranchConfirm');data['failure']=item('gitMenu').property('notice');assert data['failure'];assert item('gitPromptError').property('visible');shot('failure')
(out/f'{phase}-{theme}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));print(json.dumps(data,ensure_ascii=False));t.stop();w.close();e.deleteLater();pump()
