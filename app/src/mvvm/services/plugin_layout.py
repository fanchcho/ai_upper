"""One-time legacy layout migration; existing shared values always win."""
import json
import shutil
import uuid

from mvvm.services.chat_session_store import write_file_atomic
from mvvm.services.settings_service import SettingsService


def migrate_legacy(root):
    from mvvm.services.plugin_identity import check_owned
    legacy = root / 'deva-agent'
    if not legacy.exists(): return {'migrated': False}
    check_owned(legacy)
    for path in legacy.rglob('*'): check_owned(path)
    for name in ('config.json', 'mcp.json'): check_owned(root / name)
    def read(path):
        if not path.exists(): return {}
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict): raise ValueError('Legacy file must contain a JSON object')
        return value
    current = read(root / 'config.json')
    settings = SettingsService(root)
    if settings.get_config_sync() != current:
        raise OSError('Configuration changed while starting migration')
    identities = read(legacy / 'identity.json')
    sessions = read(legacy / 'sessions.json')
    mcp = read(legacy / 'mcp-servers.json')
    mcp_path = root / 'mcp.json'
    raw = mcp_path.read_text(encoding='utf-8') if mcp_path.exists() else None
    shared_mcp = read(mcp_path)
    backup_root = root.parent / ('.deva-backups' if root.name == '.deva' else 'deva-backups')
    check_owned(backup_root)
    backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = backup_root / ('deva-agent-' + uuid.uuid4().hex)
    shutil.copytree(legacy, backup)
    personas = dict(current.get('personas', {}))
    if isinstance(identities.get('selected'), str): personas.setdefault('selected', identities['selected'])
    selection = dict(personas.get('sessionSelected', {}))
    for sid, value in sessions.get('sessions', {}).items():
        if isinstance(value, dict) and isinstance(value.get('identity'), str): selection.setdefault(sid, value['identity'])
    personas['sessionSelected'] = selection
    servers = dict(shared_mcp.get('mcpServers', {}))
    mcp_section = dict(current.get('mcp', {}))
    enabled = dict(mcp_section.get('enabled', {}))
    for name, value in mcp.get('servers', {}).items():
        if not isinstance(value, dict): raise ValueError('Invalid legacy MCP entry')
        servers.setdefault(name, {key: val for key, val in value.items() if key != 'enabled'})
        enabled.setdefault(name, value.get('enabled') is not False)
    shared_mcp['mcpServers'] = servers
    current_raw = mcp_path.read_text(encoding='utf-8') if mcp_path.exists() else None
    if current_raw != raw: raise OSError('MCP configuration changed externally; migration stopped')
    write_file_atomic(mcp_path, json.dumps(shared_mcp, ensure_ascii=False, indent=2))
    mcp_section['enabled'] = enabled
    # Read/write the latest shared config with expectedRaw protection; preserve other keys.
    settings.set_config({'personas': personas, 'mcp': mcp_section})
    shutil.rmtree(legacy)
    return {'migrated': True, 'backup': str(backup)}
