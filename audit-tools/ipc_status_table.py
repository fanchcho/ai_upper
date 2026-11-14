"""158 条 IPC 通道的移植版判定表（`make_ipc_ledger.py` 的唯一数据源）。

约定：
- `impl` 里的 `{bridge}` 由生成器替换成 `app/src/mvvm/webui/bridge.py:<注册行号>`，
  行号是**生成时现查**的，避免手写行号漂移；不指向桥的写死具体位置。
- `result` 必须以 通过 / 已知差异 / 不适用 / 未实现 之一开头，后面写清依据。
- 每条的文字必须自证，不许「同上」。
"""
from __future__ import annotations

BRIDGE = "{bridge}"

T_UNKNOWN = "单测 tests/test_web_shell_modules.py::test_bridge_unknown_channel_is_explicit_not_silent"
T_REGISTERED = "单测 tests/test_web_shell_modules.py::test_bridge_registers_contract_channels"
T_WINDOW = "单测 tests/test_web_shell_modules.py::test_window_actions_are_wired_or_raise_not_fake_success"
T_CLIP = "单测 tests/test_web_shell_modules.py::test_clipboard_round_trip_uses_qt_clipboard"
T_BROWSER = "单测 tests/test_web_shell_modules.py::test_bridge_browser_state_carries_every_contract_key"
T_SKILLS = "单测 tests/test_web_shell_modules.py::test_bridge_skills_list_serves_builtins"
T_SHELL = "单测 tests/test_web_shell_modules.py::test_shell_window_builds_with_overlay"
T_NONE = "无（未实现，不计入通过数）"

STATUS: dict[str, tuple[str, str, str]] = {}


def _put(channel: str, impl: str, test: str, result: str) -> None:
    STATUS[channel] = (impl, test, result)


# ── window（5）────────────────────────────────────────────────────────────
_put("window:set-overlay", BRIDGE,
     "单测 tests/test_web_shell_modules.py::test_overlay_dark_theme_switches_background",
     "通过 —— 深色主题 symbolColor(#e4e4e7) 把叠加层底色切到 OVERLAY_BG_DARK，浅色回 OVERLAY_BG")
_put("window:minimize", BRIDGE, T_WINDOW,
     "通过 —— 调视图注入的 showMinimized；未注入时抛「窗口能力未接线：minimize」")
_put("window:toggle-maximize", BRIDGE, T_WINDOW,
     "通过 —— 按 isMaximized 在 showMaximized/showNormal 间切换；未注入时显式抛错")
_put("window:close", BRIDGE, T_WINDOW,
     "通过 —— 调 QMainWindow.close（触发 closeEvent 与退出流程）；未注入时显式抛错")
_put("window:is-fullscreen", BRIDGE, T_WINDOW,
     "通过 —— 读 windowState() 的 FullScreen 位；未注入时显式抛错")

# ── app（1）──────────────────────────────────────────────────────────────
_put("app:get-platform", BRIDGE, T_REGISTERED,
     "通过 —— 恒回 'linux'，与 shim 注入的 __PLATFORM__ 同值（原版读 process.platform）")

# ── fs（9）：全部未实现，逐条写清缺什么 ───────────────────────────────────
_FS_GAPS = {
    "fs:paste-attachment": "未实现 —— 需要把渲染层 DataTransfer 里的 File 转成临时文件路径，QtWebEngine 的 paste/drop 事件尚无 Python 接收端",
    "fs:dropped-entries": "未实现 —— 拖拽目录展开依赖 Electron webUtils.getPathForFile，QtWebEngine 不暴露拖入文件的绝对路径",
    "fs:attachment-image": "未实现 —— 按 路径/内联 data 读回附件图片并做 MIME 判定，读取层未接",
    "fs:pick-attachments": "未实现 —— 需要 QFileDialog 多选（图片/文档过滤）并把绝对路径数组回给渲染层",
    "fs:open-folder": "未实现 —— 需要 QFileDialog.getExistingDirectory 选工作区根目录",
    "fs:reveal-folder": "未实现 —— Linux 侧需调 xdg-open 打开父目录并选中条目，未接入",
    "fs:read-dir": "未实现 —— 目录列举（跳过 node_modules/.git、隐藏项标记、符号链接判定）未实现",
    "fs:read-file": "未实现 —— >2MB 返回 tooLarge、前 8000 字节含 0 返回 binary 的判定未实现",
    "fs:write-file": "未实现 —— 写入前不做父目录预创建的原版语义未实现",
}
for _ch, _why in _FS_GAPS.items():
    _put(_ch, "—", T_NONE, _why)

