import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from mvvm.services.plugin_settings import PluginSettings
from mvvm.services.settings_service import SettingsService
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.provider_setup import ModelGateway
from mvvm.services.provider_gateway import GenerateRequest, StreamError, TextDelta
from mvvm.models.chat_models import Message

@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_UPPER_HOME', str(tmp_path))
    monkeypatch.setenv('DEVA_SECRETS_BACKEND', 'file')
    return PluginSettings(SettingsService(tmp_path), SecretsVault(tmp_path))


def test_scope_and_keys(service, monkeypatch):
    service.save_custom('https://one.test/v1', 'model:a', 'test-secret')
    assert service.custom()['hasKey']
    assert 'test-secret' not in json.dumps(service.custom())
    service.save_custom('https://two.test', 'model:b')
    assert not service.custom()['hasKey']
    service.save_custom('https://one.test/v1', 'model:a')
    assert not service.custom()['hasKey']
    monkeypatch.setenv('AI_UPPER_PROFILE', 'different')
    assert PluginSettings(service.settings, service.vault).route() is None
    service.save_custom('', '')
    assert service.route() is None


def test_mcp_crud(service):
    service.save_server('server', {'url':'https://mcp.test', 'enabled':True}, 'mcp-secret')
    assert service.servers()[0]['hasKey']
    assert 'mcp-secret' not in json.dumps(service.servers())
    service.save_server('server', {'url':'https://mcp.test', 'enabled':False})
    assert service.servers()[0]['enabled'] is False
    service.delete_server('server')
    assert service.servers() == []
    with pytest.raises(ValueError): service.save_server('../escape', {'command':'test'})


def test_identity_disk_is_authoritative(service):
    assert service.identities()[0]['id'] == 'general'
    service.save_identity('general', 'external authoritative identity')
    other = PluginSettings(service.settings, service.vault)
    assert other.identities() == [{'id':'general','text':'external authoritative identity'}]
    with pytest.raises(ValueError): service.save_identity('../escape', 'bad')


def test_actual_http_route_and_failure(service):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, data['model'], self.headers.get('Authorization')))
            if data['model']=='fail':
                self.send_response(503); self.end_headers(); self.wfile.write(b'{"error":{"message":"test failure"}}'); return
            self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
            self.wfile.write(b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}/custom'
        service.save_custom(base, 'direct', 'test-key')
        gw=ModelGateway(service.settings,service.vault)
        async def run():
            provider, model=gw.turn_provider(None,'missing:catalog')
            return [x async for x in provider.stream(GenerateRequest(model=model,messages=[Message(role='user',content='hello')]))]
        assert any(isinstance(x,TextDelta) and x.text=='ok' for x in asyncio.run(run()))
        service.save_custom(base,'fail')
        assert any(isinstance(x,StreamError) for x in asyncio.run(run()))
        assert requests == [('/custom/chat/completions','direct','Bearer test-key'),('/custom/chat/completions','fail','Bearer test-key')]
    finally:
        server.shutdown(); server.server_close(); t.join()


def test_conflict_does_not_delete_credentials(service):
    service.save_custom('https://old.test','old','keep-secret')
    external=json.loads(service.settings.path.read_text())
    external['externalEdit']=True
    service.settings.path.write_text(json.dumps(external))
    with pytest.raises(OSError,match='changed externally'):
        service.save_custom('https://new.test','new')
    assert service.vault.get_secret(service.key_id('model','https://old.test'))=='keep-secret'
    assert json.loads(service.settings.path.read_text())==external


def test_disk_mcp_discovery_and_toggle(service):
    registry = {'mcpServers': {
        'disk-one': {'name': 'Zulu', 'command': 'example', 'env': {'TOKEN': 'private'}},
        'disk-two': {'name': 'Alpha', 'command': 'example'},
        '../bad': {'command': 'example'},
    }}
    path = service.settings.home / 'mcp.json'
    path.write_text(json.dumps(registry))
    service.settings.set_config({'mcp': {'enabled': {'disk-one': True}, 'roles': {'disk-one': ['general']}}})
    rows = service.servers(include_registered=True)
    assert [r['id'] for r in rows] == ['disk-two', 'disk-one']
    assert [r['enabled'] for r in rows] == [False, True]
    assert 'private' not in json.dumps(rows)
    assert service.set_server_enabled('disk-one', False)
    assert service.settings.get('mcp')['roles'] == {'disk-one': ['general']}
    assert json.loads(path.read_text()) == registry
    assert not PluginSettings(service.settings, service.vault).servers(include_registered=True)[1]['enabled']
    service.save_server('disk-one', {'command': 'override', 'enabled': True})
    assert len(service.servers(include_registered=True)) == 2
    assert next(r for r in service.servers(include_registered=True) if r['id'] == 'disk-one')['command'] == 'override'
    assert service.set_server_enabled('disk-one', False)
    assert not next(r for r in service.servers(include_registered=True) if r['id'] == 'disk-one')['enabled']


def test_disk_mcp_empty_and_invalid(service):
    assert service.servers(include_registered=True) == []
    path = service.settings.home / 'mcp.json'
    for raw in ['{', '[]', '{"mcpServers": []}', '{"mcpServers": {"broken": null}}']:
        path.write_text(raw)
        assert service.servers(include_registered=True) == []
    assert not service.set_server_enabled('missing', True)
