"""No credentials: exercise the real host's provider resolution without a fake model."""
import os,sys,json,uuid,time
from pathlib import Path
sys.path.insert(0,'app/src')
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.settings_service import SettingsService
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host
home=Path('/tmp/ai-upper-no-model-'+uuid.uuid4().hex);home.mkdir();os.environ['AI_UPPER_HOME']=str(home)
settings=SettingsService(home);vault=SecretsVault(home);store=ChatSessionStore(home);events=[]
host,_=build_chat_host(settings=settings,vault=vault,store=store,guard=WorkspaceGuard(),home=home,emit=events.append,emit_sessions_changed=lambda:None)
host.create_session({'sessionId':'unconfigured'})
host.send({'sessionId':'unconfigured','text':'Create a member to handle the continuing review work, then delegate it.'})
end=time.monotonic()+5
while time.monotonic()<end:
 host.drain()
 if any(p.get('event',{}).get('type')=='error' for p in events):break
 time.sleep(.05)
errors=[p for p in events if p.get('event',{}).get('type')=='error'];assert errors,events
print(json.dumps({'status':'unverified','home':str(home),'errors':errors},ensure_ascii=False))
host.shutdown()