# ── browser（16）─────────────────────────────────────────────────────────
_put("browser:state", BRIDGE, T_BROWSER,
     "已知差异 —— 回空态 open:false/pinned:false/tabs:[]/handoff:{}；内置浏览器（Electron BrowserView）未移植，键集照契约给全以免白屏")
_put("browser:ready", BRIDGE, T_BROWSER,
     "已知差异 —— 与 browser:state 同一空态；原版此处还标记视图握手完成，本工程无第二视图可握手")
_put("browser:preview-pinned", BRIDGE, T_REGISTERED,
     "已知差异 —— 当前恒回 {ok:true} 但无视图可钉，属占位式成功；移植浏览器面板时必须改为真实实现（已列入未实现清单）")
_BROWSER_GAPS = {
    "browser:open": "未实现 —— 需要新建独立 WebContents 与浏览器面板 UI，本工程只有聊天页一个 QWebEngineView",
    "browser:dock": "未实现 —— 浏览器停靠/浮动的布局切换依赖原版 BrowserView 定位，未移植",
    "browser:close-session": "未实现 —— 按会话关闭浏览器标签需要标签注册表，未移植",
    "browser:live-start": "未实现 —— 实时帧推流走 Electron capturePage 定时器，QtWebEngine 无对位接口",
    "browser:live-stop": "未实现 —— 与 live-start 成对的推流停止，同样缺帧源",
    "browser:pin": "未实现 —— 钉住窗口（alwaysOnTop 子窗口）未移植",
    "browser:activate": "未实现 —— 激活指定标签需要标签注册表与视图切换，未移植",
    "browser:close-tab": "未实现 —— 关闭标签与状态广播未移植",
    "browser:nav": "未实现 —— 前进/后退/刷新/停止需作用于浏览器视图的 navigation controller",
    "browser:menu": "未实现 —— 右键菜单需要在浏览器视图上构造原生菜单，未移植",
    "browser:thumbnail": "未实现 —— 标签缩略图来自 capturePage，QtWebEngine 无对位接口",
    "browser:handoff": "未实现 —— 浏览器把控制权交还代理需双向通道，未移植",
    "browser:stop": "未实现 —— 停止某会话的浏览器操作需运行期注册表，未移植",
}
for _ch, _why in _BROWSER_GAPS.items():
    _put(_ch, "—", T_NONE, _why)

# ── chat（31）────────────────────────────────────────────────────────────
_put("chat:send", "—", T_NONE,
     "未实现 —— 回合引擎（ChatViewModel）存在但未接进桥：缺 turnId↔会话注册表与 chat:event 转换层")
_put("chat:insert", "—", T_NONE,
     "未实现 —— 需要 pendingInserts 队列与 insertableTurns 判定（定时任务/压缩/回滚期间不可插入）")
_put("chat:withdraw-inserts", "—", T_NONE,
     "未实现 —— 需要与 insert 同一份 pendingInserts 队列，取走即清空并推 inserts{pending:[]}")
_put("chat:compact", "—", T_NONE,
     "未实现 —— ChatViewModel.compact_now 存在但未接桥，缺后台线程与 compacting/compacted 事件推送")
_put("chat:create-session", "—", T_NONE,
     "未实现 —— store.ensure_session 存在但未注册通道，缺「立即落盘使空会话跨重启存活」的 save 调用")
_put("chat:set-model", "—", T_NONE,
     "未实现 —— 需要会话级写模型并落盘的 store 方法（当前 ensure_session 只能随首发覆盖）")
