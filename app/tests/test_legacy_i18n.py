import json
import subprocess
import os
from pathlib import Path
from locale_runtime import selected_locale, tr, catalogues


def test_precedence(tmp_path, monkeypatch):
    (tmp_path/'config.json').write_text('{"locale":"zh-CN"}')
    env={'AI_UPPER_HOME':str(tmp_path),'LANG':'en_US','LC_ALL':'en_US'}
    assert selected_locale([],env)=='zh-CN'
    assert selected_locale(['--lang','en'],env)=='en'
    assert selected_locale([],dict(env,AI_UPPER_LANG='en'))=='en'
    assert selected_locale([],{'LC_ALL':'zh_TW','LANG':'en_US'})=='zh-CN'
    assert selected_locale([],{'LANG':'fr_FR'})=='en'
    monkeypatch.setenv('AI_UPPER_LANG','zh-CN')
    assert tr('missing.key')=='missing.key'
    assert catalogues()['en'].keys()==catalogues()['zh-CN'].keys()


def test_widget_and_machine_contract(monkeypatch):
    from mvvm.services.provider_gateway import http_error
    for lang in ['en','zh-CN']:
        monkeypatch.setenv('AI_UPPER_LANG',lang)
        error=http_error(401,'')
        assert error.kind=='auth'
    import ast
    source=Path('app/src/mvvm/views/settings_pane.py').read_text()
    assert "TITLE = tr(" in source
    assert "KEY_PLACEHOLDER = tr(" in source
    assert ast.parse(source)


def test_tool_summary_translates_without_mutating_protocol(monkeypatch):
    from mvvm.views.transcript_render import tool_card_title
    entry={'name':'read_file','summary':'读取失败','text':'user content','is_error':True}
    original=dict(entry)
    monkeypatch.setenv('AI_UPPER_LANG','en')
    assert '读取失败' not in tool_card_title(entry)
    assert entry==original
    monkeypatch.setenv('AI_UPPER_LANG','zh-CN')
    assert '读取失败' in tool_card_title(entry)


def test_tool_body_translates_preserving_bytes(monkeypatch):
    from mvvm.views.transcript_render import transcript_html
    from markdown.document import LIGHT, DARK
    entry={'role':'tool','name':'read_file','text':'读取失败：example.txt','summary':'读取失败','is_error':True}
    before=json.dumps(entry,ensure_ascii=False,sort_keys=True).encode()
    monkeypatch.setenv('AI_UPPER_LANG','en')
    english=transcript_html([entry],DARK)
    assert '读取失败' not in english
    assert 'example.txt' in english and DARK.fg in english
    monkeypatch.setenv('AI_UPPER_LANG','zh-CN')
    chinese=transcript_html([entry],LIGHT)
    assert '读取失败' in chinese and english!=chinese
    assert json.dumps(entry,ensure_ascii=False,sort_keys=True).encode()==before


def test_tool_display_keeps_model_payload_and_saved_bytes(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from locale_runtime import display_text
    from mvvm.services.tool_results import tool_result_message
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.views.transcript_render import transcript_html
    raw='读取失败：缺少有效的 path 参数\n（已中止）'
    message=tool_result_message(SimpleNamespace(id='call-1'),raw,True)
    store=ChatSessionStore(tmp_path)
    store.ensure_session('display-test')
    store.append_message('display-test',message)
    path=store.chats_dir/'display-test.json'
    before=path.read_bytes()
    monkeypatch.setenv('AI_UPPER_LANG','en')
    english=transcript_html([dict(role='tool',name='read_file',text=raw,is_error=True)])
    assert '读取失败' not in english and 'Missing valid path parameter' in english
    assert message.content[0].content.encode()==raw.encode()
    assert path.read_bytes()==before
    assert display_text('1: 读取失败：用户正文')=='1: 读取失败：用户正文'
    recovery=json.dumps(dict(status='interrupted_unknown',reason='中断时结果未知，未自动重试；先核对实际状态再决定新操作'),ensure_ascii=False)
    shown=json.loads(display_text(recovery))
    assert shown['status']=='interrupted_unknown'
    assert shown['reason'].startswith('Execution result')
    monkeypatch.setenv('AI_UPPER_LANG','zh-CN')
    assert display_text(raw)==raw
    assert path.read_bytes()==before


def test_network_errors_follow_language_after_import(monkeypatch):
    import httpx
    from mvvm.services.http_client import describe_net_error
    monkeypatch.setenv('AI_UPPER_LANG','en')
    assert describe_net_error(httpx.WriteTimeout(''))=='Write timeout'
    monkeypatch.setenv('AI_UPPER_LANG','zh-CN')
    assert describe_net_error(httpx.WriteTimeout(''))=='发送超时'
