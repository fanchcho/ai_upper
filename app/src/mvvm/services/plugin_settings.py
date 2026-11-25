"""Desktop equivalents for scoped plugin settings. Secrets never enter public views."""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from mvvm.services.model_resolve import ResolvedModel
from mvvm.services.persona_store import is_safe_id
from mvvm.services.chat_session_store import write_file_atomic


def scope_key():
    # Desktop has an OS identity; hosted deployments must inject authenticated scope.
    identity = os.environ.get('AI_UPPER_USER_ID', str(os.getuid()) if hasattr(os, 'getuid') else os.environ.get('USERNAME', 'local'))
    profile = os.environ.get('AI_UPPER_PROFILE', 'default')
    return hashlib.sha256(json.dumps([identity, profile]).encode()).hexdigest()


class PluginSettings:
    def __init__(self, settings, vault):
        self.settings, self.vault = settings, vault
        self.scope = scope_key()

    def data(self):
        return self.settings.get('pluginScopes', {}).get(self.scope, {})

    def write(self, **patch):
        scopes = self.settings.get('pluginScopes', {})
        scopes[self.scope] = dict(scopes.get(self.scope, {}), **patch)
        self.settings.set_config({'pluginScopes': scopes})

    def key_id(self, kind, name):
        return 'plugin-' + hashlib.sha256(f'{self.scope}:{kind}:{name}'.encode()).hexdigest()

    def custom(self):
        value = dict(self.data().get('customModel', {}))
        value['hasKey'] = bool(value.get('baseUrl') and self.vault.has_secret(self.key_id('model', value['baseUrl'])))
        return value

    def save_custom(self, base, model, key=None):
        base, model = base.strip().rstrip('/'), model.strip()
        if base:
            parsed = urlsplit(base)
            if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('Base URL must be an HTTP(S) address without credentials, query or fragment')
            if not model or any(ord(c) < 32 for c in model):
                raise ValueError('Model name is required')
        old = self.custom().get('baseUrl', '')
        self.write(customModel={'baseUrl': base, 'model': model if base else ''})
        if old != base:
            # Address changes never reuse a previously saved key, even when switching back.
            if old:
                self.vault.delete_secret(self.key_id('model', old))
            if base:
                self.vault.delete_secret(self.key_id('model', base))
        if base and key is not None:
            if key:
                if not self.vault.set_secret(self.key_id('model', base), key).get('ok'):
                    raise OSError('Credential store is unavailable')
            else:
                self.vault.delete_secret(self.key_id('model', base))
        return self.custom()

    def route(self):
        value = self.custom()
        if not value.get('baseUrl'):
            return None
        return ResolvedModel('openai', self.key_id('model', value['baseUrl']), value['baseUrl'], value['model'])

    def servers(self):
        return [dict(v, id=k, hasKey=self.vault.has_secret(self.key_id('mcp', k)))
                for k, v in self.data().get('mcp', {}).items()]

    def save_server(self, name, config, secret=None):
        if not is_safe_id(name):
            raise ValueError('Invalid server ID')
        if 'command' in config and not isinstance(config['command'], str):
            raise ValueError('command must be a string')
        if 'url' in config and not isinstance(config['url'], str):
            raise ValueError('url must be a string')
        # Executable environment/headers are credentials and must not enter the view.
        allowed = {'url', 'command', 'args', 'enabled'}
        if set(config) - allowed:
            raise ValueError('Only url, command, args, enabled are public fields')
        if not config.get('url') and not config.get('command'):
            raise ValueError('Server requires url or command')
        if config.get('url'):
            u = urlsplit(config['url'])
            if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or u.query or u.fragment:
                raise ValueError('Invalid server URL')
        if not isinstance(config.get('args', []), list) or any(not isinstance(v, str) for v in config.get('args', [])):
            raise ValueError('args must be an array of strings')
        servers = self.data().get('mcp', {})
        old = servers.get(name, {})
        servers[name] = dict(config, enabled=bool(config.get('enabled', True)))
        self.write(mcp=servers)
        from mvvm.services.mcp_runtime import stop_server
        stop_server(self.scope, name)
        if (old.get('url'), old.get('command')) != (config.get('url'), config.get('command')):
            self.vault.delete_secret(self.key_id('mcp', name))
        if secret is not None:
            if secret:
                if not self.vault.set_secret(self.key_id('mcp', name), secret).get('ok'):
                    raise OSError('Credential store is unavailable')
            else: self.vault.delete_secret(self.key_id('mcp', name))

    def delete_server(self, name):
        servers = self.data().get('mcp', {})
        servers.pop(name, None)
        self.write(mcp=servers)
        from mvvm.services.mcp_runtime import stop_server
        stop_server(self.scope, name)
        self.vault.delete_secret(self.key_id('mcp', name))

    def identity_root(self):
        from mvvm.services.plugin_identity import identity_home
        return identity_home()

    def identities(self):
        from mvvm.services.plugin_identity import shared_store, check_owned
        root = shared_store().dir
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not any(root.glob('*.md')):
            path = root / 'general.md'
            if not path.exists():
                write_file_atomic(path, '---\nname: Assistant\n---\nYou are a helpful assistant.\n')
        rows = []
        for p in sorted(root.glob('*.md')):
            if is_safe_id(p.stem):
                check_owned(p)
                rows.append({'id': p.stem, 'text': p.read_text(encoding='utf-8')})
        return rows

    def identity_prompt(self, identity_id):
        from mvvm.services.plugin_identity import shared_store, selected
        identity_id = selected(self, identity_id)
        record = shared_store().get(identity_id)
        return record['prompt'] if record else ''

    def save_identity(self, name, text):
        if not is_safe_id(name): raise ValueError('Invalid identity ID')
        from mvvm.services.plugin_identity import shared_store, check_owned
        root = shared_store().dir
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = root / (name + '.md')
        check_owned(path)
        write_file_atomic(path, text)