_put("chat:set-effort", "—", T_NONE,
     "未实现 —— 需要写 session.effort 的 store 方法并校验合法档位")
_put("chat:set-focus", "—", T_NONE,
     "未实现 —— 需要写 session.focusRoot 的 store 方法（原版恒回 ok:true）")
_put("chat:rename-session", "—", T_NONE,
     "未实现 —— store.rename_session 存在，但通道未注册、未接「空标题恢复自动标题」语义")
_put("chat:set-archived", "—", T_NONE,
     "未实现 —— store.set_archived 存在但未注册；原版忙碌会话拒绝归档的判定也需接")
_put("chat:list-sessions", BRIDGE, T_REGISTERED,
     "通过 —— 读 visible_sessions()（排除归档/子会话/未落盘惰性会话），字段与 ChatSessionMeta 一致")
_put("chat:load-session", BRIDGE, T_REGISTERED,
     "通过 —— display_messages 复刻 toDisplayMessages 的合并与 tool_result 回填规则")
_put("chat:attachment-image", "—", T_NONE,
     "未实现 —— 需解析 msgIndex:partIndex 指纹并在会话图片段里取原图；display_messages 也尚未重建图片块")
_put("chat:attach-session", BRIDGE, T_REGISTERED,
     "已知差异 —— 历史消息已真实返回，但 turnId 恒 null（无后台回合可接）；接入回合引擎后改为真实 turnId")
_put("chat:resolve-proposal", "—", T_NONE,
     "未实现 —— 需要提案边车（session.proposals）写入与 card_resolved 事件推送")
_put("chat:resolve-autotask", "—", T_NONE,
     "未实现 —— 需要自动任务边车（session.autotasks）与卡片状态落盘")
_put("chat:delete-session", "—", T_NONE,
     "未实现 —— store.delete_session 存在但未注册；还需停掉该会话进行中的回合")
_put("chat:remove-member", "—", T_NONE,
     "未实现 —— 群成员会话（parentId 链路）未移植，无成员注册表可删")
_put("chat:abort", "—", T_NONE,
     "未实现 —— 需要 turnId→ChatViewModel 注册表，再调 VM.cancel()；当前无进行中回合可中止")
_put("chat:stop-subagent", "—", T_NONE,
     "未实现 —— 子智能体（子会话）未移植，无按 toolUseId 停止的入口")
_put("chat:reset", "—", T_NONE,
     "未实现 —— 需要清空会话消息并保留会话记录的 store 方法（原版恒回 ok:true）")
_put("chat:delete-turns", "—", T_NONE,
     "未实现 —— 需要按轮删消息并返回重建后的 DisplayMessage[]")
_put("chat:todos", "—", T_NONE,
     "未实现 —— ChatViewModel.todos 存在但未注册；需回 {active} 形状")
_put("chat:todo-cancel", "—", T_NONE,
     "未实现 —— ChatViewModel.cancel_todos 存在但未注册；需回最新清单状态")
_put("chat:rewind-list", "—", T_NONE,
     "未实现 —— 回滚点（checkpoints）只读不写，尚无 checkpoint 生成逻辑")
_put("chat:rewind-preview", "—", T_NONE,
     "未实现 —— 预览回滚需比较工作区文件差异，依赖 checkpoint 快照，未移植")
_put("chat:rewind-apply", "—", T_NONE,
     "未实现 —— 应用回滚会改写会话与工作区文件，依赖 checkpoint 快照，未移植")
_put("chat:rewind-undo", "—", T_NONE,
     "未实现 —— 撤销回滚依赖回滚前快照，未移植")
_put("chat:ask-response", "—", T_NONE,
     "未实现 —— 需要交互请求注册表（ask 边车）与 interaction_resolved 事件；工具层交互目前走 Qt 对话框")
_put("chat:plan-response", "—", T_NONE,
     "未实现 —— 计划审批同理，需要 plan 边车与先到者生效语义")
_put("chat:mount-response", "—", T_NONE,
     "未实现 —— 工作区挂载审批同理，需要 mount_request 事件链路")

