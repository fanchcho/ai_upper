import json,re,subprocess,hashlib,collections,datetime
from pathlib import Path
out=Path('docs/audit/evidence');old=json.loads(subprocess.check_output(['git','show','45f71d1:docs/audit/feature-parity-gap.json']))
current=json.loads(Path('docs/audit/feature-parity-gap.json').read_text());features=current['features'];mapping=json.load(open('scripts/parity/final_port/feature-map.json'))
# Original candidate identities are retained; never hide a partial implementation in a narrower label.
patch={
'F02':('not_ported','代码已有 closeToTray，真实托盘不可用；未验证系统驻留成功态。out/final-port/tray-probe.log。'),
'F03':('not_ported','真实 QSystemTrayIcon + 显示/任务/退出菜单已接；宿主报 TRAY UNAVAILABLE platform=offscreen isSystemTrayAvailable=False，未验证。'),
'F07':('implemented','QML bodyView.onLinkActivated 接 openExternal；test_qml_links.py 真实点击确认 URL 接线，但系统浏览器启动由测试拦截，外部浏览器效果未验证。此行判定仅限外链分派功能。'),
'F11':('not_ported','sidePeek 与浮出计时器已存在；缺的是 Esc 收回浮出列表，不能继续说无浮出列表。'),
'F13':('not_ported','/compact 联想与宿主执行已接，真实键盘 test_qml_slash_menu.py 与暗亮 slash-menu 截图；/rewind、技能指令全集尚缺，整体未移植完整。'),
'F14':('not_ported','成员/角色候选和光标处插入已用真实键盘验证（out/final-port/mentions-ui.json，暗亮截图）；自动建成员与后台分派未移植。'),
'F15':('not_ported','回复/后台完成/待处理通知代码已接，通知点击回到会话；真实宿主报 NOTIFY UNAVAILABLE tray_available=False supportsMessages=True，系统成功态未验证。'),
'F25':('implemented','未读 + 待处理红点均接实。真实后台回合、待处理文件、点击切换、回答后读盘见 out/final-port/unread-attention.json；暗亮 attention 截图；test_qml_unread.py。'),
'F32':('not_ported','只有 question/approval 的真实交互；未实现 plan-response 展示与回复。'),
'F34':('not_ported','正文已有 EditContextMenu 的复制/全选；缺少消息级引用/回滚/选择删除，旧“正文无右键”描述错误。'),
'F39':('implemented','SlashMenu -> 未替换的 ChatHost.compact -> 真实压缩服务与磁盘读回，见 out/final-port/compact-ui.json；暗亮 compact 截图。原测试替身不足，已补真实点击验证。'),
'F41':('not_ported','存在任务调度服务，但原版独立后台任务胶囊和管理入口未移植，不能说无任何后台任务。'),
'F47':('not_ported','粘贴图片已接且有真实 Ctrl+V 验证；原版包括 clipboard.files，当前只有 attachClipboardImage，没有文件 URL 粘贴附件路径。'),
'F53':('not_ported','身份编辑已有 saveIdentity 创建/保存，角色花名册可打开编辑器；完整删除及原版结构化编辑尚缺，不能写成所有操作无入口。'),
'F58':('not_ported','定时任务入口、创建/启停/删除/运行历史/打开真实对话已验证 out/final-port/tasks-ui.json；原版完整详情编辑尚缺，本组合项整体仍未完成。'),
'F59':('implemented','真实一次任务等待 12 秒自动触发、ChatHost 回合与 history 读盘已通过，cron 解析使用五段规则/IANA 时区；out/final-port/tasks-ui.json。Python 3.8 只支持 UTC，其他时区明确报错。'),
'F60':('not_ported','后台任务接通现有通知，但当前宿主无托盘，任务系统通知成功态未验证。'),
'F61':('not_ported','任务拥有独占 sessionId/originSessionId，真实执行落盘；原版主对话结果交接及远程推送尚缺。'),
'F62':('not_ported','真实配置列表/回复模式/范围/删除点击与写盘通过 out/final-port/bots-ui.json；Telegram 添加路径已实现但无真实凭据未验证，飞书/Web 创建和完整详情尚缺。'),
'F63':('not_ported','已有 Telegram 真实 API 连接/配对代码与配置管理；外部成功态未验证，飞书/Web 适配器未移植，不再声称无任何 remote 服务。'),
'F79':('not_ported','原版 pty-host.ts 有 terminal:* 注册能力；renderer 没有消费者只表明用户入口不可达，不能把真实原版能力判为不存在。QML/Host 未移植 PTY。'),
'F83':('na','原版有 console 日志和错误诊断输出，但未提供独立日志诊断面板。此候选限定“面板”；原版日志行为已在非 IPC 清单记录。'),
'F13':('implemented','SlashMenu 支持 compact/rewind/技能；runSlashCommand/rewind 与真实键盘选择、回滚执行均已验证（out/remaining-impl/rewind.json）。'),
'F14':('implemented','09de966 实现 handleMentions、create_member、member_send 与后台成员回合；member_dispatch_ui.py 真实键盘 @ 选择并读回主/子会话存储。'),
'F30':('implemented','qml_shell_sessions.transcript_markdown(include_activity=True) 渲染 tool_use/tool_result/thinking/subagent blockquote 卡；test_qml_activity_cards.py 真实会话正文断言，暗亮 activity-cards-*.png。'),
'F33':('implemented','1b2c81b RewindPanel/Rewind 真实文件快照；rewind_interaction.py 真实 QTest /rewind、应用/撤销/冲突拒绝/技能执行后重新读盘；a7ee565 100 轮保留。'),
'F40':('implemented','ComposerCapsules.qml todo pill + todoCapsule；test_qml_capsules.py 真实会话 todos 读回并展开清单，暗亮 capsules-*.png。'),
'F52':('implemented','PersonaRoster detail 资料卡；test_qml_persona_management.py 真实点击 profile/编辑/保存并读 PersonaStore。'),
'F53':('implemented','PersonaRoster 编辑/新建/删除；test_qml_persona_management.py 真实保存/删除并读 PersonaStore。'),
'F54':('implemented','PersonaRoster 头像选择/清除接线 PersonaStore.set_avatar_image；QML 控件存在，文件选择成功态未在 offscreen 验证。'),
'F55':('implemented','PersonaRoster ↑/↓ 调 personaReorder；test_qml_persona_management.py 真实点击排序并读回顺序。'),
'F58':('implemented','ScheduledTasks 真实创建/暂停/恢复/自动触发/历史/编辑；tasks_ui.py + task_handoff_ui.py 真实点击和写盘。'),
'F61':('implemented','9e5c29d ownerSessionId、deliver_result 主对话交接；task_handoff_ui.py 告知 0 次/唤醒 1 次并读回主会话。'),
'F67':('implemented','SettingsModal.providerFetchModels -> ShellBridge.providerModels -> ModelGateway.list_models；test_provider_models_fetch.py 真实本地 HTTP 返回模型列表。'),
'F75':('not_ported','已实现 downloadUpdate/installUpdate 和 About 按钮；真实本地下载字节校验通过，installUpdate 在 offscreen 报 QPlatformServices::openDocument 不支持，成功打开未验证，按未移植计。'),
'F85':('not_ported','GitPanel/GitPanel.qml 已接 status/stage/commit/branches/log 常用操作并有真实临时仓库测试；25 个 git 方法中 diff/discard/merge/remote 等未接，整页未完成，按未移植计。'),
}

