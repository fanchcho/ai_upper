"""Persisted local approvals/questions. Only an explicit answer authorizes work."""
import hashlib
import json
import threading
import time

from mvvm.services.chat_session_store import write_file_atomic
from mvvm.services.tool_runtime import ToolSpec, ToolResult

ASK_SPEC = ToolSpec('ask_user', '向用户提问并等待回答；关闭、取消、超时都不是同意。', {
    'type': 'object', 'properties': {'questions': {'type': 'array', 'minItems': 1, 'maxItems': 5,
        'items': {'type': 'object', 'properties': {'question': {'type': 'string'}, 'choices': {'type': 'array', 'maxItems': 6, 'items': {'type': 'string'}}}, 'required': ['question']}}}, 'required': ['questions']})


class Interactions:
    def __init__(self, directory, timeout=300):
        self.directory, self.timeout = directory, timeout
        self.lock = threading.RLock()

    def _path(self, request_id):
        return self.directory / (hashlib.sha256(request_id.encode()).hexdigest() + '.json')

    def _write(self, row):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_file_atomic(self._path(row['id']), json.dumps(row, ensure_ascii=False))

    def has_operation(self, session, operation):
        return any(self._path(session + ':' + operation + suffix).exists() for suffix in ('', ':0'))

    def pending(self, session):
        with self.lock:
            rows = []
            for path in sorted(self.directory.glob('*.json')):
                row = json.loads(path.read_text())
                if row['session'] == session and row['outcome'] == 'pending':
                    if time.time() >= row['expires']:
                        row['outcome'] = 'timeout'; self._write(row)
                    else: rows.append(row)
            return rows

    def answer(self, session, request_id, outcome, text=''):
        with self.lock:
            path = self._path(request_id)
            if not path.exists(): return False
            row = json.loads(path.read_text())
            allowed = ('approved', 'denied', 'cancelled') if row['kind'] == 'approval' else ('answered', 'dismissed', 'cancelled')
            if row['session'] != session or row['outcome'] != 'pending' or outcome not in allowed or time.time() >= row['expires']:
                return False
            row.update(outcome=outcome, answer=str(text))
            self._write(row)
            return True

    def request(self, session, operation, kind, question, choices=(), cancelled=None):
        request_id = session + ':' + operation
        fingerprint = hashlib.sha256(json.dumps([kind, question, choices], ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            path = self._path(request_id)
            if path.exists():
                row = json.loads(path.read_text())
                if row['fingerprint'] != fingerprint:
                    raise ValueError('Interaction operation ID reused with different input')
            else:
                row = dict(id=request_id, session=session, operation=operation, kind=kind, question=question,
                           choices=list(choices), fingerprint=fingerprint, outcome='pending', expires=time.time()+self.timeout)
                self._write(row)
        while True:
            with self.lock:
                row = json.loads(path.read_text())
                if cancelled and cancelled():
                    row['outcome'] = 'cancelled'; self._write(row)
                elif row['outcome'] == 'pending' and time.time() >= row['expires']:
                    row['outcome'] = 'timeout'; self._write(row)
                if row['outcome'] != 'pending': return row
            time.sleep(.05)

    def approve(self, session, operation, tool, args, cancelled):
        preview = {key: str(args[key])[:2000] for key in ('path', 'cwd', 'command', 'url', 'action') if key in args}
        row = self.request(session, operation, 'approval', '允许执行 ' + tool + '？\n' + json.dumps(preview, ensure_ascii=False), cancelled=cancelled)
        return row['outcome'] == 'approved'

    def ask(self, session, operation, args, cancelled):
        questions = args.get('questions', []) if isinstance(args, dict) else []
        if not isinstance(questions, list) or not 1 <= len(questions) <= 5:
            return ToolResult('questions 必须包含 1–5 个问题', True)
        answers = []
        for index, item in enumerate(questions):
            if not isinstance(item, dict) or not isinstance(item.get('question'), str) or not item['question'].strip():
                return ToolResult('问题文本不能为空', True)
            choices = item.get('choices', [])
            if not isinstance(choices, list) or len(choices) > 6 or any(not isinstance(x, str) for x in choices):
                return ToolResult('choices 必须是最多 6 个字符串', True)
            row = self.request(session, operation + ':' + str(index), 'question', item['question'], choices, cancelled)
            answers.append({'question': item['question'], 'outcome': row['outcome'], 'answer': row.get('answer', '')})
            if row['outcome'] != 'answered': break
        return ToolResult(json.dumps(answers, ensure_ascii=False))
