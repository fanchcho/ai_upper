# 功能级未移植盘点（feature parity gap）

> 生成时间：2026-11-27T23:22:36 · 盘点基线：`a5634344f050cff69871e40a0431c312b92c42dd`；B 补齐后当前 HEAD：`b25dc1b7a025e807cf8e89bb6c6b989d5814e412`（= origin/develop）
> 唯一依据：`/home/agent/shared_workspace/deva` 原版真实源码（只读，未改动）；移植版证据来自 `/home/agent/shared_workspace/ai_upper` 当前工作树。

## 0. 只读对账（原始命令与输出）

```text
$ cd /home/agent/shared_workspace/ai_upper && git log --oneline -6
a563434 docs: record remaining raster differences and final navigation regression
a8ce60d test: verify saved secrets with isolated real GNOME Secret Service
0263dbd fix: align settings navigation and preserve contextual plugin editors
070eb0a fix: add role typeahead and align verified secret status UI
a80f43a feat: cap role avatar stacks and add role menu keyboard navigation
d4982e9 fix: match role menu icon sizes and document raster rounding experiments

$ git status --porcelain
(空)

$ git rev-parse HEAD
a5634344f050cff69871e40a0431c312b92c42dd

$ git ls-remote origin refs/heads/develop
a5634344f050cff69871e40a0431c312b92c42dd	refs/heads/develop
```

结论：a563434 及之前已推送提交未被回退、未重做；工作树干净。旧审计 `extensions-shell-final.md` / `extensions-rounding.md` / `extensions-runtime-parity.md` 已读，只当线索。

## 1. 三态定义与计数

| 状态 | 定义 |
|---|---|
| 已实现且可用 | 有真实 QML/接线代码，且通过真实点击/键盘/写盘读回验证（不是单测冒充） |
| 只有界面 | 控件存在于 QML，但动作未接（无 onClicked/无后端），点下去无效果 |
| 未移植 | 移植版搜不到对应实现（或仅有不可达的后端函数、无用户入口） |
| 不适用 | 原版本身不存在，或仅为 Electron 专有且无法在 QML 栈实现 |

### 功能面（非 IPC + 用户可达功能）三态计数

| 已实现且可用 | 只有界面 | 未移植 | 不适用 | 合计 |
|---|---|---|---|---|
| 43 | 3 | 35 | 4 | 85 |

### IPC / 桥通道计数（共 169 条：165 handle + 4 on，另有 18 条主进程→渲染层推送）

| 已实现且可用 | 未移植 | 不适用 | 合计 |
|---|---|---|---|
| 54 | 110 | 5 | 169 |

## 2. 原版功能全集与移植版判定（功能面）


### 应用生命周期与窗口

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F01 | 单实例锁与二次启动唤起 | `apps/desktop/src/main/index.ts:276-286` | **已实现且可用** | app/src/mvvm/services/single_instance.py（QLockFile + QLocalServer/QLocalSocket）；qml_shell.run 先 acquire 后建窗、instance.attach(window) 唤起；app/tests/test_single_instance.py 起两个真实进程，第二个 rc=0 且第一个打印激活日志 |
| F02 | 关窗驻留托盘（closeToTray） | `apps/desktop/src/main/index.ts:164-173；redesign/SettingsPane.tsx:101-113,165-172` | **未移植** | 移植版无托盘、无 close 事件驻留；Main.qml:2480 关闭即 window.close() |
| F03 | 系统托盘图标与菜单（显示/定时任务/退出） | `apps/desktop/src/main/index.ts:235-272；services/tray-icon.ts` | **未移植** | `grep -rn "QSystemTrayIcon\\|Tray" app/src` 无结果 |
| F04 | 窗口最小化/最大化/关闭 | `apps/desktop/src/main/index.ts:307-322；preload/index.ts:625-639` | **已实现且可用** | Main.qml:2462-2480 三个 WindowControlButton 接 showMinimized/showNormal\|showMaximized/close；app/tests/test_qml_window_controls.py 用 QTest 真实点击并断言窗口状态 |
| F05 | 窗口控件叠加配色随主题 | `apps/desktop/src/main/index.ts:79-97,304-312` | **已实现且可用** | Main.qml:280-345 WindowControlButton.glyphColor 按 Theme.dark 取 #E8EAED/#5F6368，底色调 Theme.bgInset；注释逐值对齐 index.ts:79-97 |
| F06 | 全屏状态通知（macOS 红绿灯让位） | `apps/desktop/src/main/index.ts:158-160；preload/index.ts:631-636；redesign/ChatFirstShell.tsx:52-66` | **未移植** | Main.qml:29,62 仅按 Qt.platform.os === 'osx' 静态加宽，无 window:fullscreen 等价信号，无 onFullScreen |
| F07 | 外链一律系统浏览器打开 | `apps/desktop/src/main/index.ts:175-181` | **已实现且可用** | Main.qml bodyView.onLinkActivated → shellBridge.openExternal；qml_shell.py openExternal 只放行 http/https/mailto；app/tests/test_qml_links.py 用真实鼠标点击链接并断言 QDesktopServices 收到完整 href |

### 菜单与快捷键

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F08 | 应用菜单栏 | `apps/desktop/src/main/index.ts:108 autoHideMenuBar:true；全仓无 setApplicationMenu` | **不适用** | 原版没有自定义菜单栏，不凭空造 |
| F09 | 编辑区右键菜单（剪切/复制/粘贴/全选） | `apps/desktop/src/main/index.ts:183-217` | **已实现且可用** | app/src/qml/EditContextMenu.qml + Main.qml composerMenu/bodyMenu；app/tests/test_qml_edit_menu.py 真实右键打开并点「全选」断言 selectedText；暗亮截图 out/feature-parity/edit-menu-*.png |
| F10 | Ctrl/Cmd+B 收起/展开会话列表 | `redesign/ChatFirstShell.tsx:191-199` | **已实现且可用** | Main.qml Shortcut Ctrl+B/Meta+B → toggleSidebar；qml_shell.py sidebarCollapsed/setSidebarCollapsed 写 config.json；app/tests/test_qml_sidebar_collapse.py 真实按键 + hover peek |
| F11 | Esc 收回浮出列表 | `redesign/ChatFirstShell.tsx:192-194` | **未移植** | 移植版没有「浮出列表」状态（列表宽度固定），无对应行为 |
| F12 | Enter 发送 / Shift+Enter 换行 | `redesign/Composer.tsx:669-700` | **已实现且可用** | Main.qml:1452-1464 inputField.Keys.onPressed：Return/Enter 且带 Shift 时放行，否则 window.submit() |
| F13 | 输入框 / 指令联想（/compact /rewind /技能） | `redesign/Composer.tsx:382-420` | **已实现且可用** | Main.qml SlashMenu.qml + updateSlash/runSlash；qml_shell.py slashCommands/runSlashCommand 接真实 ChatHost.compact；app/tests/test_qml_slash_menu.py 真实键盘 `/`+Enter。**仅 /compact 可用**，/rewind 与技能指令未移植，属部分补齐 |
| F14 | @ 提及成员/角色 | `redesign/Composer.tsx:399-419；shared/mention.ts` | **未移植** | 移植版无 mention 解析/候选浮层（grep "mention" 无结果） |
| F15 | 回复完成/待处理系统通知 | `services/reply-notify.ts:15-80；chat-turns.ts:801` | **未移植** | 移植版无 QSystemTrayIcon/Notification；ShellBridge 只有内部 signal，不弹系统通知 |

