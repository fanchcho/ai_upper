import asyncio
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from test_plugin_port import service
from mvvm.services.mcp_runtime import McpConnection, McpTools
from mvvm.services.plugin_interactions import Interactions
from mvvm.services.tool_checkpoint import ToolCheckpoint
from mvvm.services.tool_runtime import ToolRuntime, ToolResult
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.services.provider_gateway import TextDelta, Done


def wait_for(predicate):
    limit = time.monotonic() + 3
    while time.monotonic() < limit:
        value = predicate()
        if value: return value
        time.sleep(.02)
    raise AssertionError('condition timed out')


def test_real_stdio_discovery_call_disable_and_reap(service, tmp_path):
    server = tmp_path / 'stdio.py'
    server.write_text('''import json, sys, os
for line in sys.stdin:
    r=json.loads(line)
    if 'id' not in r: continue
    m=r['method']
    result={'protocolVersion':'2025-06-18','capabilities':{'tools':{}}} if m=='initialize' else {'tools':[{'name':'echo','inputSchema':{'type':'object'}}]} if m=='tools/list' else {'content':[{'type':'text','text':r['params']['arguments']['text']+os.environ['MCP_TEST_KEY']}]}
    print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)
''')
    service.save_server('local', {'command':sys.executable, 'args':[str(server)], 'enabled':True}, json.dumps({'MCP_TEST_KEY':'secret'}))
    runtime = ToolRuntime(WorkspaceGuard())
    runtime.mcp = McpTools(service, runtime)
    specs = runtime.specs()
    name = next(s.name for s in specs if s.name.startswith('mcp__'))
    process = runtime.mcp.connections['local'].process
    assert runtime.execute(name, {'text':'hello'}).content == 'hellosecret'
    assert 'secret' not in json.dumps(service.servers())
    service.save_server('local', {'command':sys.executable,'args':[str(server)],'enabled':False})
    assert process.poll() is not None
    assert runtime.execute(name, {'text':'again'}).is_error
    assert not any(s.name.startswith('mcp__') for s in runtime.specs())
    runtime.close()


@pytest.mark.parametrize('sse', [False, True])
def test_real_http_mcp_session_headers_pagination_and_results(sse):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((data, dict(self.headers)))
            if 'id' not in data:
                self.send_response(202); self.end_headers(); return
            method=data['method']
            result = {'protocolVersion':'2025-06-18','capabilities':{'tools':{}}} if method=='initialize' else {'tools':[]} if method=='tools/list' else {'content':[{'type':'text','text':'http result'}]}
            response=json.dumps({'jsonrpc':'2.0','id':data['id'],'result':result}).encode()
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream' if sse else 'application/json')
            self.send_header('Mcp-Session-Id','session-1'); self.end_headers()
            self.wfile.write(b'data: '+response+b'\n\n' if sse else response)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    connection=McpConnection({'url':f'http://127.0.0.1:{server.server_port}/mcp'},'key')
    try:
        connection.initialize()
        assert connection.request('tools/list') == {'tools':[]}
        assert connection.request('tools/call',{'name':'echo','arguments':{}})['content'][0]['text']=='http result'
        assert [r[0]['method'] for r in requests]==['initialize','notifications/initialized','tools/list','tools/call']
        assert all(h['Authorization']=='Bearer key' for _,h in requests)
        assert requests[-1][1]['Mcp-Session-Id']=='session-1'
        assert requests[-1][1]['MCP-Protocol-Version']=='2025-06-18'
    finally:
        connection.close();server.shutdown();server.server_close();thread.join()


def test_stdio_cancel_reaps_child(tmp_path):
    script=tmp_path/'stuck.py';script.write_text('import time\ntime.sleep(20)\n')
    stop=threading.Event()
    connection=McpConnection({'command':sys.executable,'args':[str(script)]},cancelled=stop.is_set)
    timer=threading.Timer(.1,stop.set);timer.start()
    try:
        with pytest.raises(OSError,match='cancelled'): connection.initialize()
        assert connection.process.poll() is not None
    finally: connection.close();timer.join()


