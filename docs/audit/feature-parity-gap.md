# 功能移植全量复核

全量 89 项：已实现且可用 57；只有界面 1；未移植 27；不适用 4。

上一轮 59 项未判定候选已全部判定：{'not_ported': 20, 'implemented': 34, 'na': 4, 'ui_only': 1}。无 pending/待判定。原 85 项 + 后发现 Git 面板 1 项 + 当前原版工作树新增协议 3 项 = 89 项。

组合项只要仍有原版行为未补齐，就保守记为未移植，并明确已有实现；不把部分能力升级为完整可用。只有界面专指可见而无动作入口。托盘等环境限制保留四态字段，同时在证据标未验证，不能当作原版不存在。

原版 deva 工作树本身存在其他执行的修改（包括新增 history-page 等），本执行只读。当前磁盘依据与旧 169 条统计不一致：172 注册 = 168 handle + 4 on。原始枚举、preload 每次调用的 文件:行号、全部 270 源文件与 1097 个非 IPC 事件声明见 evidence/source-inventory.json。动态表达式注册需人工复核，清单不把正则本身当功能验收。

web 入口单独判定：app/src/main.py:1-13 已移除 QtWebEngine/web UI；mvvm/webui 只复用 backend，每行 web_entry 均为未移植。web/host 同名 API 不计 QML 可用。

覆盖对账证据：evidence/parity-overwrite.diff 保留旧基线与被覆盖主审计差异；evidence/unverified-compatibility.diff 保留并发写入兼容补丁。保留 812fd57 与 electron_safe_storage_session.py，后者有旧环境假设，仅作历史脚本，不作为本轮验收。

