"""Shared catalogue; unknown keys follow Deva's literal-key fallback."""
import json
from importlib.resources import files

SUPPORTED = ('zh-CN', 'en')
def load_messages():
    import locales
    loader = locales.__loader__
    # The Windows memory egg loader exposes read_data, not ResourceReader.
    if hasattr(loader, "read_data"):
        return {locale: json.loads(loader.read_data("locales/" + locale + ".json"))
                for locale in SUPPORTED}
    return {locale: json.loads(files('locales').joinpath(locale + '.json').read_text(encoding='utf-8'))
            for locale in SUPPORTED}


MESSAGES = load_messages()
LANGUAGE_NAMES = (MESSAGES['zh-CN']['finish.language.chinese'], MESSAGES['en']['finish.language.english'])


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