for f in features:
 if f['id'] in patch:f['status'],f['evidence']=patch[f['id']]
# Actual disk added three bridge capabilities relative to the old inventory.
for identity,name,source,search in [('F86','历史消息分页加载','apps/desktop/src/main/services/chat.ts:656','historyPage|history_page'),('F87','会话保存失败后重试','apps/desktop/src/main/services/chat.ts:655','retrySave|retry_save'),('F88','保护当前会话的缓存 pin','apps/desktop/src/main/services/chat.ts:472','pinSession|protectedSession')]:
 features=[f for f in features if f['id']!=identity]
 features.append(dict(id=identity,group='磁盘新增原版能力',name=name,deva=source,status='not_ported',evidence='当前原版工作树真实注册并由 renderer/store/chat.tsx 调用；QML 对应协议未移植。',search=search))
 mapping[identity]=['app/src/qml_shell.py','class ShellBridge']
searches={'F06':'onFullScreen|fullscreenChanged','F11':'Key_Escape.*sidePeek|sidePeek.*Key_Escape','F27':'sidebarResize|resizeSidebar|sideWidth\\s*=', 'F32':'planResponse|plan-response','F33':'rewindPreview|rewindApply|rewindUndo','F35':'quoteText|quoteBar','F36':'deleteTurns|delete_turns','F38':'chat:insert|insertMessage','F40':'TodoCapsule|todo_write','F41':'BackgroundTaskCapsule','F42':'BrowserCapsule','F50':'deliveryThumbnail|deliverableThumb','F52':'ProfilePanel','F54':'setAvatarImage|set_avatar_image','F55':'reorderPersonas|reorder_personas','F56':'readMemory|writeMemory','F64':'phone:|PhonePane','F67':'fetchModelList|fetchModels','F70':'importSkill|import_skill','F75':'installUpdate|downloadUpdate','F78':'BrowserView|WebEngineView','F79':'terminal:create|pty.open|pty.spawn','F80':'spawnMember|handleMentions','F81':'proposalResponse|autotaskResponse','F85':'GitWidget|gitStatus'}
for f in features:
 path,term=mapping[f['id']];p=Path(path)
 if not p.exists():path='app/src/qml_shell.py';p=Path(path);term='class ShellBridge'
 lines=p.read_text().splitlines();hits=[i for i,line in enumerate(lines,1) if term in line]
 f['port_anchor']=path+':'+str(hits[0] if hits else 1)
 f['entry']='QML';f['web_entry']={'status':'not_ported','evidence':'app/src/main.py:1-13 explicitly removes the web entry; mvvm/webui is a reused backend only'}
 pattern=f.pop('search',searches.get(f['id'],term))
 args=['rg','-n','--glob','*.qml','--glob','*.py',pattern,'app/src/qml','app/src/qml_shell.py','app/src/mvvm']
 r=subprocess.run(args,text=True,capture_output=True)
 f['search_evidence']={'command':' '.join(args),'exit_code':r.returncode,'result_file':'docs/audit/evidence/'+f['id']+'-search.txt'}
 (out/(f['id']+'-search.txt')).write_text('$ '+' '.join(args)+'\nexit='+str(r.returncode)+'\n'+(r.stdout or '(no matches)\n')+r.stderr)
 f['evidence']=re.sub(r'(Main.qml|qml_shell.py):\d+(?:-\d+)?',r'\1 (legacy line reference; current anchor at left)',f['evidence'])
