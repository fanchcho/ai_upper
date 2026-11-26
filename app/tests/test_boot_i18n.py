"""Bootstrap remains usable before the app and its catalogue can be imported."""
import importlib.util
import json
from pathlib import Path
import sys

from locale_runtime import catalogues, selected_locale


def loader():
    path=Path('tools/ai_upper/egg_loader.py')
    spec=importlib.util.spec_from_file_location('isolated_egg_loader',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_boot_catalogue_and_ascii():
    module=loader()
    assert len(module._BOOT_MESSAGES)==8
    Path('tools/ai_upper/egg_loader.py').read_text().encode('ascii')
    for key, pair in module._BOOT_MESSAGES.items():
        assert pair==[catalogues()[lang][key] for lang in ('en','zh-CN')]


def test_boot_precedence_and_errors(tmp_path,monkeypatch):
    module=loader()
    monkeypatch.setenv('AI_UPPER_HOME',str(tmp_path))
    monkeypatch.delenv('AI_UPPER_LANG',raising=False)
    monkeypatch.setenv('LC_ALL','zh_CN.UTF-8')
    monkeypatch.setattr(sys,'argv',['app'])
    key='finish.d0f213d4d48e'
    for config,env,argv,expected in [(None,None,[], 'zh-CN'),('en',None,[],'en'),('en','zh-CN',[],'zh-CN'),('zh-CN','zh-CN',['--lang','en'],'en')]:
        if config:(tmp_path/'config.json').write_text(json.dumps({'locale':config}))
        if env:monkeypatch.setenv('AI_UPPER_LANG',env)
        monkeypatch.setattr(sys,'argv',['app']+argv)
        assert selected_locale()==expected
        assert module._boot_tr(key)==catalogues()[expected][key]
        try:module._key_bytes('not-a-key')
        except ValueError as exc:assert str(exc)==catalogues()[expected][key]
        else:assert False
