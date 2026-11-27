"""Role mentions create persistent per-conversation members and dispatch real turns."""
import json
import threading
from pathlib import Path
from mvvm.services.chat_session_store import write_file_atomic
import uuid
import time
from mvvm.models.chat_models import Message, TextPart
from mvvm.services.persona_store import PersonaStore
from mvvm.services.tool_runtime import ToolSpec, ToolResult


class Members:
    def __init__(self, host):
        self.host = host
        self.pending = {}
        self.escalations = {}
        self.lock = threading.RLock()
        self.path = Path(host.home)/'data'/'member-reports.json'
        self.reports = json.loads(self.path.read_text()) if self.path.exists() else []

    def save_reports(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_file_atomic(self.path,json.dumps(self.reports,ensure_ascii=False))

    def create(self, main, args):
        name = str(args.get('name') or '').strip()
        if not name: raise ValueError('成员名称不能为空')
        main.members = main.members or []
        for member in main.members:
            if member['name'].casefold() == name.casefold():
                member.pop('removedAt',None);self.host.store.save(main.id);return member
        if len([m for m in main.members if not m.get('removedAt')]) >= 10: raise ValueError('成员已满 10 个')
        sid = 'member-' + uuid.uuid4().hex
        persona = args.get('personaId') or 'general'
        root=main.focusRoot if args.get('personaId') else None
        if args.get('folder'):
            root=str(self.host.guard.assert_inside(Path(main.focusRoot or '.') / args['folder']))
            Path(root).mkdir(parents=True,exist_ok=True)
        self.host.create_session({'sessionId':sid, 'personaId':persona, 'focusRoot':root})
        member = {'id':sid, 'sessionId':sid, 'name':name, 'personaId':persona, 'duty':str(args.get('duty') or ''), 'origin':'mention' if args.get('personaId') else 'agent'}
        child = self.host.store.load_session(sid)
        child.parentId = main.id
        child.title = name
        child.model = main.model
        child.effort = main.effort
        self.host.store.save(sid)
        self.install(self.host.vm_for(sid),child)
        main.members.append(member)
        self.host.store.save(main.id)
        self.host._emit_sessions_changed()
        return member

    def mentions(self, main, text):
        own = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))
        if '@' not in own: return []
        roles = sorted(PersonaStore(self.host.home / 'deva').list_personas(), key=lambda p:len(p['name']), reverse=True)
        selected = [m for m in (main.members or []) if not m.get('removedAt') and '@'+m['name'] in own]
        for role in roles:
            if not role.get('enabled',True) or role['id'] == main.personaId or '@'+role['name'] not in own: continue
            if any(role['name'] in m['name'] for m in selected): continue
            selected.append(self.create(main, {'name':role['name'],'personaId':role['id'],'duty':role.get('description','')}))
        if not selected and any('@'+name in own for name in ('新建成员','New member')):
            return [TextPart(text='用户要求新建成员。有具体职责时调用 create_member，再通过 member_send 分派；只选了新建成员没有需求时先询问职责。')]
        if not selected: return []
        return [TextPart(text='用户提及成员：'+', '.join(m['name'] for m in selected)+ '。有具体任务时用 member_send 分派；只点名不派任务。')]

    def install(self, vm, main):
        def create(args):
            try:
                if args.get('pick_folder') and not args.get('folder'):
                    controller=getattr(self.host,'interactions',None)
                    if not controller or not vm.tools.interactive:raise ValueError('目录选择交互不可用')
                    row=controller.request(main.id,'member-folder-'+uuid.uuid4().hex,'mount','选择成员 '+str(args.get('name',''))+' 的工作目录',cancelled=vm.tools.cancel_check)
                    if row['outcome']=='answered':args=dict(args,folder=row['answer'])
                return ToolResult(json.dumps(self.create(main,args),ensure_ascii=False))
            except Exception as exc: return ToolResult(str(exc),True)
        def send(args):
            try:
                ref = str(args.get('member') or args.get('name') or '')
                member = next((m for m in main.members or [] if not m.get('removedAt') and ref in (m['id'],m['name'])),None)
                if member is None: raise ValueError('找不到成员：'+ref)
                text = str(args.get('message') or '').strip()
                if not text: raise ValueError('消息不能为空')
                sid = member['sessionId']
                busy=self.host.is_busy(sid)
                dispatch={'id':uuid.uuid4().hex,'task':str(args.get('task') or text[:80]),'delivered':not busy,'reportToMe':bool(args.get('report_to_me')),'group':self.host._session_turn.get(main.id,'')}
                with self.lock:
                    if not busy:self.pending[sid] = (main.id,member['name'],len(self.host.store.load_session(sid).messages))
                    member['openTasks']=(member.get('openTasks',[]) if busy else [])+[dispatch]
                    member['task']=dispatch['task'];self.host.store.save(main.id)
                message='【主角色派来的任务】'+dispatch['task']+'\n'+text
                if not self.host.store.load_session(sid).messages:
                    message+='\n【主对话背景】\n'+'\n'.join(m.text() for m in main.messages[-10:])
                if busy:
                    def delivered():
                        with self.lock:dispatch['delivered']=True;self.host.store.save(main.id)
                    self.host.vm_for(sid).insert_message(message,delivered)
                    turn={'inserted':True,'task':dispatch['task']}
                else:turn = self.host.send({'sessionId':sid,'text':message})
                return ToolResult(json.dumps(turn))
            except Exception as exc: return ToolResult(str(exc),True)
        vm.tools.register(ToolSpec('create_member','按用户要求或持续的不同工作块创建成员；一次性任务不建成员',{'type':'object','properties':{'name':{'type':'string'},'duty':{'type':'string'},'folder':{'type':'string'},'pick_folder':{'type':'boolean'}},'required':['name','duty']}),create)
        vm.tools.register(ToolSpec('member_send','给成员分派任务；忙碌时插入；默认直接回复用户，需要汇总时 report_to_me',{'type':'object','properties':{'member':{'type':'string'},'message':{'type':'string'},'task':{'type':'string'},'report_to_me':{'type':'boolean'}},'required':['member','task','message']}),send)

        def status(args):
            rows=[]
            for member in main.members or []:
                if member.get('removedAt') or (args.get('member') and args['member']!=member['name']):continue
                child=self.host.store.load_session(member['sessionId'])
                replies=[m.text() for m in child.messages if m.role=='assistant'] if child else []
                rows.append(dict(member,busy=self.host.is_busy(member['sessionId']),conclusion=replies[-1] if replies else ''))
            return ToolResult(json.dumps(rows,ensure_ascii=False))
        def stop(args):
            member=next((m for m in main.members or [] if m['name']==args.get('member')),None)
            if member is None:return ToolResult('成员不存在',True)
            turn=self.host._session_turn.get(member['sessionId'])
            if turn:self.host.abort(turn)
            return ToolResult('已请求停止' if turn else '成员未在运行')
        vm.tools.register(ToolSpec('member_status','查看成员名单、当前任务与最近结论',{'type':'object','properties':{'member':{'type':'string'}}}),status)
        vm.tools.register(ToolSpec('member_stop','停止指定成员当前回合',{'type':'object','properties':{'member':{'type':'string'}},'required':['member']}),stop)
        def read_main(args):
            parent=self.host.store.load_session(main.parentId) if main.parentId else None
            if not parent:return ToolResult('不是成员会话',True)
            from mvvm.services.chat_session_store import is_genuine_user_turn
            starts=[i for i,m in enumerate(parent.messages) if is_genuine_user_turn(m)]
            rows=[]
            for n,start in enumerate(starts):
                if args.get('round') and args['round']!=n+1:continue
                if args.get('before') and n+1>=args['before']:continue
                end=starts[n+1] if n+1<len(starts) else len(parent.messages)
                rows.append({'round':n+1,'text':'\n'.join(m.text() for m in parent.messages[start:end])})
            if not args.get('round'):rows=rows[-5:]
            offset=max(0,int(args.get('offset',0)))
            for row in rows:row['text']=row['text'][offset:offset+12000]
            return ToolResult(json.dumps(rows,ensure_ascii=False))
        def report(args):
            if not main.parentId:return ToolResult('不是成员会话',True)
            reason=str(args.get('reason') or '').strip()
            if not reason:return ToolResult('reason 不能为空',True)
            self.escalations[main.id]=reason
            return ToolResult('最终结论将交主角色处理')
        def reply(args):
            parent=self.host.store.load_session(main.parentId) if main.parentId else None
            ref=next((m for m in parent.members or [] if m['sessionId']==main.id and not m.get('removedAt')),None) if parent else None
            if not ref:return ToolResult('已不在主对话的成员名单里',True)
            with self.lock:
                tasks=ref.get('openTasks',[])
                if len(tasks)<2:return ToolResult('只剩一项或没有派来的任务，请直接写最终回复',True)
                normalize=lambda v:''.join(str(v).strip('「」').split()).casefold()
                hit=next((d for d in tasks if d['delivered'] and normalize(d['task'])==normalize(args.get('task',''))),None)
                if not hit:return ToolResult('没有已送达且未交回的同名任务',True)
                conclusion=str(args.get('conclusion','')).strip()
                if not conclusion:return ToolResult('conclusion 不能为空',True)
                tasks.remove(hit);self.host.store.save(parent.id)
                self.reports.append([parent.id,ref['name'],conclusion,'主角色要求汇总' if hit['reportToMe'] else '',hit['group']]);self.save_reports()
            return ToolResult('已交回 '+hit['task']+'，接着做其余任务，最终回复不重复本项')
        if main.parentId:
            for name in ('create_member','member_send','member_status','member_stop'):vm.tools._tools.pop(name,None)
            vm.tools.register(ToolSpec('read_main','分页读取主对话正文',{'type':'object','properties':{k:{'type':'integer'} for k in ('before','round','offset')}}),read_main)
            vm.tools.register(ToolSpec('report_to_main','最终结论交主角色处理',{'type':'object','properties':{'reason':{'type':'string'}},'required':['reason']}),report)
            vm.tools.register(ToolSpec('reply_task','同时有几项任务时，提前交回其中一项独立任务的结论',{'type':'object','properties':{'task':{'type':'string'},'conclusion':{'type':'string'}},'required':['task','conclusion']}),reply)

    def remove(self, main, sid):
        ref=next((m for m in main.members or [] if m['sessionId']==sid),None)
        if not ref:return False
        ref['removedAt']=int(time.time()*1000)
        turn=self.host._session_turn.get(sid)
        if turn:self.host.abort(turn)
        self.host.store.save(main.id);self.host._emit_sessions_changed()
        return True

    def finished(self, sid):
        if sid not in self.pending: return
        main_id,name,start = self.pending.pop(sid)
        member = self.host.store.load_session(sid)
        main = self.host.store.load_session(main_id)
        messages = [m for m in member.messages[start:] if m.role == 'assistant']
        if not messages or main is None: return
        content = messages[-1].content
        text = content if isinstance(content,str) else '\n'.join(p.text for p in content if isinstance(p,TextPart))
        ref=next((m for m in main.members or [] if m['sessionId']==sid),None)
        if not ref or ref.get('removedAt'):return
        turn=self.host._turns.get(self.host._session_turn.get(sid,''))
        if turn and turn.aborted:return
        with self.lock:
            closing=[d for d in ref.get('openTasks',[]) if d['delivered']]
            ref['openTasks']=[d for d in ref.get('openTasks',[]) if not d['delivered']]
            ref['last']={'text':text,'at':int(time.time()*1000),'status':'done'}
            self.host.store.save(main_id)
            requested=next((d for d in closing if d['reportToMe']),None)
            self.reports.append([main_id,name,text,self.escalations.pop(sid,'') or ('主角色要求汇总' if requested else ''),requested['group'] if requested else ''])
            self.save_reports()

    def drain(self):
        for row in list(self.reports):
            if row not in self.reports:continue
            sid,name,text = row[:3]
            wake=row[3] if len(row)>3 else ""
            if self.host.is_busy(sid): continue
            main = self.host.store.load_session(sid)
            if main:
                group=row[4] if len(row)>4 else ''
                if wake and group and any(d.get('reportToMe') and d.get('group')==group for m in main.members or [] for d in m.get('openTasks',[])):continue
                grouped=[r for r in self.reports if r[0]==sid and len(r)>4 and r[3] and r[4]==group] if wake and group else [row]
                if wake:
                    self.host.send({'sessionId':sid,'text':'\n\n'.join('成员 '+r[1]+' 请求处理：'+r[3]+'\n'+r[2] for r in grouped)})
                else:main.messages.append(Message(role='assistant',content=name+'：'+text))
                self.host.store.save(sid);self.host._emit_sessions_changed()
                self.host._emit({'turnId':'','sessionId':sid,'event':{'type':'done','stopReason':'end_turn','durationMs':0}})
            with self.lock:
                for result in grouped if main else [row]:
                    if result in self.reports:self.reports.remove(result)
                self.save_reports()
