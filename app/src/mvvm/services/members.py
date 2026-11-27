"""Role mentions create persistent per-conversation members and dispatch real turns."""
import json
import threading
from pathlib import Path
from mvvm.services.chat_session_store import write_file_atomic
import uuid
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
        if args.get('pick_folder'):raise ValueError('成员目录选择尚未接入，请先由用户在会话中选择目录')
        root=main.focusRoot if args.get('personaId') else None
        if args.get('folder'):
            root=str(self.host.guard.assert_inside(Path(main.focusRoot or '.') / args['folder']))
            Path(root).mkdir(parents=True,exist_ok=True)
        self.host.create_session({'sessionId':sid, 'personaId':persona, 'focusRoot':root})
        member = {'id':sid, 'sessionId':sid, 'name':name, 'personaId':persona, 'duty':str(args.get('duty') or ''), 'origin':'mention'}
        child = self.host.store.load_session(sid)
        child.parentId = main.id
        child.title = name
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
        selected = [m for m in (main.members or []) if '@'+m['name'] in own]
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
            try: return ToolResult(json.dumps(self.create(main,args),ensure_ascii=False))
            except Exception as exc: return ToolResult(str(exc),True)
        def send(args):
            try:
                ref = str(args.get('member') or args.get('name') or '')
                member = next((m for m in main.members or [] if ref in (m['id'],m['name'])),None)
                if member is None: raise ValueError('找不到成员：'+ref)
                text = str(args.get('message') or '').strip()
                if not text: raise ValueError('消息不能为空')
                sid = member['sessionId']
                if self.host.is_busy(sid): raise ValueError('成员正在执行')
                self.pending[sid] = (main.id,member['name'],len(self.host.store.load_session(sid).messages))
                if args.get('report_to_me'):self.escalations[sid]='主角色要求汇总'
                member['task']=str(args.get('task') or text[:80]);self.host.store.save(main.id)
                turn = self.host.send({'sessionId':sid,'text':text})
                return ToolResult(json.dumps(turn))
            except Exception as exc: return ToolResult(str(exc),True)
        vm.tools.register(ToolSpec('create_member','在当前对话创建协作成员',{'type':'object','properties':{'name':{'type':'string'},'duty':{'type':'string'},'personaId':{'type':'string'}},'required':['name']}),create)
        vm.tools.register(ToolSpec('member_send','给成员分派具体任务',{'type':'object','properties':{'member':{'type':'string'},'message':{'type':'string'}},'required':['member','message']}),send)

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
        if main.parentId:
            for name in ('create_member','member_send','member_status','member_stop'):vm.tools._tools.pop(name,None)
            vm.tools.register(ToolSpec('read_main','分页读取主对话正文',{'type':'object','properties':{k:{'type':'integer'} for k in ('before','round','offset')}}),read_main)
            vm.tools.register(ToolSpec('report_to_main','最终结论交主角色处理',{'type':'object','properties':{'reason':{'type':'string'}},'required':['reason']}),report)

    def finished(self, sid):
        if sid not in self.pending: return
        main_id,name,start = self.pending.pop(sid)
        member = self.host.store.load_session(sid)
        main = self.host.store.load_session(main_id)
        messages = [m for m in member.messages[start:] if m.role == 'assistant']
        if not messages or main is None: return
        content = messages[-1].content
        text = content if isinstance(content,str) else '\n'.join(p.text for p in content if isinstance(p,TextPart))
        # Main may still be generating: wait until its turn finishes before appending.
        with self.lock:
            self.reports.append([main_id,name,text,self.escalations.pop(sid,'')])
            self.save_reports()

    def drain(self):
        for row in list(self.reports):
            sid,name,text = row[:3]
            wake=row[3] if len(row)>3 else ""
            if self.host.is_busy(sid): continue
            main = self.host.store.load_session(sid)
            if main:
                if wake:
                    self.host.send({'sessionId':sid,'text':'成员 '+name+' 请求处理：'+wake+'\n'+text})
                else:main.messages.append(Message(role='assistant',content=name+'：'+text))
                self.host.store.save(sid);self.host._emit_sessions_changed()
                self.host._emit({'turnId':'','sessionId':sid,'event':{'type':'done','stopReason':'end_turn','durationMs':0}})
            with self.lock:
                self.reports.remove(row)
                self.save_reports()
