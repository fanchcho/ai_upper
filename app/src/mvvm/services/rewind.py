"""File checkpoints and user initiated rewind; paths only come from tool records."""
import base64
import hashlib
import json
import os
import time
from pathlib import Path
from mvvm.services.chat_session_store import write_file_atomic, is_genuine_user_turn


def state(path):
    path = Path(path)
    if path.resolve() != path.absolute() or path.is_symlink():
        raise ValueError('link: 路径包含符号链接')
    if path.exists():
        stat = path.stat()
        if stat.st_nlink != 1 or not path.is_file():
            raise ValueError('link: 非普通文件或硬链接')
        if stat.st_size > 5 * 1024 * 1024:
            raise ValueError('too_large: 文件超过 5 MiB')
        return base64.b64encode(path.read_bytes()).decode('ascii')
    return None


def restore(path, data):
    if data is None:
        Path(path).unlink(missing_ok=True)
    else:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.rewind.tmp')
        mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
        with temporary.open('xb') as stream:
            stream.write(base64.b64decode(data))
        temporary.chmod(mode)
        os.replace(temporary, target)


class Rewind:
    def __init__(self, home, session_id):
        key = hashlib.sha256(session_id.encode()).hexdigest()
        self.path = Path(home) / 'data' / 'rewind' / (key + '.json')

    def read(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {'turn': 0, 'records': []}

    def save(self, data):
        # Payloads are inline, so atomically rewriting the journal also collects
        # released bytes. Keep metadata, just as the original releases blobs.
        held = sorted({r['turn'] for r in data['records'] if isinstance(r.get('pre'),str)})
        expired = set(held[:-100])
        for row in data['records']:
            if isinstance(row.get('pre'),str) and (row['turn'] in expired or row.get('recordedAt',time.time()) < time.time()-30*86400):
                row.pop('pre',None); row.pop('post',None)
                row['released'] = True
                row['error'] = 'blob_missing: 快照已按保留策略释放'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_file_atomic(self.path, json.dumps(data))

    def begin(self, session):
        data = self.read()
        data['turn'] = sum(is_genuine_user_turn(m) for m in session.messages)
        self.save(data)

    def execute(self, runtime, name, args, invoke):
        if name not in ('write_file', 'edit_file', 'run_command'):
            return invoke()
        data = self.read()
        record = {'turn': data['turn'], 'kind': name, 'recordedAt':time.time()}
        if name == 'run_command':
            record['command'] = str(args.get('command', ''))[:500]
        else:
            path = str(runtime._guarded(args))
            record['path'] = path
            try:
                record['pre'] = state(path)
            except ValueError as exc:
                record['error'] = str(exc)
        result = invoke()
        if not result.is_error:
            if 'path' in record and 'error' not in record:
                try:
                    record['post'] = state(record['path'])
                except ValueError as exc:
                    record['error'] = str(exc)
            data['records'].append(record)
            self.save(data)
        return result

    def preview(self, turn):
        records = self.read()['records']
        paths = {}
        commands = []
        for row in records:
            if row['turn'] < turn:
                continue
            if row['kind'] == 'run_command':
                commands.append(row['command']); continue
            path = row['path']
            if path not in paths:
                paths[path] = dict(row)
            else:
                paths[path]['post'] = row.get('post')
                if row.get('error'): paths[path]['error'] = row['error']
        files = []
        for path, row in paths.items():
            status = row.get('error', 'ok')
            try:
                if status == 'ok' and state(path) != row['post']:
                    status = 'conflict: 文件在工具写入后被修改'
            except (ValueError, OSError) as exc:
                status = str(exc)
            files.append(dict(row, status=status))
        return {'files': files, 'commands': commands}

    def apply(self, turn, force=()):
        plan = self.preview(turn)
        undo = []
        self.skipped = []
        for row in plan['files']:
            allowed = row['status'] == 'ok' or (row['status'].startswith('conflict:') and row['path'] in force)
            if not allowed:
                self.skipped.append({'path':row['path'],'reason':row['status']}); continue
            try:
                before = state(row['path'])
                if before != row['post'] and row['path'] not in force:
                    raise ValueError('conflict: 文件在预览后被修改')
                restore(row['path'], row['pre'])
                undo.append({'path':row['path'], 'pre':before, 'post':row['pre']})
            except (OSError,ValueError) as exc:
                self.skipped.append({'path':row['path'],'reason':str(exc)})
        return undo

    def undo(self, rows):
        skipped = []
        for row in rows:
            try:
                if state(row['path']) != row['post']:
                    raise ValueError('conflict: 回滚后文件被修改')
                restore(row['path'], row['pre'])
            except (OSError,ValueError) as exc:
                skipped.append({'path':row['path'],'reason':str(exc)})
        return skipped
