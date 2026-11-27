# deva 功能盘点复核（未完成）

本轮入口为 b25dc1b；旧原稿以 a563434 为基线，漏掉已经推送的五项功能，不能使用旧三态计数。原稿保存在 .tmp/feature-review/。本报告不把未验证项目伪装成“只有界面”或“未移植”。

已复核子集计数：{'not_ported': 6, 'implemented': 15, 'ui_only': 4}；未验证 59 项。**这不是全量三态计数，A 尚未完成。**

## 起始对账

```text
$ git log --oneline -6
b25dc1b feat: accept dropped files and clipboard images as QML attachments
81eca98 feat: add edit context menus to the QML composer and transcript
9b43a24 feat: collapse the QML session list with Ctrl/Cmd+B and hover peek
343ae26 feat: open markdown links from the QML transcript in the system browser
942bf59 feat: add stop generation control to the QML composer
a563434 docs: record remaining raster differences and final navigation regression
$ git status --porcelain
?? docs/audit/feature-parity-gap.json
?? docs/audit/feature-parity-gap.md
$ git rev-parse HEAD
b25dc1b7a025e807cf8e89bb6c6b989d5814e412
$ git ls-remote origin refs/heads/develop
b25dc1b7a025e807cf8e89bb6c6b989d5814e412	refs/heads/develop
```

a563434 与随后五项未回退、不重做；残留为未跟踪文档，复制后按实证改写。既有五项本轮不冒领新增。

## 功能候选全集与验证状态

旧 84 项为候选集，尚未证明穷尽全部非 IPC 功能。表中未验证项的历史线索保留在 JSON 的 legacy_claim，不能当作本轮结论。web 入口在 IPC 清单另列，仅是代码出现位置，未记为 QML 可用。

