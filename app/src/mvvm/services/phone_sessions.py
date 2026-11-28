"""Authenticated phone text conversations backed by the real ChatHost/store."""
import re


def session_list(shell, bot):
    scope = bot.get('scope', {'mode': 'all'})
    rows = []
    for meta in shell._store.list_sessions():
        session = shell._store.load_session(meta.id)
        if not session or session.parentId:
            continue
        if scope.get('mode') == 'sessions' and meta.id not in scope.get('sessions', []):
            continue
        if scope.get('mode') == 'personas' and meta.personaId not in scope.get('personas', []):
            continue
        rows.append({'id': meta.id, 'title': meta.title, 'personaId': meta.personaId,
                     'createdAt': meta.createdAt, 'updatedAt': meta.updatedAt,
                     'preview': session.messages[-1].text()[:150] if session.messages else '',
                     'busy': shell._host.is_busy(meta.id), 'waiting': False, 'kind': 'chat'})
    return rows


def history(shell, sid):
    session = shell._store.load_session(sid)
    messages = []
    for index, msg in enumerate(session.messages):
        if not msg.text():
            continue
        item = {'id': str(index), 'role': msg.role}
        if msg.role == 'user':
            item['text'] = msg.text()
        else:
            item['parts'] = [{'k': 'text', 'text': msg.text()}]
        messages.append(item)
    from mvvm.services.deliverables import inspect
    files = [dict(row, tool=tool, index=i) for tool in (session.delivered or {}) for i,row in enumerate(inspect(session,tool))]
    for row in files: row.pop('path',None);row.pop('dir',None)
    return {'files': files, 't': 'history', 'sid': sid, 'messages': messages, 'start': 0,
            'end': len(session.messages), 'total': len(session.messages)}


def handle(controller, bot_id, state, frame):
    shell = controller.shell
    bot = next(b for b in controller.list() if b['id'] == bot_id)
    send = state['send_frame']
    kind = frame.get('t')
    if not hasattr(controller,'phone_uploads'):
        from mvvm.services.phone_uploads import Uploads
        controller.phone_uploads=Uploads(shell._host)
    if kind in ('up_begin','up_chunk','up_end','up_cancel'):
        controller.phone_uploads.handle(state['device'],frame,send);return
    rows = session_list(shell, bot)
    if kind in ('hello', 'refresh'):
        send({'t': 'sessions', 'list': rows})
        return
    if kind == 'new':
        sid = frame.get('sid', '')
        if not re.fullmatch(r'sess_[0-9a-z]{1,12}_[0-9a-z]{1,8}', sid) or shell._store.load_session(sid):
            send({'t': 'created', 'rid': frame.get('rid'), 'error': '对话 id 无效或已存在'});return
        if bot.get('scope', {}).get('mode') == 'sessions':
            send({'t': 'created', 'rid': frame.get('rid'), 'error': '指定对话范围不能新建对话'});return
        persona = frame.get('personaId') or 'general'
        if bot.get('scope', {}).get('mode') == 'personas' and persona not in bot['scope'].get('personas', []):
            send({'t': 'created', 'rid': frame.get('rid'), 'error': '角色不在允许范围'});return
        shell._host.create_session({'sessionId': sid, 'personaId': persona})
        send({'t': 'created', 'rid': frame.get('rid'), 'sid': sid})
        send({'t': 'sessions', 'list': session_list(shell, bot)})
        return
    sid = frame.get('sid')
    if kind not in ('send', 'history', 'stop', 'file'):
        return
    if sid not in {row['id'] for row in rows}:
        send({'t': 'err', 'code': 'gone', 'message': '对话不存在或超出允许范围'});return
    if kind == 'file':
        from mvvm.services.phone_files import send_file
        send_file(shell._store.load_session(sid),frame,send);return
    if kind == 'history':
        state['watch'] = sid
        send(history(shell, sid));return
    if kind == 'stop':
        shell._host.abort(shell._host.attach(sid).get('turnId'));return
    text = frame.get('text')
    if not isinstance(text, str) or (not text.strip() and not frame.get('files')):
        send({'t': 'sent', 'cid': frame.get('cid'), 'sid': sid, 'ok': False, 'message': '请输入文字或上传附件'});return
    if shell._host.is_busy(sid):
        send({'t': 'sent', 'cid': frame.get('cid'), 'sid': sid, 'ok': False, 'message': '当前回合尚未结束'});return
    state['watch'] = sid
    controller.turns[sid] = (bot_id, state['device'])
    try:
        paths=controller.phone_uploads.take(state['device'],frame.get('files',[]))
        shell._host.send({'sessionId': sid, 'text': text, 'attachments':paths})
        send({'t': 'sent', 'cid': frame.get('cid'), 'sid': sid, 'ok': True})
    except Exception as exc:
        controller.turns.pop(sid, None)
        send({'t': 'sent', 'cid': frame.get('cid'), 'sid': sid, 'ok': False, 'message': str(exc)})
