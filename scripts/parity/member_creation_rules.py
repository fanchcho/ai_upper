import os,sys,uuid
from pathlib import Path
sys.path.insert(0,'app/src')
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.host import ChatHost
home=Path('/tmp/ai-upper-member-create-rules-'+uuid.uuid4().hex);home.mkdir();os.environ['AI_UPPER_HOME']=str(home)
store=ChatSessionStore(home);guard=WorkspaceGuard([home]);host=ChatHost(store=store,guard=guard,home=home,emit=lambda p:None,emit_sessions_changed=lambda:None)
host.create_session({'sessionId':'main','focusRoot':str(home)});main=store.load_session('main')
first=host._members.create(main,{'name':'Reviewer','duty':'review','folder':'relative'})
assert first['origin']=='created' and (home/'relative').is_dir()
for args in [{'name':'Reviewer'},{'name':'Bad Name'},{'name':'Missing','folder':str(home/'missing')}]:
 try:host._members.create(main,args)
 except ValueError as e:print('REFUSED',str(e))
 else:raise AssertionError(args)
assert not (home/'missing').exists();host._members.remove(main,first['sessionId']);again=host._members.create(main,{'name':'Reviewer'})
assert again['sessionId']==first['sessionId'] and not again.get('removedAt')
assert ChatSessionStore(home).load_session('main').members[0]['origin']=='created'
print('PASS duplicate refusal, relative creation, nonexistent absolute refusal, restore retained child and reopen disk')
