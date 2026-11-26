"""Persistent MCP discovery sessions for the disk-backed extensions settings page."""
import json
import threading
from mvvm.services.mcp_runtime import McpConnection


class ExtensionRuntime:
    def __init__(self, service, changed=lambda: None):
        self.service, self.changed = service, changed
        self.states, self.jobs = {}, {}
        self.lock = threading.RLock()

    def view(self, key):
        with self.lock:
            return dict(self.states.get(key, {'status':'disconnected','tools':[],'lastError':''}))

    def publish(self, key, token, **state):
        with self.lock:
            if self.jobs.get(key, (None,))[0] is not token: return
            self.states[key] = state
        self.changed()

    def reconcile(self):
        registry = self.service.registry()
        config = self.service.read('config.json').get('mcp', {}).get('enabled', {})
        wanted = {k:v for k,v in registry.items() if config.get(k) is True}
        with self.lock:
            for key in list(self.jobs):
                signature = json.dumps(wanted.get(key), sort_keys=True)
                if key not in wanted or self.jobs[key][1] != signature:
                    self.jobs.pop(key)[0].set()
                    self.states.pop(key, None)
            for key, value in wanted.items():
                if key in self.jobs: continue
                token = threading.Event()
                self.jobs[key] = (token, json.dumps(value, sort_keys=True))
                self.states[key] = {'status':'connecting','tools':[],'lastError':''}
                threading.Thread(target=self.connect,args=(key,value,token),daemon=True).start()
        self.changed()

    def retry(self, key):
        with self.lock:
            old = self.jobs.pop(key, None)
            if old: old[0].set()
        self.reconcile()

    def connect(self, key, record, token):
        connection = None
        try:
            transport = record.get('transport', 'stdio')
            if transport not in ('stdio','http','sse'): raise ValueError('Unknown MCP transport')
            field = 'command' if transport == 'stdio' else 'url'
            if not record.get(field):
                self.publish(key,token,status='needs_config',tools=[],lastError=f'Missing {field}')
                return
            values = {}
            for name, value in record.get('env' if transport == 'stdio' else 'headers', {}).items():
                if isinstance(value, dict):
                    reference = value.get('secretRef') or name
                    secret_key = reference if reference.startswith('mcp:') else f'mcp:{key}:{reference}'
                    value = self.service.vault.get_secret(secret_key)
                    if not value:
                        self.publish(key,token,status='needs_secret',tools=[],lastError=f'Missing secret: {name}')
                        return
                values[name] = value
            params = {field: record[field], 'transport': transport}
            if transport == 'stdio': params['args'] = record.get('args', [])
            connection = McpConnection(params, json.dumps(values) if values else '', cancelled=token.is_set, timeout=8)
            connection.initialize()
            tools, cursor, seen = [], None, set()
            while True:
                result = connection.request('tools/list', {'cursor':cursor} if cursor else {})
                tools.extend({'name':row['name'],'description':row.get('description','')} for row in result.get('tools', []))
                cursor = result.get('nextCursor')
                if not cursor: break
                if cursor in seen: raise ValueError('Repeated tools cursor')
                seen.add(cursor)
            self.publish(key,token,status='connected',tools=tools,lastError='')
            while not token.wait(5): connection.request('ping')
        except Exception as exc:
            self.publish(key,token,status='error',tools=[],lastError=f'{type(exc).__name__}: {exc}')
        finally:
            if connection: connection.close()

    def close(self):
        with self.lock:
            for token, _ in self.jobs.values(): token.set()
            self.jobs.clear()
