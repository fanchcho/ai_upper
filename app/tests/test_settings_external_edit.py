"""The desktop model mirror must not lose edits made by another process."""
import json
import pytest
from mvvm.services.settings_service import SettingsService


def test_stale_settings_write_preserves_external_model_edit(tmp_path):
    settings = SettingsService(tmp_path)
    settings.set_config({'models': {'activeModelId': 'p:old'}, 'language': 'en'})
    external = {'models': {'activeModelId': 'p:new:variant'}, 'language': 'en'}
    settings.path.write_text(json.dumps(external), encoding='utf-8')
    with pytest.raises(OSError, match='changed externally'):
        settings.set_config({'theme': 'dark'})
    assert json.loads(settings.path.read_text()) == external
    settings.reload()
    settings.set_config({'theme': 'dark'})
    assert json.loads(settings.path.read_text()) == dict(external, theme='dark')
