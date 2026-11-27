"""Persistent once/cron tasks (deva tasks.ts, schedule.ts, scheduler.ts)."""
from __future__ import annotations
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal, Slot


def next_run(schedule, now=None):
    now = time.time() if now is None else now
    zone = ZoneInfo(schedule['tz'])
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


class ScheduledTasks(QObject):
    changed = Signal()

    def __init__(self, shell):
        super().__init__(shell)
        self.shell = shell
        self.path = Path(shell._store.home)/'tasks.json'
        self.running = {}
        self.timer = QTimer(self); self.timer.setInterval(1000)
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
        result=self.shell._host.send({'sessionId':row['sessionId'],'text':row['prompt']})
        self.running[identity]={'turnId':result.get('turnId'),'startedAt':int(time.time()*1000)}
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
            row['runs']=(row.get('runs',[])+[run])[-50:]
            row['consecutiveErrors']=row.get('consecutiveErrors',0)+1 if kind=='error' else 0
            if row['consecutiveErrors']>=5:row['status']='error';row['nextRunAt']=None
            changed=True
        if changed:self.write(rows)

    def tick(self):
        rows=self.read();changed=False
        for row in rows:
            if row['status']!='active' or row['id'] in self.running or not row.get('nextRunAt') or row['nextRunAt']>time.time()*1000:continue
            try:self.run(row)
            except Exception as exc:
                row['status']='error';row['nextRunAt']=None;row['lastError']=str(exc)
            changed=True
        if changed:self.write(rows)
