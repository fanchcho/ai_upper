"""Original mobile task list/details and pause/resume/run/delete actions."""
ORDER = {'active':0, 'error':1, 'paused':2, 'completed':3}


def task_list(shell):
    rows = shell.tasksService().read()
    rows.sort(key=lambda r:(ORDER.get(r['status'],4), r.get('nextRunAt') or float('inf'), -r['createdAt']))
    result=[]
    for row in rows:
        schedule=row['schedule'];auth=row.get('auth',{});owner=shell._store.load_session(row['ownerSessionId']) if row.get('ownerSessionId') else None
        result.append({'id':row['id'],'title':row['title'],'status':row['status'],
            'schedule':(schedule.get('cron') or schedule.get('at') or '')+' · '+schedule['tz'],
            'nextRunAt':row.get('nextRunAt') if row['status']=='active' else None,
            'lastRun':row.get('runs',[])[-1] if row.get('runs') else None,
            'personaId':auth.get('personaId'),'model':auth.get('modelRef'),
            'owner':{'sid':owner.id,'title':owner.title} if owner else None,
            'sessionId':row['sessionId'] if shell._store.load_session(row['sessionId']) else None})
    return result


def task_action(shell, frame, send):
    api=shell.tasksService();row=next((r for r in api.read() if r['id']==frame.get('id')),None)
    action=frame.get('action');error=''
    if not row: error='这个定时任务不存在或已被删除。'
    elif action not in ('pause','resume','run','delete'): error='不支持的操作。'
    elif action=='resume' and row['status']=='completed': error='这个一次性任务已经完成，不能恢复。'
    elif action=='run' and (row['id'] in api.running or row['id'] in api.deciding):
        send({'t':'result','rid':frame.get('rid'),'ok':True,'message':'这个任务正在运行。'});return
    elif (action=='pause' and row['status']!='active') or (action=='resume' and row['status']=='active'): pass
    else: error=api.action(row['id'],action)
    send({'t':'result','rid':frame.get('rid'),'ok':not error,'message':error or '任务已更新'})
    send({'t':'tasks','list':task_list(shell)})