def test_authoritative_persona_prompt_and_local_command(service, tmp_path):
    from test_chat_vm import make_vm
    from mvvm.services.chat_session_store import ChatSessionStore
    requests=[]
    class Provider:
        async def stream(self, request):
            requests.append(request)
            yield TextDelta('done');yield Done('end_turn')
    service.save_identity('general', 'disk general')
    service.save_identity('coder', '---\nname: Coder\n---\nUse the authoritative disk prompt.')
    vm=make_vm(tmp_path/'chat',tmp_path,provider=Provider());vm.identity_service=service;vm.open_session('one')
    assert asyncio.run(vm.run_turn('/deva:identity coder')).stop=='end_turn'
    assert requests==[]
    assert ChatSessionStore(tmp_path/'chat').load_session('one').personaId=='coder'
    assert asyncio.run(vm.run_turn('hello')).stop=='end_turn'
    assert requests[-1].system=='Use the authoritative disk prompt.'
    service.save_identity('coder','new external content')
    asyncio.run(vm.run_turn('again'))
    assert requests[-1].system=='new external content'
    asyncio.run(vm.run_turn('@deva:general next'))
    assert requests[-1].system=='disk general'
    assert [m.text() for m in requests[-1].messages if m.role == 'user'][-1]=='next'
    asyncio.run(vm.run_turn('/deva:identity default'))
    assert vm.store.load_session('one').personaId is None


@pytest.mark.parametrize('outcome,executed', [('approved',True),('denied',False),('cancelled',False)])
def test_approval_gates_real_file_write_and_is_session_bound(tmp_path,outcome,executed):
    control=Interactions(tmp_path/'interactions',timeout=3)
    runtime=ToolRuntime(WorkspaceGuard([tmp_path]),tmp_path,session_id='one')
    runtime.interactions=control;runtime.approval_enabled=lambda:True
    results=[]
    worker=threading.Thread(target=lambda:results.append(runtime.execute('write_file',{'path':'proof.txt','content':'written'},'op')))
    worker.start()
    row=wait_for(lambda:control.pending('one'))[0]
    assert not (tmp_path/'proof.txt').exists()
    assert not control.answer('other',row['id'],'approved')
    assert control.answer('one',row['id'],outcome)
    worker.join(3);assert not worker.is_alive()
    assert (tmp_path/'proof.txt').exists()==executed
    assert results[0].is_error != executed


def test_question_restart_reattach_dismiss_and_timeout(tmp_path):
    controller=Interactions(tmp_path/'interactions',timeout=.1)
    row=controller.request('s','timeout','question','question')
    assert row['outcome']=='timeout'
    controller=Interactions(tmp_path/'persisted')
    replies=[]
    worker=threading.Thread(target=lambda:replies.append(controller.ask('s','op',{'questions':[{'question':'Choice?','choices':['A','B']}]},None)))
    worker.start()
    row=wait_for(lambda:controller.pending('s'))[0]
    restarted=Interactions(tmp_path/'persisted')
    assert restarted.pending('s')[0]['id']==row['id']
    assert restarted.answer('s',row['id'],'dismissed')
    worker.join(3);assert not worker.is_alive()
    assert json.loads(replies[0].content)[0]['outcome']=='dismissed'


def test_checkpoint_restart_reuses_result_without_reexecuting_and_rejects_changed_input(tmp_path):
    journal=ToolCheckpoint(tmp_path/'journal')
    count=[]
    def execute(): count.append(1);return ToolResult('saved')
    assert journal.execute('s','op','write_file',{'path':'a'},execute).content=='saved'
    restarted=ToolCheckpoint(tmp_path/'journal')
    assert restarted.execute('s','op','write_file',{'path':'a'},execute).content=='saved'
    assert count==[1]
    assert restarted.execute('s','op','write_file',{'path':'b'},execute).is_error
    def interrupted(): raise RuntimeError('crash after side effect')
    with pytest.raises(RuntimeError): journal.execute('s','crash','run_command',{},interrupted)
    assert 'interrupted_unknown' in restarted.execute('s','crash','run_command',{},execute).content
    assert count==[1]