### 会话列表

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F16 | 新建会话 | `redesign/Rail.tsx:600-660（加号菜单）；preload/index.ts:805-940 chat.createSession` | **已实现且可用** | Main.qml:580-597 加号 onClicked shellBridge.newSession；qml_shell.py:595-606 建真实会话并落盘 |
| F17 | 切换会话 | `redesign/Rail.tsx:700-760` | **已实现且可用** | Main.qml:684-712 行 onClicked openSession；qml_shell.py:585-594 读真实会话 |
| F18 | 重命名会话 | `redesign/Rail.tsx:175-182 RowMenu；chat:rename-session` | **已实现且可用** | Main.qml:2102-2106 右键菜单 rename + 重命名弹层；qml_shell.py:626-642 写盘 |
| F19 | 删除会话 | `redesign/Rail.tsx:175-182；chat:delete-session` | **已实现且可用** | Main.qml 右键 delete + 确认框；qml_shell.py:606-626 删会话文件 |
| F20 | 归档/取消归档 | `redesign/Rail.tsx:620-650；chat:set-archived` | **已实现且可用** | Main.qml:800-830 归档横幅与右键 archive；qml_shell.py:643-700 archiveSession/unarchiveSession/archiveSessions |
| F21 | 归档视图 | `redesign/Rail.tsx archiveView` | **已实现且可用** | Main.qml:600-760 archiveHeader/archiveBack，Python archivedSessions 投影 |
| F22 | 会话搜索（标题/角色/挂载目录） | `redesign/Rail.tsx:600-640` | **已实现且可用** | Main.qml:159-200 visibleSessions 按 title/personaName/focusName 过滤；搜索框 Main.qml:495-575 可聚焦输入 |
| F23 | 会话筛选面板（角色/文件夹） | `redesign/Rail.tsx:183-186,664-710` | **已实现且可用** | Main.qml:627-630 filterBtn → SessionFilter.qml；filterRoles/filterFolders/visibleSessions 同类 OR、跨类 AND；scripts/parity/feature_review/filter_evidence.py 真实点击角色+完整目录路径并读回 visibleSessions；暗亮截图 out/parity-close/filter-*.png |
| F24 | 会话多选批量归档/删除 | `redesign/ThreadSelect.tsx` | **已实现且可用** | Main.qml:116-118,684-800,1898-1940 selectMode/selectedSessions + 批量归档/删除 |
| F25 | 未读/待处理状态与红点 | `redesign/Rail.tsx:116-129；store/chat.tsx sessionStates.unread/attention` | **已实现且可用** | qml_shell.py _unread（后台回合 done/error 记未读，openSession 清除）；ThreadRow.qml threadUnread 10px danger 红点；app/tests/test_qml_unread.py 真实回合+点击；暗亮截图 out/feature-parity/unread-dot-*.png。attention 仍无 |
| F26 | 草稿按会话保留 | `redesign/Composer.tsx:109-121,755-760` | **已实现且可用** | Main.qml:102-115 composerDrafts 按 sessionId 保存 text+pendingFiles；scripts/parity/draft_evidence.py 真实键盘输入、真实拖放附件、切会话后读回；drafts.json 暗亮各一组 |
| F27 | 会话列表宽度拖动 | `redesign/resizable.ts；ChatFirstShell.tsx:143-160` | **未移植** | Main.qml 侧栏宽固定 Theme.sideWidth（Main.qml:44-46,462-470），无拖动手柄 |
| F27b | 会话列表收起/展开并记忆 | `redesign/ChatFirstShell.tsx:143-199` | **已实现且可用** | Main.qml sideCollapsed/sidePeek + 200/150ms 浮出定时器；qml_shell.py:515-522 落盘 config.json；真实截图 out/feature-parity/sidebar-{collapsed,peek}-{dark,light}.png |
| F28 | 会话行右键菜单（新建/重命名/多选/归档/删除） | `redesign/Rail.tsx:175-182；ContextMenu.tsx` | **已实现且可用** | Main.qml:2076-2130 自绘 contextMenu，动作齐全；test_qml_context_menu.py 真实右键触发 |

