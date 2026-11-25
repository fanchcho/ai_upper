import asyncio
from mvvm.models.chat_models import Message, ToolUsePart, ToolResultPart
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.checkpoint_recovery import close_pending_tools
from test_chat_vm import make_vm


def test_restart_marks_uncertain_call_without_replay(tmp_path):
    home=tmp_path/'home'; work=tmp_path/'work';work.mkdir()
    store=ChatSessionStore(home);store.ensure_session('crashed')
    store.append_message('crashed',Message(role='assistant',content=[ToolUsePart(id='side-effect',name='write_file',input={'path':'never.txt','content':'bad'})]))
    vm=make_vm(home,work)
    vm.open_session('crashed')
    asyncio.run(vm.run_turn('continue'))
    assert not (work/'never.txt').exists()
    loaded=ChatSessionStore(home).load_session('crashed')
    results=[p for m in loaded.messages if isinstance(m.content,list) for p in m.content if isinstance(p,ToolResultPart) and p.toolUseId=='side-effect']
    assert len(results)==1 and 'interrupted_unknown' in results[0].content
    assert close_pending_tools(loaded) is False
