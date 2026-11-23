"""Inspect actual rendered blocks/line boxes, retaining source and target evidence."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app/src')); sys.path.insert(0,str(ROOT/'app/tests'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from utils.qt_compat import QtWidgets,QtGui
from markdown.body import BodyDocument
from markdown.parser import parse_markdown
from test_markdown_body import QuickDocumentStub
app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
source=json.loads((Path(os.environ['AI_UPPER_HOME'])/'data/chats/parity-000.json').read_text())['messages'][1]['content'][0]['text']
body=BodyDocument(); body.set_width(696); body.set_markdown(source)
quick=QuickDocumentStub(); body.attach(quick); doc=quick.document; doc.setTextWidth(696); doc.size()
result={'parser':parse_markdown(source),'plain':doc.toPlainText(),'blocks':[]}
block=doc.begin()
while block.isValid():
 layout=block.layout(); rect=doc.documentLayout().blockBoundingRect(block); fmt=block.blockFormat()
 result['blocks'].append({'text':block.text(),'y':rect.y(),'height':rect.height(),'topMargin':fmt.topMargin(),'bottomMargin':fmt.bottomMargin(),'lineHeight':fmt.lineHeight(),'lines':[{'y':layout.lineAt(i).y(),'height':layout.lineAt(i).height(),'textStart':layout.lineAt(i).textStart(),'textLength':layout.lineAt(i).textLength()} for i in range(layout.lineCount())]})
 block=block.next()
print(json.dumps(result,ensure_ascii=False,indent=2))
