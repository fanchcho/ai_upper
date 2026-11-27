import json,sys,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from scripted_transport import ScriptedTransport,sse
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF,QObject
from PySide6.QtTest import QTest
from mvvm.services.chat_session_store import ChatSessionStore
class Wire:
 def __init__(self):self.called=False
 async def post(self,url,**kw):
  if self.called:return await text_stream('CREATED_WITH_FOLDER').post(url,**kw)
  self.called=True
  wire=ScriptedTransport(chunks=[sse('message_start',{'type':'message_start','message':{'usage':{'input_tokens':5}}}),sse('content_block_start',{'type':'content_block_start','index':0,'content_block':{'type':'tool_use','id':uuid.uuid4().hex,'name':'create_member','input':{}}}),sse('content_block_delta',{'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':json.dumps({'name':'FolderMember','duty':'Inspect chosen directory','pick_folder':True})}}),sse('content_block_stop',{'type':'content_block_stop','index':0}),sse('message_delta',{'type':'message_delta','delta':{'stop_reason':'tool_use'},'usage':{'output_tokens':5}}),sse('message_stop',{'type':'message_stop'})])
  return await wire.post(url,**kw)
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');out=Path('out/final-four');results=[]
for theme in ['dark','light']:
 base=Path('/tmp/ai-upper-member-folder-'+uuid.uuid4().hex);target=base/'chosen';target.mkdir(parents=True)
 w,b,s,t,e,h=build(base,theme,Wire())
 def click(name):
  o=find_item(w.contentItem(),name) or w.findChild(QObject,name);assert o,name
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint());_pump(app,lambda:False,.3)
 field=find_item(w.contentItem(),'inputField');field.forceActiveFocus();app.clipboard().setText('Create member and choose folder');QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier);QTest.keyClick(w,Qt.Key_Return)
 assert _pump(app,lambda:find_item(w.contentItem(),'interactionPrompt').isVisible(),5)
 shot(w,out/f'member-folder-prompt-{theme}.png');click('interactionAccept')
 assert _pump(app,lambda:any(x!=w and x.isVisible() for x in app.topLevelWindows()),5)
 picker=next(x for x in app.topLevelWindows() if x!=w and x.isVisible())
 QTest.keyClick(picker,Qt.Key_L,Qt.ControlModifier);app.clipboard().setText(str(base));QTest.keyClick(picker,Qt.Key_V,Qt.ControlModifier);QTest.keyClick(picker,Qt.Key_Return);_pump(app,lambda:False,.3)
 def walk(o):
  yield o
  for c in o.childItems():yield from walk(c)
 rows=[x for x in walk(picker.contentItem()) if x.property('fileName')=='chosen']
 shot(picker,out/f'member-folder-picker-{theme}.png')
 assert rows,'chosen directory not listed'
 entry=rows[0];QTest.mouseClick(picker,Qt.LeftButton,Qt.NoModifier,entry.mapToScene(QPointF(40,entry.height()/2)).toPoint());_pump(app,lambda:False,.2)
 shot(picker,out/f'member-folder-picker-{theme}.png')
 button=next(x for x in walk(picker.contentItem()) if x.property('text')=='Open' and x.property('enabled') and x.metaObject().indexOfSignal('clicked()')>=0)
 QTest.mouseClick(picker,Qt.LeftButton,Qt.NoModifier,button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint())
 assert _pump(app,lambda:bool(s.load_session(b._active).members),6),b.pendingInteractions()
 disk=ChatSessionStore(h);main=disk.load_session(b._active);child=disk.load_session(main.members[0]['sessionId']);assert child.focusRoot==str(target),(child.focusRoot,target)
 results.append({'theme':theme,'target':str(target),'main':main.model_dump(),'child':child.model_dump()})
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.2)
(out/'member-folder.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS actual folder picker, tool resumed, reopened member workspace')