|ID|功能分组 / 功能|原版依据|移植版状态|证据 / 缺口|
|---|---|---|---|---|
|F01|应用生命周期与窗口 / 单实例锁与二次启动唤起|apps/desktop/src/main/index.ts:276-286|未移植|out/feature-review/F01-search.txt; scope QML + ShellBridge; 原版依据需继续逐段复核，不能外推 web 入口。|
|F02|应用生命周期与窗口 / 关窗驻留托盘（closeToTray）|apps/desktop/src/main/index.ts:164-173；redesign/SettingsPane.tsx:101-113,165-172|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F03|应用生命周期与窗口 / 系统托盘图标与菜单（显示/定时任务/退出）|apps/desktop/src/main/index.ts:235-272；services/tray-icon.ts|未移植|out/feature-review/F03-search.txt; scope QML + ShellBridge; 原版依据需继续逐段复核，不能外推 web 入口。|
|F04|应用生命周期与窗口 / 窗口最小化/最大化/关闭|apps/desktop/src/main/index.ts:307-322；preload/index.ts:625-639|已实现且可用|Main.qml windowControlMinimize/windowControlMaximize/windowControlClose，真实点击断言窗口状态；app/tests/test_qml_window_controls.py:219；out/feature-review/pytest.log。测试并非纯后端单测。|
|F05|应用生命周期与窗口 / 窗口控件叠加配色随主题|apps/desktop/src/main/index.ts:79-97,304-312|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F06|应用生命周期与窗口 / 全屏状态通知（macOS 红绿灯让位）|apps/desktop/src/main/index.ts:158-160；preload/index.ts:631-636；redesign/ChatFirstShell.tsx:52-66|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F07|应用生命周期与窗口 / 外链一律系统浏览器打开|apps/desktop/src/main/index.ts:175-181|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F08|菜单与快捷键 / 应用菜单栏|apps/desktop/src/main/index.ts:108 autoHideMenuBar:true；全仓无 setApplicationMenu|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F09|菜单与快捷键 / 编辑区右键菜单（剪切/复制/粘贴/全选）|apps/desktop/src/main/index.ts:183-217|已实现且可用|Main.qml:1560 → EditContextMenu.qml；真实右键、点击全选及选区断言；app/tests/test_qml_edit_menu.py:52；out/feature-review/pytest.log。测试并非纯后端单测。|
|F10|菜单与快捷键 / Ctrl/Cmd+B 收起/展开会话列表|redesign/ChatFirstShell.tsx:191-199|已实现且可用|Main.qml Shortcut/toggleSidebar；真实 Ctrl+B/鼠标悬停及配置读回；lifecycle.log 通过；app/tests/test_qml_sidebar_collapse.py:99；out/feature-review/pytest.log。测试并非纯后端单测。|
|F11|菜单与快捷键 / Esc 收回浮出列表|redesign/ChatFirstShell.tsx:192-194|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F12|菜单与快捷键 / Enter 发送 / Shift+Enter 换行|redesign/Composer.tsx:669-700|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F13|菜单与快捷键 / 输入框 / 指令联想（/compact /rewind /技能）|redesign/Composer.tsx:382-420|未移植|out/feature-review/F13-search.txt; scope QML + ShellBridge; 原版依据需继续逐段复核，不能外推 web 入口。|
|F14|菜单与快捷键 / @ 提及成员/角色|redesign/Composer.tsx:399-419；shared/mention.ts|未移植|out/feature-review/F14-search.txt; scope QML + ShellBridge; 原版依据需继续逐段复核，不能外推 web 入口。|
|F15|菜单与快捷键 / 回复完成/待处理系统通知|services/reply-notify.ts:15-80；chat-turns.ts:801|未移植|out/feature-review/F15-search.txt; scope QML + ShellBridge; 原版依据需继续逐段复核，不能外推 web 入口。|
|F16|会话列表 / 新建会话|redesign/Rail.tsx:600-660（加号菜单）；preload/index.ts:805-940 chat.createSession|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F17|会话列表 / 切换会话|redesign/Rail.tsx:700-760|已实现且可用|Main.qml activate → ShellBridge.openSession；实际会话行点击和文档切换；另 drafts.json 双主题通过；app/tests/test_qml_session_switch.py:6；out/feature-review/pytest.log。测试并非纯后端单测。|
|F18|会话列表 / 重命名会话|redesign/Rail.tsx:175-182 RowMenu；chat:rename-session|已实现且可用|Main.qml confirmRename；真实右键、输入、确认后标题及会话文件读回；app/tests/test_qml_context_menu.py:294；out/feature-review/pytest.log。测试并非纯后端单测。|
|F19|会话列表 / 删除会话|redesign/Rail.tsx:175-182；chat:delete-session|已实现且可用|Main.qml confirmDelete；真实右键、确认后会话文件删除；app/tests/test_qml_context_menu.py:170；out/feature-review/pytest.log。测试并非纯后端单测。|
|F20|会话列表 / 归档/取消归档|redesign/Rail.tsx:620-650；chat:set-archived|已实现且可用|Main.qml archiveSelected/contextMenu；真实点击归档并读回会话；app/tests/test_qml_context_menu.py:466；out/feature-review/pytest.log。测试并非纯后端单测。|
|F21|会话列表 / 归档视图|redesign/Rail.tsx archiveView|已实现且可用|Main.qml archiveView/archiveBack；真实点击进入归档列表；app/tests/test_qml_context_menu.py:466；out/feature-review/pytest.log。测试并非纯后端单测。|
|F22|会话列表 / 会话搜索（标题/角色/挂载目录）|redesign/Rail.tsx:600-640|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F23|会话列表 / 会话筛选面板（角色/文件夹）|redesign/Rail.tsx:183-186,664-710|只有界面|app/src/qml/Main.qml:583-599 filterBtn 仅 Item/Icon，无输入 handler；本轮读取完整控件块。|
|F24|会话列表 / 会话多选批量归档/删除|redesign/ThreadSelect.tsx|已实现且可用|Main.qml selectMode/selectedSessions/batch controls；真实菜单多选及批量归档读回；app/tests/test_qml_context_menu.py:337；out/feature-review/pytest.log。测试并非纯后端单测。|
|F25|会话列表 / 未读/待处理状态与红点|redesign/Rail.tsx:116-129；store/chat.tsx sessionStates.unread/attention|未移植|out/feature-review/F25-search.txt; scope QML + ShellBridge; 原版依据需继续逐段复核，不能外推 web 入口。|
|F26|会话列表 / 草稿按会话保留|redesign/Composer.tsx:109-121,755-760|已实现且可用|app/src/qml/Main.qml:104 onActiveIdChanged; scripts/parity/draft_evidence.py; out/feature-review/draft-before.log 真实点击失败；drafts.json 暗亮切换后恢复各自输入；drafts-dark/light.png。文字及待发附件实现；附件经真实拖放、切换和源文件读回通过；撤销历史边界尚需专门验证。|
|F27|会话列表 / 会话列表宽度拖动/收起并记忆|redesign/resizable.ts；ChatFirstShell.tsx:143-160|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F28|会话列表 / 会话行右键菜单（新建/重命名/多选/归档/删除）|redesign/Rail.tsx:175-182；ContextMenu.tsx|已实现且可用|Main.qml 右键命中非当前会话；真实菜单动作作用于目标行；app/tests/test_qml_context_menu.py:368；out/feature-review/pytest.log。测试并非纯后端单测。|
|F29|对话正文 / 用户/助手 Markdown 正文|redesign/ConvMessage.tsx；features/chat/blocks.tsx|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F30|对话正文 / 工具调用/工具结果/思考/子代理活动卡|features/chat/blocks.tsx BlockView；redesign/ChatFirstShell.tsx:39-44 注释|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F31|对话正文 / 待处理交互卡（ask/审批）|features/chat/blocks.tsx AskCard；chat:ask-response|已实现且可用|InteractionPrompt.qml；真实按钮点击回答与审批，后端事件结果断言；app/tests/test_qml_plugin_settings.py:44；out/feature-review/pytest.log。测试并非纯后端单测。|
|F32|对话正文 / 计划卡与 plan-response|chat:plan-response；features/chat/blocks.tsx PlanCard|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F33|对话正文 / 回滚 rewind（列点/预览/应用/撤销）|redesign/RewindModal.tsx:31；Conversation.tsx:998-1003；chat:rewind-*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F34|对话正文 / 消息右键菜单（复制/引用/回滚/选择删除）|redesign/Conversation.tsx:905-950|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F35|对话正文 / 引用条 quote|redesign/ConvMessage.tsx leadingQuote/withQuote；Composer.tsx|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F36|对话正文 / 选择消息删除（delete-turns）|chat:delete-turns；redesign/Conversation.tsx:955-1000|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F37|对话正文 / 停止生成|redesign/Composer.tsx:973-991（busy 时空输入框显示停止键）；chat:abort|已实现且可用|Main.qml:1693 stopGlyph → ShellBridge.stopGeneration:1319；真实点击停止，测试传输结束原因 aborted；不声称真实云端网络验证；app/tests/test_qml_stop_generation.py:133；out/feature-review/pytest.log。测试并非纯后端单测。|
|F38|对话正文 / 回合中插入消息（插话）|chat:insert / chat:withdraw-inserts；Composer.tsx:463-467|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F39|对话正文 / 手动压缩 /compact|redesign/Composer.tsx:382-386；chat:compact|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F40|对话正文 / Todo 胶囊|redesign/Composer.tsx:864 TodoCapsule|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F41|对话正文 / 后台任务胶囊|redesign/Composer.tsx:865 BackgroundCapsule|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F42|对话正文 / 浏览器操作胶囊|redesign/Composer.tsx:866 BrowserCapsule|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F43|对话正文 / 上下文用量圆环|redesign/ContextRing.tsx；chat:context-usage|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F44|对话正文 / 模型/思考等级切换菜单|redesign/ModelMenu.tsx, EffortPicker.tsx|已实现且可用|Main.qml 模型与思考贴片 → ModelPicker.qml；真实点击并读取模型/effort 配置；app/tests/test_qml_model_picker.py:133；out/feature-review/pytest.log。测试并非纯后端单测。|
|F45|对话正文 / 附件选择（回形针）|redesign/Composer.tsx:950；fs:pick-attachments|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F46|对话正文 / 附件拖放|redesign/Composer.tsx:576-596；fs:dropped-entries|已实现且可用|Main.qml:74 DropArea → ShellBridge.acceptDroppedFiles:1406；真实拖放并验证 pendingFiles；drafts.json 另做暗亮附件切换验证；app/tests/test_qml_attachments_drop.py:70；out/feature-review/pytest.log。测试并非纯后端单测。|
|F47|对话正文 / 粘贴图片/文件为附件|redesign/Composer.tsx:508,567；fs:paste-attachment|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F48|对话正文 / 附件贴片与图片缩略图|redesign/attachments.tsx；fs:attachment-image|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F49|对话正文 / 交付卡（打开/定位/复制路径）|features/chat/DeliverablesCard.tsx；deliverables:*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F50|对话正文 / 交付卡图片缩略图|deliverables:thumbnail|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F51|角色 / 角色花名册 tab（列表/搜索/快速对话）|redesign/Rail.tsx:130-170,600-744|只有界面|app/src/qml/Main.qml:517 RailButton 只有 iconName，无 onClicked；组件默认仅发 clicked 信号，无页面接线。|
|F52|角色 / 角色资料卡（ProfilePanel）|redesign/Rail.tsx:117 ProfilePanel|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F53|角色 / 新建/编辑/删除角色|redesign/ProfileView.tsx PersonaEditor；personas:upsert/remove|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F54|角色 / 角色头像编辑|redesign/AvatarEditor.tsx；personas:set-avatar-image|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F55|角色 / 角色排序（拖拽/置顶）|redesign/Rail.tsx reorderIds；personas:reorder|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F56|角色 / 角色记忆查看/编辑|redesign/RoleMemoryTab.tsx, MemoryDetail.tsx；memory:*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F57|角色 / 快速开始角色卡|redesign/Rail.tsx QuickStart|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F58|定时任务 / 定时任务页（列表/详情/运行历史）|redesign/TasksPane.tsx:1-70；tasks:list/get|只有界面|app/src/qml/Main.qml:518 RailButton 只有 iconName，无 onClicked；组件默认仅发 clicked 信号，无页面接线。|
|F59|定时任务 / 任务调度引擎（once/cron、自动触发）|services/schedule.ts, scheduler.ts；tasks:*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F60|定时任务 / 任务系统通知|services/scheduler.ts:103 new Notification|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F61|定时任务 / 任务绑定主对话与结果交接|services/chat-task-handoff.ts；TasksPane 绑定徽标|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F62|机器人/手机 / 机器人页（Bots tab 列表/添加/详情）|redesign/BotsPane.tsx:1-80；remote:get-state|只有界面|app/src/qml/Main.qml:525 RailButton 只有 iconName，无 onClicked；组件默认仅发 clicked 信号，无页面接线。|
|F63|机器人/手机 / 远程渠道（Web/飞书/Telegram 扫码配对、回复模式/范围）|services/remote/*；remote:*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F64|机器人/手机 / 手机联动（QR/设备/中转）|redesign/PhonePane.tsx；services/remote/web/phone.ts；phone:*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F65|设置与扩展 / 语言/主题/聊天字号|redesign/SettingsPane.tsx:92-176|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F66|设置与扩展 / 模型服务商列表/详情/密钥/请求头|features/settings/ModelSettings.tsx；preload models|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F67|设置与扩展 / 从服务商拉取模型列表|services/provider.ts:74 provider:list-models；ModelSettings.tsx:250|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F68|设置与扩展 / 自定义服务商/自定义模型|ModelSettings.tsx 自定义入口；provider:list-models|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F69|设置与扩展 / 技能列表/启停/删除|SettingsPane.tsx ExtensionsPane；skills:*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F70|设置与扩展 / 技能导入（zip/md）|services/skills.ts:767-787；dialog.showOpenDialog|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F71|设置与扩展 / MCP 列表/编辑/密钥/重试/工具清单|SettingsPane.tsx:493-760；mcp:*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F72|设置与扩展 / 技能/MCP 角色白名单|SettingsPane.tsx roles 下拉；skills:set-roles/mcp:set-roles|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F73|设置与扩展 / About/版本|SettingsPane.tsx:878-894|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F74|设置与扩展 / 检查更新|services/updater.ts:270-273；UpdateSection.tsx|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F75|设置与扩展 / 下载/安装更新|services/updater.ts:270-273 download/install；UpdateSection.tsx:47-120|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F76|设置与扩展 / 个人资料（头像/昵称）|services/profile.ts:49-58；redesign/ProfilePanel.tsx|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F77|其他原生能力 / 剪贴板读写|services/clipboard.ts:15-25|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F78|其他原生能力 / 内置浏览器（多窗口/标签/缩略图/导航）|services/browser/host.ts:554-660；features/browser/*|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F79|其他原生能力 / 终端（PTY 会话）|services/terminal.ts:87-108|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F80|其他原生能力 / 子智能体/成员对话|services/subagents.ts, chat-members.ts, MemberBar.tsx；chat:remove-member|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F81|其他原生能力 / 自动任务卡/提案卡响应|chat:resolve-proposal / resolve-autotask；features/chat blocks|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F82|其他原生能力 / 代理与网络设置|apps/desktop/src/main/http.ts:94-96|—（未验证，不作状态判定）|原版确有 system/env/direct 网络路由；旧稿 na 不成立。QML 设置入口与 Python 网络栈语义尚未逐项验证；out/feature-review/platform-features.txt。|
|F83|其他原生能力 / 日志与诊断面板|原版无日志 UI（仅 main 进程 console）|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|
|F84|其他原生能力 / 语音输入/输入法专属功能|原版无语音/听写代码（grep speech/voice 无结果）|—（未验证，不作状态判定）|旧判定尚未获得本轮逐项验收，不计入三态。|

## 原版 IPC 注册与 preload 全量字面量枚举

重新扫描真实源码：169 个注册点，169 个唯一通道；preload 185 个 invoke/send/on 出现点。正则仅枚举字面量，不以此宣称动态注册已排除。JSON 保留所有出现点及未匹配 preload。

|通道|注册方式|主进程依据|preload 依据|
|---|---|---|---|
|window:set-overlay|handle|apps/desktop/src/main/index.ts:304|apps/desktop/src/preload/index.ts:638|
|window:minimize|handle|apps/desktop/src/main/index.ts:314|apps/desktop/src/preload/index.ts:626|
|window:toggle-maximize|handle|apps/desktop/src/main/index.ts:315|apps/desktop/src/preload/index.ts:627|
|window:close|handle|apps/desktop/src/main/index.ts:320|apps/desktop/src/preload/index.ts:628|
|window:is-fullscreen|handle|apps/desktop/src/main/index.ts:321|apps/desktop/src/preload/index.ts:630|
|app:get-platform|handle|apps/desktop/src/main/index.ts:322||
|fs:paste-attachment|handle|apps/desktop/src/main/services/attachments.ts:166|apps/desktop/src/preload/index.ts:658|
|fs:dropped-entries|handle|apps/desktop/src/main/services/attachments.ts:201|apps/desktop/src/preload/index.ts:675|
|fs:attachment-image|handle|apps/desktop/src/main/services/attachments.ts:221|apps/desktop/src/preload/index.ts:661|
|fs:pick-attachments|handle|apps/desktop/src/main/services/attachments.ts:235|apps/desktop/src/preload/index.ts:651|
|browser:state|handle|apps/desktop/src/main/services/browser/host.ts:554|apps/desktop/src/preload/index.ts:1130; apps/desktop/src/preload/index.ts:1135|
|browser:open|handle|apps/desktop/src/main/services/browser/host.ts:556|apps/desktop/src/preload/index.ts:1140|
|browser:dock|handle|apps/desktop/src/main/services/browser/host.ts:561|apps/desktop/src/preload/index.ts:1142|
|browser:close-session|handle|apps/desktop/src/main/services/browser/host.ts:566|apps/desktop/src/preload/index.ts:1145|
|browser:preview-pinned|handle|apps/desktop/src/main/services/browser/host.ts:572|apps/desktop/src/preload/index.ts:1148|
|browser:live-start|handle|apps/desktop/src/main/services/browser/host.ts:579|apps/desktop/src/preload/index.ts:1150|
|browser:live-stop|handle|apps/desktop/src/main/services/browser/host.ts:582|apps/desktop/src/preload/index.ts:1151|
|browser:pin|handle|apps/desktop/src/main/services/browser/host.ts:586|apps/desktop/src/preload/index.ts:1157|
|browser:activate|handle|apps/desktop/src/main/services/browser/host.ts:590|apps/desktop/src/preload/index.ts:1158|
|browser:close-tab|handle|apps/desktop/src/main/services/browser/host.ts:594|apps/desktop/src/preload/index.ts:1159|
|browser:nav|handle|apps/desktop/src/main/services/browser/host.ts:598|apps/desktop/src/preload/index.ts:1161|
|browser:menu|handle|apps/desktop/src/main/services/browser/host.ts:610|apps/desktop/src/preload/index.ts:1167|
|browser:thumbnail|handle|apps/desktop/src/main/services/browser/host.ts:639|apps/desktop/src/preload/index.ts:1169|
|browser:handoff|handle|apps/desktop/src/main/services/browser/host.ts:650|apps/desktop/src/preload/index.ts:1172|
|browser:stop|handle|apps/desktop/src/main/services/browser/host.ts:654|apps/desktop/src/preload/index.ts:1174|
|browser:ready|handle|apps/desktop/src/main/services/browser/host.ts:660|apps/desktop/src/preload/index.ts:1132|
|chat:send|handle|apps/desktop/src/main/services/chat.ts:482|apps/desktop/src/preload/index.ts:807|
|chat:insert|handle|apps/desktop/src/main/services/chat.ts:485|apps/desktop/src/preload/index.ts:809|
|chat:withdraw-inserts|handle|apps/desktop/src/main/services/chat.ts:486|apps/desktop/src/preload/index.ts:812|
|chat:compact|handle|apps/desktop/src/main/services/chat.ts:494|apps/desktop/src/preload/index.ts:815|
|chat:create-session|handle|apps/desktop/src/main/services/chat.ts:551|apps/desktop/src/preload/index.ts:818|
|chat:set-model|handle|apps/desktop/src/main/services/chat.ts:566|apps/desktop/src/preload/index.ts:821|
|chat:set-effort|handle|apps/desktop/src/main/services/chat.ts:571|apps/desktop/src/preload/index.ts:824|
|chat:set-focus|handle|apps/desktop/src/main/services/chat.ts:584|apps/desktop/src/preload/index.ts:827|
|chat:rename-session|handle|apps/desktop/src/main/services/chat.ts:601|apps/desktop/src/preload/index.ts:830|
|chat:set-archived|handle|apps/desktop/src/main/services/chat.ts:621|apps/desktop/src/preload/index.ts:833|
|chat:list-sessions|handle|apps/desktop/src/main/services/chat.ts:626|apps/desktop/src/preload/index.ts:840|
|chat:load-session|handle|apps/desktop/src/main/services/chat.ts:644|apps/desktop/src/preload/index.ts:843|
|chat:attachment-image|handle|apps/desktop/src/main/services/chat.ts:650|apps/desktop/src/preload/index.ts:846|
|chat:attach-session|handle|apps/desktop/src/main/services/chat.ts:656|apps/desktop/src/preload/index.ts:852|
|chat:resolve-proposal|handle|apps/desktop/src/main/services/chat.ts:669|apps/desktop/src/preload/index.ts:896|
|chat:resolve-autotask|handle|apps/desktop/src/main/services/chat.ts:676|apps/desktop/src/preload/index.ts:908|
|chat:delete-session|handle|apps/desktop/src/main/services/chat.ts:691|apps/desktop/src/preload/index.ts:855|
|chat:remove-member|handle|apps/desktop/src/main/services/chat.ts:701|apps/desktop/src/preload/index.ts:858|
|chat:abort|handle|apps/desktop/src/main/services/chat.ts:730|apps/desktop/src/preload/index.ts:834|
|chat:stop-subagent|handle|apps/desktop/src/main/services/chat.ts:737|apps/desktop/src/preload/index.ts:837|
|chat:delete-turns|handle|apps/desktop/src/main/services/chat.ts:751|apps/desktop/src/preload/index.ts:869|
|chat:todos|handle|apps/desktop/src/main/services/chat.ts:773|apps/desktop/src/preload/index.ts:871|
|chat:todo-cancel|handle|apps/desktop/src/main/services/chat.ts:780|apps/desktop/src/preload/index.ts:877|
|chat:rewind-list|handle|apps/desktop/src/main/services/chat.ts:798|apps/desktop/src/preload/index.ts:880|
|chat:rewind-preview|handle|apps/desktop/src/main/services/chat.ts:808|apps/desktop/src/preload/index.ts:883|
|chat:rewind-apply|handle|apps/desktop/src/main/services/chat.ts:824|apps/desktop/src/preload/index.ts:886|
|chat:rewind-undo|handle|apps/desktop/src/main/services/chat.ts:916|apps/desktop/src/preload/index.ts:889|
|chat:ask-response|handle|apps/desktop/src/main/services/chat.ts:946|apps/desktop/src/preload/index.ts:911|
|chat:plan-response|handle|apps/desktop/src/main/services/chat.ts:950|apps/desktop/src/preload/index.ts:914|
|chat:mount-response|handle|apps/desktop/src/main/services/chat.ts:954|apps/desktop/src/preload/index.ts:917|
|clipboard:read-text|handle|apps/desktop/src/main/services/clipboard.ts:15|apps/desktop/src/preload/index.ts:1094|
|clipboard:write-text|handle|apps/desktop/src/main/services/clipboard.ts:18|apps/desktop/src/preload/index.ts:1096|
|config:get-sync|on|apps/desktop/src/main/services/config.ts:83||
|config:get|handle|apps/desktop/src/main/services/config.ts:89|apps/desktop/src/preload/index.ts:682|
|config:set|handle|apps/desktop/src/main/services/config.ts:95|apps/desktop/src/preload/index.ts:685|
|chat:context-usage|handle|apps/desktop/src/main/services/context-usage.ts:54|apps/desktop/src/preload/index.ts:874|
|deliverables:inspect|handle|apps/desktop/src/main/services/deliverables.ts:71|apps/desktop/src/preload/index.ts:1104|
|deliverables:thumbnail|handle|apps/desktop/src/main/services/deliverables.ts:91|apps/desktop/src/preload/index.ts:1107|
|deliverables:open|handle|apps/desktop/src/main/services/deliverables.ts:111|apps/desktop/src/preload/index.ts:1110|
|deliverables:reveal|handle|apps/desktop/src/main/services/deliverables.ts:121|apps/desktop/src/preload/index.ts:1113|
|git:available|handle|apps/desktop/src/main/services/git.ts:626|apps/desktop/src/preload/index.ts:969|
|git:status|handle|apps/desktop/src/main/services/git.ts:639|apps/desktop/src/preload/index.ts:971|
|git:diff|handle|apps/desktop/src/main/services/git.ts:682|apps/desktop/src/preload/index.ts:977|
|git:stage|handle|apps/desktop/src/main/services/git.ts:704|apps/desktop/src/preload/index.ts:979|
|git:unstage|handle|apps/desktop/src/main/services/git.ts:713|apps/desktop/src/preload/index.ts:981|
|git:discard|handle|apps/desktop/src/main/services/git.ts:726|apps/desktop/src/preload/index.ts:984|
|git:commit|handle|apps/desktop/src/main/services/git.ts:741|apps/desktop/src/preload/index.ts:986|
|git:set-config|handle|apps/desktop/src/main/services/git.ts:757|apps/desktop/src/preload/index.ts:989|
|git:branches|handle|apps/desktop/src/main/services/git.ts:766|apps/desktop/src/preload/index.ts:990|
|git:checkout|handle|apps/desktop/src/main/services/git.ts:793|apps/desktop/src/preload/index.ts:992|
|git:create-branch|handle|apps/desktop/src/main/services/git.ts:803|apps/desktop/src/preload/index.ts:994|
|git:checkout-remote|handle|apps/desktop/src/main/services/git.ts:813|apps/desktop/src/preload/index.ts:997|
|git:merge|handle|apps/desktop/src/main/services/git.ts:823|apps/desktop/src/preload/index.ts:999|
|git:merge-abort|handle|apps/desktop/src/main/services/git.ts:834|apps/desktop/src/preload/index.ts:1000|
|git:delete-branch|handle|apps/desktop/src/main/services/git.ts:841|apps/desktop/src/preload/index.ts:1003|
|git:rename-branch|handle|apps/desktop/src/main/services/git.ts:855|apps/desktop/src/preload/index.ts:1005|
|git:delete-remote-branch|handle|apps/desktop/src/main/services/git.ts:863|apps/desktop/src/preload/index.ts:1008|
|git:log|handle|apps/desktop/src/main/services/git.ts:874|apps/desktop/src/preload/index.ts:1010|
|git:init|handle|apps/desktop/src/main/services/git.ts:889|apps/desktop/src/preload/index.ts:1011|
|git:fetch|handle|apps/desktop/src/main/services/git.ts:896|apps/desktop/src/preload/index.ts:1012|
|git:pull|handle|apps/desktop/src/main/services/git.ts:905|apps/desktop/src/preload/index.ts:1013|
|git:push|handle|apps/desktop/src/main/services/git.ts:914|apps/desktop/src/preload/index.ts:1016|
|git:generate-commit-message|handle|apps/desktop/src/main/services/git.ts:930|apps/desktop/src/preload/index.ts:1027|
|git:cancel-commit-message|handle|apps/desktop/src/main/services/git.ts:1028|apps/desktop/src/preload/index.ts:1030|
|mcp:list|handle|apps/desktop/src/main/services/mcp.ts:633|apps/desktop/src/preload/index.ts:759|
|mcp:get|handle|apps/desktop/src/main/services/mcp.ts:634|apps/desktop/src/preload/index.ts:760|
|mcp:upsert|handle|apps/desktop/src/main/services/mcp.ts:635|apps/desktop/src/preload/index.ts:763|
|mcp:remove|handle|apps/desktop/src/main/services/mcp.ts:636|apps/desktop/src/preload/index.ts:764|
|mcp:set-roles|handle|apps/desktop/src/main/services/mcp.ts:642|apps/desktop/src/preload/index.ts:769|
|mcp:set-enabled|handle|apps/desktop/src/main/services/mcp.ts:649|apps/desktop/src/preload/index.ts:766|
|mcp:retry|handle|apps/desktop/src/main/services/mcp.ts:654|apps/desktop/src/preload/index.ts:771|
|mcp:set-secret|handle|apps/desktop/src/main/services/mcp.ts:660|apps/desktop/src/preload/index.ts:778|
|mcp:has-secret|handle|apps/desktop/src/main/services/mcp.ts:675|apps/desktop/src/preload/index.ts:781|
|memory:list|handle|apps/desktop/src/main/services/memory.ts:461|apps/desktop/src/preload/index.ts:720|
|memory:write|handle|apps/desktop/src/main/services/memory.ts:462|apps/desktop/src/preload/index.ts:726|
|memory:delete|handle|apps/desktop/src/main/services/memory.ts:471|apps/desktop/src/preload/index.ts:728|
|memory:clear|handle|apps/desktop/src/main/services/memory.ts:476|apps/desktop/src/preload/index.ts:729|
|personas:list|handle|apps/desktop/src/main/services/personas.ts:508|apps/desktop/src/preload/index.ts:733|
|personas:get|handle|apps/desktop/src/main/services/personas.ts:509|apps/desktop/src/preload/index.ts:734|
|personas:upsert|handle|apps/desktop/src/main/services/personas.ts:510|apps/desktop/src/preload/index.ts:736|
|personas:remove|handle|apps/desktop/src/main/services/personas.ts:513|apps/desktop/src/preload/index.ts:737|
|personas:set-enabled|handle|apps/desktop/src/main/services/personas.ts:517|apps/desktop/src/preload/index.ts:739|
|personas:reorder|handle|apps/desktop/src/main/services/personas.ts:521|apps/desktop/src/preload/index.ts:742|
|personas:set-avatar-image|handle|apps/desktop/src/main/services/personas.ts:526|apps/desktop/src/preload/index.ts:748|
|personas:clear-avatar-image|handle|apps/desktop/src/main/services/personas.ts:529|apps/desktop/src/preload/index.ts:751|
|profile:get|handle|apps/desktop/src/main/services/profile.ts:49|apps/desktop/src/preload/index.ts:708|
|profile:set-avatar|handle|apps/desktop/src/main/services/profile.ts:50|apps/desktop/src/preload/index.ts:709|
|profile:set-avatar-image|handle|apps/desktop/src/main/services/profile.ts:55|apps/desktop/src/preload/index.ts:712|
|provider:list-models|handle|apps/desktop/src/main/services/provider.ts:74|apps/desktop/src/preload/index.ts:802|
|chat:mark-read|handle|apps/desktop/src/main/services/read-sync.ts:81|apps/desktop/src/preload/index.ts:931|
|remote:get-state|handle|apps/desktop/src/main/services/remote/index.ts:214|apps/desktop/src/preload/index.ts:1189|
|remote:scan-start|handle|apps/desktop/src/main/services/remote/index.ts:218|apps/desktop/src/preload/index.ts:1197|
|remote:scan-cancel|handle|apps/desktop/src/main/services/remote/index.ts:282|apps/desktop/src/preload/index.ts:1198|
|remote:set-enabled|handle|apps/desktop/src/main/services/remote/index.ts:287|apps/desktop/src/preload/index.ts:1200|
|remote:set-reply-mode|handle|apps/desktop/src/main/services/remote/index.ts:303|apps/desktop/src/preload/index.ts:1202|
|remote:set-scope|handle|apps/desktop/src/main/services/remote/index.ts:309|apps/desktop/src/preload/index.ts:1204|
|remote:delete-bot|handle|apps/desktop/src/main/services/remote/index.ts:316|apps/desktop/src/preload/index.ts:1205|
|remote:pair-code|handle|apps/desktop/src/main/services/remote/index.ts:324|apps/desktop/src/preload/index.ts:1207|
|remote:pair-cancel|handle|apps/desktop/src/main/services/remote/index.ts:326|apps/desktop/src/preload/index.ts:1208|
|remote:remove-user|handle|apps/desktop/src/main/services/remote/index.ts:331|apps/desktop/src/preload/index.ts:1210|
|phone:get-state|handle|apps/desktop/src/main/services/remote/web/phone.ts:367|apps/desktop/src/preload/index.ts:1224|
|phone:add|handle|apps/desktop/src/main/services/remote/web/phone.ts:369|apps/desktop/src/preload/index.ts:1226|
|phone:remove|handle|apps/desktop/src/main/services/remote/web/phone.ts:376|apps/desktop/src/preload/index.ts:1228|
|phone:set-enabled|handle|apps/desktop/src/main/services/remote/web/phone.ts:389|apps/desktop/src/preload/index.ts:1229|
|phone:retry|handle|apps/desktop/src/main/services/remote/web/phone.ts:398|apps/desktop/src/preload/index.ts:1231|
|phone:qr|handle|apps/desktop/src/main/services/remote/web/phone.ts:426|apps/desktop/src/preload/index.ts:1233|
|phone:link|handle|apps/desktop/src/main/services/remote/web/phone.ts:433|apps/desktop/src/preload/index.ts:1235|
|phone:qr-cancel|handle|apps/desktop/src/main/services/remote/web/phone.ts:435|apps/desktop/src/preload/index.ts:1237|
|phone:remove-device|handle|apps/desktop/src/main/services/remote/web/phone.ts:441|apps/desktop/src/preload/index.ts:1238|
|workspace:role-home|handle|apps/desktop/src/main/services/role-home.ts:83|apps/desktop/src/preload/index.ts:1119|
|secrets:set|handle|apps/desktop/src/main/services/secrets.ts:126|apps/desktop/src/preload/index.ts:792|
|secrets:has|handle|apps/desktop/src/main/services/secrets.ts:132|apps/desktop/src/preload/index.ts:793|
|secrets:delete|handle|apps/desktop/src/main/services/secrets.ts:137|apps/desktop/src/preload/index.ts:795|
|secrets:list|handle|apps/desktop/src/main/services/secrets.ts:143|apps/desktop/src/preload/index.ts:796|
|secrets:available|handle|apps/desktop/src/main/services/secrets.ts:149|apps/desktop/src/preload/index.ts:797|
|skills:list|handle|apps/desktop/src/main/services/skills.ts:753|apps/desktop/src/preload/index.ts:689|
|skills:get|handle|apps/desktop/src/main/services/skills.ts:754|apps/desktop/src/preload/index.ts:690|
|skills:remove|handle|apps/desktop/src/main/services/skills.ts:755|apps/desktop/src/preload/index.ts:693|
|skills:set-enabled|handle|apps/desktop/src/main/services/skills.ts:756|apps/desktop/src/preload/index.ts:695|
|skills:set-roles|handle|apps/desktop/src/main/services/skills.ts:761|apps/desktop/src/preload/index.ts:698|
|skills:import|handle|apps/desktop/src/main/services/skills.ts:767|apps/desktop/src/preload/index.ts:691|
|tasks:list|handle|apps/desktop/src/main/services/tasks.ts:520|apps/desktop/src/preload/index.ts:1043|
|tasks:get|handle|apps/desktop/src/main/services/tasks.ts:521|apps/desktop/src/preload/index.ts:1044|
|tasks:create|handle|apps/desktop/src/main/services/tasks.ts:523|apps/desktop/src/preload/index.ts:1046|
|tasks:update|handle|apps/desktop/src/main/services/tasks.ts:526|apps/desktop/src/preload/index.ts:1048|
|tasks:delete|handle|apps/desktop/src/main/services/tasks.ts:529|apps/desktop/src/preload/index.ts:1049|
|tasks:set-status|handle|apps/desktop/src/main/services/tasks.ts:533|apps/desktop/src/preload/index.ts:1051|
|tasks:preview|handle|apps/desktop/src/main/services/tasks.ts:537|apps/desktop/src/preload/index.ts:1071|
|tasks:run-now|handle|apps/desktop/src/main/services/tasks.ts:542|apps/desktop/src/preload/index.ts:1060|
|terminal:list-shells|handle|apps/desktop/src/main/services/terminal.ts:87|apps/desktop/src/preload/index.ts:942|
|terminal:create|handle|apps/desktop/src/main/services/terminal.ts:91|apps/desktop/src/preload/index.ts:944|
|terminal:input|on|apps/desktop/src/main/services/terminal.ts:100|apps/desktop/src/preload/index.ts:945|
|terminal:resize|on|apps/desktop/src/main/services/terminal.ts:104|apps/desktop/src/preload/index.ts:947|
|terminal:dispose|on|apps/desktop/src/main/services/terminal.ts:108|apps/desktop/src/preload/index.ts:948|
|update:get-state|handle|apps/desktop/src/main/services/updater.ts:270|apps/desktop/src/preload/index.ts:1177|
|update:check|handle|apps/desktop/src/main/services/updater.ts:271|apps/desktop/src/preload/index.ts:1178|
|update:download|handle|apps/desktop/src/main/services/updater.ts:272|apps/desktop/src/preload/index.ts:1179|
|update:install|handle|apps/desktop/src/main/services/updater.ts:273|apps/desktop/src/preload/index.ts:1180|
|fs:open-folder|handle|apps/desktop/src/main/services/workspace.ts:43|apps/desktop/src/preload/index.ts:642|
|fs:reveal-folder|handle|apps/desktop/src/main/services/workspace.ts:55|apps/desktop/src/preload/index.ts:645|
|fs:read-dir|handle|apps/desktop/src/main/services/workspace.ts:64|apps/desktop/src/preload/index.ts:646|
|fs:read-file|handle|apps/desktop/src/main/services/workspace.ts:82|apps/desktop/src/preload/index.ts:647|
|fs:write-file|handle|apps/desktop/src/main/services/workspace.ts:92|apps/desktop/src/preload/index.ts:649|

## 未完成清单

- A：非 IPC 全集穷尽性及绝大多数功能的真实交互验证；不能发布旧稿 29/5/45 为可信计数。
- B：本轮仅完成会话文字草稿隔离；附件经真实 QDropEvent、切换会话和源文件读回复验通过。缺口优先继续核对筛选按钮、未读状态、指令与提及、角色编辑真实入口。
- C：见 out/feature-review 下原版 safeStorage 真实运行日志；成功 API 不等于同状态像素闭环。取整实验须独立复跑。
- D：全量回归结果见 out/feature-review/pytest.log，最终结果另附交付记录。


## 本轮新实现和真实成功态

- `fdb229918ee4e70a5372962b057c569906c42166`：QML 文字和待发附件按会话保留。真实键盘、行点击与拖放验证见 `out/feature-review/drafts.json`；暗亮截图 `drafts-dark.png` / `drafts-light.png`。修前失败在 `draft-before.log`，修后成功在 `draft-attachments-final.log`。
- 推送原文：`out/feature-review/push-drafts.log`：`b25dc1b..fdb2299 develop -> develop`，远端回读 fdb229918ee4e70a5372962b057c569906c42166。
- C9：真实私有 D-Bus + GNOME Secret Service + Electron `--password-store=gnome-libsecret`，API 返回 available=true、saved.ok=true、has=true；真实鼠标聚焦密码框及 CDP 输入后，dark/light 均 Saved=true。Qt 也经真实键盘及 OS 读回复验 Saved/Configured。
- 同尺寸 1280×820，未缩放并排图：`out/feature-review/compare-saved-dark.png` / `compare-saved-light.png`。两端都是真实 Saved，但命令字段 fixture 与滚动位置并不相同，**不得作为全页面同数据像素验收**。OS 成功态环境阻塞已排除，严格同数据像素闭环仍未完成。
- 原始失败保留：`electron-os-session.log` 中 xauth 不在 PATH；`electron-ui-session.log` 中 Configured placeholder 导致探针定位失败。最终日志 `electron-qt-ui-final.log`；系统 D-Bus 警告仍有，但私有 session bus 实际可用。
- C10：32 条真实合成采样重新确认单通道差异，详情追加到 `extensions-rounding.md`。正文与阴影相位未复跑。
- 工作期间新出现 `scripts/parity/electron_safe_storage_session.py`，不在入口 status 中，也不是本次执行创建的文件。保留、不覆盖、不纳入本次提交。

## 回归中发现并修复的问题

- 首轮：`3 failed, 1435 passed, 9 skipped in 407.71s`，原始输出 `out/feature-review/pytest.log`。
- `ad72344670b3c161effd4e8d42a5fbe6b60364c0`：侧栏未收起时 HoverHandler 也置 sidePeek，z=20 截获设置确认框背板点击。限制真实 peek 的生效条件，暗亮真实鼠标取消均通过，截图 `provider-confirm-{dark,light}.png` / `provider-dismissed-{dark,light}.png`；focused `4 passed`。
- `1ebe26a498bc787b605debf2ba28fbd6d26cffc6`：两条滚动条测试停了 ticker 却未关闭窗口，后续 ApplicationShortcut 竞争、目录框数量多两个。只增加 window.close/engine.deleteLater 四行，零断言变更。组合回归 `53 passed in 36.91s`。
- 完整原始搜索输出：`out/feature-review/ipc-raw.txt`、`non-ipc-raw.txt`、`platform-features.txt`。原版确有网络代理路由，旧“不适用”不能接受。

## 最终全量回归

```sh
AI_UPPER_HOME=/tmp/ai-upper-feature-review-final \
TMPDIR=$PWD/.tmp/feature-review \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests -q \
--basetemp=$PWD/.tmp/feature-review/final
```

真实输出：`1438 passed, 9 skipped in 411.23s (0:06:51)`，0 failed。
原始日志 `out/feature-review/pytest-final.log`。既有断言 AST 与 b25dc1b 完全相同，验证记录 `assertions-preserved.txt`。机器清单计数校验 `inventory-validation.txt`。

最终状态：**本轮整体目标未完成**。A 仍有 59 项未判定、非 IPC 全集穷尽性未证实；B 仍有大量功能未补齐；C9 严格同数据像素对照未完成；C10 正文与阴影相位复跑未完成。测试通过只说明本次回归通过，不代表移植完整或视觉一致。