### 对话正文

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F29 | 用户/助手 Markdown 正文 | `redesign/ConvMessage.tsx；features/chat/blocks.tsx` | **已实现且可用** | qml_shell.py:1513-1528 transcript_markdown → app/src/markdown/body.py 渲染进 QTextDocument；Main.qml:1090-1106 |
| F30 | 工具调用/工具结果/思考/子代理活动卡 | `features/chat/blocks.tsx BlockView；redesign/ChatFirstShell.tsx:39-44 注释` | **未移植** | qml_shell_sessions.py:223-260 只拼 text 块，注释明说「纯工具调用 / 纯工具结果跳过」；无 tool_use block UI |
| F31 | 待处理交互卡（ask/审批） | `features/chat/blocks.tsx AskCard；chat:ask-response` | **已实现且可用** | InteractionPrompt.qml + qml_shell.py:355-365 pendingInteractions/answerInteraction（kind=question/approval） |
| F32 | 计划卡与 plan-response | `chat:plan-response；features/chat/blocks.tsx PlanCard` | **未移植** | 移植版 only ask/approval；`grep -rn "plan" app/src/qml_shell.py` 无结果 |
| F33 | 回滚 rewind（列点/预览/应用/撤销） | `redesign/RewindModal.tsx:31；Conversation.tsx:998-1003；chat:rewind-*` | **未移植** | `grep -rn "rewind" app/src/qml app/src/qml_shell.py` 无结果；host.py 也没有 rewind 入口 |
| F34 | 消息右键菜单（复制/引用/回滚/选择删除） | `redesign/Conversation.tsx:905-950` | **未移植** | 正文 TextEdit 无 contextMenu/onPressed 右键处理；Main.qml 只有会话行右键 |
| F35 | 引用条 quote | `redesign/ConvMessage.tsx leadingQuote/withQuote；Composer.tsx` | **未移植** | `grep -rn "quote" app/src/qml app/src/qml_shell.py` 只命中 CSS/无关词；无引用状态 |
| F36 | 选择消息删除（delete-turns） | `chat:delete-turns；redesign/Conversation.tsx:955-1000` | **未移植** | host.py:415-425 delete_turns 有后端，但 QML 无入口（`grep -rn "deleteTurns" app/src/qml*` 无结果） |
| F37 | 停止生成 | `redesign/Composer.tsx:973-991（busy 时空输入框显示停止键）；chat:abort` | **已实现且可用** | qml_shell.py stopGeneration → host.abort；Main.qml sendBtn busy 时切 Square 中性态；app/tests/test_qml_stop_generation.py 真实鼠标点停止并断言 stopReason=aborted；暗亮截图 out/feature-parity/stop-busy-*.png |
| F38 | 回合中插入消息（插话） | `chat:insert / chat:withdraw-inserts；Composer.tsx:463-467` | **未移植** | `grep -rn "insert" app/src/mvvm/webui/host.py app/src/qml_shell.py` 无 chat:insert 路径 |
| F39 | 手动压缩 /compact | `redesign/Composer.tsx:382-386；chat:compact` | **未移植** | host.py:446-508 compact 有后端；QML 无 /compact 入口（grep slash 无结果） |
| F40 | Todo 胶囊 | `redesign/Composer.tsx:864 TodoCapsule` | **未移植** | tool_runtime.py:260 todo_write 工具有，但 QML 无 Todo 展示（`grep -rn "todo" app/src/qml*` 无结果） |
| F41 | 后台任务胶囊 | `redesign/Composer.tsx:865 BackgroundCapsule` | **未移植** | 移植版无后台任务概念 |
| F42 | 浏览器操作胶囊 | `redesign/Composer.tsx:866 BrowserCapsule` | **未移植** | 移植版无内置浏览器 |
| F43 | 上下文用量圆环 | `redesign/ContextRing.tsx；chat:context-usage` | **已实现且可用** | qml_shell.py:964-1005 contextUsage 真实计算；Main.qml ContextRing |
| F44 | 模型/思考等级切换菜单 | `redesign/ModelMenu.tsx, EffortPicker.tsx` | **已实现且可用** | qml_shell.py:900-963 modelMenuGroups/effortMenu；Main.qml ModelPicker |
| F45 | 附件选择（回形针） | `redesign/Composer.tsx:950；fs:pick-attachments` | **已实现且可用** | Main.qml:1480-1520 clipBtn → pickAttachments；qml_shell.py:1338-1364 QFileDialog + AttachmentService |
| F46 | 附件拖放 | `redesign/Composer.tsx:576-596；fs:dropped-entries` | **已实现且可用** | Main.qml DropArea + dropOverlay → shellBridge.acceptDroppedFiles；attachments.py inspect_paths 登记文件/文件夹；app/tests/test_qml_attachments_drop.py 用真实 QDragEnterEvent/QDropEvent 投递并断言 pendingFiles；暗亮截图 out/feature-parity/drop-overlay-*.png |
| F47 | 粘贴图片/文件为附件 | `redesign/Composer.tsx:508,567；fs:paste-attachment` | **已实现且可用** | qml_shell.py attachClipboardImage 取 QClipboard 图片落临时 PNG；Main.qml inputField Ctrl+V 接上；app/tests/test_qml_attachments_drop.py 真实键盘 Ctrl+V 断言待发列表出现 pasted.png（纯文本仍走默认粘贴） |
| F48 | 附件贴片与图片缩略图 | `redesign/attachments.tsx；fs:attachment-image` | **已实现且可用** | qml_shell_sessions.py:304-329 attachment_rows + Main.qml:1128-1180 贴片；图片 data URI 内联 |
| F49 | 交付卡（打开/定位/复制路径） | `features/chat/DeliverablesCard.tsx；deliverables:*` | **已实现且可用** | qml_shell.py:1371-1395 deliveryItems/openDeliverable/revealDeliverable/copyDeliverablePath；Main.qml:1240-1330 |
| F50 | 交付卡图片缩略图 | `deliverables:thumbnail` | **未移植** | delivery_row（transcript_parts.py:144-158）不含 thumb 字段，卡片只按类型画图标 |

### 角色

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F51 | 角色花名册 tab（列表/搜索/快速对话） | `redesign/Rail.tsx:130-170,600-744` | **已实现且可用** | Main.qml:560 railRoster onClicked page=roster；PersonaRoster.qml 列表+搜索+开始会话；scripts/parity/feature_review/roster_evidence.py 真实点击入口、粘贴角色名搜索、点开始并读回会话 personaId；截图 out/parity-close/roster-*.png |
| F52 | 角色资料卡（ProfilePanel） | `redesign/Rail.tsx:117 ProfilePanel` | **未移植** | Main.qml:414-425 meBtn 只有 Avatar，无 MouseArea；无资料卡 |
| F53 | 新建/编辑/删除角色 | `redesign/ProfileView.tsx PersonaEditor；personas:upsert/remove` | **未移植** | PersonaStore 有 upsert/remove（persona_store.py:205-250）但 QML 无入口；Settings 的 identities 只编辑 prompt 文本 |
| F54 | 角色头像编辑 | `redesign/AvatarEditor.tsx；personas:set-avatar-image` | **未移植** | PersonaStore.set_avatar_image 有后端（persona_store.py:269-286），QML 无头像编辑 UI |
| F55 | 角色排序（拖拽/置顶） | `redesign/Rail.tsx reorderIds；personas:reorder` | **未移植** | persona_store.py:260-268 reorder 有后端，QML 无拖拽/排序入口 |
| F56 | 角色记忆查看/编辑 | `redesign/RoleMemoryTab.tsx, MemoryDetail.tsx；memory:*` | **未移植** | 移植版无 memory 服务/UI（grep "memory" app/src 只命中无关词） |
| F57 | 快速开始角色卡 | `redesign/Rail.tsx QuickStart` | **已实现且可用** | qml_shell.py:701-753 quickStartPersonas/startQuickStart；Main.qml 空态卡片 |

### 定时任务

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F58 | 定时任务页（列表/详情/运行历史） | `redesign/TasksPane.tsx:1-70；tasks:list/get` | **只有界面** | Main.qml:440 RailButton alarmClock 无 onClicked；无 TasksPane 对应 QML，无 tasks 服务 |
| F59 | 任务调度引擎（once/cron、自动触发） | `services/schedule.ts, scheduler.ts；tasks:*` | **未移植** | `grep -rli "scheduler\\|cron\\|schedule" app/src --include=*.py` 无结果 |
| F60 | 任务系统通知 | `services/scheduler.ts:103 new Notification` | **未移植** | 移植版无 Notification |
| F61 | 任务绑定主对话与结果交接 | `services/chat-task-handoff.ts；TasksPane 绑定徽标` | **未移植** | 移植版无任务概念 |

