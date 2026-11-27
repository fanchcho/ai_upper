"""Persistent remote bot management; Telegram ownership linking and private chats.

Reference: deva remote/index.ts, store.ts, telegram-onboard.ts. External
connectivity is reported separately from saved configuration.
"""
from __future__ import annotations
import asyncio,json,re,secrets,threading,time,uuid
from PySide6.QtCore import QObject,Signal,Slot,Qt
from mvvm.services.provider_setup import build_transport


def telegram(token,method,payload):
    async def call():
        transport=build_transport()
        try:
            response=await transport.post('https://api.telegram.org/bot'+token+'/'+method,
                headers={'Content-Type':'application/json'},body=json.dumps(payload).encode())
            result=json.loads(await response.text())
            if not result.get('ok'):raise RuntimeError(result.get('description','Telegram request failed'))
            return result['result']
        finally:await transport.aclose()
    return asyncio.run(call())


class RemoteBots(QObject):
    changed=Signal()
    status=Signal(str,str)
    delivered=Signal(object)

    def __init__(self,shell):
        super().__init__(shell);self.shell=shell;self.workers={};self.states={};self.turns={};self.streams={};self.link_cancel=threading.Event()
        self.delivered.connect(self.receive,Qt.QueuedConnection)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.instance().aboutToQuit.connect(self.close)
        for bot in self.list():
            if bot.get('enabled'):self.start(bot)

    @Slot(result='QVariantList')
    def list(self):
        bots=self.shell._settings.get('remote',{}).get('bots',[])
        return [dict(b,state=self.states.get(b['id'],'off')) for b in bots if isinstance(b,dict) and b.get('id')]

    def save(self,rows):
        remote=self.shell._settings.get('remote',{});remote['bots']=[{k:v for k,v in b.items() if k!='state'} for b in rows]
        self.shell._settings.set_config({'remote':remote});self.changed.emit()

    @Slot(str,str,str,result=str)
    def action(self,identity,action,value=''):
        try:
            rows=self.list();bot=next(b for b in rows if b['id']==identity)
            if action in ('delete','disable'):
                if identity in self.workers:self.workers.pop(identity).set()
                bot['enabled']=False;self.states[identity]='off'
                if action=='delete':
                    for field in ('botToken','appSecret','verificationToken','encryptKey'):
                        self.shell._vault.delete_secret('remote:'+identity+':'+field)
                    rows=[b for b in rows if b['id']!=identity]
            elif action=='enable':
                error=self.start(bot)
                if error:return error
                bot['enabled']=True
            elif action=='reply':bot['replyMode']='final' if value=='final' else 'stream'
            elif action=='scope':
                scope=json.loads(value)
                if scope.get('mode') not in ('all','personas','sessions'):raise ValueError('未知回复范围')
                bot['scope']={'mode':scope['mode'],'personas':list(dict.fromkeys(scope.get('personas',[]))),'sessions':list(dict.fromkeys(scope.get('sessions',[])))}
            elif action=='remove-user':
                removed=[u for u in bot.get('users',[]) if u['id']==value]
                bot['users']=[u for u in bot.get('users',[]) if u['id']!=value]
                for u in removed:bot.get('bindings',{}).pop(u.get('chatId',''),None)
            else:raise ValueError('未知机器人操作')
            self.save(rows);return ''
        except Exception as exc:return str(exc)

    @Slot(str,result=str)
    def linkTelegram(self,token):
        token=token.strip()
        if not re.fullmatch(r'\d+:[\w-]{20,}',token):return 'Token 格式不对，请从 @BotFather 完整复制'
        self.link_cancel.set();self.link_cancel=threading.Event();cancel=self.link_cancel
        def run():
            try:
                me=telegram(token,'getMe',{})
                telegram(token,'deleteWebhook',{'drop_pending_updates':False})
                code=secrets.token_urlsafe(9);link=f"https://t.me/{me['username']}?start={code}"
                self.delivered.emit({'kind':'link','url':link});deadline=time.monotonic()+600;offset=0
                while not cancel.is_set() and time.monotonic()<deadline:
                    for update in telegram(token,'getUpdates',{'offset':offset,'timeout':20,'allowed_updates':['message']}):
                        offset=update['update_id']+1;m=update.get('message',{});user=m.get('from',{})
                        if user.get('is_bot') or m.get('chat',{}).get('type')!='private':continue
                        if not re.fullmatch(r'/start(?:@'+re.escape(me['username'])+r')?\s+'+re.escape(code),m.get('text',''),re.I):continue
                        telegram(token,'getUpdates',{'offset':offset,'timeout':0})
                        if not cancel.is_set():self.delivered.emit({'kind':'linked','token':token,'me':me,'user':user,'chat':str(m['chat']['id'])})
                        return
                self.delivered.emit({'kind':'link-error','message':'配对已取消或过期'})
            except Exception as exc:self.delivered.emit({'kind':'link-error','message':str(exc).replace(token,'[redacted]')})
        threading.Thread(target=run,daemon=True).start();return ''

    @Slot()
    def cancelLink(self):self.link_cancel.set()

    def start(self,bot):
        identity=bot['id']
        if bot.get('platform')!='telegram':return '此平台的连接适配器尚未移植'
        token=self.shell._vault.get_secret('remote:'+identity+':botToken')
        if not token:return '机器人密钥不存在或系统密钥库不可用'
        if identity in self.workers:return ''
        stop=threading.Event();self.workers[identity]=stop;self.states[identity]='connecting'
        def poll():
            offset=0
            try:
                telegram(token,'getMe',{});self.delivered.emit({'kind':'state','id':identity,'state':'connected'})
                while not stop.is_set():
                    for update in telegram(token,'getUpdates',{'offset':offset,'timeout':20,'allowed_updates':['message']}):
                        offset=update['update_id']+1
                        if not stop.is_set():self.delivered.emit({'kind':'message','id':identity,'message':update.get('message',{})})
            except Exception as exc:
                if not stop.is_set():self.delivered.emit({'kind':'state','id':identity,'state':'error: '+str(exc).replace(token,'[redacted]')})
        threading.Thread(target=poll,daemon=True).start();return ''

    @Slot(object)
    def receive(self,data):
        kind=data['kind']
        if kind=='link':self.status.emit('',data['url']);return
        if kind=='link-error':self.status.emit(data['message'],'');return
        if kind=='state':
            self.states[data['id']]=data['state']
            if data['state'].startswith('error'):self.workers.pop(data['id'],None)
            self.changed.emit();return
        if kind=='linked':
            me=data['me'];rows=self.list()
            if any(b.get('settings',{}).get('botId')==me['id'] for b in rows):self.status.emit('这个机器人已经添加','');return
            identity='bot_'+uuid.uuid4().hex[:16]
            if not self.shell._vault.set_secret('remote:'+identity+':botToken',data['token']).get('ok'):self.status.emit('系统密钥存储不可用','');return
            user=data['user'];bot={'id':identity,'platform':'telegram','name':me.get('first_name',me['username']),
                'enabled':True,'createdAt':int(time.time()*1000),'replyMode':'final','scope':{'mode':'all','personas':[],'sessions':[]},
                'users':[{'id':str(user['id']),'name':user.get('first_name',''),'chatId':data['chat'],'pairedAt':int(time.time()*1000)}],
                'bindings':{},'settings':{'botId':me['id'],'username':me['username']}}
            self.save(rows+[bot]);self.start(bot);self.status.emit('','');return
        if kind!='message':return
        rows=self.list();bot=next((b for b in rows if b['id']==data['id']),None);m=data['message']
        if not bot or not bot.get('enabled') or m.get('chat',{}).get('type')!='private':return
        if not any(u['id']==str(m.get('from',{}).get('id')) for u in bot.get('users',[])):return
        text=m.get('text','').strip();chat=str(m['chat']['id'])
        if not text or text.startswith('/start'):return
        sid=bot.setdefault('bindings',{}).get(chat)
        scope=bot.get('scope',{'mode':'all'})
        if not sid:
            if scope.get('mode')=='sessions':
                sid=next((s for s in scope.get('sessions',[]) if self.shell._store.load_session(s)),None)
                if not sid:return
            else:
                persona=(scope.get('personas') or ['general'])[0]
                sid='remote-'+uuid.uuid4().hex[:16];self.shell._host.create_session({'sessionId':sid,'personaId':persona})
            bot['bindings'][chat]=sid;self.save(rows)
        session=self.shell._store.load_session(sid)
        if scope.get('mode')=='sessions' and sid not in scope.get('sessions',[]):return
        if scope.get('mode')=='personas' and session.personaId not in scope.get('personas',[]):return
        if self.shell._host.is_busy(sid):return
        self.turns[sid]=(bot['id'],chat)
        try:self.shell._host.send({'sessionId':sid,'text':text})
        except Exception as exc:self.status.emit(str(exc),'')

    def turn_event(self,payload):
        sid=payload.get('sessionId');event=payload.get('event',{});kind=event.get('type')
        if sid not in self.turns or kind not in ('text_delta','done','error'):return
        identity,chat=self.turns[sid];bot=next((b for b in self.list() if b['id']==identity),None)
        if not bot or not bot.get('enabled'):return
        state=self.streams.setdefault(sid,{'text':'','message_id':None,'busy':False,'sent':'','lock':threading.Lock()})
        if kind=='text_delta':
            state['text']+=event.get('text','')
            if bot.get('replyMode')!='stream' or state['busy']:return
        else:
            self.turns.pop(sid,None);self.streams.pop(sid,None)
            session=self.shell._store.load_session(sid)
            from qml_shell_sessions import transcript_markdown
            state['text']=transcript_markdown(session.messages[-1:],lang=self.shell.language()) if session.messages else event.get('message','')
            state['finished']=True
            if state['busy']:return
        token=self.shell._vault.get_secret('remote:'+identity+':botToken')
        if not token:return
        state['busy']=True
        def reply():
            try:
                # One writer per turn; newest text replaces the same Telegram message.
                while state['sent']!=state['text']:
                    text=state['text'][:4000]
                    if not text:break
                    if state['message_id']:
                        telegram(token,'editMessageText',{'chat_id':chat,'message_id':state['message_id'],'text':text})
                    else:
                        sent=telegram(token,'sendMessage',{'chat_id':chat,'text':text});state['message_id']=sent['message_id']
                    state['sent']=text
                    if len(state['text'])>4000:
                        if state.get('finished'):
                            for start in range(4000,len(state['text']),4000):telegram(token,'sendMessage',{'chat_id':chat,'text':state['text'][start:start+4000]})
                        break
                    if not state.get('finished'):time.sleep(1)
            except Exception as exc:self.delivered.emit({'kind':'state','id':identity,'state':'error: '+str(exc).replace(token,'[redacted]')})
            finally:state['busy']=False
        threading.Thread(target=reply,daemon=True).start()

    def close(self):
        self.link_cancel.set()
        for stop in self.workers.values():stop.set()