| ID / 功能分组 | 功能 | 原版依据 | QML 状态 | 当前代码 / 证据与缺口 |
|---|---|---|---|---|
|F01 / 应用生命周期与窗口|单实例锁与二次启动唤起|`apps/desktop/src/main/index.ts:276`|已实现且可用|`app/src/mvvm/services/single_instance.py:5`；app/src/mvvm/services/single_instance.py（QLockFile + QLocalServer/QLocalSocket）；qml_shell.run 先 acquire 后建窗、instance.attach(window) 唤起；app/tests/test_single_instance.py 起两个真实进程，第二个 rc=0 且第一个打印激活日志；搜索命令及原始结果：`docs/audit/evidence/F01-search.txt`|
|F02 / 应用生命周期与窗口|关窗驻留托盘（closeToTray）|`apps/desktop/src/main/index.ts:164`, `apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:101`|未移植|`app/src/qml/Main.qml:52`；代码已有 closeToTray，真实托盘不可用；未验证系统驻留成功态。out/final-port/tray-probe.log。；搜索命令及原始结果：`docs/audit/evidence/F02-search.txt`|
|F03 / 应用生命周期与窗口|系统托盘图标与菜单（显示/定时任务/退出）|`apps/desktop/src/main/index.ts:235`, `apps/desktop/src/main/services/tray-icon.ts:1`|未移植|`app/src/mvvm/services/tray.py:21`；真实 QSystemTrayIcon + 显示/任务/退出菜单已接；宿主报 TRAY UNAVAILABLE platform=offscreen isSystemTrayAvailable=False，未验证。；搜索命令及原始结果：`docs/audit/evidence/F03-search.txt`|
|F04 / 应用生命周期与窗口|窗口最小化/最大化/关闭|`apps/desktop/src/main/index.ts:307`, `apps/desktop/src/preload/index.ts:625`|已实现且可用|`app/src/qml/Main.qml:2855`；Main.qml (legacy line reference; current anchor at left) 三个 WindowControlButton 接 showMinimized/showNormal\|showMaximized/close；app/tests/test_qml_window_controls.py 用 QTest 真实点击并断言窗口状态；搜索命令及原始结果：`docs/audit/evidence/F04-search.txt`|
|F05 / 应用生命周期与窗口|窗口控件叠加配色随主题|`apps/desktop/src/main/index.ts:79`|已实现且可用|`app/src/qml/Main.qml:412`；Main.qml (legacy line reference; current anchor at left) WindowControlButton.glyphColor 按 Theme.dark 取 #E8EAED/#5F6368，底色调 Theme.bgInset；注释逐值对齐 index.ts:79-97；搜索命令及原始结果：`docs/audit/evidence/F05-search.txt`|
|F06 / 应用生命周期与窗口|全屏状态通知（macOS 红绿灯让位）|`apps/desktop/src/main/index.ts:158`, `apps/desktop/src/preload/index.ts:631`, `apps/desktop/src/renderer/src/redesign/ChatFirstShell.tsx:52`|未移植|`app/src/qml/Main.qml:32`；Main.qml (legacy line reference; current anchor at left),62 仅按 Qt.platform.os === 'osx' 静态加宽，无 window:fullscreen 等价信号，无 onFullScreen；搜索命令及原始结果：`docs/audit/evidence/F06-search.txt`|
|F07 / 应用生命周期与窗口|外链一律系统浏览器打开|`apps/desktop/src/main/index.ts:175`|已实现且可用|`app/src/qml_shell.py:1900`；QML bodyView.onLinkActivated 接 openExternal；test_qml_links.py 真实点击确认 URL 接线，但系统浏览器启动由测试拦截，外部浏览器效果未验证。此行判定仅限外链分派功能。；搜索命令及原始结果：`docs/audit/evidence/F07-search.txt`|
|F08 / 菜单与快捷键|应用菜单栏|`apps/desktop/src/main/index.ts:108`|不适用|`app/src/qml/Main.qml:18`；原版没有自定义菜单栏，不凭空造；搜索命令及原始结果：`docs/audit/evidence/F08-search.txt`|
|F09 / 菜单与快捷键|编辑区右键菜单（剪切/复制/粘贴/全选）|`apps/desktop/src/main/index.ts:183`|已实现且可用|`app/src/qml/EditContextMenu.qml:7`；app/src/qml/EditContextMenu.qml + Main.qml composerMenu/bodyMenu；app/tests/test_qml_edit_menu.py 真实右键打开并点「全选」断言 selectedText；暗亮截图 out/feature-parity/edit-menu-*.png；搜索命令及原始结果：`docs/audit/evidence/F09-search.txt`|
|F10 / 菜单与快捷键|Ctrl/Cmd+B 收起/展开会话列表|`apps/desktop/src/renderer/src/redesign/ChatFirstShell.tsx:191`|已实现且可用|`app/src/qml/Main.qml:99`；Main.qml Shortcut Ctrl+B/Meta+B → toggleSidebar；qml_shell.py sidebarCollapsed/setSidebarCollapsed 写 config.json；app/tests/test_qml_sidebar_collapse.py 真实按键 + hover peek；搜索命令及原始结果：`docs/audit/evidence/F10-search.txt`|
|F11 / 菜单与快捷键|Esc 收回浮出列表|`apps/desktop/src/renderer/src/redesign/ChatFirstShell.tsx:192`|未移植|`app/src/qml/Main.qml:142`；sidePeek 与浮出计时器已存在；缺的是 Esc 收回浮出列表，不能继续说无浮出列表。；搜索命令及原始结果：`docs/audit/evidence/F11-search.txt`|
|F12 / 菜单与快捷键|Enter 发送 / Shift+Enter 换行|`apps/desktop/src/renderer/src/redesign/Composer.tsx:669`|已实现且可用|`app/src/qml/Main.qml:1663`；Main.qml (legacy line reference; current anchor at left) inputField.Keys.onPressed：Return/Enter 且带 Shift 时放行，否则 window.submit()；搜索命令及原始结果：`docs/audit/evidence/F12-search.txt`|
|F13 / 菜单与快捷键|输入框 / 指令联想（/compact /rewind /技能）|`apps/desktop/src/renderer/src/redesign/Composer.tsx:382`|已实现且可用|`app/src/qml_shell.py:1640`；SlashMenu 支持 compact/rewind/技能；runSlashCommand/rewind 与真实键盘选择、回滚执行均已验证（out/remaining-impl/rewind.json）。；搜索命令及原始结果：`docs/audit/evidence/F13-search.txt`|
|F14 / 菜单与快捷键|@ 提及成员/角色|`apps/desktop/src/renderer/src/redesign/Composer.tsx:399`, `apps/desktop/src/shared/mention.ts:1`|已实现且可用|`app/src/qml_shell.py:1622`；09de966 实现 handleMentions、create_member、member_send 与后台成员回合；member_dispatch_ui.py 真实键盘 @ 选择并读回主/子会话存储。；搜索命令及原始结果：`docs/audit/evidence/F14-search.txt`|
|F15 / 菜单与快捷键|回复完成/待处理系统通知|`apps/desktop/src/main/services/reply-notify.ts:15`, `apps/desktop/src/main/services/chat-turns.ts:801`|未移植|`app/src/qml_shell.py:2021`；回复/后台完成/待处理通知代码已接，通知点击回到会话；真实宿主报 NOTIFY UNAVAILABLE tray_available=False supportsMessages=True，系统成功态未验证。；搜索命令及原始结果：`docs/audit/evidence/F15-search.txt`|
|F16 / 会话列表|新建会话|`apps/desktop/src/renderer/src/redesign/Rail.tsx:600`, `apps/desktop/src/preload/index.ts:805`|已实现且可用|`app/src/qml_shell.py:669`；Main.qml (legacy line reference; current anchor at left) 加号 onClicked shellBridge.newSession；qml_shell.py (legacy line reference; current anchor at left) 建真实会话并落盘；搜索命令及原始结果：`docs/audit/evidence/F16-search.txt`|
|F17 / 会话列表|切换会话|`apps/desktop/src/renderer/src/redesign/Rail.tsx:700`|已实现且可用|`app/src/qml_shell.py:658`；Main.qml (legacy line reference; current anchor at left) 行 onClicked openSession；qml_shell.py (legacy line reference; current anchor at left) 读真实会话；搜索命令及原始结果：`docs/audit/evidence/F17-search.txt`|
|F18 / 会话列表|重命名会话|`apps/desktop/src/renderer/src/redesign/Rail.tsx:175`|已实现且可用|`app/src/qml_shell.py:701`；Main.qml (legacy line reference; current anchor at left) 右键菜单 rename + 重命名弹层；qml_shell.py (legacy line reference; current anchor at left) 写盘；搜索命令及原始结果：`docs/audit/evidence/F18-search.txt`|
|F19 / 会话列表|删除会话|`apps/desktop/src/renderer/src/redesign/Rail.tsx:175`|已实现且可用|`app/src/qml_shell.py:681`；Main.qml 右键 delete + 确认框；qml_shell.py (legacy line reference; current anchor at left) 删会话文件；搜索命令及原始结果：`docs/audit/evidence/F19-search.txt`|
|F20 / 会话列表|归档/取消归档|`apps/desktop/src/renderer/src/redesign/Rail.tsx:620`|已实现且可用|`app/src/qml_shell.py:717`；Main.qml (legacy line reference; current anchor at left) 归档横幅与右键 archive；qml_shell.py (legacy line reference; current anchor at left) archiveSession/unarchiveSession/archiveSessions；搜索命令及原始结果：`docs/audit/evidence/F20-search.txt`|
|F21 / 会话列表|归档视图|`apps/desktop/src/renderer/src/redesign/Rail.tsx:1`|已实现且可用|`app/src/qml/Main.qml:204`；Main.qml (legacy line reference; current anchor at left) archiveHeader/archiveBack，Python archivedSessions 投影；搜索命令及原始结果：`docs/audit/evidence/F21-search.txt`|
|F22 / 会话列表|会话搜索（标题/角色/挂载目录）|`apps/desktop/src/renderer/src/redesign/Rail.tsx:600`|已实现且可用|`app/src/qml/Main.qml:291`；Main.qml (legacy line reference; current anchor at left) visibleSessions 按 title/personaName/focusName 过滤；搜索框 Main.qml (legacy line reference; current anchor at left) 可聚焦输入；搜索命令及原始结果：`docs/audit/evidence/F22-search.txt`|
|F23 / 会话列表|会话筛选面板（角色/文件夹）|`apps/desktop/src/renderer/src/redesign/Rail.tsx:183`|已实现且可用|`app/src/qml/SessionFilter.qml:5`；Main.qml (legacy line reference; current anchor at left) filterBtn → SessionFilter.qml；filterRoles/filterFolders/visibleSessions 同类 OR、跨类 AND；scripts/parity/feature_review/filter_evidence.py 真实点击角色+完整目录路径并读回 visibleSessions；暗亮截图 out/parity-close/filter-*.png；搜索命令及原始结果：`docs/audit/evidence/F23-search.txt`|
|F24 / 会话列表|会话多选批量归档/删除|`apps/desktop/src/renderer/src/redesign/ThreadSelect.tsx:1`|已实现且可用|`app/src/qml/Main.qml:205`；Main.qml (legacy line reference; current anchor at left),684-800,1898-1940 selectMode/selectedSessions + 批量归档/删除；搜索命令及原始结果：`docs/audit/evidence/F24-search.txt`|
|F25 / 会话列表|未读/待处理状态与红点|`apps/desktop/src/renderer/src/redesign/Rail.tsx:116`, `apps/desktop/src/renderer/src/store/chat.tsx:1`|已实现且可用|`app/src/qml/ThreadRow.qml:73`；未读 + 待处理红点均接实。真实后台回合、待处理文件、点击切换、回答后读盘见 out/final-port/unread-attention.json；暗亮 attention 截图；test_qml_unread.py。；搜索命令及原始结果：`docs/audit/evidence/F25-search.txt`|
|F26 / 会话列表|草稿按会话保留|`apps/desktop/src/renderer/src/redesign/Composer.tsx:109`|已实现且可用|`app/src/qml/Main.qml:112`；Main.qml (legacy line reference; current anchor at left) composerDrafts 按 sessionId 保存 text+pendingFiles；scripts/parity/draft_evidence.py 真实键盘输入、真实拖放附件、切会话后读回；drafts.json 暗亮各一组；搜索命令及原始结果：`docs/audit/evidence/F26-search.txt`|
|F27 / 会话列表|会话列表宽度拖动|`apps/desktop/src/renderer/src/redesign/ChatFirstShell.tsx:143`|未移植|`app/src/qml/Main.qml:602`；Main.qml 侧栏宽固定 Theme.sideWidth（Main.qml (legacy line reference; current anchor at left),462-470），无拖动手柄；搜索命令及原始结果：`docs/audit/evidence/F27-search.txt`|
|F27b / 会话列表|会话列表收起/展开并记忆|`apps/desktop/src/renderer/src/redesign/ChatFirstShell.tsx:143`|已实现且可用|`app/src/qml/Main.qml:141`；Main.qml sideCollapsed/sidePeek + 200/150ms 浮出定时器；qml_shell.py (legacy line reference; current anchor at left) 落盘 config.json；真实截图 out/feature-parity/sidebar-{collapsed,peek}-{dark,light}.png；搜索命令及原始结果：`docs/audit/evidence/F27b-search.txt`|
|F28 / 会话列表|会话行右键菜单（新建/重命名/多选/归档/删除）|`apps/desktop/src/renderer/src/redesign/Rail.tsx:175`, `apps/desktop/src/renderer/src/redesign/ContextMenu.tsx:1`|已实现且可用|`app/src/qml/Main.qml:2466`；Main.qml (legacy line reference; current anchor at left) 自绘 contextMenu，动作齐全；test_qml_context_menu.py 真实右键触发；搜索命令及原始结果：`docs/audit/evidence/F28-search.txt`|
|F29 / 对话正文|用户/助手 Markdown 正文|`apps/desktop/src/renderer/src/redesign/ConvMessage.tsx:1`, `apps/desktop/src/renderer/src/features/chat/blocks.tsx:1`|已实现且可用|`app/src/qml_shell_sessions.py:330`；qml_shell.py (legacy line reference; current anchor at left) transcript_markdown → app/src/markdown/body.py 渲染进 QTextDocument；Main.qml (legacy line reference; current anchor at left)；搜索命令及原始结果：`docs/audit/evidence/F29-search.txt`|
|F30 / 对话正文|工具调用/工具结果/思考/子代理活动卡|`apps/desktop/src/renderer/src/features/chat/blocks.tsx:1`, `apps/desktop/src/renderer/src/redesign/ChatFirstShell.tsx:39`|已实现且可用|`app/src/qml_shell_sessions.py:330`；qml_shell_sessions.transcript_markdown(include_activity=True) 渲染 tool_use/tool_result/thinking/subagent blockquote 卡；test_qml_activity_cards.py 真实会话正文断言，暗亮 activity-cards-*.png。；搜索命令及原始结果：`docs/audit/evidence/F30-search.txt`|
|F31 / 对话正文|待处理交互卡（ask/审批）|`apps/desktop/src/renderer/src/features/chat/blocks.tsx:1`|已实现且可用|`app/src/qml/InteractionPrompt.qml:19`；InteractionPrompt.qml + qml_shell.py (legacy line reference; current anchor at left) pendingInteractions/answerInteraction（kind=question/approval）；搜索命令及原始结果：`docs/audit/evidence/F31-search.txt`|
|F32 / 对话正文|计划卡与 plan-response|`apps/desktop/src/renderer/src/features/chat/blocks.tsx:1`|未移植|`app/src/qml_shell.py:378`；只有 question/approval 的真实交互；未实现 plan-response 展示与回复。；搜索命令及原始结果：`docs/audit/evidence/F32-search.txt`|
|F33 / 对话正文|回滚 rewind（列点/预览/应用/撤销）|`apps/desktop/src/renderer/src/redesign/RewindModal.tsx:31`, `apps/desktop/src/renderer/src/redesign/Conversation.tsx:998`|已实现且可用|`app/src/mvvm/webui/host.py:441`；1b2c81b RewindPanel/Rewind 真实文件快照；rewind_interaction.py 真实 QTest /rewind、应用/撤销/冲突拒绝/技能执行后重新读盘；a7ee565 100 轮保留。；搜索命令及原始结果：`docs/audit/evidence/F33-search.txt`|
|F34 / 对话正文|消息右键菜单（复制/引用/回滚/选择删除）|`apps/desktop/src/renderer/src/redesign/Conversation.tsx:905`|未移植|`app/src/qml/Main.qml:71`；正文已有 EditContextMenu 的复制/全选；缺少消息级引用/回滚/选择删除，旧“正文无右键”描述错误。；搜索命令及原始结果：`docs/audit/evidence/F34-search.txt`|
|F35 / 对话正文|引用条 quote|`apps/desktop/src/renderer/src/redesign/ConvMessage.tsx:1`, `apps/desktop/src/renderer/src/redesign/Composer.tsx:1`|未移植|`app/src/qml/Main.qml:67`；`grep -rn "quote" app/src/qml app/src/qml_shell.py` 只命中 CSS/无关词；无引用状态；搜索命令及原始结果：`docs/audit/evidence/F35-search.txt`|
|F36 / 对话正文|选择消息删除（delete-turns）|`apps/desktop/src/renderer/src/redesign/Conversation.tsx:955`|未移植|`app/src/mvvm/webui/host.py:441`；host.py:415-425 delete_turns 有后端，但 QML 无入口（`grep -rn "deleteTurns" app/src/qml*` 无结果）；搜索命令及原始结果：`docs/audit/evidence/F36-search.txt`|
|F37 / 对话正文|停止生成|`apps/desktop/src/renderer/src/redesign/Composer.tsx:973`|已实现且可用|`app/src/qml_shell.py:1459`；qml_shell.py stopGeneration → host.abort；Main.qml sendBtn busy 时切 Square 中性态；app/tests/test_qml_stop_generation.py 真实鼠标点停止并断言 stopReason=aborted；暗亮截图 out/feature-parity/stop-busy-*.png；搜索命令及原始结果：`docs/audit/evidence/F37-search.txt`|
|F38 / 对话正文|回合中插入消息（插话）|`apps/desktop/src/renderer/src/redesign/Composer.tsx:463`|未移植|`app/src/qml/Main.qml:1651`；`grep -rn "insert" app/src/mvvm/webui/host.py app/src/qml_shell.py` 无 chat:insert 路径；搜索命令及原始结果：`docs/audit/evidence/F38-search.txt`|
|F39 / 对话正文|手动压缩 /compact|`apps/desktop/src/renderer/src/redesign/Composer.tsx:382`|已实现且可用|`app/src/qml_shell.py:1669`；SlashMenu -> 未替换的 ChatHost.compact -> 真实压缩服务与磁盘读回，见 out/final-port/compact-ui.json；暗亮 compact 截图。原测试替身不足，已补真实点击验证。；搜索命令及原始结果：`docs/audit/evidence/F39-search.txt`|
|F40 / 对话正文|Todo 胶囊|`apps/desktop/src/renderer/src/redesign/Composer.tsx:864`|已实现且可用|`app/src/mvvm/webui/host.py:498`；ComposerCapsules.qml todo pill + todoCapsule；test_qml_capsules.py 真实会话 todos 读回并展开清单，暗亮 capsules-*.png。；搜索命令及原始结果：`docs/audit/evidence/F40-search.txt`|
|F41 / 对话正文|后台任务胶囊|`apps/desktop/src/renderer/src/redesign/Composer.tsx:865`|已实现且可用|`app/src/qml/Main.qml:63`；ComposerCapsules background list + backgroundTasks/openBackground/cancelBackground；test_background_tasks.py 真实成员会话列表/打开；取消依赖真实 busy turn。；搜索命令及原始结果：`docs/audit/evidence/F41-search.txt`|
|F42 / 对话正文|浏览器操作胶囊|`apps/desktop/src/renderer/src/redesign/Composer.tsx:866`|不适用|`app/src/qml/Main.qml:63`；浏览器操作胶囊依赖原版内置浏览器（BrowserView），F78 路线 B 无 QtWebEngine，故不适用；原版依据 features/browser/BrowserCapsule.tsx、services/browser/host.ts。；搜索命令及原始结果：`docs/audit/evidence/F42-search.txt`|
|F43 / 对话正文|上下文用量圆环|`apps/desktop/src/renderer/src/redesign/ContextRing.tsx:1`|已实现且可用|`app/src/qml_shell.py:1128`；qml_shell.py (legacy line reference; current anchor at left) contextUsage 真实计算；Main.qml ContextRing；搜索命令及原始结果：`docs/audit/evidence/F43-search.txt`|
|F44 / 对话正文|模型/思考等级切换菜单|`apps/desktop/src/renderer/src/redesign/ModelMenu.tsx:1`, `apps/desktop/src/renderer/src/redesign/EffortPicker.tsx:1`|已实现且可用|`app/src/qml/ModelPicker.qml:30`；qml_shell.py (legacy line reference; current anchor at left) modelMenuGroups/effortMenu；Main.qml ModelPicker；搜索命令及原始结果：`docs/audit/evidence/F44-search.txt`|
|F45 / 对话正文|附件选择（回形针）|`apps/desktop/src/renderer/src/redesign/Composer.tsx:950`|已实现且可用|`app/src/qml_shell.py:1519`；Main.qml (legacy line reference; current anchor at left) clipBtn → pickAttachments；qml_shell.py (legacy line reference; current anchor at left) QFileDialog + AttachmentService；搜索命令及原始结果：`docs/audit/evidence/F45-search.txt`|
|F46 / 对话正文|附件拖放|`apps/desktop/src/renderer/src/redesign/Composer.tsx:576`|已实现且可用|`app/src/qml_shell.py:1546`；Main.qml DropArea + dropOverlay → shellBridge.acceptDroppedFiles；attachments.py inspect_paths 登记文件/文件夹；app/tests/test_qml_attachments_drop.py 用真实 QDragEnterEvent/QDropEvent 投递并断言 pendingFiles；暗亮截图 out/feature-parity/drop-overlay-*.png；搜索命令及原始结果：`docs/audit/evidence/F46-search.txt`|
|F47 / 对话正文|粘贴图片/文件为附件|`apps/desktop/src/renderer/src/redesign/Composer.tsx:508`|未移植|`app/src/qml_shell.py:1569`；粘贴图片已接且有真实 Ctrl+V 验证；原版包括 clipboard.files，当前只有 attachClipboardImage，没有文件 URL 粘贴附件路径。；搜索命令及原始结果：`docs/audit/evidence/F47-search.txt`|
|F48 / 对话正文|附件贴片与图片缩略图|`apps/desktop/src/renderer/src/redesign/attachments.tsx:1`|已实现且可用|`app/src/qml_shell_sessions.py:427`；qml_shell_sessions.py:304-329 attachment_rows + Main.qml (legacy line reference; current anchor at left) 贴片；图片 data URI 内联；搜索命令及原始结果：`docs/audit/evidence/F48-search.txt`|
|F49 / 对话正文|交付卡（打开/定位/复制路径）|`apps/desktop/src/renderer/src/features/chat/DeliverablesCard.tsx:1`|已实现且可用|`app/src/qml_shell.py:1600`；qml_shell.py (legacy line reference; current anchor at left) deliveryItems/openDeliverable/revealDeliverable/copyDeliverablePath；Main.qml (legacy line reference; current anchor at left)；搜索命令及原始结果：`docs/audit/evidence/F49-search.txt`|
|F50 / 对话正文|交付卡图片缩略图|`apps/desktop/src/main/index.ts:1`|未移植|`app/src/mvvm/services/transcript_parts.py:126`；delivery_row（transcript_parts.py:144-158）不含 thumb 字段，卡片只按类型画图标；搜索命令及原始结果：`docs/audit/evidence/F50-search.txt`|
|F51 / 角色|角色花名册 tab（列表/搜索/快速对话）|`apps/desktop/src/renderer/src/redesign/Rail.tsx:130`|已实现且可用|`app/src/qml/PersonaRoster.qml:128`；Main.qml (legacy line reference; current anchor at left) railRoster onClicked page=roster；PersonaRoster.qml 列表+搜索+开始会话；scripts/parity/feature_review/roster_evidence.py 真实点击入口、粘贴角色名搜索、点开始并读回会话 personaId；截图 out/parity-close/roster-*.png；搜索命令及原始结果：`docs/audit/evidence/F51-search.txt`|
|F52 / 角色|角色资料卡（ProfilePanel）|`apps/desktop/src/renderer/src/redesign/Rail.tsx:117`|已实现且可用|`app/src/qml/PersonaRoster.qml:8`；PersonaRoster detail 资料卡；test_qml_persona_management.py 真实点击 profile/编辑/保存并读 PersonaStore。；搜索命令及原始结果：`docs/audit/evidence/F52-search.txt`|
|F53 / 角色|新建/编辑/删除角色|`apps/desktop/src/renderer/src/redesign/ProfileView.tsx:1`|已实现且可用|`app/src/qml_shell.py:358`；PersonaRoster 编辑/新建/删除；test_qml_persona_management.py 真实保存/删除并读 PersonaStore。；搜索命令及原始结果：`docs/audit/evidence/F53-search.txt`|
|F54 / 角色|角色头像编辑|`apps/desktop/src/renderer/src/redesign/AvatarEditor.tsx:1`|已实现且可用|`app/src/mvvm/services/persona_store.py:269`；PersonaRoster 头像选择/清除接线 PersonaStore.set_avatar_image；QML 控件存在，文件选择成功态未在 offscreen 验证。；搜索命令及原始结果：`docs/audit/evidence/F54-search.txt`|
|F55 / 角色|角色排序（拖拽/置顶）|`apps/desktop/src/renderer/src/redesign/Rail.tsx:1`|已实现且可用|`app/src/mvvm/services/persona_store.py:260`；PersonaRoster ↑/↓ 调 personaReorder；test_qml_persona_management.py 真实点击排序并读回顺序。；搜索命令及原始结果：`docs/audit/evidence/F55-search.txt`|
|F56 / 角色|角色记忆查看/编辑|`apps/desktop/src/renderer/src/redesign/RoleMemoryTab.tsx:1`, `apps/desktop/src/renderer/src/redesign/MemoryDetail.tsx:1`|已实现且可用|`app/src/mvvm/services/persona_store.py:79`；memory_store.py 实现角色记忆 v2 JSON（personas/memory/<id>.json）；PersonaRoster 资料页新增列表/添加/删除；test_role_memory.py 真实写盘读回。；搜索命令及原始结果：`docs/audit/evidence/F56-search.txt`|
|F57 / 角色|快速开始角色卡|`apps/desktop/src/renderer/src/redesign/Rail.tsx:1`|已实现且可用|`app/src/qml_shell.py:885`；qml_shell.py (legacy line reference; current anchor at left) quickStartPersonas/startQuickStart；Main.qml 空态卡片；搜索命令及原始结果：`docs/audit/evidence/F57-search.txt`|
|F58 / 定时任务|定时任务页（列表/详情/运行历史）|`apps/desktop/src/renderer/src/redesign/TasksPane.tsx:1`|已实现且可用|`app/src/qml/ScheduledTasks.qml:42`；ScheduledTasks 真实创建/暂停/恢复/自动触发/历史/编辑；tasks_ui.py + task_handoff_ui.py 真实点击和写盘。；搜索命令及原始结果：`docs/audit/evidence/F58-search.txt`|
|F59 / 定时任务|任务调度引擎（once/cron、自动触发）|`apps/desktop/src/main/services/schedule.ts:1`, `apps/desktop/src/main/services/scheduler.ts:1`|已实现且可用|`app/src/mvvm/services/scheduled_tasks.py:10`；真实一次任务等待 12 秒自动触发、ChatHost 回合与 history 读盘已通过，cron 解析使用五段规则/IANA 时区；out/final-port/tasks-ui.json。Python 3.8 只支持 UTC，其他时区明确报错。；搜索命令及原始结果：`docs/audit/evidence/F59-search.txt`|
|F60 / 定时任务|任务系统通知|`apps/desktop/src/main/services/scheduler.ts:103`|未移植|`app/src/qml_shell.py:2021`；后台任务接通现有通知，但当前宿主无托盘，任务系统通知成功态未验证。；搜索命令及原始结果：`docs/audit/evidence/F60-search.txt`|
|F61 / 定时任务|任务绑定主对话与结果交接|`apps/desktop/src/main/services/chat-task-handoff.ts:1`|已实现且可用|`app/src/mvvm/services/scheduled_tasks.py:103`；9e5c29d ownerSessionId、deliver_result 主对话交接；task_handoff_ui.py 告知 0 次/唤醒 1 次并读回主会话。；搜索命令及原始结果：`docs/audit/evidence/F61-search.txt`|
|F62 / 机器人/手机|机器人页（Bots tab 列表/添加/详情）|`apps/desktop/src/renderer/src/redesign/BotsPane.tsx:1`|未移植|`app/src/qml/RemoteBots.qml:26`；真实配置列表/回复模式/范围/删除点击与写盘通过 out/final-port/bots-ui.json；Telegram 添加路径已实现但无真实凭据未验证，飞书/Web 创建和完整详情尚缺。；搜索命令及原始结果：`docs/audit/evidence/F62-search.txt`|
|F63 / 机器人/手机|远程渠道（Web/飞书/Telegram 扫码配对、回复模式/范围）|`apps/desktop/src/main/index.ts:1`|未移植|`app/src/mvvm/services/remote_bots.py:79`；已有 Telegram 真实 API 连接/配对代码与配置管理；外部成功态未验证，飞书/Web 适配器未移植，不再声称无任何 remote 服务。；搜索命令及原始结果：`docs/audit/evidence/F63-search.txt`|
|F64 / 机器人/手机|手机联动（QR/设备/中转）|`apps/desktop/src/renderer/src/redesign/PhonePane.tsx:1`, `apps/desktop/src/main/services/remote/web/phone.ts:1`|未移植|`app/src/qml/Main.qml:588`；移植版无 phone 服务/UI；搜索命令及原始结果：`docs/audit/evidence/F64-search.txt`|
|F65 / 设置与扩展|语言/主题/聊天字号|`apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:92`|已实现且可用|`app/src/qml_shell.py:560`；SettingsModal.qml:280-345 三行 SetRow → qml_shell.py (legacy line reference; current anchor at left) setLanguage/setTheme/setTextSize（sm/md/lg/xl）；搜索命令及原始结果：`docs/audit/evidence/F65-search.txt`|
|F66 / 设置与扩展|模型服务商列表/详情/密钥/请求头|`apps/desktop/src/renderer/src/features/settings/ModelSettings.tsx:1`|已实现且可用|`app/src/qml_shell.py:1008`；SettingsModal modelsPane + qml_shell.py (legacy line reference; current anchor at left)/850-861 setProviderHeaders；上一轮已验收；搜索命令及原始结果：`docs/audit/evidence/F66-search.txt`|
|F67 / 设置与扩展|从服务商拉取模型列表|`apps/desktop/src/main/services/provider.ts:74`, `apps/desktop/src/renderer/src/features/settings/ModelSettings.tsx:250`|已实现且可用|`app/src/mvvm/services/provider_setup.py:170`；SettingsModal.providerFetchModels -> ShellBridge.providerModels -> ModelGateway.list_models；test_provider_models_fetch.py 真实本地 HTTP 返回模型列表。；搜索命令及原始结果：`docs/audit/evidence/F67-search.txt`|
|F68 / 设置与扩展|自定义服务商/自定义模型|`apps/desktop/src/renderer/src/features/settings/ModelSettings.tsx:1`|已实现且可用|`app/src/qml_shell.py:979`；SettingsModal.qml:545 custom-model 入口 + qml_shell.py (legacy line reference; current anchor at left) addProvider/addModel；搜索命令及原始结果：`docs/audit/evidence/F68-search.txt`|
|F69 / 设置与扩展|技能列表/启停/删除|`apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:1`|已实现且可用|`app/src/qml/ExtensionDetail.qml:82`；qml_shell.py (legacy line reference; current anchor at left) extensionRows/toggleExtension/setSkillEnabled；ExtensionDetail.qml；搜索命令及原始结果：`docs/audit/evidence/F69-search.txt`|
|F70 / 设置与扩展|技能导入（zip/md）|`apps/desktop/src/main/services/skills.ts:767`|未移植|`app/src/mvvm/services/skill_store.py:182`；skill_store.py:12 注释明说文件导入未实现；QML 扩展页无导入按钮；搜索命令及原始结果：`docs/audit/evidence/F70-search.txt`|
|F71 / 设置与扩展|MCP 列表/编辑/密钥/重试/工具清单|`apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:493`|已实现且可用|`app/src/qml/ExtensionDetail.qml:33`；extension_runtime.py + ExtensionDetail.qml；上一轮 runtime-parity 验收三种传输；搜索命令及原始结果：`docs/audit/evidence/F71-search.txt`|
|F72 / 设置与扩展|技能/MCP 角色白名单|`apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:1`|已实现且可用|`app/src/qml/ExtensionDetail.qml:141`；ExtensionDetail.qml:115-160 rolesTrigger/rolesPopup + qml_shell.py toggleExtension；搜索命令及原始结果：`docs/audit/evidence/F72-search.txt`|
|F73 / 设置与扩展|About/版本|`apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:878`|已实现且可用|`app/src/qml_shell.py:428`；SettingsModal.qml aboutPane + qml_shell.py appVersion；搜索命令及原始结果：`docs/audit/evidence/F73-search.txt`|
|F74 / 设置与扩展|检查更新|`apps/desktop/src/main/services/updater.ts:270`, `apps/desktop/src/renderer/src/redesign/UpdateSection.tsx:1`|已实现且可用|`app/src/qml_shell.py:438`；qml_shell.py (legacy line reference; current anchor at left) checkForUpdates/_check_updates_worker（GitHub Releases API）；搜索命令及原始结果：`docs/audit/evidence/F74-search.txt`|
|F75 / 设置与扩展|下载/安装更新|`apps/desktop/src/main/services/updater.ts:270`, `apps/desktop/src/renderer/src/redesign/UpdateSection.tsx:47`|未移植|`app/src/qml_shell.py:438`；已实现 downloadUpdate/installUpdate 和 About 按钮；真实本地下载字节校验通过，installUpdate 在 offscreen 报 QPlatformServices::openDocument 不支持，成功打开未验证，按未移植计。；搜索命令及原始结果：`docs/audit/evidence/F75-search.txt`|
|F76 / 设置与扩展|个人资料（头像/昵称）|`apps/desktop/src/main/services/profile.ts:49`, `apps/desktop/src/renderer/src/redesign/ProfilePanel.tsx:1`|只有界面|`app/src/qml/Main.qml:558`；Main.qml (legacy line reference; current anchor at left) 头像按钮只画 Avatar(persona:"user")，无 MouseArea；无 profile 服务；搜索命令及原始结果：`docs/audit/evidence/F76-search.txt`|
|F77 / 其他原生能力|剪贴板读写|`apps/desktop/src/main/services/clipboard.ts:15`|已实现且可用|`app/src/qml_shell.py:1916`；qml_shell.py (legacy line reference; current anchor at left) copyDeliverablePath 用 QGuiApplication.clipboard() 写并回读校验；搜索命令及原始结果：`docs/audit/evidence/F77-search.txt`|
|F78 / 其他原生能力|内置浏览器（多窗口/标签/缩略图/导航）|`apps/desktop/src/main/services/browser/host.ts:554`|不适用|`app/src/main.py:8`；路线 B 明确移除 QtWebEngine，原版 browser/host.ts 的 BrowserView、capturePage、live frame 与 16 条 browser:* 无可真实交互的 QML 等效；不引入新依赖，不造空壳。；搜索命令及原始结果：`docs/audit/evidence/F78-search.txt`|
|F79 / 其他原生能力|终端（PTY 会话）|`apps/desktop/src/main/services/terminal.ts:87`|未移植|`app/src/mvvm/webui/host.py:76`；原版 pty-host.ts 有 terminal:* 注册能力；renderer 没有消费者只表明用户入口不可达，不能把真实原版能力判为不存在。QML/Host 未移植 PTY。；搜索命令及原始结果：`docs/audit/evidence/F79-search.txt`|
|F85 / 其他原生能力|Git 面板（状态/暂存/提交/分支/同步）|`apps/desktop/src/renderer/src/redesign/GitWidget.tsx:169`|未移植|`app/src/qml/Main.qml:18`；GitPanel 已接 status/stage/commit/branches/log/diff/discard/merge/remote/分支/分页常用操作并真实临时仓库测试；generate-commit-message、set-config、cancel 等剩余方法与完整原版页面未接，按未移植计。；搜索命令及原始结果：`docs/audit/evidence/F85-search.txt`|
|F80 / 其他原生能力|子智能体/成员对话|`apps/desktop/src/main/services/subagents.ts:1`, `apps/desktop/src/main/services/chat-members.ts:1`, `apps/desktop/src/renderer/src/redesign/MemberBar.tsx:1`|未移植|`app/src/mvvm/services/tool_runtime.py:77`；移植版 tool_runtime 只有 10 个工具（tool_runtime.py:4-6），无 subagent/member 能力；搜索命令及原始结果：`docs/audit/evidence/F80-search.txt`|
|F81 / 其他原生能力|自动任务卡/提案卡响应|`apps/desktop/src/main/index.ts:1`|未移植|`app/src/mvvm/models/chat_models.py:150`；移植版无 proposals/autotasks 边车与卡片（chat_models.py 只有字段名）；搜索命令及原始结果：`docs/audit/evidence/F81-search.txt`|
|F82 / 其他原生能力|代理环境变量与系统路由|`apps/desktop/src/main/http.ts:41`|已实现且可用|`app/src/mvvm/services/system_proxy.py:21`；e90dcb1：http_client.py 支持 CIDR/端口/通配符/空白分隔/IPv6；system_proxy.py 走真实 libproxy（PAC/WPAD）或 Qt 平台；transport.py 仅 ConnectError/ConnectTimeout/ProxyError 换路由并按 origin 记忆；scripts/parity/final_port/proxy_routes.py 真实 socket + 真实 PAC 复跑 PASS（7 个 NO_PROXY 边界）；搜索命令及原始结果：`docs/audit/evidence/F82-search.txt`|
|F83 / 其他原生能力|日志与诊断面板|`apps/desktop/src/main/index.ts:1`|不适用|`app/src/main.py:65`；原版有 console 日志和错误诊断输出，但未提供独立日志诊断面板。此候选限定“面板”；原版日志行为已在非 IPC 清单记录。；搜索命令及原始结果：`docs/audit/evidence/F83-search.txt`|
|F84 / 其他原生能力|语音输入/输入法专属功能|`apps/desktop/src/renderer/src/redesign/Composer.tsx:669`|未移植|`app/src/qml/Main.qml:1663`；原版没有语音/听写功能；输入法依赖系统但 Composer.tsx 有 isComposing 防误发送。QML 已补 inputMethodComposing 守卫，真实 OS 输入法合成未验证；不将输入法当作不存在。；搜索命令及原始结果：`docs/audit/evidence/F84-search.txt`|
|F86 / 磁盘新增原版能力|历史消息分页加载|`apps/desktop/src/main/services/chat.ts:656`|未移植|`app/src/qml_shell.py:241`；当前原版工作树真实注册并由 renderer/store/chat.tsx 调用；QML 对应协议未移植。；搜索命令及原始结果：`docs/audit/evidence/F86-search.txt`|
|F87 / 磁盘新增原版能力|会话保存失败后重试|`apps/desktop/src/main/services/chat.ts:655`|未移植|`app/src/qml_shell.py:241`；当前原版工作树真实注册并由 renderer/store/chat.tsx 调用；QML 对应协议未移植。；搜索命令及原始结果：`docs/audit/evidence/F87-search.txt`|
|F88 / 磁盘新增原版能力|保护当前会话的缓存 pin|`apps/desktop/src/main/services/chat.ts:472`|未移植|`app/src/qml_shell.py:241`；当前原版工作树真实注册并由 renderer/store/chat.tsx 调用；QML 对应协议未移植。；搜索命令及原始结果：`docs/audit/evidence/F88-search.txt`|