### 机器人/手机

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F62 | 机器人页（Bots tab 列表/添加/详情） | `redesign/BotsPane.tsx:1-80；remote:get-state` | **只有界面** | Main.qml:447 RailButton bot 无 onClicked；无 BotsPane 对应 QML |
| F63 | 远程渠道（Web/飞书/Telegram 扫码配对、回复模式/范围） | `services/remote/*；remote:*` | **未移植** | 移植版无 remote 服务；`grep -rn "telegram\\|feishu" app/src` 无结果 |
| F64 | 手机联动（QR/设备/中转） | `redesign/PhonePane.tsx；services/remote/web/phone.ts；phone:*` | **未移植** | 移植版无 phone 服务/UI |

### 设置与扩展

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F65 | 语言/主题/聊天字号 | `redesign/SettingsPane.tsx:92-176` | **已实现且可用** | SettingsModal.qml:280-345 三行 SetRow → qml_shell.py:483-516 setLanguage/setTheme/setTextSize（sm/md/lg/xl） |
| F66 | 模型服务商列表/详情/密钥/请求头 | `features/settings/ModelSettings.tsx；preload models` | **已实现且可用** | SettingsModal modelsPane + qml_shell.py:764-880/850-861 setProviderHeaders；上一轮已验收 |
| F67 | 从服务商拉取模型列表 | `services/provider.ts:74 provider:list-models；ModelSettings.tsx:250` | **未移植** | ModelGateway.list_models 有后端（provider_setup.py:168-190），QML 无「获取模型列表」按钮/建议列表 |
| F68 | 自定义服务商/自定义模型 | `ModelSettings.tsx 自定义入口；provider:list-models` | **已实现且可用** | SettingsModal.qml:545 custom-model 入口 + qml_shell.py:821-845 addProvider/addModel |
| F69 | 技能列表/启停/删除 | `SettingsPane.tsx ExtensionsPane；skills:*` | **已实现且可用** | qml_shell.py:1145-1245 extensionRows/toggleExtension/setSkillEnabled；ExtensionDetail.qml |
| F70 | 技能导入（zip/md） | `services/skills.ts:767-787；dialog.showOpenDialog` | **未移植** | skill_store.py:12 注释明说文件导入未实现；QML 扩展页无导入按钮 |
| F71 | MCP 列表/编辑/密钥/重试/工具清单 | `SettingsPane.tsx:493-760；mcp:*` | **已实现且可用** | extension_runtime.py + ExtensionDetail.qml；上一轮 runtime-parity 验收三种传输 |
| F72 | 技能/MCP 角色白名单 | `SettingsPane.tsx roles 下拉；skills:set-roles/mcp:set-roles` | **已实现且可用** | ExtensionDetail.qml:115-160 rolesTrigger/rolesPopup + qml_shell.py toggleExtension |
| F73 | About/版本 | `SettingsPane.tsx:878-894` | **已实现且可用** | SettingsModal.qml aboutPane + qml_shell.py appVersion |
| F74 | 检查更新 | `services/updater.ts:270-273；UpdateSection.tsx` | **已实现且可用** | qml_shell.py:415-464 checkForUpdates/_check_updates_worker（GitHub Releases API） |
| F75 | 下载/安装更新 | `services/updater.ts:270-273 download/install；UpdateSection.tsx:47-120` | **未移植** | ShellBridge 只有 checking/latest/available/error 四态，无 download/install 槽；原版 autoUpdater(electron-updater) 为 Electron 特有 |
| F76 | 个人资料（头像/昵称） | `services/profile.ts:49-58；redesign/ProfilePanel.tsx` | **只有界面** | Main.qml:414-425 头像按钮只画 Avatar(persona:"user")，无 MouseArea；无 profile 服务 |

### 其他原生能力

| ID | 功能 | 原版依据（文件:行号） | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|
| F77 | 剪贴板读写 | `services/clipboard.ts:15-25` | **已实现且可用** | qml_shell.py:1385-1395 copyDeliverablePath 用 QGuiApplication.clipboard() 写并回读校验 |
| F78 | 内置浏览器（多窗口/标签/缩略图/导航） | `services/browser/host.ts:554-660；features/browser/*` | **未移植** | 16 条 browser:* 通道无对应；移植版单窗口 QML，无 BrowserView/标签注册表 |
| F79 | 终端（PTY 会话） | `services/terminal.ts:87-108` | **不适用** | 原版渲染层无任何 terminal.* 调用（grep 无结果），属未接线的服务端能力，不构成用户可达功能 |
| F80 | 子智能体/成员对话 | `services/subagents.ts, chat-members.ts, MemberBar.tsx；chat:remove-member` | **未移植** | 移植版 tool_runtime 只有 10 个工具（tool_runtime.py:4-6），无 subagent/member 能力 |
| F81 | 自动任务卡/提案卡响应 | `chat:resolve-proposal / resolve-autotask；features/chat blocks` | **未移植** | 移植版无 proposals/autotasks 边车与卡片（chat_models.py 只有字段名） |
| F82 | 代理环境变量与系统路由 | `apps/desktop/src/main/http.ts:41-123,162-180（env 代理 + system/PAC 探测 + 换路由重试 + NO_PROXY/CIDR/端口/通配符）` | **已实现且可用** | e90dcb1：http_client.py 支持 CIDR/端口/通配符/空白分隔/IPv6；system_proxy.py 走真实 libproxy（PAC/WPAD）或 Qt 平台；transport.py 仅 ConnectError/ConnectTimeout/ProxyError 换路由并按 origin 记忆；scripts/parity/final_port/proxy_routes.py 真实 socket + 真实 PAC 复跑 PASS（7 个 NO_PROXY 边界） |
| F83 | 日志与诊断面板 | `原版无日志 UI（仅 main 进程 console）` | **不适用** | 原版不存在此功能 |
| F84 | 语音输入/输入法专属功能 | `原版无语音/听写代码（grep speech/voice 无结果）` | **不适用** | 原版不存在语音功能；输入法由系统提供 |

## 3. 最要紧的未移植项（按用户影响排序）

