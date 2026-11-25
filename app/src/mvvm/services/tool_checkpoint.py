"""Durable tool result journal. Interrupted side effects are never retried."""
import hashlib
import json
import threading
from dataclasses import asdict

from mvvm.models.chat_models import ImagePart
from mvvm.services.chat_session_store import write_file_atomic
from mvvm.services.tool_runtime import ToolResult


class ToolCheckpoint:
    def __init__(self, root):
        self.root = root
        self.lock = threading.RLock()

    def path(self, session, operation):
        return self.root / (hashlib.sha256(json.dumps([session, operation]).encode()).hexdigest() + '.json')

    def result(self, session, operation):
        path = self.path(session, operation)
        if not path.exists(): return None
        row = json.loads(path.read_text())
        if row['state'] != 'completed':
            return ToolResult('interrupted_unknown: 工具可能已执行，不自动重放，请核查结果。', True)
        value = row['result']
        if value.get('images'):
            value['images'] = [ImagePart(**item) for item in value['images']]
        return ToolResult(**value)

    def execute(self, session, operation, name, args, invoke):
        if not operation: return invoke()
        fingerprint = hashlib.sha256(json.dumps([name, args], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path = self.path(session, operation)
        with self.lock:
            if path.exists():
                row = json.loads(path.read_text())
                if row['fingerprint'] != fingerprint:
                    return ToolResult('工具调用 ID 已用于不同参数；拒绝重放', True)
                return self.result(session, operation)
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            row = dict(session=session, operation=operation, fingerprint=fingerprint, revision=1, state='running')
            # Exclusive creation arbitrates concurrent processes before any side effect.
            try:
                with path.open('x', encoding='utf-8') as stream:
                    json.dump(row, stream, ensure_ascii=False)
                    stream.flush()
                    import os
                    os.fsync(stream.fileno())
            except FileExistsError:
                return ToolResult('工具正在执行或执行状态未知；未重复执行', True)
        result = invoke()
        value = asdict(result)
        if result.images:
            value['images'] = [image.model_dump() for image in result.images]
        row.update(state='completed', revision=2, result=value)
        write_file_atomic(path, json.dumps(row, ensure_ascii=False))
        return result
