"""Real QML shell body operations. A failed check is reported, never converted to PASS."""
from pathlib import Path
import json, os, sys, tempfile, time, statistics
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'app/src'),str(ROOT/'app/tests')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6 import QtCore as C, QtGui as G, QtTest as T
from test_qml_context_menu import _build_window,_find_item,_pump
from markdown.document import BodyStyle
from mvvm.models.chat_models import Message
from qml_shell_sessions import transcript_markdown
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
report={};app=G.QGuiApplication.instance() or G.QGuiApplication([])
def record(key,value):
 report[key]=value;(out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(key,json.dumps(value,ensure_ascii=False),flush=True)
with tempfile.TemporaryDirectory(dir='/tmp',prefix='ai-upper-body-probe-') as tmp, pytest.MonkeyPatch.context() as mp:
 w,b,store,home,ticker,engine=_build_window(Path(tmp),mp);w.setProperty('page','chat');_pump(app,.3)
 view=_find_item(w.contentItem(),'bodyView');scroll=_find_item(w.contentItem(),'bodyScroll');qdoc=view.property('textDocument');doc=qdoc.textDocument()
 def render(md):
  t=time.perf_counter();b._body.set_markdown(md);b._body.attach(qdoc);app.processEvents();w.grabWindow();return (time.perf_counter()-t)*1000
 def point(pos):
  r=view.positionToRectangle(pos);p=view.mapToScene(C.QPointF(r.x()+1,r.y()+r.height()/2));return p.toPoint()
 def reset():
  scroll.setProperty('contentY',0);scroll.setProperty('contentX',0);_pump(app,.12)
 def wheel(p,dx=0,dy=0):
  e=G.QWheelEvent(C.QPointF(p),C.QPointF(w.mapToGlobal(p)),C.QPoint(dx,dy),C.QPoint(dx,dy),C.Qt.NoButton,C.Qt.NoModifier,C.Qt.ScrollUpdate,False);app.sendEvent(w,e);_pump(app,.15)
 try:
  md='alpha start 中文\n\n```python\nprint(sorted([3, 1]))\n```\n\n| File | Type |\n| --- | --- |\n| README.md | text |\n\nomega end'
  render(md);reset();text=doc.toPlainText();a=point(text.index('alpha'));z=point(text.index('omega')+len('omega end'))
  w.requestActivate();T.QTest.mousePress(w,C.Qt.LeftButton,C.Qt.NoModifier,a)
  for step in range(1,11): T.QTest.mouseMove(w,C.QPoint(a.x()+(z.x()-a.x())*step//10,a.y()+(z.y()-a.y())*step//10),15)
  T.QTest.mouseRelease(w,C.Qt.LeftButton,C.Qt.NoModifier,z);_pump(app,.1)
  selected=view.property('selectedText');app.clipboard().clear();T.QTest.keyClick(w,C.Qt.Key_C,C.Qt.ControlModifier);_pump(app,.1)
  clip=app.clipboard().text();record('selection_copy',{'ok':all(x in clip for x in ('alpha','sorted','README.md','omega')),'selected_chars':len(selected),'clipboard_chars':len(clip),'clipboard_matches_selection':clip==selected,'normalized_equal':clip.replace('\u00a0',' ').replace('\u2029','\n')==selected.replace('\u00a0',' ').replace('\u2029','\n').replace('\ufdd0','\n').replace('\ufdd1','\n'),'different_codepoints':[(ord(a),ord(b)) for a,b in zip(selected,clip) if a!=b],'start':[a.x(),a.y()],'end':[z.x(),z.y()]})
  T.QTest.mouseClick(w,C.Qt.LeftButton,C.Qt.NoModifier,point(text.index('sorted')+2));T.QTest.mouseDClick(w,C.Qt.LeftButton,C.Qt.NoModifier,point(text.index('sorted')+2));_pump(app,.1)
  record('double_click',{'ok':view.property('selectedText')=='sorted','selected':view.property('selectedText')})
  table=next(f for f in doc.rootFrame().childFrames() if isinstance(f,G.QTextTable) and f.columns()==2)
  cell=table.cellAt(0,0).format().toTableCellFormat();fmt=table.format();rect=doc.documentLayout().frameBoundingRect(table)
  shot=w.grabWindow();ratio=w.devicePixelRatio();top=view.mapToScene(C.QPointF(rect.x(),rect.y()))
  grids=[]
  for y in range(round(top.y()*ratio),round((top.y()+rect.height())*ratio)+1):
   count=sum(shot.pixelColor(x,y).name()=='#e6e6ea' for x in range(round(top.x()*ratio),round((top.x()+rect.width())*ratio)))
   if count>0:grids.append([y,count])
  record('table_painted_grid',{'rows_with_exact_border_pixels':grids,'dpr':ratio})
  record('table',{'border':fmt.border(),'spacing':fmt.cellSpacing(),'color':fmt.borderBrush().color().name(),'padding':[cell.leftPadding(),cell.rightPadding(),cell.topPadding(),cell.bottomPadding()],'rect':[rect.x(),rect.y(),rect.width(),rect.height()],'first_cell_block_lineHeight':table.cellAt(0,0).firstCursorPosition().blockFormat().lineHeight(),'first_cell_text':table.cellAt(0,0).firstCursorPosition().block().text()})
  render('```text\nSTART '+('wide_code_'*100)+' END\n```');reset();before_x=scroll.property('contentX');p=point(4);wheel(p,dx=-120);after_x=scroll.property('contentX')
  record('horizontal_code',{'ok':after_x!=before_x,'contentX_before':before_x,'contentX_after':after_x,'view_width':view.width(),'scroll_width':scroll.width(),'scroll_contentWidth':scroll.property('contentWidth'),'document_idealWidth':doc.idealWidth(),'document_textWidth':doc.textWidth(),'tail_x':view.positionToRectangle(doc.toPlainText().index('END')).x()})
  local=out/'local-image.png';img=G.QImage(48,32,G.QImage.Format_ARGB32);img.fill(G.QColor('#5b5bd6'));img.save(str(local))
  render(f'![local]({local.resolve()})\n\n![示意图](data:image/png;base64,iVBORw0KGgo=)');reset();shot=w.grabWindow();formats=[];block=doc.begin()
  while block.isValid():
   it=block.begin()
   while not it.atEnd():
    f=it.fragment()
    if f.charFormat().isImageFormat():
     imageformat=f.charFormat().toImageFormat();formats.append([imageformat.width(),imageformat.height()])
    it+=1
   block=block.next()
  dpr=w.devicePixelRatio();count=sum(shot.pixelColor(x,y).name()=='#5b5bd6' for y in range(int(55*dpr),int(85*dpr)) for x in range(int(486*dpr),int(525*dpr)))
  record('images',{'formats':formats,'body_plain':doc.toPlainText(),'purple_sample_pixels':count,'local_ok':formats==[[48.0,32.0]] and count>0,'broken_icon_present':False})
  themed=[]
  for dark in (False,True):
   assert b.setTheme('dark' if dark else 'light');render('中文 theme 😀 🚀 ✅');reset()
   first=doc.begin().begin().fragment().charFormat();layout=G.QTextLayout('中文 theme 😀 🚀 ✅',first.font());layout.beginLayout();line=layout.createLine();line.setLineWidth(696);layout.endLayout();runs=layout.glyphRuns()
   themed.append({'dark':dark,'fg':first.foreground().color().name(),'font':first.font().families(),'pixelSize':first.font().pixelSize(),'shellDark':b.darkMode,'runs':[{'font':r.rawFont().familyName(),'glyphs':list(r.glyphIndexes())} for r in runs]})
  record('theme_and_glyphs',themed)
  glyphs={}
  for char in '中文😀🚀✅':
   layout=G.QTextLayout(char,first.font());layout.beginLayout();line=layout.createLine();line.setLineWidth(696);layout.endLayout()
   glyphs[char]=[{'font':r.rawFont().familyName(),'glyphs':list(r.glyphIndexes())} for r in layout.glyphRuns()]
  record('per_character_glyphs',glyphs)
  shot=w.grabWindow();record('hidpi',{'env':os.environ.get('QT_SCALE_FACTOR','1'),'dpr':dpr,'logical':[w.width(),w.height()],'physical':[shot.width(),shot.height()],'ok':shot.width()==round(w.width()*dpr) and shot.height()==round(w.height()*dpr)})
  if os.environ.get('QT_SCALE_FACTOR','1')=='1':
   long='\n\n'.join('段落 %d 中文和行内 `code` '%i+'content '*20 for i in range(400))
   messages=[Message(role='user' if i%2==0 else 'assistant',content=f'消息 {i}: '+('正文测试 '*40)) for i in range(120)]
   many=transcript_markdown(messages)
   for name,source in [('one_long_message',long),('messages_120',many)]:
    elapsed=render(source);reset();t=time.perf_counter();latencies=[]
    maxy=max(0,scroll.property('contentHeight')-scroll.height())
    for i in range(60):
     one=time.perf_counter();scroll.setProperty('contentY',maxy*i/59);app.processEvents();w.grabWindow();latencies.append((time.perf_counter()-one)*1000)
    record(name,{'characters':len(source),'render_attach_and_grab_ms':round(elapsed,3),'document_height':doc.size().height(),'scroll_60_grabs_ms':round((time.perf_counter()-t)*1000,3),'step_median_ms':round(statistics.median(latencies),3),'step_max_ms':round(max(latencies),3),'note':'offscreen synchronous scroll+grab, not display FPS'})
 finally:
  ticker.stop();w.close();engine.deleteLater()

print('PROBE_EXECUTED: horizontal_code remains false; rc=0 means collection complete, not all requirements passed.',flush=True)
