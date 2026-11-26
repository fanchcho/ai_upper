import os, sys, json, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'app/src'),str(ROOT/'app/tests')]
from PySide6.QtGui import QGuiApplication, QFontDatabase
from PySide6.QtCore import QPointF
from pytest import MonkeyPatch
from test_qml_window_controls import _build_window,_pump,_find_item
app=QGuiApplication([])
QFontDatabase.addApplicationFont(str(ROOT/'.tmp/theme-settings/NotoSansCJKsc-Regular.otf'))
stage=sys.argv[1]
if stage == 'before':
 import qml_shell, shutil
 source=ROOT/'.tmp/theme-settings/before-qml'
 shutil.copytree(ROOT/'app/src/qml',source,dirs_exist_ok=True)
 for name in ['SettingsModal','PluginSettingsPane','Theme']:
  shutil.copyfile(ROOT/'out/theme-settings'/(name+'.before.qml'),source/(name+'.qml'))
 qml_shell.qml_main=lambda: source/'Main.qml'

out=ROOT/'out/theme-settings'/stage
out.mkdir(exist_ok=True)
mp=MonkeyPatch()
w,b,t,e=_build_window(Path(tempfile.mkdtemp(prefix='ai-upper-theme-',dir='/tmp')),mp)
w.resize(1420,1076)
rows=[]
def walk(i):
    yield i
    for c in i.childItems(): yield from walk(c)
for theme in ['light','dark']:
 b.setTheme(theme)
 for page in ['general','models','models-provider','models-advanced','extensions','about','custom-model','mcp','identities','mcp-filled','mcp-hover','mcp-pressed','mcp-disabled']:
  w.setProperty('page','settings-'+('mcp' if page.startswith('mcp-') else page));_pump(app,.25)
  if page.startswith('mcp-'):
   field=_find_item(w.contentItem(),'pluginBaseUrl');field.setProperty('text','https://example.test/mcp')
   button=_find_item(w.contentItem(),'pluginSave')
   from PySide6.QtTest import QTest
   from PySide6.QtCore import QPoint, Qt
   point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
   if page=='mcp-hover':QTest.mouseMove(w,point)
   if page=='mcp-pressed':QTest.mousePress(w,Qt.LeftButton,Qt.NoModifier,point)
   if page=='mcp-disabled':button.setProperty('enabled',False)
   _pump(app,.1)
  im=w.grabWindow();assert not im.isNull();im.save(str(out/(page+'-'+theme+'.png')))
  texts=[]
  for i in walk(_find_item(w.contentItem(),'settingsModal')):
   if not i.isVisible():continue
   try:
    txt=i.property('text') or i.property('placeholderText')
    if not isinstance(txt,str) or not txt:continue
    p=i.mapToScene(QPointF(0,0)); color=i.property('color')
    if not hasattr(color,'name'):continue
    texts.append(dict(text=txt,x=p.x(),y=p.y(),w=i.width(),h=i.height(),color=color.name()))
   except Exception:pass
  rows.append(dict(theme=theme,page=page,texts=texts))
  if page=='mcp-pressed':QTest.mouseRelease(w,Qt.LeftButton,Qt.NoModifier,QPoint(0,0))
  if page=='mcp-disabled':button.setProperty('enabled',True)
(out/'text-regions.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
t.stop();w.close();mp.undo()
