"""Catalogue parity and real QML live-language/persistence regression tests."""
import json
import os
from pathlib import Path

from native_i18n import MESSAGES, SUPPORTED, LANGUAGE_NAMES, translate
from test_qml_window_controls import qapp, _build_window, _pump, _find_item


def test_catalogue_coverage():
    assert SUPPORTED == ('zh-CN', 'en')
    assert LANGUAGE_NAMES == ('简体中文', 'English')
    assert MESSAGES['en'].keys() == MESSAGES['zh-CN'].keys()
    import re
    for key in MESSAGES['en']:
        # Deva deliberately uses total n in Chinese and remaining rest in English.
        if key in ('extensions.rolesSummary', 'chat.deliver.collapsedMany'):
            continue
        assert set(re.findall(r'\{\w+\}', MESSAGES['en'][key])) == set(re.findall(r'\{\w+\}', MESSAGES['zh-CN'][key])), key
    assert translate('zh-CN', 'unknown.key') == 'unknown.key'
    assert translate('en', 'unknown.key') == 'unknown.key'
    assert translate('en', 'chat.panel.approx', n=12) == '~12'


def _texts(item):
    value = item.property('text')
    result = [value] if isinstance(value, str) else []
    for child in item.childItems():
        result.extend(_texts(child))
    return result


def test_live_language_and_persistence(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QLocale
    from mvvm.services.settings_service import SettingsService
    if os.environ.get("I18N_TEST_FONT"):
        from PySide6.QtGui import QFontDatabase
        assert QFontDatabase.addApplicationFont(os.environ["I18N_TEST_FONT"]) >= 0
    w, bridge, ticker, engine = _build_window(tmp_path, monkeypatch, sessions=[('empty', '')])
    try:
        for system, expected in [('zh_TW', 'zh-CN'), ('en_US', 'en'), ('fr_FR', 'en')]:
            monkeypatch.setattr(QLocale, 'system', lambda value=system: QLocale(value))
            assert bridge.locale == expected
        evidence = os.environ.get('I18N_EVIDENCE')
        for locale, heading, send in [('zh-CN', '通用', '发送'), ('en', 'General', 'Send')]:
            assert bridge.setLanguage(locale)
            assert SettingsService(bridge._settings.home).get('locale') == locale
            assert bridge.locale == locale
            for theme in ['light', 'dark']:
                assert bridge.setTheme(theme)
                for page in ['settings-general', 'chat']:
                    w.setProperty('page', page)
                    _pump(qapp, .3)
                    texts = _texts(w.contentItem())
                    assert send in texts
                    if page == 'settings-general':
                        assert heading in texts
                        assert _find_item(w.contentItem(), 'settingsLanguageChoice').property('current') == (0 if locale == 'zh-CN' else 1)
                    if evidence:
                        assert w.grabWindow().save(str(Path(evidence) / f'{locale}-{theme}-{page}.png'))
        assert not bridge.setLanguage('fr')
        assert bridge.locale == 'en'
    finally:
        ticker.stop()
        w.close()
        engine.deleteLater()


def test_body_preserves_model_and_user_text():
    from types import SimpleNamespace
    from qml_shell_sessions import transcript_markdown
    messages = [SimpleNamespace(role='assistant', content='不要翻译 Settings 或 General')]
    assert '不要翻译 Settings 或 General' in transcript_markdown(messages, lang='en')
    assert transcript_markdown([], pending_user='原文', streaming='回答', lang='en') == '## You\n\n原文\n\n## Assistant\n\n回答'
