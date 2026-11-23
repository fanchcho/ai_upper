import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'app/src'),str(ROOT/'app/tests')];os.environ['QT_QPA_PLATFORM']='offscreen'
import pytest
from PySide6 import QtCore as C,QtGui as G
from test_qml_context_menu import _build_window,_find_item,_pump
app=G.QGuiApplication([]);mp=pytest.MonkeyPatch()
if sys.argv[1]=='before':
 import utils.emoji_font
 utils.emoji_font.ensure_emoji_font=lambda:None
out=ROOT/'out/final-parity'/('emoji-'+sys.argv[1]);out.mkdir(exist_ok=True)
w,b,store,home,ticker,engine=_build_window(Path(os.environ['AI_UPPER_HOME']),mp)
try:
 w.setProperty('page','chat');v=_find_item(w.contentItem(),'bodyView');b._body.set_markdown('🚀 ✅');b._body.attach(v.property('textDocument'));_pump(app,.4)
 doc=v.property('textDocument').textDocument();shot=w.grabWindow();shot.save(str(out/'glyphs.png'));res={}
 for char,pos in [('🚀',0),('✅',3)]:
  r=v.positionToRectangle(pos);point=v.mapToScene(C.QPointF(r.x(),r.y()));x,y=int(point.x()),int(point.y());pixels=[];colored=0
  for yy in range(y,y+24):
   for xx in range(x,x+17):
    col=shot.pixelColor(xx,yy);rgb=(col.red(),col.green(),col.blue())
    if min(rgb)<220:pixels.append([xx,yy]);colored+=max(rgb)-min(rgb)>30
  font=doc.begin().begin().fragment().charFormat().font();layout=G.QTextLayout(char,font);layout.beginLayout();line=layout.createLine();line.setLineWidth(100);layout.endLayout()
  res[char]={'xy':[x,y],'dark_pixels':len(pixels),'colored_pixels':colored,'runs':[{'font':r.rawFont().familyName(),'glyphs':list(r.glyphIndexes())} for r in layout.glyphRuns()]}
 print(json.dumps(res,ensure_ascii=False));(out/'glyphs.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
finally:ticker.stop();w.close();engine.deleteLater();mp.undo()