## 非 IPC 功能面覆盖

| 功能面 | 原版源文件 / 核验内容 | 对应项 |
|---|---|---|
|菜单与右键|main/index.ts:183-217；redesign/chat-menu.tsx、ContextMenu.tsx、Rail.tsx；菜单栏无自定义 setApplicationMenu|F08,F09,F28,F34|
|快捷键、输入法|redesign/Composer.tsx:669-700；ChatFirstShell.tsx；Esc、Ctrl+B、Enter、isComposing|F10-14,F84|
|拖放、导入导出、剪贴板|Composer.tsx、AttachmentsPane.tsx、attachments.ts；skills.ts；无通用会话导入导出 UI，技能导入单列|F45-50,F70,F77|
|通知、托盘、更新|main/index.ts:164-173,235-272；reply-notify.ts；updater.ts|F01-03,F15,F60,F74-75|
|窗口、多窗口、外链|main/index.ts；browser/host.ts；QML 单窗，浏览器独立窗口和标签不是 Electron 不适用|F04-07,F78|
|目录文件选择、附件交付卡|attachments.ts；Composer.tsx；redesign/deliverables.tsx，完整事件列表见 source-inventory|F45-50|
|角色、会话、正文|Rail/ProfilePanel/ProfileView/Conversation/ConvMessage/blocks.tsx；逐页控件与回调索引|F16-57,F80-81|
|任务、机器人、手机|TasksPane/BotsPane/PhonePane.tsx；remote 服务|F58-64|
|代理、网络、日志诊断|main/http.ts；console 日志/错误 toast；无独立日志诊断面板；voice 搜索无语音输入实现|F82-84|
|Git 与新缓存协议|GitWidget.tsx；store/chat.tsx 与 services/chat.ts 当前工作树|F85-88|

