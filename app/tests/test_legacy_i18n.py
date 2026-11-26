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