1. **F30 工具调用/思考/子代理活动卡**：原版每条工具调用都有可展开卡片（`features/chat/blocks.tsx`），移植版 `transcript_markdown` 只拼 text 块、纯工具消息直接跳过——用户看不到模型在做什么。
2. **F58-F61 定时任务整页**：原版有完整 cron/once 调度、运行历史、通知与主对话交接；移植版只有 `Main.qml:440` 一个无动作的闹钟图标。
3. **F62-F64 机器人/手机联动**：原版 BotsPane + PhonePane（Web/飞书/Telegram 扫码、设备管理）；移植版 `Main.qml:447` 一个无动作的 bot 图标。
4. **F52-F56 角色资料与编辑**：资料卡、新建/编辑/删除、头像编辑、排序、角色记忆仍未移植；花名册入口只到列表/搜索/开始会话。
5. **F33/F34/F35/F36 消息操作**：回滚、消息右键（复制/引用/选择删除）、引用条、按轮删除全部缺失。
6. **F78 内置浏览器**：16 条 browser:* 通道与多窗口/标签/缩略图全缺。
7. **F67 从服务商拉取模型列表**：原版模型设置里有「获取模型列表」，移植版只有手工输入模型 ID。
8. **F14/F80 @提及与子智能体成员**：原版 @ 成员进入对话依赖 subagent/member 架构，移植版无成员注册表，@ 候选不能单独实现。
9. **F02/F03/F15 托盘与系统通知**：代码已接线但本环境 offscreen `isSystemTrayAvailable=false`，未验证；回复通知同样依赖托盘消息。
10. **F75 下载/安装更新**：原版 electron-updater 的 download/install 未移植，现只有检查更新。

## 4. 两个入口分开写

- 本表所有「移植版」列只针对当前 QML 壳（`app/src/qml/Main.qml` + `app/src/qml_shell.py` + `app/src/qml_shell_sessions.py`）。
- 旧 `app/src/mvvm/webui/bridge.py` 是 **web 入口**，虽然实现了部分 `chat:*`/`fs:*` 通道，但 QML 壳不走它；本表不把 web 入口的存在算作 QML 已移植。
- 同理，`PersonaStore`/`SkillStore`/`ModelGateway` 有后端函数不等于用户可用——只有 QML 槽和控件都接上才记为已实现。

## 5. 复现命令

```sh
# 原版 IPC 全集（文件:行号）
cd /home/agent/shared_workspace/deva && grep -rn "ipcMain\.\(handle\|on\)(" apps/desktop/src/main --include=*.ts

# 原版 preload 桥（21 组、186 个方法，含 18 个监听）
cd /home/agent/shared_workspace/deva && sed -n "623,1252p" apps/desktop/src/preload/index.ts

# 移植版 QML 槽
cd /home/agent/shared_workspace/ai_upper && grep -n "@QtCore.Slot" app/src/qml_shell.py
```

## 6. 本轮 B 补齐记录（均已单独 commit + push）

| 项 | commit | 远端 SHA | 真实交互证据 |
|---|---|---|---|
| F37 停止生成 | 942bf59 | 942bf59407688acc4680e321b4ab97d3d42f655e | test_qml_stop_generation.py 真实鼠标点停止键，stopReason=aborted；暗亮截图 stop-busy-*.png |
| F07 正文链接 | 343ae26 | 343ae26993d000a3f500398704cad22c3cfa9cd8 | test_qml_links.py 真实鼠标点链接，openExternal 收到 https://example.com/docs |
| F10/F27b 会话列表收起 | 9b43a24 | 9b43a244c8bbce7fdae0f4d82e4083ff0ade1c31 | test_qml_sidebar_collapse.py 真实 Ctrl+B + hover peek，config 落盘；暗亮截图 sidebar-*.png |
| F09 编辑右键菜单 | 81eca98 | 81eca986ba52e5637af09b4bdd43ebf093834637 | test_qml_edit_menu.py 真实右键 + 点击「全选」；暗亮截图 edit-menu-*.png |
| F46/F47 拖放与粘贴附件 | b25dc1b | b25dc1b7a025e807cf8e89bb6c6b989d5814e412 | test_qml_attachments_drop.py 真实 QDragEnterEvent/QDropEvent + Ctrl+V；暗亮截图 drop-overlay-*.png |
| F01 单实例唤起 | 4bee356 | 4bee3567348acea1e8a6907e88edb96be2c633ad | test_single_instance.py 两个真实进程，第二个 rc=0，第一个打印 SINGLE INSTANCE ACTIVATE |
| F25 未读红点 | dfd6c05 | dfd6c05c852eeecd7dcaf310cb3b9c2c144b131a | test_qml_unread.py 后台回合 done 后红点、点击清除；暗亮截图 unread-dot-*.png |
| F13 指令联想（/compact） | 68abc0a | 68abc0adddd8d840ab8398e8d9841c9060ec0cea | test_qml_slash_menu.py 真实键盘 `/`+Enter 调 compact；暗亮截图 slash-menu-*.png。仅 /compact，/rewind 与技能指令未移植 |
| F02/F03/F15 托盘+通知 | 2880334 | 28803342d4e9795a1db2ed2091fe81f1a774a631 | TrayController 接线 + closeToTray + _notify_turn；本环境 offscreen `isSystemTrayAvailable=false`，真实报错见 out/feature-parity/tray-platform.json，**未验证**，不冒充已可用 |
| F82 代理/系统路由 | e90dcb1（并行执行） | e90dcb17759b05dbdb79b869305dc5070fcc68c2 | proxy_routes.py 真实 socket + 真实 libproxy/PAC，7 个 NO_PROXY 边界 PASS |

并行执行另推送 f4df491（会话筛选）、92d9be2（角色花名册）、fdb2299（会话草稿隔离）；本盘点采用其 `out/parity-close/*.json` 真实点击证据计入 F23/F26/F51，不属于本会话产出。

## 7. 附录：169 条 IPC / 桥通道逐条判定

> 通道原名、kind（handle/on）、原版注册位置均来自 `grep -rn "ipcMain\.\(handle\|on\)("` 实测；`移植版判定` 为按通道语义逐条对照 QML 壳后的结论。

