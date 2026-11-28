"""Phone decisions consume the same persisted requests as desktop interaction cards."""

def prompts(shell, sid):
    interactions = getattr(shell._host, 'interactions', None)
    if interactions is None: return []
    return [dict(row, key=row['id'], sessionId=sid, state='open') for row in interactions.pending(sid)]


def action(shell, allowed, frame, send):
    value = frame.get('value') or {}
    key = value.get('key', '')
    request = next((p for sid in allowed for p in prompts(shell,sid) if p['key']==key), None)
    ok = False
    if request:
        expected = {'plan':'plan', 'approval':'approval', 'question':'ask', 'mount':'mount'}[request['kind']]
        if value.get('k') == expected:
            decision = value.get('d')
            text = (frame.get('form') or {}).get('text', '')
            if expected == 'mount': decision = 'skipped'
            if expected == 'ask': decision = 'answered'
            ok = shell._host.interactions.answer(request['session'],key,decision,text)
    send({'t':'result','rid':frame.get('rid'),'ok':ok,'message':'已提交' if ok else '请求已结束、决定无效或超出允许范围'})
    return request['session'] if request else None


def enable(shell, sid):
    """The original phone can skip a mount request, never select a desktop path."""
    from mvvm.services.tool_runtime import ToolSpec, ToolResult
    runtime = shell._host.vm_for(sid).tools
    def mount(args):
        if not runtime.interactive: return ToolResult('当前无法请用户挂载工作区', True)
        if runtime.root: return ToolResult('当前已挂载工作区：'+str(runtime.root))
        if getattr(runtime, 'phone_mount_declined', False): return ToolResult('用户暂不挂载工作区；不要重复请求，请使用绝对路径。')
        import uuid
        row = runtime.interactions.request(sid,'mount_'+uuid.uuid4().hex,'mount',str(args.get('question','请选择工作区'))[:200],cancelled=runtime.cancel_check)
        if row['outcome']=='skipped': runtime.phone_mount_declined=True
        return ToolResult('用户暂不挂载工作区；不要重复请求，请使用绝对路径。' if row['outcome']=='skipped' else '已取消挂载',row['outcome']!='skipped')
    runtime.register(ToolSpec('mount_workspace','请用户指定工作区；手机只能跳过，不能授权任意电脑路径。',{'type':'object','properties':{'question':{'type':'string'}}}),mount)
