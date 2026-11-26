import json
import pytest
from mvvm.services.extension_settings import ExtensionSettings
from mvvm.services.settings_service import SettingsService
from mvvm.services.secrets_vault import SecretsVault


@pytest.fixture
def ext(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_UPPER_HOME', str(tmp_path))
    monkeypatch.setenv('DEVA_SECRETS_BACKEND', 'file')
    for key in ['alpha', 'beta']:
        folder=tmp_path/'skills'/key;folder.mkdir(parents=True)
        (folder/'SKILL.md').write_text(f'---\nname: {key}\ndescription: test\n---\n# Instructions\n')
    (tmp_path/'mcp.json').write_text(json.dumps({'mcpServers': {'local': {'name':'Local', 'transport':'stdio','command':'example','env':{}}}}))
    return ExtensionSettings(SettingsService(tmp_path), SecretsVault(tmp_path))


def test_details_and_restart(ext):
    assert ext.detail('skill','alpha')['instructions'].startswith('# Instructions')
    ext.update('skill','alpha', {'enabled':False, 'roles':['general']})
    ext.update('mcp','local', {'enabled':True, 'args':['a','b'], 'roles':['general']})
    other=ExtensionSettings(SettingsService(ext.home),ext.vault)
    assert other.detail('skill','alpha')['enabled'] is False
    assert other.detail('skill','alpha')['roles']==['general']
    assert other.detail('mcp','local')['enabled'] is True
    assert other.detail('mcp','local')['args']==['a','b']
    with pytest.raises(ValueError):ext.update('skill','create-skill',{'enabled':False})


def test_secret_and_delete(ext):
    ext.update('mcp','local',{'env':[{'key':'TOKEN','secret':True}]})
    ext.secret('local','TOKEN','sensitive-test-value')
    detail=ext.detail('mcp','local')
    assert detail['env'][0]['configured'] is True
    assert 'sensitive-test-value' not in json.dumps(detail)
    assert 'sensitive-test-value' not in (ext.home/'mcp.json').read_text()
    ext.remove('mcp','local')
    assert ext.registry()=={}
    assert not ext.vault.has_secret('mcp:local:TOKEN')


def test_corrupt_registry_is_visible_and_not_overwritten(ext):
    (ext.home/'mcp.json').write_text('{invalid')
    assert ext.errors()
    with pytest.raises(ValueError):ext.update('mcp','local',{'command':'overwrite'})
    assert (ext.home/'mcp.json').read_text()=='{invalid'