# ── config（3）───────────────────────────────────────────────────────────
_put("config:get-sync", "app/assets/renderer/shim.js:121",
     "单测 tests/test_web_shell_modules.py::test_shell_shim_source_substitutes_placeholders",
     "通过 —— 原版是 ipcMain.on + sendSync 同步取配置；本工程由 shim 直接返回注入的 __CONFIG_JSON__，无跨进程往返")
_put("config:get", BRIDGE, T_REGISTERED,
     "通过 —— 返回 SettingsService 的配置深拷贝（get_config_sync）")
_put("config:set", BRIDGE, T_REGISTERED,
     "通过 —— 顶层浅合并、None 删键、落盘失败抛出（不静默）")

# ── clipboard（2）────────────────────────────────────────────────────────
_put("clipboard:read-text", BRIDGE, T_CLIP,
     "通过 —— 走 QClipboard.text()，粘贴回环用例验证读回写入值")
_put("clipboard:write-text", BRIDGE, T_CLIP,
     "通过 —— 非字符串入参按空串处理（与原版 typeof 判定一致）")

# ── deliverables（4）─────────────────────────────────────────────────────
for _ch, _why in {
    "deliverables:inspect": "未实现 —— 交付物清单（本轮产出的文件卡片）未移植，无 toolUseId→文件映射",
    "deliverables:thumbnail": "未实现 —— 缩略图生成依赖图像解码与缓存目录，未移植",
    "deliverables:open": "未实现 —— 需用系统默认程序打开文件（QDesktopServices），未接入",
    "deliverables:reveal": "未实现 —— 需在文件管理器里定位文件，Linux 侧未接入",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── git（24）─────────────────────────────────────────────────────────────
for _ch, _why in {
    "git:available": "未实现 —— 检测 git 可执行文件与版本，git 服务层未移植",
    "git:status": "未实现 —— porcelain 解析（暂存/未暂存/未跟踪分栏）未实现",
    "git:diff": "未实现 —— 单文件 diff（含 staged 变体）未实现",
    "git:stage": "未实现 —— 按路径 add 未实现",
    "git:unstage": "未实现 —— reset HEAD 语义未实现",
    "git:discard": "未实现 —— 丢弃已跟踪修改与删除未跟踪文件是高危操作，未实现",
    "git:commit": "未实现 —— 提交并返回 oid 未实现",
    "git:set-config": "未实现 —— user.name/email 写入（含 --global）未实现",
    "git:branches": "未实现 —— 本地/远端分支列举未实现",
    "git:checkout": "未实现 —— 切换分支（含失败分类）未实现",
    "git:create-branch": "未实现 —— 建分支并可选中切换，未实现",
    "git:checkout-remote": "未实现 —— 检出远端分支并建跟踪分支，未实现",
    "git:merge": "未实现 —— 合并且返回冲突分类，未实现",
    "git:merge-abort": "未实现 —— 中止合并，未实现",
    "git:delete-branch": "未实现 —— 删分支（含 force）未实现",
    "git:rename-branch": "未实现 —— 重命名分支未实现",
    "git:delete-remote-branch": "未实现 —— 删远端分支（safeRef + listRemotes 校验）未实现",
    "git:log": "未实现 —— 提交列表（depth 1..500）未实现",
    "git:init": "未实现 —— 初始化仓库未实现",
    "git:fetch": "未实现 —— fetch --prune 未实现",
    "git:pull": "未实现 —— pull 未实现",
    "git:push": "未实现 —— push / push -u 未实现",
    "git:generate-commit-message": "未实现 —— 需 diff 摘要 + 模型流式生成 + 中断，未实现",
    "git:cancel-commit-message": "未实现 —— 需进行中生成请求注册表，未实现",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── mcp（9）──────────────────────────────────────────────────────────────
for _ch, _why in {
    "mcp:list": "未实现 —— mcp.json 配置读写与运行期状态（连接/工具数）未移植",
    "mcp:get": "未实现 —— 单条 MCP 配置读取未移植",
    "mcp:upsert": "未实现 —— 名称去空白、slug 生成唯一 id 的写路径未移植",
    "mcp:remove": "未实现 —— 撤运行态 + 删配置 + 清 mcp:<id>: 前缀密钥未移植",
    "mcp:set-roles": "未实现 —— 角色白名单写入未移植",
    "mcp:set-enabled": "未实现 —— 启停写入并触发 reconcile 未移植",
    "mcp:retry": "未实现 —— 重连并回最新视图未移植",
    "mcp:set-secret": "未实现 —— 写 mcp:<id>:<field> 密钥未移植（密钥库本身可用）",
    "mcp:has-secret": "未实现 —— 查 mcp:<id>:<field> 密钥存在性未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── memory（4）───────────────────────────────────────────────────────────
for _ch, _why in {
    "memory:list": "未实现 —— 记忆文件（全局/项目作用域）读写服务未移植",
    "memory:write": "未实现 —— 去重/字数上限/总量预算判定未实现",
    "memory:delete": "未实现 —— 按 id 删除记忆未实现",
    "memory:clear": "未实现 —— 清空作用域记忆未实现",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── personas（8）─────────────────────────────────────────────────────────
_put("personas:list", BRIDGE, T_REGISTERED,
     "通过 —— PersonaStore.list_personas 返回 frontmatter 解析后的角色列表")
_put("personas:get", BRIDGE, T_REGISTERED,
     "通过 —— 按 id 取角色；不存在返回 None（与原版 null 对应）")
_put("personas:upsert", "—", T_NONE,
     "未实现 —— PersonaStore 只读（ALLOWED_WRITES_NOTE 明示写路径未接入），upsert/重名 id 生成未实现")
_put("personas:remove", "—", T_NONE,
     "未实现 —— 删角色文件与索引维护未实现（原版恒回 ok:true）")
_put("personas:set-enabled", "—", T_NONE,
     "未实现 —— 启用位写侧车未实现")
_put("personas:reorder", "—", T_NONE,
     "未实现 —— 排序写侧车未实现")
_put("personas:set-avatar-image", "—", T_NONE,
     "未实现 —— 头像 MIME 白名单（webp/png/jpeg）与 1..2MB 限制未实现")
_put("personas:clear-avatar-image", "—", T_NONE,
     "未实现 —— 清空角色头像未实现")

# ── profile（3）─────────────────────────────────────────────────────────
_put("profile:get", BRIDGE, T_REGISTERED,
     "通过 —— 返回 Humation 头像 spec，缺省为 DEFAULT_USER_AVATAR（与原版首帧一致）")
_put("profile:set-avatar", "—", T_NONE,
     "未实现 —— 写 config.profile.avatar，spec >4096 存空串的语义未实现")
_put("profile:set-avatar-image", "—", T_NONE,
     "未实现 —— 用户头像图片落盘与 MIME 校验未实现")

# ── provider（1）─────────────────────────────────────────────────────────
_put("provider:list-models", "—", T_NONE,
     "未实现 —— ModelGateway.list_models 已存在（15s 超时、失败回 ok:false），但通道未注册")

# ── remote（10）──────────────────────────────────────────────────────────
_put("remote:get-state", BRIDGE, T_REGISTERED,
     "已知差异 —— 回 {bots:[], enabled:false}，比契约多一个 enabled 键；远端接入（手机端）未移植，空态即为当前事实")
for _ch, _why in {
    "remote:scan-start": "未实现 —— 局域网扫码配对未移植",
    "remote:scan-cancel": "未实现 —— 扫描取消未移植",
    "remote:set-enabled": "未实现 —— 远端机器人启停未移植",
    "remote:set-reply-mode": "未实现 —— 回复模式设置未移植",
    "remote:set-scope": "未实现 —— 作用域设置未移植",
    "remote:delete-bot": "未实现 —— 删除远端机器人未移植",
    "remote:pair-code": "未实现 —— 配对码生成未移植",
    "remote:pair-cancel": "未实现 —— 取消配对未移植",
    "remote:remove-user": "未实现 —— 移除已授权用户未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── secrets（5）──────────────────────────────────────────────────────────
_put("secrets:set", "—", T_NONE,
     "未实现 —— SecretsVault.set_secret 存在（空串=删除、后端不可用回 ok:false），但通道未注册")
_put("secrets:has", BRIDGE, T_REGISTERED,
     "通过 —— has_secret(providerId)；无密钥库时回 false")
_put("secrets:delete", "—", T_NONE,
     "未实现 —— SecretsVault.delete_secret 存在（回 {ok,available}），但通道未注册")
_put("secrets:list", BRIDGE, T_REGISTERED,
     "通过 —— list_keys() 读 secret-names.json 侧车，只回键名不回密钥")
_put("secrets:available", BRIDGE, T_REGISTERED,
     "通过 —— describe_backend()/available()：keyring 或 file 后端为真，none 为假")

# ── skills（6）───────────────────────────────────────────────────────────
_put("skills:list", BRIDGE, T_SKILLS,
     "通过 —— 三条内置技能 create-skill/create-agent/create-mcp 顺序稳定")
_put("skills:get", BRIDGE, T_SKILLS,
     "通过 —— 按 id 取技能正文；不存在返回 None")
_put("skills:remove", "—", T_NONE,
     "未实现 —— SkillStore 只读且内置技能须回 {ok:false}，写路径未接入")
_put("skills:set-enabled", "—", T_NONE,
     "未实现 —— 技能启用位写侧车未实现")
_put("skills:set-roles", "—", T_NONE,
     "未实现 —— 技能角色白名单写入未实现")
_put("skills:import", "—", T_NONE,
     "未实现 —— 从文件/目录导入 SKILL.md 并解析 frontmatter 未实现")

# ── tasks（8）────────────────────────────────────────────────────────────
for _ch, _why in {
    "tasks:list": "未实现 —— 定时任务调度器（tasks.json + cron 解析）未移植",
    "tasks:get": "未实现 —— 单条任务读取未移植",
    "tasks:create": "未实现 —— 校验 tz/cron/once 并算 nextRun 未移植",
    "tasks:update": "未实现 —— 局部更新且非法 schedule 静默忽略的语义未移植",
    "tasks:delete": "未实现 —— 删任务并清理其会话未移植",
    "tasks:set-status": "未实现 —— active 时清零错误计数并重算 nextRun 未移植",
    "tasks:preview": "未实现 —— cron 描述生成与下次运行时间预览未移植",
    "tasks:run-now": "未实现 —— 立即运行（含已在运行的 already 回报）未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── terminal（5）─────────────────────────────────────────────────────────
for _ch, _why in {
    "terminal:list-shells": "未实现 —— 终端面板（xterm.js + pty）未移植，无 shell 清单",
    "terminal:create": "未实现 —— 需要 pty 主进程与会话 id 注册表",
    "terminal:input": "未实现 —— 这条是 ipcMain.on 单向通道，需要 pty 写入端",
    "terminal:resize": "未实现 —— 需要 pty TIOCSWINSZ 调整",
    "terminal:dispose": "未实现 —— 需要关闭 pty 并清理注册表",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── update（4）───────────────────────────────────────────────────────────
_put("update:get-state", BRIDGE, T_REGISTERED,
     "已知差异 —— 回 {status:'idle'}，契约应为 {phase:'idle'}；自动更新（electron-updater）未移植，字段名待对齐")
for _ch, _why in {
    "update:check": "未实现 —— 检查更新依赖发布源与 electron-updater，未移植",
    "update:download": "未实现 —— 下载更新包未移植",
    "update:install": "未实现 —— 安装并重启未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

assert len(STATUS) == 158, len(STATUS)

EVENT_ROWS = [
    ("chat:event",
     "`{turnId, sessionId, event}`，event 为 camelCase 判别联合（text_delta/tool_call/…/done{stopReason}）",
     "—",
     "未实现 —— 事件推送链尚未建立：DevaBridge.event 无订阅者，ChatViewModel.emit 形状也需转换层"),
    ("chat:sessions-changed",
     "无 payload；会话增删改归档后推送，渲染层据此 refreshSessions",
     "—",
     "未实现 —— 尚无会话写路径触发点，也无 emit_event 的调用方"),
]