| # | 通道 | kind | 原版位置 | 移植版状态 | 证据 / 缺口 |
|---|---|---|---|---|---|
| 1 | `app:get-platform` | handle | `index.ts:322` | 已实现且可用 | Main.qml:29 用 Qt.platform.os 判平台；qml_shell 无平台 IPC 但行为等价 |
| 2 | `browser:activate` | handle | `services/browser/host.ts:590` | 未移植 | 移植版无内置浏览器 |
| 3 | `browser:close-session` | handle | `services/browser/host.ts:566` | 未移植 | 移植版无内置浏览器 |
| 4 | `browser:close-tab` | handle | `services/browser/host.ts:594` | 未移植 | 移植版无内置浏览器 |
| 5 | `browser:dock` | handle | `services/browser/host.ts:561` | 未移植 | 移植版无内置浏览器 |
| 6 | `browser:handoff` | handle | `services/browser/host.ts:650` | 未移植 | 移植版无内置浏览器 |
| 7 | `browser:live-start` | handle | `services/browser/host.ts:579` | 未移植 | 移植版无内置浏览器 |
| 8 | `browser:live-stop` | handle | `services/browser/host.ts:582` | 未移植 | 移植版无内置浏览器 |
| 9 | `browser:menu` | handle | `services/browser/host.ts:610` | 未移植 | 移植版无内置浏览器 |
| 10 | `browser:nav` | handle | `services/browser/host.ts:598` | 未移植 | 移植版无内置浏览器 |
| 11 | `browser:open` | handle | `services/browser/host.ts:556` | 未移植 | 移植版无内置浏览器 |
| 12 | `browser:pin` | handle | `services/browser/host.ts:586` | 未移植 | 移植版无内置浏览器 |
| 13 | `browser:preview-pinned` | handle | `services/browser/host.ts:572` | 未移植 | 移植版无内置浏览器 |
| 14 | `browser:ready` | handle | `services/browser/host.ts:660` | 未移植 | 移植版无内置浏览器 |
| 15 | `browser:state` | handle | `services/browser/host.ts:554` | 未移植 | 移植版无内置浏览器 |
| 16 | `browser:stop` | handle | `services/browser/host.ts:654` | 未移植 | 移植版无内置浏览器 |
| 17 | `browser:thumbnail` | handle | `services/browser/host.ts:639` | 未移植 | 移植版无内置浏览器 |
| 18 | `chat:abort` | handle | `services/chat.ts:730` | 未移植 | host.py:306 abort 有后端，QML 无停止键/槽 |
| 19 | `chat:ask-response` | handle | `services/chat.ts:946` | 未移植 | 无对应实现 |
| 20 | `chat:attach-session` | handle | `services/chat.ts:656` | 未移植 | host.py:509 attach 有后端，QML 无接续回合入口 |
| 21 | `chat:attachment-image` | handle | `services/chat.ts:650` | 已实现且可用 | qml_shell_sessions.py:304-329 |
| 22 | `chat:compact` | handle | `services/chat.ts:494` | 未移植 | host.py:446 compact 有后端，QML 无 /compact 入口 |
| 23 | `chat:context-usage` | handle | `services/context-usage.ts:54` | 已实现且可用 | qml_shell.py:964-1005 |
| 24 | `chat:create-session` | handle | `services/chat.ts:551` | 已实现且可用 | qml_shell.py:595-606 |
| 25 | `chat:delete-session` | handle | `services/chat.ts:691` | 已实现且可用 | qml_shell.py:606-626 |
| 26 | `chat:delete-turns` | handle | `services/chat.ts:751` | 未移植 | host.py:415 有后端，QML 无入口 |
| 27 | `chat:insert` | handle | `services/chat.ts:485` | 未移植 | 无 chat:insert |
| 28 | `chat:list-sessions` | handle | `services/chat.ts:626` | 已实现且可用 | qml_shell.py:1663-1683 _rows → session_rows |
| 29 | `chat:load-session` | handle | `services/chat.ts:644` | 已实现且可用 | qml_shell.py:585-594 openSession |
| 30 | `chat:mark-read` | handle | `services/read-sync.ts:81` | 未移植 | 无未读状态 |
| 31 | `chat:mount-response` | handle | `services/chat.ts:954` | 未移植 | 无对应实现 |
| 32 | `chat:plan-response` | handle | `services/chat.ts:950` | 未移植 | 无对应实现 |
| 33 | `chat:remove-member` | handle | `services/chat.ts:701` | 未移植 | 无成员对话 |
| 34 | `chat:rename-session` | handle | `services/chat.ts:601` | 已实现且可用 | qml_shell.py:626-642 |
| 35 | `chat:resolve-autotask` | handle | `services/chat.ts:676` | 未移植 | 无自动任务卡 |
| 36 | `chat:resolve-proposal` | handle | `services/chat.ts:669` | 未移植 | 无提案卡边车 |
| 37 | `chat:rewind-apply` | handle | `services/chat.ts:824` | 未移植 | 无 rewind |
| 38 | `chat:rewind-list` | handle | `services/chat.ts:798` | 未移植 | 无 rewind |
| 39 | `chat:rewind-preview` | handle | `services/chat.ts:808` | 未移植 | 无 rewind |
| 40 | `chat:rewind-undo` | handle | `services/chat.ts:916` | 未移植 | 无 rewind |
| 41 | `chat:send` | handle | `services/chat.ts:482` | 已实现且可用 | qml_shell.py:1251-1297 → ChatHost.send(host.py:166) |
| 42 | `chat:set-archived` | handle | `services/chat.ts:621` | 已实现且可用 | qml_shell.py:643-700 |
| 43 | `chat:set-effort` | handle | `services/chat.ts:571` | 已实现且可用 | qml_shell.py:1026-1040 setActiveEffort |
| 44 | `chat:set-focus` | handle | `services/chat.ts:584` | 已实现且可用 | qml_shell.py:1312-1338 acceptWorkspace |
| 45 | `chat:set-model` | handle | `services/chat.ts:566` | 已实现且可用 | qml_shell.py:1006-1026 setActiveModel |
| 46 | `chat:stop-subagent` | handle | `services/chat.ts:737` | 未移植 | 无子智能体 |
| 47 | `chat:todo-cancel` | handle | `services/chat.ts:780` | 未移植 | 无 Todo UI |
| 48 | `chat:todos` | handle | `services/chat.ts:773` | 未移植 | host.py:426 有后端，QML 无 Todo 展示 |
| 49 | `chat:withdraw-inserts` | handle | `services/chat.ts:486` | 未移植 | 无插入队列 |
| 50 | `clipboard:read-text` | handle | `services/clipboard.ts:15` | 已实现且可用 | QGuiApplication.clipboard() 可用；复制路径走写端 |
| 51 | `clipboard:write-text` | handle | `services/clipboard.ts:18` | 已实现且可用 | qml_shell.py:1385-1395 |
| 52 | `config:get` | handle | `services/config.ts:89` | 已实现且可用 | qml_shell.py:366-379 _config/_write_config |
| 53 | `config:get-sync` | on | `services/config.ts:83` | 已实现且可用 | 同上同步读取 |
| 54 | `config:set` | handle | `services/config.ts:95` | 已实现且可用 | qml_shell.py:369-379 set_config |
| 55 | `deliverables:inspect` | handle | `services/deliverables.ts:71` | 已实现且可用 | qml_shell.py:1371-1374 deliveryItems |
| 56 | `deliverables:open` | handle | `services/deliverables.ts:111` | 已实现且可用 | qml_shell.py:1375-1379 openDeliverable |
| 57 | `deliverables:reveal` | handle | `services/deliverables.ts:121` | 已实现且可用 | qml_shell.py:1380-1384 revealDeliverable |
| 58 | `deliverables:thumbnail` | handle | `services/deliverables.ts:91` | 未移植 | delivery_row 无缩略图字段 |
| 59 | `fs:attachment-image` | handle | `services/attachments.ts:221` | 已实现且可用 | qml_shell_sessions.py:304-329 图片 data URI；AttachmentService |
| 60 | `fs:dropped-entries` | handle | `services/attachments.ts:201` | 未移植 | attachments.py:12-14 明说未移植；QML 无 DropArea |
| 61 | `fs:open-folder` | handle | `services/workspace.ts:43` | 已实现且可用 | Main.qml:20-31 FolderDialog + qml_shell.py:1300-1338 beginWorkspace/acceptWorkspace |
| 62 | `fs:paste-attachment` | handle | `services/attachments.ts:166` | 未移植 | attachments.py:12-14 明说未移植 |
| 63 | `fs:pick-attachments` | handle | `services/attachments.ts:235` | 已实现且可用 | qml_shell.py:1338-1364 pickAttachments + Main.qml:1497 clipBtn |
| 64 | `fs:read-dir` | handle | `services/workspace.ts:64` | 已实现且可用 | Agent list_dir 工具（tool_runtime.py:117-127） |
| 65 | `fs:read-file` | handle | `services/workspace.ts:82` | 已实现且可用 | Agent read_file 工具（tool_runtime.py:94-116） |
| 66 | `fs:reveal-folder` | handle | `services/workspace.ts:55` | 未移植 | 无工作区「在文件夹中显示」入口；仅交付卡 reveal 已实现 |
| 67 | `fs:write-file` | handle | `services/workspace.ts:92` | 已实现且可用 | Agent write_file 工具（tool_runtime.py:180-197） |
| 68 | `git:available` | handle | `services/git.ts:626` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 69 | `git:branches` | handle | `services/git.ts:766` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 70 | `git:cancel-commit-message` | handle | `services/git.ts:1028` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 71 | `git:checkout` | handle | `services/git.ts:793` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 72 | `git:checkout-remote` | handle | `services/git.ts:813` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 73 | `git:commit` | handle | `services/git.ts:741` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 74 | `git:create-branch` | handle | `services/git.ts:803` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 75 | `git:delete-branch` | handle | `services/git.ts:841` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 76 | `git:delete-remote-branch` | handle | `services/git.ts:863` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 77 | `git:diff` | handle | `services/git.ts:682` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 78 | `git:discard` | handle | `services/git.ts:726` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 79 | `git:fetch` | handle | `services/git.ts:896` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 80 | `git:generate-commit-message` | handle | `services/git.ts:930` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 81 | `git:init` | handle | `services/git.ts:889` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 82 | `git:log` | handle | `services/git.ts:874` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 83 | `git:merge` | handle | `services/git.ts:823` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 84 | `git:merge-abort` | handle | `services/git.ts:834` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 85 | `git:pull` | handle | `services/git.ts:905` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 86 | `git:push` | handle | `services/git.ts:914` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 87 | `git:rename-branch` | handle | `services/git.ts:855` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 88 | `git:set-config` | handle | `services/git.ts:757` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 89 | `git:stage` | handle | `services/git.ts:704` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 90 | `git:status` | handle | `services/git.ts:639` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 91 | `git:unstage` | handle | `services/git.ts:713` | 未移植 | 移植版无 git 服务/面板；24 条通道全缺 |
| 92 | `mcp:get` | handle | `services/mcp.ts:634` | 已实现且可用 | extensionAction detail |
| 93 | `mcp:has-secret` | handle | `services/mcp.ts:675` | 已实现且可用 | ExtensionDetail keyStatus |
| 94 | `mcp:list` | handle | `services/mcp.ts:633` | 已实现且可用 | qml_shell.py:1145-1198 extensionRows(mcp) |
| 95 | `mcp:remove` | handle | `services/mcp.ts:636` | 已实现且可用 | extensionAction remove |
| 96 | `mcp:retry` | handle | `services/mcp.ts:654` | 已实现且可用 | extensionAction retry → extension_runtime.retry |
| 97 | `mcp:set-enabled` | handle | `services/mcp.ts:649` | 已实现且可用 | toggleExtension |
| 98 | `mcp:set-roles` | handle | `services/mcp.ts:642` | 已实现且可用 | ExtensionDetail rolesPopup |
| 99 | `mcp:set-secret` | handle | `services/mcp.ts:660` | 已实现且可用 | extensionAction secret |
| 100 | `mcp:upsert` | handle | `services/mcp.ts:635` | 已实现且可用 | extensionAction update/save |
| 101 | `memory:clear` | handle | `services/memory.ts:476` | 未移植 | 无 memory 服务/UI |
| 102 | `memory:delete` | handle | `services/memory.ts:471` | 未移植 | 无 memory 服务/UI |
| 103 | `memory:list` | handle | `services/memory.ts:461` | 未移植 | 无 memory 服务/UI |
| 104 | `memory:write` | handle | `services/memory.ts:462` | 未移植 | 无 memory 服务/UI |
| 105 | `personas:clear-avatar-image` | handle | `services/personas.ts:529` | 未移植 | QML 无头像编辑 |
| 106 | `personas:get` | handle | `services/personas.ts:509` | 已实现且可用 | PersonaStore.get（persona_store.py:179-187）经 quickStart/roles 使用 |
| 107 | `personas:list` | handle | `services/personas.ts:508` | 已实现且可用 | qml_shell.py:701-753 quickStartPersonas + extensionRows 角色头像 |
| 108 | `personas:remove` | handle | `services/personas.ts:513` | 未移植 | PersonaStore.remove 有后端，QML 无删除入口 |
| 109 | `personas:reorder` | handle | `services/personas.ts:521` | 未移植 | QML 无角色排序 |
| 110 | `personas:set-avatar-image` | handle | `services/personas.ts:526` | 未移植 | QML 无头像编辑 |
| 111 | `personas:set-enabled` | handle | `services/personas.ts:517` | 未移植 | QML 无角色启停 UI |
| 112 | `personas:upsert` | handle | `services/personas.ts:510` | 未移植 | PersonaStore.upsert 有后端（persona_store.py:205-237），QML 无新建/编辑角色入口 |
| 113 | `phone:add` | handle | `services/remote/web/phone.ts:369` | 未移植 | 移植版无手机联动 |
| 114 | `phone:get-state` | handle | `services/remote/web/phone.ts:367` | 未移植 | 移植版无手机联动 |
| 115 | `phone:link` | handle | `services/remote/web/phone.ts:433` | 未移植 | 移植版无手机联动 |
| 116 | `phone:qr` | handle | `services/remote/web/phone.ts:426` | 未移植 | 移植版无手机联动 |
| 117 | `phone:qr-cancel` | handle | `services/remote/web/phone.ts:435` | 未移植 | 移植版无手机联动 |
| 118 | `phone:remove` | handle | `services/remote/web/phone.ts:376` | 未移植 | 移植版无手机联动 |
| 119 | `phone:remove-device` | handle | `services/remote/web/phone.ts:441` | 未移植 | 移植版无手机联动 |
| 120 | `phone:retry` | handle | `services/remote/web/phone.ts:398` | 未移植 | 移植版无手机联动 |
| 121 | `phone:set-enabled` | handle | `services/remote/web/phone.ts:389` | 未移植 | 移植版无手机联动 |
| 122 | `profile:get` | handle | `services/profile.ts:49` | 未移植 | 无 profile 服务/资料卡 |
| 123 | `profile:set-avatar` | handle | `services/profile.ts:50` | 未移植 | 无头像编辑 |
| 124 | `profile:set-avatar-image` | handle | `services/profile.ts:55` | 未移植 | 无头像编辑 |
| 125 | `provider:list-models` | handle | `services/provider.ts:74` | 未移植 | ModelGateway.list_models 有后端（provider_setup.py:168-190），QML 无按钮/建议列表 |
| 126 | `remote:delete-bot` | handle | `services/remote/index.ts:316` | 未移植 | 移植版无远程机器人 |
| 127 | `remote:get-state` | handle | `services/remote/index.ts:214` | 未移植 | 移植版无远程机器人 |
| 128 | `remote:pair-cancel` | handle | `services/remote/index.ts:326` | 未移植 | 移植版无远程机器人 |
| 129 | `remote:pair-code` | handle | `services/remote/index.ts:324` | 未移植 | 移植版无远程机器人 |
| 130 | `remote:remove-user` | handle | `services/remote/index.ts:331` | 未移植 | 移植版无远程机器人 |
| 131 | `remote:scan-cancel` | handle | `services/remote/index.ts:282` | 未移植 | 移植版无远程机器人 |
| 132 | `remote:scan-start` | handle | `services/remote/index.ts:218` | 未移植 | 移植版无远程机器人 |
| 133 | `remote:set-enabled` | handle | `services/remote/index.ts:287` | 未移植 | 移植版无远程机器人 |
| 134 | `remote:set-reply-mode` | handle | `services/remote/index.ts:303` | 未移植 | 移植版无远程机器人 |
| 135 | `remote:set-scope` | handle | `services/remote/index.ts:309` | 未移植 | 移植版无远程机器人 |
| 136 | `secrets:available` | handle | `services/secrets.ts:149` | 已实现且可用 | describe_backend（secrets_vault.py:84-89），上一轮私有 D-Bus 实测 |
| 137 | `secrets:delete` | handle | `services/secrets.ts:137` | 已实现且可用 | 同上 |
| 138 | `secrets:has` | handle | `services/secrets.ts:132` | 已实现且可用 | 同上 |
| 139 | `secrets:list` | handle | `services/secrets.ts:143` | 已实现且可用 | 同上 |
| 140 | `secrets:set` | handle | `services/secrets.ts:126` | 已实现且可用 | SecretsVault（keyring/file 双后端）+ 模型/MCP 密钥 UI |
| 141 | `skills:get` | handle | `services/skills.ts:754` | 已实现且可用 | extensionAction detail → ExtensionSettings.detail |
| 142 | `skills:import` | handle | `services/skills.ts:767` | 未移植 | skill_store.py:12 注释明说文件导入未实现 |
| 143 | `skills:list` | handle | `services/skills.ts:753` | 已实现且可用 | qml_shell.py:1145-1198 extensionRows；ExtensionDetail.qml |
| 144 | `skills:remove` | handle | `services/skills.ts:755` | 已实现且可用 | qml_shell.py:1199-1212 toggleExtension/extensionAction remove |
| 145 | `skills:set-enabled` | handle | `services/skills.ts:756` | 已实现且可用 | qml_shell.py:1213-1245 setSkillEnabled |
| 146 | `skills:set-roles` | handle | `services/skills.ts:761` | 已实现且可用 | ExtensionDetail.qml:115-160 rolesPopup |
| 147 | `tasks:create` | handle | `services/tasks.ts:523` | 未移植 | 移植版无任务调度服务 |
| 148 | `tasks:delete` | handle | `services/tasks.ts:529` | 未移植 | 移植版无任务调度服务 |
| 149 | `tasks:get` | handle | `services/tasks.ts:521` | 未移植 | 移植版无任务调度服务 |
| 150 | `tasks:list` | handle | `services/tasks.ts:520` | 未移植 | 移植版无任务调度服务 |
| 151 | `tasks:preview` | handle | `services/tasks.ts:537` | 未移植 | 移植版无任务调度服务 |
| 152 | `tasks:run-now` | handle | `services/tasks.ts:542` | 未移植 | 移植版无任务调度服务 |
| 153 | `tasks:set-status` | handle | `services/tasks.ts:533` | 未移植 | 移植版无任务调度服务 |
| 154 | `tasks:update` | handle | `services/tasks.ts:526` | 未移植 | 移植版无任务调度服务 |
| 155 | `terminal:create` | handle | `services/terminal.ts:91` | 不适用 | 原版渲染层无 terminal 调用，用户不可达 |
| 156 | `terminal:dispose` | on | `services/terminal.ts:108` | 不适用 | 原版渲染层无 terminal 调用，用户不可达 |
| 157 | `terminal:input` | on | `services/terminal.ts:100` | 不适用 | 原版渲染层无 terminal 调用，用户不可达 |
| 158 | `terminal:list-shells` | handle | `services/terminal.ts:87` | 不适用 | 原版渲染层无 terminal 调用，用户不可达 |
| 159 | `terminal:resize` | on | `services/terminal.ts:104` | 不适用 | 原版渲染层无 terminal 调用，用户不可达 |
| 160 | `update:check` | handle | `services/updater.ts:271` | 已实现且可用 | qml_shell.py:420-464 checkForUpdates |
| 161 | `update:download` | handle | `services/updater.ts:272` | 未移植 | 无下载槽（electron-updater 特有） |
| 162 | `update:get-state` | handle | `services/updater.ts:270` | 已实现且可用 | qml_shell.py:415-419 updateState |
| 163 | `update:install` | handle | `services/updater.ts:273` | 未移植 | 无安装槽（electron-updater 特有） |
| 164 | `window:close` | handle | `index.ts:320` | 已实现且可用 | Main.qml:2477-2480 window.close；同测 |
| 165 | `window:is-fullscreen` | handle | `index.ts:321` | 未移植 | 无全屏状态查询/信号 |
| 166 | `window:minimize` | handle | `index.ts:314` | 已实现且可用 | Main.qml:2462-2465 showMinimized；test_qml_window_controls.py |
| 167 | `window:set-overlay` | handle | `index.ts:304` | 已实现且可用 | Main.qml:280-345 自绘窗口控件按 Theme.dark 取色 |
| 168 | `window:toggle-maximize` | handle | `index.ts:315` | 已实现且可用 | Main.qml:2467-2476 showNormal/showMaximized；同测 |
| 169 | `workspace:role-home` | handle | `services/role-home.ts:83` | 未移植 | 无角色主目录 |
