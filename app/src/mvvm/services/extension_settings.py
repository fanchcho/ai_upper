"""Disk-backed extension detail operations; never return secret values to QML."""
import json
from pathlib import Path
from mvvm.services.chat_session_store import write_file_atomic
from mvvm.services.persona_store import PersonaStore, is_safe_id
from mvvm.services.skill_store import SkillStore, RESERVED_IDS


class ExtensionSettings:
    def __init__(self, settings, vault):
        self.settings, self.vault = settings, vault
        self.home = settings.home

    def read(self, name):
        path = self.home / name
        if not path.exists():
            return {}
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError(f'{name}: expected an object')
        return value

    def registry(self):
        value = self.read('mcp.json').get('mcpServers', {})
        if not isinstance(value, dict):
            raise ValueError('mcp.json: mcpServers must be an object')
        for key, item in value.items():
            if not is_safe_id(key) or not isinstance(item, dict):
                raise ValueError(f'mcp.json: invalid registration {key}')
        return value

    def errors(self):
        errors = []
        for name in ['config.json', 'mcp.json']:
            try:
                self.read(name)
                if name == 'mcp.json': self.registry()
            except (OSError, ValueError) as exc:
                errors.append(f'{name}: {exc}')
        folder = self.home / 'skills'
        try:
            for path in folder.iterdir() if folder.exists() else []:
                if path.is_dir() and path.name not in RESERVED_IDS:
                    try: (path / 'SKILL.md').read_text(encoding='utf-8')
                    except (OSError, ValueError) as exc: errors.append(f'{path.name}/SKILL.md: {exc}')
        except OSError as exc: errors.append(str(exc))
        return errors

    def detail(self, kind, key):
        if not is_safe_id(key): raise ValueError('Invalid extension id')
        config = self.read('config.json')
        if kind == 'skill':
            if key in RESERVED_IDS: raise ValueError('Built-in skill is read-only')
            record = SkillStore(self.home).get(key)
            if record is None: raise ValueError('Skill no longer exists')
        elif kind == 'mcp':
            record = dict(self.registry()[key], id=key)
            record['name'] = record.get('name') or key
            record['enabled'] = config.get('mcp', {}).get('enabled', {}).get(key) is True
            record['roles'] = config.get('mcp', {}).get('roles', {}).get(key)
            for field in ['env', 'headers']:
                rows=[]
                for name, value in record.get(field, {}).items():
                    secret = isinstance(value, dict)
                    rows.append({'key': name, 'value': '' if secret else str(value), 'secret': secret,
                                 'configured': self.vault.has_secret(f'mcp:{key}:{name}') if secret else False})
                record[field] = rows
        else: raise ValueError('Invalid extension kind')
        record['kind'] = kind
        from mvvm.services.plugin_identity import shared_store
        record['personas'] = [{'id': p['id'], 'name': p['name']} for p in shared_store().list_personas()]
        return record

    def update(self, kind, key, patch):
        self.detail(kind, key)  # Validate existence and the built-in boundary before writing.
        if 'roles' in patch or 'enabled' in patch:
            config = self.read('config.json')
            section = dict(config.get('skills' if kind == 'skill' else 'mcp', {}))
            if 'roles' in patch:
                roles = patch['roles']
                if roles is not None and (not isinstance(roles, list) or any(not is_safe_id(p) for p in roles)):
                    raise ValueError('Invalid roles')
                section['roles'] = dict(section.get('roles', {}), **{key: roles or None})
            if 'enabled' in patch:
                section['enabled'] = dict(section.get('enabled', {}), **{key: patch['enabled'] is True})
            self.settings.reload()
            self.settings.set_config({'skills' if kind == 'skill' else 'mcp': section})
        fields = set(patch) - {'roles', 'enabled'}
        if not fields: return
        if kind != 'mcp' or fields - {'transport', 'command', 'args', 'url', 'env', 'headers'}:
            raise ValueError('Unsupported extension field')
        data = self.read('mcp.json'); record = dict(data['mcpServers'][key])
        for field in fields:
            value = patch[field]
            if field in ('env', 'headers'):
                value = {r['key']: {'secretRef': f'mcp:{key}:{r["key"]}'} if r.get('secret') else r.get('value', '')
                         for r in value if r.get('key', '').strip()}
            if field == 'transport' and value not in ['stdio', 'sse', 'http']: raise ValueError('Invalid transport')
            if field == 'args' and (not isinstance(value, list) or any(not isinstance(a, str) for a in value)): raise ValueError('Invalid arguments')
            record[field] = value
        data['mcpServers'][key] = record
        write_file_atomic(self.home / 'mcp.json', json.dumps(data, ensure_ascii=False, indent=2))

    def secret(self, key, field, value):
        record = self.registry()[key]
        if not any(field in record.get(group, {}) for group in ['env', 'headers']): raise ValueError('Unknown secret field')
        result = self.vault.set_secret(f'mcp:{key}:{field}', value)
        if not result.get('ok'): raise OSError('Secret could not be saved')

    def remove(self, kind, key):
        self.detail(kind, key)
        if kind == 'skill':
            from utils.qt_compat import QtCore
            result = QtCore.QFile.moveToTrash(str(self.home / 'skills' / key))
            if not (result[0] if isinstance(result, tuple) else result): raise OSError('Cannot move skill to trash')
        else:
            data = self.read('mcp.json'); record = data['mcpServers'].pop(key)
            write_file_atomic(self.home / 'mcp.json', json.dumps(data, ensure_ascii=False, indent=2))
            for group in ['env', 'headers']:
                for field, value in record.get(group, {}).items():
                    if isinstance(value, dict): self.vault.delete_secret(f'mcp:{key}:{field}')
        self.settings.reload()
        section_name = 'skills' if kind == 'skill' else 'mcp'
        section = dict(self.settings.get(section_name, {}))
        for field in ['enabled', 'roles']:
            section[field] = {k:v for k,v in section.get(field, {}).items() if k != key}
        self.settings.set_config({section_name: section})