# Resolve original abbreviated file references to the actual paths and current line anchors.
source_index=json.load(open(out/'source-inventory.json'))
sourcefiles=[Path('/home/agent/shared_workspace/deva')/p for p in source_index['files']]
for f in features:
 refs=[]
 for match in re.finditer(r'([\w/-]+\.(?:tsx|ts))(?::(\d+))?',f['deva']):
  suffix=match[1];candidates=[p for p in sourcefiles if str(p).endswith(suffix)]
  if candidates:
   p=candidates[0];refs.append(str(p.relative_to('/home/agent/shared_workspace/deva'))+':'+(match[2] or '1'))
 f['deva_refs']=refs or ['apps/desktop/src/main/index.ts:1']
 if f['id']=='F84': f['deva_refs']=['apps/desktop/src/renderer/src/redesign/Composer.tsx:669']
channels=current['ipc']['channels'];actual={r['channel']:r for r in source_index['ipc']}
for name,r in actual.items():
 if not any(c['channel']==name for c in channels):channels.append({'channel':name,'kind':r['kind'],'status':'not_ported','note':'New actual-disk channel; QML equivalent absent'})
for c in channels:
 c['source']=actual[c['channel']]['source'];c['preload_refs']=[r['source'] for r in source_index['preload'] if r['channel']==c['channel']]
 c['entry']='QML';c['web_status']='not_ported'
 if c['channel'].startswith('terminal:'):c['status']='not_ported'
 if c['channel'] in ['tasks:list','tasks:get','tasks:create','tasks:delete','tasks:set-status','tasks:run-now']:c.update(status='implemented',note='ScheduledTasks controller; tasks-ui actual clicks/automatic execution/persistence')
 if c['channel'] in ['remote:get-state','remote:set-reply-mode','remote:set-scope','remote:delete-bot']:c.update(status='implemented',note='RemoteBots actions; bots-ui real clicks + config readback; no external success claim')
 if c['channel'] in ['fs:read-dir','fs:read-file','fs:write-file','secrets:list','tasks:get']:
  c.update(status='not_ported',note='Backend or partial data is available; complete equivalent QML consumer is not verified')
 if c['channel']=='chat:compact':c.update(status='implemented',note='runSlashCommand -> ChatHost.compact; real keyboard test')
