"""Shared catalogue; unknown keys follow Deva's literal-key fallback."""
import json
from importlib.resources import files

SUPPORTED = ('zh-CN', 'en')
LANGUAGE_NAMES = ('简体中文', 'English')
MESSAGES = {locale: json.loads(files('locales').joinpath(locale + '.json').read_text(encoding='utf-8'))
            for locale in SUPPORTED}


def translate(locale, key, **values):
    text = MESSAGES.get(locale, MESSAGES['en']).get(key, key)
    for name, value in values.items():
        text = text.replace('{' + name + '}', str(value))
    return text


def translate_error(locale, message):
    """Translate known application errors; retain external diagnostics verbatim."""
    for key, source in MESSAGES["en"].items():
        if key.startswith("native.error") and source == message:
            return translate(locale, key)
    return message
