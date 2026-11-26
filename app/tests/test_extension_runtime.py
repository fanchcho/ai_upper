import queue
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mvvm.services.extension_settings import ExtensionSettings
from mvvm.services.extension_runtime import ExtensionRuntime
from mvvm.services.settings_service import SettingsService
from mvvm.services.secrets_vault import SecretsVault


def wait(runtime, key, state):
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        if runtime.view(key)['status']==state:return runtime.view(key)
        time.sleep(.03)
    raise AssertionError(runtime.view(key))


def test_stdio_http_sse_error_retry_and_tools(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_UPPER_HOME',str(tmp_path));monkeypatch.setenv('DEVA_SECRETS_BACKEND','file')
    server_script=tmp_path/'server.py'
    server_script.write_text('''import sys,json
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r: continue
 result={'protocolVersion':'2025-06-18','capabilities':{},'serverInfo':{'name':'fixture','version':'1'}} if r['method']=='initialize' else {'tools':[{'name':'echo','description':'Echo input','inputSchema':{'type':'object'}}]} if r['method']=='tools/list' else {}
 print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)
''')
    messages = queue.Queue()
    stream_done = threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
            self.wfile.write(b'event: endpoint\ndata: /messages\n\n'); self.wfile.flush()
            while not stream_done.is_set():
                try: data = messages.get(timeout=.1)
                except queue.Empty: continue
                self.wfile.write(b'event: message\ndata: '+data+b'\n\n'); self.wfile.flush()
        def do_POST(self):
            r=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if 'id' not in r:
                self.send_response(202);self.end_headers();return
            result={'protocolVersion':'2025-06-18','capabilities':{},'serverInfo':{'name':'http-fixture','version':'1'}} if r['method']=='initialize' else {'tools':[{'name':'http_echo','description':'HTTP echo','inputSchema':{'type':'object'}}]} if r['method']=='tools/list' else {}
            data=json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}).encode()
            if self.path == '/messages':
                messages.put(data); self.send_response(202); self.end_headers(); return
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    config={'mcpServers':{'stdio':{'transport':'stdio','command':sys.executable,'args':[str(server_script)]},'http':{'transport':'http','url':f'http://127.0.0.1:{server.server_port}'},'sse':{'transport':'sse','url':f'http://127.0.0.1:{server.server_port}/sse'},'broken':{'transport':'stdio','command':str(tmp_path/'missing')}}}
    path=tmp_path/'mcp.json';path.write_text(json.dumps(config))
    settings=SettingsService(tmp_path);settings.set_config({'mcp':{'enabled':dict.fromkeys(config['mcpServers'],True)}})
    events=[];runtime=ExtensionRuntime(ExtensionSettings(settings,SecretsVault(tmp_path)),lambda:events.append(True))
    try:
        runtime.reconcile()
        assert wait(runtime,'stdio','connected')['tools'][0]['name']=='echo'
        assert wait(runtime,'http','connected')['tools'][0]['name']=='http_echo'
        assert wait(runtime,'sse','connected')['tools'][0]['name']=='http_echo'
        assert wait(runtime,'broken','error')['lastError']
        config['mcpServers']['broken']=config['mcpServers']['stdio'];path.write_text(json.dumps(config));runtime.retry('broken')
        assert wait(runtime,'broken','connected')['tools'][0]['name']=='echo'
        assert events
        print('stdio connected tools=1; HTTP connected tools=1; SSE connected tools=1; missing executable error; retry connected tools=1; broadcasts=',len(events))
    finally:runtime.close();stream_done.set();server.shutdown();server.server_close()


def test_non_ascii_skill_order_matches_chromium_fixture(tmp_path):
    # Actual Chromium Intl localeCompare baseline, out/extensions-complete/deva-sort.json.
    from mvvm.services.skill_store import SkillStore
    names = ['中文', 'Zulu', '日本語', 'éclair', 'Álpha', 'alpha', 'ä']
    for i, name in enumerate(names):
        folder = tmp_path / 'skills' / f'skill-{i}'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text(f'---\nname: {name}\n---\nBody')
    assert [row['name'] for row in SkillStore(tmp_path).list_skills() if row['source'] != 'builtin'] == [
        'ä', 'alpha', 'Álpha', 'éclair', 'Zulu', '中文', '日本語']
