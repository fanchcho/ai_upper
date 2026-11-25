"""Shared deva identities; session overrides never rewrite the shared default."""
import json
import os
import re
from pathlib import Path

from mvvm.services.persona_store import PersonaStore


def identity_home():
    isolated = os.environ.get('AI_UPPER_HOME')
    return Path(isolated) / 'deva' if isolated else Path.home() / '.deva'


def check_owned(path):
    """Reject redirects and foreign/group-writable identity files on POSIX."""
    if path.is_symlink():
        raise PermissionError('Identity path must not be a symlink')
    if path.exists() and os.name == 'posix':
        stat = path.stat()
        if stat.st_uid != os.getuid() or stat.st_mode & 0o022:
            raise PermissionError('Identity path must be owned by current user and not group/world writable')


def shared_store():
    root = identity_home()
    check_owned(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    from mvvm.services.plugin_layout import migrate_legacy
    migrate_legacy(root)
    check_owned(root / 'personas')
    return PersonaStore(root)


def selected(service, session_id=None):
    ids = [row['id'] for row in service.identities()]
    path = service.identity_root() / 'config.json'
    check_owned(path)
    config = json.loads(path.read_text()) if path.exists() else {}
    wanted = session_id or config.get('personas', {}).get('selected', 'general')
    return wanted if wanted in ids else ('general' if 'general' in ids else ids[0])


def apply_input(service, session, text):
    command = re.fullmatch(r'/?deva:identity(?:\s+(.*))?', text.strip(), re.I)
    prefix = re.match(r'^@deva:([a-z][a-z0-9_-]{0,63})(?:[\s，,]+|$)', text, re.I)
    if not command and not prefix: return text, None
    ids = [row['id'] for row in service.identities()]
    token = ((command.group(1) or '').strip().split() or [''])[0].lower() if command else prefix.group(1).lower()
    if token == 'deva': token = 'general'
    if command and token in ('default', 'off', 'reset', 'clear', '默认'):
        session.personaId = None
    elif token and token not in ('list', '查看'):
        if token not in ids:
            if prefix: return text, None
            raise ValueError('未知身份：' + token + '（可选：' + ' / '.join(ids) + '）')
        session.personaId = token
    if command:
        current = selected(service, session.personaId)
        return text, f'本会话身份：{current}；可选 {" / ".join(ids)}；/deva:identity default 回到默认。'
    return text[prefix.end():].strip() or '继续', None
