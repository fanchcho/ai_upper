import os,sys,json
from pathlib import Path
sys.path[:0]=['app/src','app/tests']
from PySide6.QtGui import QGuiApplication
from pytest import MonkeyPatch
from test_qml_settings_provider import _build_window,_pump
from test_qml_window_controls import _find_item,_click_item
app=QGuiApplication([]);w,b,s,v,t,e=_build_window(Path(os.environ['AI_UPPER_HOME']),MonkeyPatch(),'chat')
theme=sys.argv[1];out=Path('out/extensions-shell');s.set_config({'theme':theme,'locale':'en'});b._apply_theme()
def page(p):w.setProperty('page',p);_pump(app,.3)
def click(n):
 o=_find_item(w.contentItem(),n);assert o is not None,n
 _click_item(w,o);_pump(app,.3);print('CLICK',n,flush=True)
def field(n,value):_find_item(w.contentItem(),n).setProperty('text',value)
def shot(n):assert w.grabWindow().save(str(out/f'{theme}-{n}.png'))
page('settings-general');shot('navigation')
for n in ['general','models','extensions','about']:click('settingsNav_'+n)
for n in ['custom-model','mcp','identities']:assert _find_item(w.contentItem(),'settingsNav_'+n) is None
click('settingsNav_models');click('modelsCustomNetwork');field('pluginBaseUrl','https://example.test/v1');field('pluginModelName','fixture-model');click('pluginSave');shot('custom-saved')
r=json.loads(b.pluginSettings('read','{}'));assert r['model']['model']=='fixture-model';print('MODEL READBACK',r['model'],flush=True)
click('pluginBack');click('settingsNav_extensions');click('extensionsManageMcp');field('pluginIdentifier','fixture');field('pluginBaseUrl','https://mcp.test');click('pluginSave');shot('mcp-saved')
r=json.loads(b.pluginSettings('read','{}'));assert any(x['id']=='fixture' for x in r['servers']);print('MCP READBACK',r['servers'],flush=True)
click('pluginBack');page('chat');click('chatManagePersonas');field('pluginIdentifier','fixture-persona');field('pluginPersonaBody','Persistent persona fixture');click('pluginSave');shot('persona-saved')
r=json.loads(b.pluginSettings('identities','{}'));assert {'id':'fixture-persona','text':'Persistent persona fixture'} in r['identities'];print('PERSONA READBACK',r,flush=True)
(out/f'{theme}-disk-files.json').write_text(json.dumps([str(p) for p in s.home.rglob('*') if p.is_file()],indent=2))
t.stop();w.close();e.deleteLater();_pump(app,.1)