def test_legacy_layout_backup_preserves_shared_authority_and_is_idempotent(tmp_path):
    from mvvm.services.plugin_layout import migrate_legacy
    root=tmp_path/'deva';legacy=root/'deva-agent';legacy.mkdir(parents=True)
    (root/'config.json').write_text(json.dumps({'personas':{'selected':'authoritative','sessionSelected':{'same':'current'}},'other':42}))
    (root/'mcp.json').write_text(json.dumps({'mcpServers':{'same':{'url':'https://current.test'}}}))
    (legacy/'identity.json').write_text(json.dumps({'selected':'stale'}))
    (legacy/'sessions.json').write_text(json.dumps({'sessions':{'same':{'identity':'stale'},'new':{'identity':'coder'}}}))
    (legacy/'mcp-servers.json').write_text(json.dumps({'servers':{'same':{'url':'https://stale.test'},'new':{'command':'server','enabled':False}}}))
    result=migrate_legacy(root)
    from pathlib import Path
    assert Path(result['backup']).is_dir() and not legacy.exists()
    cfg=json.loads((root/'config.json').read_text())
    assert cfg['personas']['selected']=='authoritative' and cfg['personas']['sessionSelected']=={'same':'current','new':'coder'}
    assert cfg['other']==42 and not cfg['mcp']['enabled']['new']
    assert json.loads((root/'mcp.json').read_text())['mcpServers']['same']['url']=='https://current.test'
    assert migrate_legacy(root)=={'migrated':False}


def test_identity_permissions_and_symlink_are_rejected(service, tmp_path):
    import os
    if os.name!='posix':pytest.skip('POSIX ownership checks require POSIX')
    service.identities()
    path=service.identity_root()/'personas'/'general.md'
    path.chmod(0o666)
    with pytest.raises(PermissionError): service.save_identity('general','overwrite')
    path.chmod(0o600);path.unlink();path.symlink_to(tmp_path/'outside')
    with pytest.raises(PermissionError): service.identities()


def test_recovery_restores_completed_tool_result_and_delivery_without_side_effect(tmp_path):
    from mvvm.models.chat_models import Message,ToolUsePart,ToolResultPart,StoredSession
    from mvvm.services.checkpoint_recovery import close_pending_tools
    checkpoint=ToolCheckpoint(tmp_path/'journal')
    checkpoint.execute('s','op','write_file',{},lambda:ToolResult('persisted result'))
    session=StoredSession(id='s',messages=[Message(role='assistant',content=[ToolUsePart(id='op',name='write_file',input={})])])
    assert close_pending_tools(session,checkpoint)
    assert session.messages[-1].content[0].content=='persisted result'
    assert not session.messages[-1].content[0].isError


def test_vm_resume_reattaches_pending_approval_then_executes_once(tmp_path):
    from test_chat_vm import make_vm
    from mvvm.models.chat_models import Message,ToolUsePart
    directory=tmp_path/'interactions';controller=Interactions(directory)
    args={'path':'resume.txt','content':'one write'}
    class Crash(BaseException):pass
    def crash():raise Crash()
    with pytest.raises(Crash):controller.approve('s','op','write_file',args,crash)
    vm=make_vm(tmp_path/'home',tmp_path)
    vm.open_session('s')
    vm.store.append_message('s',Message(role='assistant',content=[ToolUsePart(id='op',name='write_file',input=args)]))
    vm.tools.interactions=Interactions(directory)
    vm.tools.approval_enabled=lambda:True
    vm.tools.checkpoint=ToolCheckpoint(tmp_path/'journal')
    class Provider:
        async def stream(self, request):yield TextDelta('recovered');yield Done('end_turn')
    vm.provider=Provider()
    outcomes=[]
    worker=threading.Thread(target=lambda:outcomes.append(asyncio.run(vm.run_turn('/resume'))))
    worker.start()
    row=wait_for(lambda:vm.tools.interactions.pending('s'))[0]
    assert not (tmp_path/'resume.txt').exists()
    assert vm.tools.interactions.answer('s',row['id'],'approved')
    worker.join(3);assert not worker.is_alive()
    assert outcomes[0].stop=='end_turn'
    assert (tmp_path/'resume.txt').read_text()=='one write'
    (tmp_path/'resume.txt').write_text('changed after execution')
    assert not vm.tools.execute('write_file',args,'op').is_error
    assert (tmp_path/'resume.txt').read_text()=='changed after execution'


def test_checkpoint_image_result_roundtrip(tmp_path):
    from mvvm.models.chat_models import ImagePart
    journal=ToolCheckpoint(tmp_path/'journal')
    result=ToolResult('image',images=[ImagePart(mediaType='image/png',data='aGVsbG8=')])
    journal.execute('s','image','read_file',{},lambda:result)
    assert ToolCheckpoint(tmp_path/'journal').result('s','image').images[0].data=='aGVsbG8='
