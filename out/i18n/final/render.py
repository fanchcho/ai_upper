import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'app/src'))
from PySide6.QtWidgets import QApplication,QTextBrowser
from PySide6.QtGui import QFontDatabase
from markdown.document import LIGHT,DARK
from mvvm.views.transcript_render import transcript_html
app=QApplication([]);QFontDatabase.addApplicationFont(str(Path.cwd()/'.tmp/theme-settings/NotoSansCJKsc-Regular.otf'))
def luminance(h):
 v=[int(h[i:i+2],16)/255 for i in (1,3,5)]
 v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v]
 return sum(a*b for a,b in zip(v,[.2126,.7152,.0722]))
rows=[]
for lang in ['en','zh-CN']:
 os.environ['AI_UPPER_LANG']=lang
 for name,palette in [('light',LIGHT),('dark',DARK)]:
  entries=[dict(role='tool',name='read_file',text='读取失败：example.txt',summary='读取失败',is_error=True),dict(role='assistant',text='Sample body / 正文测试')]
  before=json.dumps(entries,ensure_ascii=False).encode()
  w=QTextBrowser();w.resize(900,480);w.setStyleSheet('QTextBrowser { background: %s; color: %s; }'%(palette.bg,palette.fg));w.setHtml(transcript_html(entries,palette));w.show();app.processEvents();assert w.grab().save(str(Path('out/i18n/final')/f'{lang}-{name}-body.png'))
  assert json.dumps(entries,ensure_ascii=False).encode()==before
  for fg,bg in [(palette.fg,palette.bg),(palette.fg,palette.error_bg),(palette.error_fg,palette.error_bg)]:
   a,b=sorted([luminance(fg),luminance(bg)]);ratio=(b+.05)/(a+.05);assert ratio>=4.5;rows.append(dict(locale=lang,theme=name,foreground=fg,background=bg,contrast=ratio))
  w.close()
Path('out/i18n/final/contrast.json').write_text(json.dumps(rows,indent=2)+'\n');print('4 screenshots; original bytes unchanged; all body/error contrast >= 4.5: PASS')
