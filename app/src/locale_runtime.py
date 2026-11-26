"""Language selection shared by legacy widgets, services and build commands."""
import json
import os
import sys
from pathlib import Path

_catalogues = None


def selected_locale(argv=None, environ=None):
    env = os.environ if environ is None else environ
    args = sys.argv[1:] if argv is None else argv
    explicit = None
    for i, arg in enumerate(args):
        if arg.startswith('--lang='):
            explicit = arg.split('=', 1)[1]
        elif arg == '--lang' and i + 1 < len(args):
            explicit = args[i + 1]
    value = explicit or env.get('AI_UPPER_LANG')
    if not value:
        home = env.get('AI_UPPER_HOME')
        if home:
            try:
                value = json.loads((Path(home) / 'config.json').read_text(encoding='utf-8')).get('locale')
            except (OSError, ValueError):
                pass
    value = value or env.get('LC_ALL') or env.get('LC_MESSAGES') or env.get('LANG') or 'en'
    return 'zh-CN' if str(value).lower().startswith('zh') else 'en'


def catalogues():
    global _catalogues
    if _catalogues is None:
        import locales
        loader = locales.__loader__
        if hasattr(loader, 'read_data'):
            _catalogues = {loc: json.loads(loader.read_data('locales/' + loc + '.json')) for loc in ('en', 'zh-CN')}
        else:
            root = Path(locales.__file__).parent
            _catalogues = {loc: json.loads((root / (loc + '.json')).read_text(encoding='utf-8')) for loc in ('en', 'zh-CN')}
    return _catalogues


def tr(key, **values):
    text = catalogues()[selected_locale()].get(key, key)
    for name, value in values.items():
        text = text.replace('{' + name + '}', str(value))
    return text


def configure_cli(argv=None):
    import argparse
    # Resolve command-line language once; human output shares this choice.
    os.environ['AI_UPPER_LANG'] = selected_locale(argv)
    reverse = {v: k for k, v in catalogues()['en'].items()}
    argparse._ = lambda text: tr(reverse[text]) if text in reverse else text


def display_text(text):
    """Localize app-owned tool summaries at presentation, never persisted payloads."""
    import re
    value = str(text)
    for key, source in catalogues()['zh-CN'].items():
        if not key.startswith('display.'):
            continue
        names = re.findall(r'\{(p\d+)\}', source)
        parts = re.split(r'\{p\d+\}', source)
        if not names:
            if source == value:
                return tr(key)
            continue
        pattern = '(.*?)'.join(re.escape(part) for part in parts)
        match = re.fullmatch(pattern, value, re.DOTALL)
        if match:
            return tr(key, **dict(zip(names, match.groups())))
    return value