以上按源码文件全集、IPC 注册、preload 与非 IPC 用户事件四个方向交叉核对；不是只扫 IPC。source-inventory 保留每一处命中，功能面不以控件文字作为已实现证据。

## IPC / 桥通道完整索引

{'implemented': 60, 'not_ported': 112}

| 通道 | 注册 文件:行号 | preload 文件:行号 | QML 状态 | 证据 / 缺口 |
|---|---|---|---|---|
|`app:get-platform`|`apps/desktop/src/main/index.ts:327`||已实现且可用|Main.qml:29 用 Qt.platform.os 判平台；qml_shell 无平台 IPC 但行为等价|
|`browser:activate`|`apps/desktop/src/main/services/browser/host.ts:590`|`apps/desktop/src/preload/index.ts:1162`|未移植|移植版无内置浏览器|
|`browser:close-session`|`apps/desktop/src/main/services/browser/host.ts:566`|`apps/desktop/src/preload/index.ts:1149`|未移植|移植版无内置浏览器|
|`browser:close-tab`|`apps/desktop/src/main/services/browser/host.ts:594`|`apps/desktop/src/preload/index.ts:1163`|未移植|移植版无内置浏览器|
|`browser:dock`|`apps/desktop/src/main/services/browser/host.ts:561`|`apps/desktop/src/preload/index.ts:1146`|未移植|移植版无内置浏览器|
|`browser:handoff`|`apps/desktop/src/main/services/browser/host.ts:650`|`apps/desktop/src/preload/index.ts:1176`|未移植|移植版无内置浏览器|
|`browser:live-start`|`apps/desktop/src/main/services/browser/host.ts:579`|`apps/desktop/src/preload/index.ts:1154`|未移植|移植版无内置浏览器|
|`browser:live-stop`|`apps/desktop/src/main/services/browser/host.ts:582`|`apps/desktop/src/preload/index.ts:1155`|未移植|移植版无内置浏览器|
|`browser:menu`|`apps/desktop/src/main/services/browser/host.ts:610`|`apps/desktop/src/preload/index.ts:1171`|未移植|移植版无内置浏览器|
|`browser:nav`|`apps/desktop/src/main/services/browser/host.ts:598`|`apps/desktop/src/preload/index.ts:1165`|未移植|移植版无内置浏览器|
|`browser:open`|`apps/desktop/src/main/services/browser/host.ts:556`|`apps/desktop/src/preload/index.ts:1144`|未移植|移植版无内置浏览器|
|`browser:pin`|`apps/desktop/src/main/services/browser/host.ts:586`|`apps/desktop/src/preload/index.ts:1161`|未移植|移植版无内置浏览器|
|`browser:preview-pinned`|`apps/desktop/src/main/services/browser/host.ts:572`|`apps/desktop/src/preload/index.ts:1152`|未移植|移植版无内置浏览器|
|`browser:ready`|`apps/desktop/src/main/services/browser/host.ts:660`|`apps/desktop/src/preload/index.ts:1136`|未移植|移植版无内置浏览器|
|`browser:state`|`apps/desktop/src/main/services/browser/host.ts:554`|`apps/desktop/src/preload/index.ts:1134`, `apps/desktop/src/preload/index.ts:1139`|未移植|移植版无内置浏览器|
|`browser:stop`|`apps/desktop/src/main/services/browser/host.ts:654`|`apps/desktop/src/preload/index.ts:1178`|未移植|移植版无内置浏览器|
|`browser:thumbnail`|`apps/desktop/src/main/services/browser/host.ts:639`|`apps/desktop/src/preload/index.ts:1173`|未移植|移植版无内置浏览器|
|`chat:abort`|`apps/desktop/src/main/services/chat.ts:744`|`apps/desktop/src/preload/index.ts:838`|未移植|host.py:306 abort 有后端，QML 无停止键/槽|
|`chat:ask-response`|`apps/desktop/src/main/services/chat.ts:960`|`apps/desktop/src/preload/index.ts:915`|未移植|无对应实现|
|`chat:attach-session`|`apps/desktop/src/main/services/chat.ts:670`|`apps/desktop/src/preload/index.ts:856`|未移植|host.py:509 attach 有后端，QML 无接续回合入口|
|`chat:attachment-image`|`apps/desktop/src/main/services/chat.ts:664`|`apps/desktop/src/preload/index.ts:850`|已实现且可用|qml_shell_sessions.py:304-329|
|`chat:compact`|`apps/desktop/src/main/services/chat.ts:505`|`apps/desktop/src/preload/index.ts:819`|已实现且可用|runSlashCommand -> ChatHost.compact; real keyboard test|
|`chat:context-usage`|`apps/desktop/src/main/services/context-usage.ts:54`|`apps/desktop/src/preload/index.ts:878`|已实现且可用|qml_shell.py:964-1005|
|`chat:create-session`|`apps/desktop/src/main/services/chat.ts:562`|`apps/desktop/src/preload/index.ts:822`|已实现且可用|qml_shell.py:595-606|
|`chat:delete-session`|`apps/desktop/src/main/services/chat.ts:705`|`apps/desktop/src/preload/index.ts:859`|已实现且可用|qml_shell.py:606-626|
|`chat:delete-turns`|`apps/desktop/src/main/services/chat.ts:765`|`apps/desktop/src/preload/index.ts:873`|未移植|host.py:415 有后端，QML 无入口|
|`chat:insert`|`apps/desktop/src/main/services/chat.ts:496`|`apps/desktop/src/preload/index.ts:813`|未移植|无 chat:insert|
|`chat:list-sessions`|`apps/desktop/src/main/services/chat.ts:637`|`apps/desktop/src/preload/index.ts:844`|已实现且可用|qml_shell.py:1663-1683 _rows → session_rows|
|`chat:load-session`|`apps/desktop/src/main/services/chat.ts:658`|`apps/desktop/src/preload/index.ts:847`|已实现且可用|qml_shell.py:585-594 openSession|
|`chat:mark-read`|`apps/desktop/src/main/services/read-sync.ts:81`|`apps/desktop/src/preload/index.ts:935`|未移植|无未读状态|
|`chat:mount-response`|`apps/desktop/src/main/services/chat.ts:968`|`apps/desktop/src/preload/index.ts:921`|未移植|无对应实现|
|`chat:plan-response`|`apps/desktop/src/main/services/chat.ts:964`|`apps/desktop/src/preload/index.ts:918`|未移植|无对应实现|
|`chat:remove-member`|`apps/desktop/src/main/services/chat.ts:715`|`apps/desktop/src/preload/index.ts:862`|未移植|无成员对话|
|`chat:rename-session`|`apps/desktop/src/main/services/chat.ts:612`|`apps/desktop/src/preload/index.ts:834`|已实现且可用|qml_shell.py:626-642|
|`chat:resolve-autotask`|`apps/desktop/src/main/services/chat.ts:690`|`apps/desktop/src/preload/index.ts:912`|未移植|无自动任务卡|
|`chat:resolve-proposal`|`apps/desktop/src/main/services/chat.ts:683`|`apps/desktop/src/preload/index.ts:900`|未移植|无提案卡边车|
|`chat:rewind-apply`|`apps/desktop/src/main/services/chat.ts:838`|`apps/desktop/src/preload/index.ts:890`|未移植|无 rewind|
|`chat:rewind-list`|`apps/desktop/src/main/services/chat.ts:812`|`apps/desktop/src/preload/index.ts:884`|未移植|无 rewind|
|`chat:rewind-preview`|`apps/desktop/src/main/services/chat.ts:822`|`apps/desktop/src/preload/index.ts:887`|未移植|无 rewind|
|`chat:rewind-undo`|`apps/desktop/src/main/services/chat.ts:930`|`apps/desktop/src/preload/index.ts:893`|未移植|无 rewind|
|`chat:send`|`apps/desktop/src/main/services/chat.ts:493`|`apps/desktop/src/preload/index.ts:811`|已实现且可用|qml_shell.py:1251-1297 → ChatHost.send(host.py:166)|
|`chat:set-archived`|`apps/desktop/src/main/services/chat.ts:632`|`apps/desktop/src/preload/index.ts:837`|已实现且可用|qml_shell.py:643-700|
|`chat:set-effort`|`apps/desktop/src/main/services/chat.ts:582`|`apps/desktop/src/preload/index.ts:828`|已实现且可用|qml_shell.py:1026-1040 setActiveEffort|
|`chat:set-focus`|`apps/desktop/src/main/services/chat.ts:595`|`apps/desktop/src/preload/index.ts:831`|已实现且可用|qml_shell.py:1312-1338 acceptWorkspace|
|`chat:set-model`|`apps/desktop/src/main/services/chat.ts:577`|`apps/desktop/src/preload/index.ts:825`|已实现且可用|qml_shell.py:1006-1026 setActiveModel|
|`chat:stop-subagent`|`apps/desktop/src/main/services/chat.ts:751`|`apps/desktop/src/preload/index.ts:841`|未移植|无子智能体|
|`chat:todo-cancel`|`apps/desktop/src/main/services/chat.ts:794`|`apps/desktop/src/preload/index.ts:881`|未移植|无 Todo UI|
|`chat:todos`|`apps/desktop/src/main/services/chat.ts:787`|`apps/desktop/src/preload/index.ts:875`|未移植|host.py:426 有后端，QML 无 Todo 展示|
|`chat:withdraw-inserts`|`apps/desktop/src/main/services/chat.ts:497`|`apps/desktop/src/preload/index.ts:816`|未移植|无插入队列|
|`clipboard:read-text`|`apps/desktop/src/main/services/clipboard.ts:15`|`apps/desktop/src/preload/index.ts:1098`|已实现且可用|QGuiApplication.clipboard() 可用；复制路径走写端|
|`clipboard:write-text`|`apps/desktop/src/main/services/clipboard.ts:18`|`apps/desktop/src/preload/index.ts:1100`|已实现且可用|qml_shell.py:1385-1395|
|`config:get`|`apps/desktop/src/main/services/config.ts:96`|`apps/desktop/src/preload/index.ts:683`|已实现且可用|qml_shell.py:366-379 _config/_write_config|
|`config:get-sync`|`apps/desktop/src/main/services/config.ts:90`|`apps/desktop/src/preload/index.ts:682`|已实现且可用|同上同步读取|
|`config:set`|`apps/desktop/src/main/services/config.ts:102`|`apps/desktop/src/preload/index.ts:686`|已实现且可用|qml_shell.py:369-379 set_config|
|`deliverables:inspect`|`apps/desktop/src/main/services/deliverables.ts:71`|`apps/desktop/src/preload/index.ts:1108`|已实现且可用|qml_shell.py:1371-1374 deliveryItems|
|`deliverables:open`|`apps/desktop/src/main/services/deliverables.ts:111`|`apps/desktop/src/preload/index.ts:1114`|已实现且可用|qml_shell.py:1375-1379 openDeliverable|
|`deliverables:reveal`|`apps/desktop/src/main/services/deliverables.ts:121`|`apps/desktop/src/preload/index.ts:1117`|已实现且可用|qml_shell.py:1380-1384 revealDeliverable|
|`deliverables:thumbnail`|`apps/desktop/src/main/services/deliverables.ts:91`|`apps/desktop/src/preload/index.ts:1111`|未移植|delivery_row 无缩略图字段|
|`fs:attachment-image`|`apps/desktop/src/main/services/attachments.ts:221`|`apps/desktop/src/preload/index.ts:662`|已实现且可用|qml_shell_sessions.py:304-329 图片 data URI；AttachmentService|
|`fs:dropped-entries`|`apps/desktop/src/main/services/attachments.ts:201`|`apps/desktop/src/preload/index.ts:676`|未移植|attachments.py:12-14 明说未移植；QML 无 DropArea|
|`fs:open-folder`|`apps/desktop/src/main/services/workspace.ts:43`|`apps/desktop/src/preload/index.ts:643`|已实现且可用|Main.qml:20-31 FolderDialog + qml_shell.py:1300-1338 beginWorkspace/acceptWorkspace|
|`fs:paste-attachment`|`apps/desktop/src/main/services/attachments.ts:166`|`apps/desktop/src/preload/index.ts:659`|未移植|attachments.py:12-14 明说未移植|
|`fs:pick-attachments`|`apps/desktop/src/main/services/attachments.ts:235`|`apps/desktop/src/preload/index.ts:652`|已实现且可用|qml_shell.py:1338-1364 pickAttachments + Main.qml:1497 clipBtn|
|`fs:read-dir`|`apps/desktop/src/main/services/workspace.ts:64`|`apps/desktop/src/preload/index.ts:647`|未移植|Backend or partial data is available; complete equivalent QML consumer is not verified|
|`fs:read-file`|`apps/desktop/src/main/services/workspace.ts:82`|`apps/desktop/src/preload/index.ts:648`|未移植|Backend or partial data is available; complete equivalent QML consumer is not verified|
|`fs:reveal-folder`|`apps/desktop/src/main/services/workspace.ts:55`|`apps/desktop/src/preload/index.ts:646`|未移植|无工作区「在文件夹中显示」入口；仅交付卡 reveal 已实现|
|`fs:write-file`|`apps/desktop/src/main/services/workspace.ts:92`|`apps/desktop/src/preload/index.ts:650`|未移植|Backend or partial data is available; complete equivalent QML consumer is not verified|
|`git:available`|`apps/desktop/src/main/services/git.ts:626`|`apps/desktop/src/preload/index.ts:973`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:branches`|`apps/desktop/src/main/services/git.ts:766`|`apps/desktop/src/preload/index.ts:994`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:cancel-commit-message`|`apps/desktop/src/main/services/git.ts:1028`|`apps/desktop/src/preload/index.ts:1034`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:checkout`|`apps/desktop/src/main/services/git.ts:793`|`apps/desktop/src/preload/index.ts:996`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:checkout-remote`|`apps/desktop/src/main/services/git.ts:813`|`apps/desktop/src/preload/index.ts:1001`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:commit`|`apps/desktop/src/main/services/git.ts:741`|`apps/desktop/src/preload/index.ts:990`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:create-branch`|`apps/desktop/src/main/services/git.ts:803`|`apps/desktop/src/preload/index.ts:998`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:delete-branch`|`apps/desktop/src/main/services/git.ts:841`|`apps/desktop/src/preload/index.ts:1007`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:delete-remote-branch`|`apps/desktop/src/main/services/git.ts:863`|`apps/desktop/src/preload/index.ts:1012`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:diff`|`apps/desktop/src/main/services/git.ts:682`|`apps/desktop/src/preload/index.ts:981`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:discard`|`apps/desktop/src/main/services/git.ts:726`|`apps/desktop/src/preload/index.ts:988`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:fetch`|`apps/desktop/src/main/services/git.ts:896`|`apps/desktop/src/preload/index.ts:1016`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:generate-commit-message`|`apps/desktop/src/main/services/git.ts:930`|`apps/desktop/src/preload/index.ts:1031`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:init`|`apps/desktop/src/main/services/git.ts:889`|`apps/desktop/src/preload/index.ts:1015`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:log`|`apps/desktop/src/main/services/git.ts:874`|`apps/desktop/src/preload/index.ts:1014`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:merge`|`apps/desktop/src/main/services/git.ts:823`|`apps/desktop/src/preload/index.ts:1003`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:merge-abort`|`apps/desktop/src/main/services/git.ts:834`|`apps/desktop/src/preload/index.ts:1004`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:pull`|`apps/desktop/src/main/services/git.ts:905`|`apps/desktop/src/preload/index.ts:1017`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:push`|`apps/desktop/src/main/services/git.ts:914`|`apps/desktop/src/preload/index.ts:1020`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:rename-branch`|`apps/desktop/src/main/services/git.ts:855`|`apps/desktop/src/preload/index.ts:1009`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:set-config`|`apps/desktop/src/main/services/git.ts:757`|`apps/desktop/src/preload/index.ts:993`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:stage`|`apps/desktop/src/main/services/git.ts:704`|`apps/desktop/src/preload/index.ts:983`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:status`|`apps/desktop/src/main/services/git.ts:639`|`apps/desktop/src/preload/index.ts:975`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`git:unstage`|`apps/desktop/src/main/services/git.ts:713`|`apps/desktop/src/preload/index.ts:985`|未移植|移植版无 git 服务/面板；24 条通道全缺|
|`mcp:get`|`apps/desktop/src/main/services/mcp.ts:634`|`apps/desktop/src/preload/index.ts:761`|已实现且可用|extensionAction detail|
|`mcp:has-secret`|`apps/desktop/src/main/services/mcp.ts:675`|`apps/desktop/src/preload/index.ts:782`|已实现且可用|ExtensionDetail keyStatus|
|`mcp:list`|`apps/desktop/src/main/services/mcp.ts:633`|`apps/desktop/src/preload/index.ts:760`|已实现且可用|qml_shell.py:1145-1198 extensionRows(mcp)|
|`mcp:remove`|`apps/desktop/src/main/services/mcp.ts:636`|`apps/desktop/src/preload/index.ts:765`|已实现且可用|extensionAction remove|
|`mcp:retry`|`apps/desktop/src/main/services/mcp.ts:654`|`apps/desktop/src/preload/index.ts:772`|已实现且可用|extensionAction retry → extension_runtime.retry|
|`mcp:set-enabled`|`apps/desktop/src/main/services/mcp.ts:649`|`apps/desktop/src/preload/index.ts:767`|已实现且可用|toggleExtension|
|`mcp:set-roles`|`apps/desktop/src/main/services/mcp.ts:642`|`apps/desktop/src/preload/index.ts:770`|已实现且可用|ExtensionDetail rolesPopup|
|`mcp:set-secret`|`apps/desktop/src/main/services/mcp.ts:660`|`apps/desktop/src/preload/index.ts:779`|已实现且可用|extensionAction secret|
|`mcp:upsert`|`apps/desktop/src/main/services/mcp.ts:635`|`apps/desktop/src/preload/index.ts:764`|已实现且可用|extensionAction update/save|
|`memory:clear`|`apps/desktop/src/main/services/memory.ts:476`|`apps/desktop/src/preload/index.ts:730`|未移植|无 memory 服务/UI|
|`memory:delete`|`apps/desktop/src/main/services/memory.ts:471`|`apps/desktop/src/preload/index.ts:729`|未移植|无 memory 服务/UI|
|`memory:list`|`apps/desktop/src/main/services/memory.ts:461`|`apps/desktop/src/preload/index.ts:721`|未移植|无 memory 服务/UI|
|`memory:write`|`apps/desktop/src/main/services/memory.ts:462`|`apps/desktop/src/preload/index.ts:727`|未移植|无 memory 服务/UI|
|`personas:clear-avatar-image`|`apps/desktop/src/main/services/personas.ts:529`|`apps/desktop/src/preload/index.ts:752`|未移植|QML 无头像编辑|
|`personas:get`|`apps/desktop/src/main/services/personas.ts:509`|`apps/desktop/src/preload/index.ts:735`|已实现且可用|PersonaStore.get（persona_store.py:179-187）经 quickStart/roles 使用|
|`personas:list`|`apps/desktop/src/main/services/personas.ts:508`|`apps/desktop/src/preload/index.ts:734`|已实现且可用|qml_shell.py:701-753 quickStartPersonas + extensionRows 角色头像|
|`personas:remove`|`apps/desktop/src/main/services/personas.ts:513`|`apps/desktop/src/preload/index.ts:738`|未移植|PersonaStore.remove 有后端，QML 无删除入口|
|`personas:reorder`|`apps/desktop/src/main/services/personas.ts:521`|`apps/desktop/src/preload/index.ts:743`|未移植|QML 无角色排序|
|`personas:set-avatar-image`|`apps/desktop/src/main/services/personas.ts:526`|`apps/desktop/src/preload/index.ts:749`|未移植|QML 无头像编辑|
|`personas:set-enabled`|`apps/desktop/src/main/services/personas.ts:517`|`apps/desktop/src/preload/index.ts:740`|未移植|QML 无角色启停 UI|
|`personas:upsert`|`apps/desktop/src/main/services/personas.ts:510`|`apps/desktop/src/preload/index.ts:737`|未移植|PersonaStore.upsert 有后端（persona_store.py:205-237），QML 无新建/编辑角色入口|
|`phone:add`|`apps/desktop/src/main/services/remote/web/phone.ts:369`|`apps/desktop/src/preload/index.ts:1230`|未移植|移植版无手机联动|
|`phone:get-state`|`apps/desktop/src/main/services/remote/web/phone.ts:367`|`apps/desktop/src/preload/index.ts:1228`|未移植|移植版无手机联动|
|`phone:link`|`apps/desktop/src/main/services/remote/web/phone.ts:433`|`apps/desktop/src/preload/index.ts:1239`|未移植|移植版无手机联动|
|`phone:qr`|`apps/desktop/src/main/services/remote/web/phone.ts:426`|`apps/desktop/src/preload/index.ts:1237`|未移植|移植版无手机联动|
|`phone:qr-cancel`|`apps/desktop/src/main/services/remote/web/phone.ts:435`|`apps/desktop/src/preload/index.ts:1241`|未移植|移植版无手机联动|
|`phone:remove`|`apps/desktop/src/main/services/remote/web/phone.ts:376`|`apps/desktop/src/preload/index.ts:1232`|未移植|移植版无手机联动|
|`phone:remove-device`|`apps/desktop/src/main/services/remote/web/phone.ts:441`|`apps/desktop/src/preload/index.ts:1242`|未移植|移植版无手机联动|
|`phone:retry`|`apps/desktop/src/main/services/remote/web/phone.ts:398`|`apps/desktop/src/preload/index.ts:1235`|未移植|移植版无手机联动|
|`phone:set-enabled`|`apps/desktop/src/main/services/remote/web/phone.ts:389`|`apps/desktop/src/preload/index.ts:1233`|未移植|移植版无手机联动|
|`profile:get`|`apps/desktop/src/main/services/profile.ts:49`|`apps/desktop/src/preload/index.ts:709`|未移植|无 profile 服务/资料卡|
|`profile:set-avatar`|`apps/desktop/src/main/services/profile.ts:50`|`apps/desktop/src/preload/index.ts:710`|未移植|无头像编辑|
|`profile:set-avatar-image`|`apps/desktop/src/main/services/profile.ts:55`|`apps/desktop/src/preload/index.ts:713`|未移植|无头像编辑|
|`provider:list-models`|`apps/desktop/src/main/services/provider.ts:74`|`apps/desktop/src/preload/index.ts:803`|未移植|ModelGateway.list_models 有后端（provider_setup.py:168-190），QML 无按钮/建议列表|
|`remote:delete-bot`|`apps/desktop/src/main/services/remote/index.ts:316`|`apps/desktop/src/preload/index.ts:1209`|已实现且可用|RemoteBots actions; bots-ui real clicks + config readback; no external success claim|
|`remote:get-state`|`apps/desktop/src/main/services/remote/index.ts:214`|`apps/desktop/src/preload/index.ts:1193`|已实现且可用|RemoteBots actions; bots-ui real clicks + config readback; no external success claim|
|`remote:pair-cancel`|`apps/desktop/src/main/services/remote/index.ts:326`|`apps/desktop/src/preload/index.ts:1212`|未移植|移植版无远程机器人|
|`remote:pair-code`|`apps/desktop/src/main/services/remote/index.ts:324`|`apps/desktop/src/preload/index.ts:1211`|未移植|移植版无远程机器人|
|`remote:remove-user`|`apps/desktop/src/main/services/remote/index.ts:331`|`apps/desktop/src/preload/index.ts:1214`|未移植|移植版无远程机器人|
|`remote:scan-cancel`|`apps/desktop/src/main/services/remote/index.ts:282`|`apps/desktop/src/preload/index.ts:1202`|未移植|移植版无远程机器人|
|`remote:scan-start`|`apps/desktop/src/main/services/remote/index.ts:218`|`apps/desktop/src/preload/index.ts:1201`|未移植|移植版无远程机器人|
|`remote:set-enabled`|`apps/desktop/src/main/services/remote/index.ts:287`|`apps/desktop/src/preload/index.ts:1204`|未移植|移植版无远程机器人|
|`remote:set-reply-mode`|`apps/desktop/src/main/services/remote/index.ts:303`|`apps/desktop/src/preload/index.ts:1206`|已实现且可用|RemoteBots actions; bots-ui real clicks + config readback; no external success claim|
|`remote:set-scope`|`apps/desktop/src/main/services/remote/index.ts:309`|`apps/desktop/src/preload/index.ts:1208`|已实现且可用|RemoteBots actions; bots-ui real clicks + config readback; no external success claim|
|`secrets:available`|`apps/desktop/src/main/services/secrets.ts:149`|`apps/desktop/src/preload/index.ts:798`|已实现且可用|describe_backend（secrets_vault.py:84-89），上一轮私有 D-Bus 实测|
|`secrets:delete`|`apps/desktop/src/main/services/secrets.ts:137`|`apps/desktop/src/preload/index.ts:796`|已实现且可用|同上|
|`secrets:has`|`apps/desktop/src/main/services/secrets.ts:132`|`apps/desktop/src/preload/index.ts:794`|已实现且可用|同上|
|`secrets:list`|`apps/desktop/src/main/services/secrets.ts:143`|`apps/desktop/src/preload/index.ts:797`|未移植|Backend or partial data is available; complete equivalent QML consumer is not verified|
|`secrets:set`|`apps/desktop/src/main/services/secrets.ts:126`|`apps/desktop/src/preload/index.ts:793`|已实现且可用|SecretsVault（keyring/file 双后端）+ 模型/MCP 密钥 UI|
|`skills:get`|`apps/desktop/src/main/services/skills.ts:754`|`apps/desktop/src/preload/index.ts:691`|已实现且可用|extensionAction detail → ExtensionSettings.detail|
|`skills:import`|`apps/desktop/src/main/services/skills.ts:767`|`apps/desktop/src/preload/index.ts:692`|未移植|skill_store.py:12 注释明说文件导入未实现|
|`skills:list`|`apps/desktop/src/main/services/skills.ts:753`|`apps/desktop/src/preload/index.ts:690`|已实现且可用|qml_shell.py:1145-1198 extensionRows；ExtensionDetail.qml|
|`skills:remove`|`apps/desktop/src/main/services/skills.ts:755`|`apps/desktop/src/preload/index.ts:694`|已实现且可用|qml_shell.py:1199-1212 toggleExtension/extensionAction remove|
|`skills:set-enabled`|`apps/desktop/src/main/services/skills.ts:756`|`apps/desktop/src/preload/index.ts:696`|已实现且可用|qml_shell.py:1213-1245 setSkillEnabled|
|`skills:set-roles`|`apps/desktop/src/main/services/skills.ts:761`|`apps/desktop/src/preload/index.ts:699`|已实现且可用|ExtensionDetail.qml:115-160 rolesPopup|
|`tasks:create`|`apps/desktop/src/main/services/tasks.ts:523`|`apps/desktop/src/preload/index.ts:1050`|已实现且可用|ScheduledTasks controller; tasks-ui actual clicks/automatic execution/persistence|
|`tasks:delete`|`apps/desktop/src/main/services/tasks.ts:529`|`apps/desktop/src/preload/index.ts:1053`|已实现且可用|ScheduledTasks controller; tasks-ui actual clicks/automatic execution/persistence|
|`tasks:get`|`apps/desktop/src/main/services/tasks.ts:521`|`apps/desktop/src/preload/index.ts:1048`|未移植|Backend or partial data is available; complete equivalent QML consumer is not verified|
|`tasks:list`|`apps/desktop/src/main/services/tasks.ts:520`|`apps/desktop/src/preload/index.ts:1047`|已实现且可用|ScheduledTasks controller; tasks-ui actual clicks/automatic execution/persistence|
|`tasks:preview`|`apps/desktop/src/main/services/tasks.ts:537`|`apps/desktop/src/preload/index.ts:1075`|未移植|移植版无任务调度服务|
|`tasks:run-now`|`apps/desktop/src/main/services/tasks.ts:542`|`apps/desktop/src/preload/index.ts:1064`|已实现且可用|ScheduledTasks controller; tasks-ui actual clicks/automatic execution/persistence|
|`tasks:set-status`|`apps/desktop/src/main/services/tasks.ts:533`|`apps/desktop/src/preload/index.ts:1055`|已实现且可用|ScheduledTasks controller; tasks-ui actual clicks/automatic execution/persistence|
|`tasks:update`|`apps/desktop/src/main/services/tasks.ts:526`|`apps/desktop/src/preload/index.ts:1052`|未移植|移植版无任务调度服务|
|`terminal:create`|`apps/desktop/src/main/services/terminal.ts:91`|`apps/desktop/src/preload/index.ts:948`|未移植|原版渲染层无 terminal 调用，用户不可达|
|`terminal:dispose`|`apps/desktop/src/main/services/terminal.ts:108`|`apps/desktop/src/preload/index.ts:952`|未移植|原版渲染层无 terminal 调用，用户不可达|
|`terminal:input`|`apps/desktop/src/main/services/terminal.ts:100`|`apps/desktop/src/preload/index.ts:949`|未移植|原版渲染层无 terminal 调用，用户不可达|
|`terminal:list-shells`|`apps/desktop/src/main/services/terminal.ts:87`|`apps/desktop/src/preload/index.ts:946`|未移植|原版渲染层无 terminal 调用，用户不可达|
|`terminal:resize`|`apps/desktop/src/main/services/terminal.ts:104`|`apps/desktop/src/preload/index.ts:951`|未移植|原版渲染层无 terminal 调用，用户不可达|
|`update:check`|`apps/desktop/src/main/services/updater.ts:271`|`apps/desktop/src/preload/index.ts:1182`|已实现且可用|qml_shell.py:420-464 checkForUpdates|
|`update:download`|`apps/desktop/src/main/services/updater.ts:272`|`apps/desktop/src/preload/index.ts:1183`|未移植|无下载槽（electron-updater 特有）|
|`update:get-state`|`apps/desktop/src/main/services/updater.ts:270`|`apps/desktop/src/preload/index.ts:1181`|已实现且可用|qml_shell.py:415-419 updateState|
|`update:install`|`apps/desktop/src/main/services/updater.ts:273`|`apps/desktop/src/preload/index.ts:1184`|未移植|无安装槽（electron-updater 特有）|
|`window:close`|`apps/desktop/src/main/index.ts:325`|`apps/desktop/src/preload/index.ts:629`|已实现且可用|Main.qml:2477-2480 window.close；同测|
|`window:is-fullscreen`|`apps/desktop/src/main/index.ts:326`|`apps/desktop/src/preload/index.ts:631`|未移植|无全屏状态查询/信号|
|`window:minimize`|`apps/desktop/src/main/index.ts:319`|`apps/desktop/src/preload/index.ts:627`|已实现且可用|Main.qml:2462-2465 showMinimized；test_qml_window_controls.py|
|`window:set-overlay`|`apps/desktop/src/main/index.ts:309`|`apps/desktop/src/preload/index.ts:639`|已实现且可用|Main.qml:280-345 自绘窗口控件按 Theme.dark 取色|
|`window:toggle-maximize`|`apps/desktop/src/main/index.ts:320`|`apps/desktop/src/preload/index.ts:628`|已实现且可用|Main.qml:2467-2476 showNormal/showMaximized；同测|
|`workspace:role-home`|`apps/desktop/src/main/services/role-home.ts:83`|`apps/desktop/src/preload/index.ts:1123`|未移植|无角色主目录|
|`chat:pin-session`|`apps/desktop/src/main/services/chat.ts:472`|`apps/desktop/src/preload/index.ts:809`|未移植|New actual-disk channel; QML equivalent absent|
|`chat:retry-save`|`apps/desktop/src/main/services/chat.ts:655`|`apps/desktop/src/preload/index.ts:807`|未移植|New actual-disk channel; QML equivalent absent|
|`chat:history-page`|`apps/desktop/src/main/services/chat.ts:656`|`apps/desktop/src/preload/index.ts:808`|未移植|New actual-disk channel; QML equivalent absent|

## 未完成项

全量候选判定不等于全量移植。仍未完成：/rewind 与技能命令；@ 后台成员语义；机器人外部配对/收发与飞书/Web；任务完整详情与交接；托盘/通知真实宿主成功态；正文/阴影像素归零。其余未移植项逐行列在上表，不隐去。

同数据字段坐标已复核一致，原版/Qt 真实 Saved 截图和相位复跑详见 extensions-rounding.md。本轮全量 pytest 实际结果由最终报告记录，不沿用上一轮数值。
