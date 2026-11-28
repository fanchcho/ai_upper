"""Persistent remote bot management; Telegram ownership linking and private chats.

Reference: deva remote/index.ts, store.ts, telegram-onboard.ts. External
connectivity is reported separately from saved configuration.
"""
from __future__ import annotations
import asyncio,json,os,re,secrets,threading,time,uuid
from mvvm.services.provider_setup import build_transport


def telegram(token,method,payload):
    async def call():
        transport=build_transport()
        try:
            base=os.environ.get('AI_UPPER_TELEGRAM_API','https://api.telegram.org')
            response=await transport.post(base.rstrip('/')+'/bot'+token+'/'+method,
                headers={'Content-Type':'application/json'},body=json.dumps(payload).encode())
            result=json.loads(await response.text())
            if not result.get('ok'):raise RuntimeError(result.get('description','Telegram request failed'))
            return result['result']
        finally:await transport.aclose()
    return asyncio.run(call())


def RemoteBots(shell):
    """Create the native controller lazily after the Qt application starts."""
    from utils.qt_compat import QtCore, Signal, Slot

    class Controller(QtCore.QObject):
        changed=Signal()
        status=Signal(str,str)
        delivered=Signal(object)
        scanChanged=Signal('QVariantMap')
    
        def __init__(self,shell):
            super().__init__(shell);self.shell=shell;self.workers={};self.states={};self.turns={};self.streams={};self.link_cancel=threading.Event();self.pairing={}
            self.scan_cancel=threading.Event();self.scan_id=''
            self.delivered.connect(self.receive,QtCore.Qt.QueuedConnection)
            QtCore.QCoreApplication.instance().aboutToQuit.connect(self.close)
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
                    self.pairing.pop(identity,None)
                    bot['enabled']=False;self.states[identity]='off'
                    if action=='delete':
                        for field in ('botToken','appSecret','verificationToken','encryptKey','vapid','deskKey',*('dev:'+u['id'] for u in bot.get('users',[]))):
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
                    if bot['platform']=='web':
                        self.shell._vault.delete_secret('remote:'+identity+':dev:'+value)
                        worker=self.workers.get(identity)
                        if worker:worker.revoke(value)
                else:raise ValueError('未知机器人操作')
                self.save(rows);return ''
            except Exception as exc:return str(exc)
    
        @Slot(str,result='QVariantList')
        def scopeChoices(self,kind):
            if kind=='personas':
                return [{'id':p['id'],'title':p['name']} for p in self.shell.personaRecords()]
            return [{'id':s.id,'title':s.title or s.id} for s in self.shell._store.list_sessions()]

        @Slot(str)
        def cancelPair(self,identity):
            self.pairing.pop(identity,None)
            self.status.emit('配对邀请已取消','')

        @Slot()
        def startFeishuScan(self):
            from mvvm.services.feishu_onboard import scan
            self.cancelScan();self.scan_cancel=threading.Event();self.scan_id=uuid.uuid4().hex
            current=self.scan_id;cancel=self.scan_cancel
            self.scanChanged.emit({'status':'loading'})
            threading.Thread(target=scan,args=(cancel,lambda result:self.delivered.emit(
                {'kind':'scan','scanId':current,**result})),daemon=True).start()

        @Slot()
        def cancelScan(self):
            self.scan_cancel.set();self.scan_id=''
            self.scanChanged.emit({'status':'cancelled'})

        @Slot(result=str)
        def webPairTicket(self):
            bot=next((b for b in self.list() if b['platform']=='web'),None)
            if not bot:
                bot={'id':'web_'+uuid.uuid4().hex[:12],'name':'本地浏览器','platform':'web','enabled':True,'users':[],'bindings':{},'settings':{},'replyMode':'final','scope':{'mode':'all','personas':[],'sessions':[]}}
                self.save(self.list()+[bot])
            elif not bot.get('enabled'):
                rows=self.list();next(b for b in rows if b['id']==bot['id'])['enabled']=True;self.save(rows)
            if bot['id'] not in self.workers:self.start(bot)
            return self.workers[bot['id']].issue()

        @Slot(str,str,result='QVariantMap')
        def phoneTicket(self,via,kind):
            try:
                bot=next((b for b in self.list() if b['platform']=='web'),None)
                if not bot:
                    self.webPairTicket();bot=next(b for b in self.list() if b['platform']=='web')
                rows=self.list();bot=next(b for b in rows if b['id']==bot['id'])
                bot['settings'].setdefault('deskId',secrets.token_hex(8));bot['settings']['lastVia']=via
                bot['name']='手机联动';bot['enabled']=True;self.save(rows)
                if bot['id'] not in self.workers:self.start(bot)
                return self.workers[bot['id']].phone_issue('lan' if via=='lan' else 'relay','link' if kind=='link' else 'pair')
            except Exception as exc:return {'error':str(exc)}

        @Slot(result='QVariantMap')
        def phoneState(self):
            bot=next((b for b in self.list() if b['platform']=='web'),None)
            if not bot:return {'added':False,'devices':[],'links':{'lan':'off','relay':'off'}}
            server=self.workers.get(bot['id'])
            return {'added':True,'id':bot['id'],'enabled':bot['enabled'],'devices':server.devices() if server else bot['users'],
                    'links':server.links if server else {'lan':'off','relay':'off'}}

        @Slot()
        def cancelPhoneQr(self):
            for bot in self.list():
                server=self.workers.get(bot['id'])
                if bot['platform']=='web' and server:
                    server.tickets={k:t for k,t in server.tickets.items() if t.get('sticky')}
                    if server.ticket and not server.ticket.get('sticky'):server.ticket=None
                    server.release_qr()

        @Slot(str)
        def copyLink(self,url):
            from utils.qt_compat import QtGui
            QtGui.QGuiApplication.clipboard().setText(url)

        @Slot(str,result=str)
        def feishuPairCode(self,identity):
            if not any(b['id']==identity and b['platform']=='feishu' for b in self.list()):return '机器人不存在'
            code=str(secrets.randbelow(1000000)).zfill(6);self.pairing[identity]={'code':code,'expires':time.time()+600,'failures':0}
            return '向机器人发送 /pair '+code+'（10分钟有效）'

        @Slot(str,str,str,result=str)
        def linkFeishu(self,app_id,secret,domain):
            if not app_id.strip() or not secret.strip():return '未验证：飞书 App ID 或 App Secret 未配置'
            identity='feishu_'+uuid.uuid4().hex[:12]
            if not self.shell._vault.set_secret('remote:'+identity+':appSecret',secret).get('ok'):return '系统密钥存储不可用'
            bot={'id':identity,'platform':'feishu','name':app_id.strip(),'enabled':True,'replyMode':'final','scope':{'mode':'all','sessions':[],'personas':[]},'users':[],'bindings':{},'settings':{'appId':app_id.strip(),'domain':'lark' if domain=='lark' else 'feishu'}}
            self.save(self.list()+[bot]);self.start(bot);return ''

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
            if identity in self.workers:return ''
            if bot.get('platform')=='feishu':
                from mvvm.services.feishu_inbound import connection
                self.workers[identity]=connection(self,bot,self.shell._vault,lambda state:self.delivered.emit({'kind':'state','id':identity,'state':state}),lambda event:self.delivered.emit({'kind':'feishu-event','id':identity,'event':event}))
                return ''
            if bot.get('platform')=='web':
                from mvvm.services.web_pairing import start
                self.workers[identity]=start(self,bot)
                if bot.get('settings',{}).get('deskId'):
                    for via in {u.get('via','relay') for u in bot.get('users',[])}:
                        try:self.workers[identity].phone_issue(via)
                        except Exception as exc:self.states[identity]='error: '+str(exc)
                    self.workers[identity].ticket=None;self.workers[identity].tickets.clear()
                self.states[identity]='本地配对服务已启动；外部推送未验证'
                return ''
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
            if kind=='scan':
                if data['scanId']!=self.scan_id or self.scan_cancel.is_set():return
                if data['status']=='done':
                    result=data['result'];identity='feishu_'+uuid.uuid4().hex[:12]
                    if not self.shell._vault.set_secret('remote:'+identity+':appSecret',result['client_secret']).get('ok'):
                        self.scanChanged.emit({'status':'error','error':'系统密钥存储不可用，无法安全保存机器人凭据。'});return
                    owner=result.get('user_info',{}).get('open_id')
                    bot={'id':identity,'platform':'feishu','name':result.get('name') or 'Deva','enabled':True,
                         'createdAt':int(time.time()*1000),'replyMode':'final','scope':{'mode':'all','sessions':[],'personas':[]},
                         'users':[{'id':owner,'chatId':'','pairedAt':int(time.time()*1000)}] if owner else [],'bindings':{},
                         'settings':{'appId':result['client_id'],'domain':data['domain']}}
                    self.save(self.list()+[bot]);self.start(bot)
                    self.scanChanged.emit({'status':'done','botId':identity});return
                self.scanChanged.emit({k:v for k,v in data.items() if k not in ('kind','scanId')});return
            if kind=='feishu-event':
                event=data['event'].get('event',{});message=event.get('message',{});sender=event.get('sender',{}).get('sender_id',{}).get('open_id','')
                if message.get('chat_type')!='p2p' or message.get('message_type')!='text':return
                text=json.loads(message.get('content','{}')).get('text','');rows=self.list();bot=next((b for b in rows if b['id']==data['id']),None)
                if not bot or not bot.get('enabled') or not sender:return
                if text.startswith('/pair '):
                    pair=self.pairing.get(bot['id'])
                    if not pair or time.time()>pair['expires']:
                        self.pairing.pop(bot['id'],None);self.status.emit('配对码已过期或尚未生成','');return
                    if not secrets.compare_digest(text[6:].strip(),pair['code']):
                        pair['failures']+=1
                        if pair['failures']>=5:self.pairing.pop(bot['id'],None)
                        self.status.emit('配对码错误次数过多，已作废' if pair['failures']>=5 else '配对码不正确','');return
                    self.pairing.pop(bot['id'],None)
                    bot['users']=[u for u in bot['users'] if u['id']!=sender]+[{'id':sender,'chatId':message['chat_id'],'name':sender,'pairedAt':int(time.time()*1000)}]
                    self.save(rows);self.status.emit('已配对','');return
                self.receive({'kind':'message','id':bot['id'],'message':{'text':text,'chat':{'id':message.get('chat_id'),'type':'private'},'from':{'id':sender}}});return
            if kind=='push-result':
                rows=self.list();bot=next((b for b in rows if b['id']==data['id']),None)
                if bot:
                    bot['lastDelivery']=data['result']
                    if data['result']['status']=='gone':
                        for user in bot.get('users',[]):
                            if user['id']==data['userId']:user.pop('push',None)
                    self.save(rows)
                self.status.emit(json.dumps(data['result'],ensure_ascii=False),'');return
            if kind=='link':
                from mvvm.services.qr_image import qr_image
                self.scanChanged.emit({'status':'waiting','url':data['url'],'qr':qr_image(data['url']),'expiresAt':int((time.time()+600)*1000)})
                self.status.emit('',data['url']);return
            if kind=='link-error':
                self.scanChanged.emit({'status':'error','error':data['message']})
                self.status.emit(data['message'],'');return
            if kind=='state':
                self.states[data['id']]=data['state']
                # Feishu owns its reconnect timer; keep it available for disable/close.
                if data['state'].startswith('error') and isinstance(self.workers.get(data['id']),threading.Event):self.workers.pop(data['id'],None)
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
                self.save(rows+[bot]);self.start(bot);self.scanChanged.emit({'status':'done','botId':identity});self.status.emit('','');return
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
    
        def publish_notice(self,sid,title,body):
            session=self.shell._store.load_session(sid)
            sent=0;reasons=[]
            for bot in self.list():
                if not bot.get('enabled'):continue
                scope=bot.get('scope',{'mode':'all'})
                if scope.get('mode')=='sessions' and sid not in scope.get('sessions',[]):continue
                if scope.get('mode')=='personas' and (not session or session.personaId not in scope.get('personas',[])):continue
                if bot.get('platform') in ('feishu','web'):
                    from mvvm.services.channel_push import push
                    users=bot.get('users',[])
                    if bot['platform']=='web':
                        server=self.workers.get(bot['id']);users=[u for u in users if not (server and server.visible(u['id']))]
                    if not users:reasons.append('未配置可用的已配对远程渠道');continue
                    def deliver(bot=bot,users=users):
                        for user in users:
                            result=push(self.shell._vault,bot,user,title,body,sid)
                            self.delivered.emit({'kind':'push-result','id':bot['id'],'userId':user['id'],'result':result})
                    threading.Thread(target=deliver,daemon=True).start();sent+=len(users);continue
                if bot.get('platform')!='telegram':reasons.append('渠道未接入');continue
                token=self.shell._vault.get_secret('remote:'+bot['id']+':botToken')
                if not token:reasons.append('机器人密钥不存在或系统密钥库不可用');continue
                for user in bot.get('users',[]):
                    chat=user.get('chatId')
                    if not chat:continue
                    def send(token=token,chat=chat):
                        try:telegram(token,'sendMessage',{'chat_id':chat,'text':(title+'\n'+body)[:4000]})
                        except Exception as exc:self.status.emit(str(exc),'')
                    threading.Thread(target=send,daemon=True).start();sent+=1
            return {'status':'queued' if sent else 'unverified','recipients':sent,'reason':'; '.join(reasons) or ('未配置可用的已配对远程渠道' if not sent else '')}

        def turn_event(self,payload):
            sid=payload.get('sessionId');event=payload.get('event',{});kind=event.get('type')
            if kind in ('done','error') and sid not in self.turns:
                for bot in self.list():
                    server=self.workers.get(bot['id'])
                    if bot['platform']=='web' and server:server.publish(sid)
            if sid not in self.turns or kind not in ('text_delta','done','error'):return
            identity,chat=self.turns[sid];bot=next((b for b in self.list() if b['id']==identity),None)
            if not bot or not bot.get('enabled'):return
            if bot.get('platform')=='web':
                if kind in ('done','error'):
                    server=self.workers.get(identity)
                    if server:server.publish(sid)
                    self.turns.pop(sid,None)
                return
            if bot.get('platform')!='telegram':return
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
            self.scan_cancel.set()
            for stop in self.workers.values():stop.set()

    return Controller(shell)
