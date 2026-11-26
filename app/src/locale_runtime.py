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
    """Localize known tool templates in a display copy, preserving protocol data.

    Matching is against complete templates or complete lines, never arbitrary
    substrings in file contents. Unknown upstream text and numbered source lines
    remain verbatim. Structured recovery results retain their JSON field names.
    """
    import re
    value = str(text)
    if selected_locale() == 'zh-CN':
        return value
    if value.startswith('{'):
        try:
            record = json.loads(value)
        except ValueError:
            record = None
        if isinstance(record, dict) and record.get('status') == 'interrupted_unknown' and isinstance(record.get('reason'), str):
            record['reason'] = display_text(record['reason'])
            return json.dumps(record, ensure_ascii=False)
    for key, source in catalogues()['zh-CN'].items():
        if not key.startswith('display.'):
            continue
        names = re.findall(r'\{([a-zA-Z][a-zA-Z0-9_]*)\}', source)
        parts = re.split(r'\{[a-zA-Z][a-zA-Z0-9_]*\}', source)
        if not names:
            if source == value:
                return tr(key)
            continue
        pattern = '(.*?)'.join(re.escape(part) for part in parts)
        match = re.fullmatch(pattern, value, re.DOTALL)
        if match:
            fields = {name: display_text(part) if part and part != value else part
                      for name, part in zip(names, match.groups())}
            return tr(key, **fields)
    if '\n' in value:
        return '\n'.join(display_text(line) for line in value.split('\n'))
    return value