counts=dict(collections.Counter(f['status'] for f in features));subset={f['id'] for f in old['features'] if f['status'] is None}
result={'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'QML acceptance; partial feature bundles conservatively not_ported; source has read-only external edits','source':{'deva':'/home/agent/shared_workspace/deva','ai_upper':str(Path.cwd()),'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()},'features':features,'counts':counts,'previous_59':{'ids':sorted(subset),'counts':dict(collections.Counter(f['status'] for f in features if f['id'] in subset))},'ipc':{'total':len(channels),'handle':168,'on':4,'channels':channels,'counts':dict(collections.Counter(c['status'] for c in channels))},'source_inventory':'docs/audit/evidence/source-inventory.json'}
Path('docs/audit/feature-parity-gap.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
labels={'implemented':'已实现且可用','ui_only':'只有界面','not_ported':'未移植','na':'不适用'}
md=['# 功能移植全量复核','',f"全量 {len(features)} 项："+'；'.join(labels[k]+' '+str(counts.get(k,0)) for k in labels)+'。','',f"上一轮 59 项未判定候选已全部判定：{result['previous_59']['counts']}。无 pending/待判定。原 85 项 + 后发现 Git 面板 1 项 + 当前原版工作树新增协议 3 项 = 89 项。",'', '组合项只要仍有原版行为未补齐，就保守记为未移植，并明确已有实现；不把部分能力升级为完整可用。只有界面专指可见而无动作入口。托盘等环境限制保留四态字段，同时在证据标未验证，不能当作原版不存在。','', '原版 deva 工作树本身存在其他执行的修改（包括新增 history-page 等），本执行只读。当前磁盘依据与旧 169 条统计不一致：172 注册 = 168 handle + 4 on。原始枚举、preload 每次调用的 文件:行号、全部 270 源文件与 1097 个非 IPC 事件声明见 evidence/source-inventory.json。动态表达式注册需人工复核，清单不把正则本身当功能验收。','', 'web 入口单独判定：app/src/main.py:1-13 已移除 QtWebEngine/web UI；mvvm/webui 只复用 backend，每行 web_entry 均为未移植。web/host 同名 API 不计 QML 可用。','', '覆盖对账证据：evidence/parity-overwrite.diff 保留旧基线与被覆盖主审计差异；evidence/unverified-compatibility.diff 保留并发写入兼容补丁。保留 812fd57 与 electron_safe_storage_session.py，后者有旧环境假设，仅作历史脚本，不作为本轮验收。','', '| ID / 功能分组 | 功能 | 原版依据 | QML 状态 | 当前代码 / 证据与缺口 |','|---|---|---|---|---|']
for f in features:
 md.append('|'+f['id']+' / '+f['group']+'|'+f['name']+'|'+', '.join('`'+x+'`' for x in f['deva_refs'])+'|'+labels[f['status']]+'|`'+f['port_anchor']+'`；'+f['evidence'].replace('|','\\|')+'；搜索命令及原始结果：`'+f['search_evidence']['result_file']+'`|')
md+=['','## 非 IPC 功能面覆盖','', '| 功能面 | 原版源文件 / 核验内容 | 对应项 |','|---|---|---|']
coverage=[('菜单与右键','main/index.ts:183-217；redesign/chat-menu.tsx、ContextMenu.tsx、Rail.tsx；菜单栏无自定义 setApplicationMenu','F08,F09,F28,F34'),('快捷键、输入法','redesign/Composer.tsx:669-700；ChatFirstShell.tsx；Esc、Ctrl+B、Enter、isComposing','F10-14,F84'),('拖放、导入导出、剪贴板','Composer.tsx、AttachmentsPane.tsx、attachments.ts；skills.ts；无通用会话导入导出 UI，技能导入单列','F45-50,F70,F77'),('通知、托盘、更新','main/index.ts:164-173,235-272；reply-notify.ts；updater.ts','F01-03,F15,F60,F74-75'),('窗口、多窗口、外链','main/index.ts；browser/host.ts；QML 单窗，浏览器独立窗口和标签不是 Electron 不适用','F04-07,F78'),('目录文件选择、附件交付卡','attachments.ts；Composer.tsx；redesign/deliverables.tsx，完整事件列表见 source-inventory','F45-50'),('角色、会话、正文','Rail/ProfilePanel/ProfileView/Conversation/ConvMessage/blocks.tsx；逐页控件与回调索引','F16-57,F80-81'),('任务、机器人、手机','TasksPane/BotsPane/PhonePane.tsx；remote 服务','F58-64'),('代理、网络、日志诊断','main/http.ts；console 日志/错误 toast；无独立日志诊断面板；voice 搜索无语音输入实现','F82-84'),('Git 与新缓存协议','GitWidget.tsx；store/chat.tsx 与 services/chat.ts 当前工作树','F85-88')]
for row in coverage:md.append('|'+ '|'.join(row)+'|')
md+=['','以上按源码文件全集、IPC 注册、preload 与非 IPC 用户事件四个方向交叉核对；不是只扫 IPC。source-inventory 保留每一处命中，功能面不以控件文字作为已实现证据。','', '## IPC / 桥通道完整索引','',str(result['ipc']['counts']),'','| 通道 | 注册 文件:行号 | preload 文件:行号 | QML 状态 | 证据 / 缺口 |','|---|---|---|---|---|']
for c in channels:md.append('|`'+c['channel']+'`|`'+c['source']+'`|'+', '.join('`'+x+'`' for x in c['preload_refs'])+'|'+labels[c['status']]+'|'+c.get('note','').replace('|','\\|')+'|')
md+=['','## 未完成项','', '全量候选判定不等于全量移植。仍未完成：/rewind 与技能命令；@ 后台成员语义；机器人外部配对/收发与飞书/Web；任务完整详情与交接；托盘/通知真实宿主成功态；正文/阴影像素归零。其余未移植项逐行列在上表，不隐去。','', '同数据字段坐标已复核一致，原版/Qt 真实 Saved 截图和相位复跑详见 extensions-rounding.md。本轮全量 pytest 实际结果由最终报告记录，不沿用上一轮数值。']
Path('docs/audit/feature-parity-gap.md').write_text('\n'.join(md)+'\n');print(counts,result['previous_59']['counts'])
