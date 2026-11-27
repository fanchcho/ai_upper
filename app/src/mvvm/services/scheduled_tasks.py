"""Persistent once/cron tasks (deva tasks.ts, schedule.ts, scheduler.ts)."""
from __future__ import annotations
import json
import time
import uuid
import threading
import queue
from datetime import datetime, timedelta, timezone
from pathlib import Path


def next_run(schedule, now=None):
    now = time.time() if now is None else now
    import importlib
    import sys
    if sys.version_info >= (3, 9):
        zone = importlib.import_module('zoneinfo').ZoneInfo(schedule['tz'])
    elif schedule['tz'] == 'UTC':
        zone = timezone.utc
    else:
        raise RuntimeError('Python 3.8 仅支持 UTC；IANA 时区调度需要 Python 3.9 或更新版本')
    if schedule['kind'] == 'once':
        value = datetime.fromisoformat(schedule['at']).replace(tzinfo=zone).timestamp()
        if value <= now:
            raise ValueError('执行时间必须在未来')
        return value
    if schedule['kind'] != 'recurring':
        raise ValueError('未知计划类型')
    fields = schedule['cron'].split()
    if len(fields) != 5:
        raise ValueError('cron 必须为五段：分 时 日 月 周')
    sets = []
    for raw, (low, high) in zip(fields, [(0,59),(0,23),(1,31),(1,12),(0,7)]):
        values = set()
        for part in raw.split(','):
            step_parts = part.split('/')
            if len(step_parts) > 2:
                raise ValueError('非法 cron 步长')
            step = int(step_parts[1]) if len(step_parts) == 2 else 1
            if step <= 0:
                raise ValueError('cron 步长必须为正')
            span = step_parts[0]
            if span == '*':
                a,b = low,high
            elif '-' in span:
                a,b = map(int,span.split('-'))
            else:
                a=int(span);b=high if len(step_parts)==2 else a
            if a < low or b > high or a > b:
                raise ValueError('cron 数值超出范围')
            values.update(range(a,b+1,step))
        sets.append(values)
    sets[4] = {v % 7 for v in sets[4]}
    # Match wall time by stepping real UTC minutes; skip nonexistent DST minutes.
    current = datetime.fromtimestamp((int(now)//60+1)*60, timezone.utc)
    for _ in range(366*24*60*2):
        local = current.astimezone(zone)
        dom = local.day in sets[2]; dow = (local.weekday()+1)%7 in sets[4]
        day = dom and dow if fields[2]=='*' or fields[4]=='*' else dom or dow
        if local.minute in sets[0] and local.hour in sets[1] and local.month in sets[3] and day and local.fold == 0:
            return current.timestamp()
        current += timedelta(minutes=1)
    raise ValueError('两年内没有匹配的执行时间')


def ScheduledTasks(shell):
    """Create the native controller lazily after the Qt application starts."""
    from utils.qt_compat import QtCore, Signal, Slot

    class Controller(QtCore.QObject):
        changed = Signal()
    
        def __init__(self, shell):
            super().__init__(shell)
            self.shell = shell
            self.path = Path(shell._store.home)/'tasks.json'
            self.running = {}
            self.deciding=set();self.decisions=queue.Queue()
            self.timer = QtCore.QTimer(self); self.timer.setInterval(1000)
            self.timer.timeout.connect(self.tick); self.timer.start()
    
        def read(self):
            if not self.path.exists():
                return []
            return json.loads(self.path.read_text()).get('tasks', [])
    
        def write(self, rows):
            temp = self.path.with_suffix('.json.tmp')
            temp.write_text(json.dumps({'version':1,'tasks':rows},ensure_ascii=False,indent=2))
            temp.replace(self.path)
            self.changed.emit()
    
        @Slot(result='QVariantList')
        def list(self):
            return sorted(self.read(),key=lambda r:r['createdAt'],reverse=True)
    
        @Slot(str,str,str,str,str,str,result=str)
        def create(self,title,prompt,kind,when,tz,persona):
            try:
                if not prompt.strip():raise ValueError('请输入任务内容')
                schedule={'kind':kind,'tz':tz,'at' if kind=='once' else 'cron':when}
                next_at=next_run(schedule)
                identity='task-'+uuid.uuid4().hex[:16];now=int(time.time()*1000)
                record={'id':identity,'title':title.strip() or prompt[:40], 'prompt':prompt.strip(),
                        'schedule':schedule,'auth':{'personaId':persona},'status':'active',
                        'sessionId':identity,'originSessionId':self.shell._active,'createdAt':now,
                        'updatedAt':now,'nextRunAt':int(next_at*1000),'consecutiveErrors':0,'runs':[]}
                self.shell._host.create_session({'sessionId':identity,'personaId':persona})
                session=self.shell._store.load_session(identity);session.title=record['title'];self.shell._store.save(identity)
                self.write(self.read()+[record]);self.shell._publish();return ''
            except Exception as exc:return str(exc)
    
        @Slot(result='QVariantList')
        def decisionProviders(self):
            return [p for p in self.shell._settings.models_section().get('providers',[]) if p.get('purpose')=='decision' and p.get('adapter')=='jev' and p.get('enabled')]

        @Slot(str,str,result=str)
        def update(self, identity, encoded):
            try:
                patch=json.loads(encoded); rows=self.read(); row=next(r for r in rows if r['id']==identity)
                if identity in self.running: raise ValueError('运行期间不能编辑任务')
                prompt=str(patch['prompt']).strip()
                if not prompt: raise ValueError('任务内容不能为空')
                schedule=patch['schedule']; next_at=next_run(schedule)
                owner=patch.get('ownerSessionId') or None
                if owner and (owner==row['sessionId'] or self.shell._store.load_session(owner) is None): raise ValueError('主对话无效')
                if patch.get('decision',{}).get('enabled'):
                    from mvvm.services.task_decision import config
                    config(self.shell._settings,patch['decision'])
                row.update(title=str(patch['title']).strip() or prompt[:40],prompt=prompt,schedule=schedule,
                           auth=patch['auth'],ownerSessionId=owner,decision=patch.get('decision'),
                           status='active' if patch.get('enabled') else 'paused',nextRunAt=int(next_at*1000) if patch.get('enabled') else None,
                           updatedAt=int(time.time()*1000))
                session=self.shell._store.load_session(row['sessionId']);session.title=row['title'];session.personaId=row['auth'].get('personaId');session.model=row['auth'].get('modelRef')
                self.shell._store.save(session.id);self.write(rows);self.shell._publish();return ''
            except Exception as exc:return str(exc)

        @Slot(str,str,result=str)
        def action(self,identity,action):
            try:
                rows=self.read();row=next(r for r in rows if r['id']==identity)
                if action=='delete':
                    if identity in self.running:raise ValueError('请等待正在执行的任务结束')
                    self.write([r for r in rows if r['id']!=identity]);return ''
                if action=='open':
                    self.shell.openSession(row['sessionId']);self.shell._window.setProperty('page','chat');return ''
                if action=='run':self.run(row)
                elif action=='pause':row['status']='paused';row['nextRunAt']=None
                elif action=='resume':
                    row['nextRunAt']=int(next_run(row['schedule'])*1000);row['status']='active';row['consecutiveErrors']=0
                else:raise ValueError('未知任务操作')
                row['updatedAt']=int(time.time()*1000);self.write(rows);return ''
            except Exception as exc:return str(exc)
    
        def run(self,row):
            identity=row['id']
            if identity in self.running or self.shell._host.is_busy(row['sessionId']):
                raise ValueError('任务已经在运行')
            from mvvm.services.tool_runtime import ToolSpec, ToolResult
            running={'startedAt':int(time.time()*1000)}
            self.running[identity]=running
            vm=self.shell._host.vm_for(row['sessionId']);vm.tools.interactive=False
            def deliver(args):
                if not row.get('ownerSessionId'):return ToolResult('任务未绑定主对话',True)
                if 'handoff' in running:return ToolResult('本轮已经交接',True)
                needs=args.get('needs_action')
                if not isinstance(needs,bool):return ToolResult('needs_action 必须为布尔值',True)
                if needs and not str(args.get('content','')).strip():return ToolResult('需要处理时 content 不能为空',True)
                running['handoff']={'needsAction':needs,'summary':str(args.get('summary','')),'content':str(args.get('content',''))}
                return ToolResult('交接已登记；仅告知时请在最终回复中写完整内容')
            vm.tools.register(ToolSpec('deliver_result','向主对话交接；仅告知使用最终回复原文，需要处理则填写 content',{'type':'object','properties':{'needs_action':{'type':'boolean'},'summary':{'type':'string'},'content':{'type':'string'}},'required':['needs_action']}),deliver)
            try:result=self.shell._host.send({'sessionId':row['sessionId'],'text':row['prompt']})
            except Exception:
                self.running.pop(identity,None);raise
            running['turnId']=result.get('turnId')
            row['lastRunAt']=self.running[identity]['startedAt']
            if row['schedule']['kind']=='once':row['status']='completed';row['nextRunAt']=None
            else:row['nextRunAt']=int(next_run(row['schedule'])*1000)
    
        def turn_event(self,payload):
            event=payload.get('event',{});kind=event.get('type')
            if kind not in ('done','error'):return
            rows=self.read();changed=False
            for row in rows:
                if row['sessionId']!=payload.get('sessionId') or row['id'] not in self.running:continue
                run=self.running.pop(row['id']);run.update(endedAt=int(time.time()*1000),status=kind,error=event.get('message',''))
                session=self.shell._store.load_session(row['sessionId'])
                from mvvm.models.chat_models import TextPart
                last=next((m for m in reversed(session.messages) if m.role=='assistant'),None)
                content=last.content if last else ''
                final=content if isinstance(content,str) else '\n'.join(p.text for p in content if isinstance(p,TextPart))
                if kind=='done' and event.get('stopReason')=='end_turn':
                    if run.get('handoff'):
                        handoff=dict(run['handoff'])
                        if not handoff['needsAction']:handoff['content']=final
                        row['pendingHandoff']=handoff
                    elif not row.get('ownerSessionId'):
                        row['remoteDelivery']=self.shell.botsService().publish_notice(row['sessionId'],row['title'],final)
                row['runs']=(row.get('runs',[])+[run])[-50:]
                row['consecutiveErrors']=row.get('consecutiveErrors',0)+1 if kind=='error' else 0
                if row['consecutiveErrors']>=5:row['status']='error';row['nextRunAt']=None
                changed=True
            if changed:self.write(rows)
    
        def tick(self):
            rows=self.read();changed=False
            from mvvm.models.chat_models import Message
            while not self.decisions.empty():
                identity,stamp,result=self.decisions.get();self.deciding.discard(identity)
                row=next((r for r in rows if r['id']==identity),None)
                if not row or row['updatedAt']!=stamp or row['status']!='active':continue
                row['lastDecision']=result;changed=True
                if result['status']=='allowed':
                    try:self.run(row)
                    except Exception as exc:row['lastError']=str(exc)
                else:
                    row['runs']=(row.get('runs',[])+[{'status':'skipped','decision':result,'endedAt':int(time.time()*1000)}])[-50:]
                    if row['schedule']['kind']=='once':row['status']='completed';row['nextRunAt']=None
                    else:row['nextRunAt']=int(next_run(row['schedule'])*1000)
            for row in rows:
                handoff=row.get('pendingHandoff');owner=row.get('ownerSessionId')
                if not handoff or not owner or self.shell._host.is_busy(owner):continue
                main=self.shell._store.load_session(owner)
                if main is None:continue
                if handoff['needsAction']:
                    self.shell._host.send({'sessionId':owner,'text':'<定时任务交接>\n'+row['title']+'：'+handoff['summary']+'\n'+handoff['content']+'\n</定时任务交接>'})
                else:
                    main.messages.append(Message(role='assistant',content=row['title']+'：'+handoff['content']))
                    self.shell._store.save(owner)
                    row['remoteDelivery']=self.shell.botsService().publish_notice(owner,row['title'],handoff['content'])
                    self.shell._publish()
                row.pop('pendingHandoff',None);changed=True
            for row in rows:
                if row['status']!='active' or row['id'] in self.deciding or row['id'] in self.running or not row.get('nextRunAt') or row['nextRunAt']>time.time()*1000:continue
                if (row.get('decision') or {}).get('enabled'):
                    from mvvm.services.task_decision import evaluate
                    snapshot=json.loads(json.dumps(row));self.deciding.add(row['id'])
                    def decide(snapshot=snapshot):self.decisions.put((snapshot['id'],snapshot['updatedAt'],evaluate(self.shell._settings,self.shell._vault,snapshot)))
                    threading.Thread(target=decide,daemon=True).start();continue
                try:self.run(row)
                except Exception as exc:
                    row['status']='error';row['nextRunAt']=None;row['lastError']=str(exc)
                changed=True
            if changed:self.write(rows)

    return Controller(shell)
