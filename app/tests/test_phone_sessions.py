"""Phone authorization must use the same scope as its session list."""
from types import SimpleNamespace
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.phone_sessions import handle


def test_phone_scope_rejects_outside_session_and_traversal(tmp_path):
    store=ChatSessionStore(tmp_path);store.ensure_session('private');store.save('private')
    bot={'id':'phone','scope':{'mode':'sessions','sessions':['allowed']}}
    calls=[]
    shell=SimpleNamespace(_store=store,_host=SimpleNamespace(is_busy=lambda sid:False,send=lambda request:calls.append(request)))
    controller=SimpleNamespace(shell=shell,list=lambda:[bot])
    replies=[];state={'device':'device','send_frame':replies.append}
    handle(controller,'phone',state,{'t':'send','sid':'private','text':'forbidden'})
    handle(controller,'phone',state,{'t':'history','sid':'private'})
    handle(controller,'phone',state,{'t':'new','sid':'../../outside','rid':'r'})
    assert not calls
    assert [r['t'] for r in replies]==['err','err','created']
    assert replies[-1].get('error')
    assert not store.load_session('../../outside')
