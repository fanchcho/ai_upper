"""158 条 IPC 通道的移植版判定表（`make_ipc_ledger.py` 的唯一数据源）。

约定：
- `impl` 里的 `{bridge}` 由生成器替换成 `app/src/mvvm/webui/bridge.py:<注册行号>`，
  行号是**生成时现查**的（字面量注册与写通道批量循环都认），避免手写行号漂移。
- `result` 必须以 通过 / 已知差异 / 不适用 / 未实现 之一开头，后面写清依据。
- 每条的文字必须自证，不许「同上」。
- 判定口径：`通过` = 通道已注册且行为有可复现的实测依据；`已知差异` = 已注册但语义/形状
  与原版有明确差距；`不适用` = 该通道在本移植的形态下没有对应物；`未实现` = 桥里没有这条
  通道，原因是具体的能力缺口（阻塞）。
"""
from __future__ import annotations

BRIDGE = "{bridge}"

T_UNKNOWN = "单测 tests/test_web_shell_modules.py::test_bridge_unknown_channel_is_explicit_not_silent"
T_REGISTERED = "单测 tests/test_web_shell_modules.py::test_bridge_registers_contract_channels"
T_WINDOW = "单测 tests/test_web_shell_modules.py::test_window_actions_are_wired_or_raise_not_fake_success"
T_CLIP = "单测 tests/test_web_shell_modules.py::test_clipboard_round_trip_uses_qt_clipboard"
T_BROWSER = "单测 tests/test_web_shell_modules.py::test_bridge_browser_state_carries_every_contract_key"
T_BROWSER_SHAPE = "单测 tests/test_web_shell_modules.py::test_browser_ready_and_preview_pinned_follow_contract"
T_SKILLS = "单测 tests/test_web_shell_modules.py::test_bridge_skills_list_serves_builtins"
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
     "通过 —— 读视图注入的 isFullScreen；未注入时显式抛错")

# ── app（1）──────────────────────────────────────────────────────────────
_put("app:get-platform", BRIDGE,
     "单测 tests/test_web_shell_modules.py::test_app_platform_matches_shim",
     "通过 —— 恒回 'linux'，与 shim 注入的 __PLATFORM__ 同值（原版读 process.platform）")

# ── fs（9）：附件与工作区文件，本轮全部接通 ──────────────────────────────
_put("fs:pick-attachments", BRIDGE,
     "单测 tests/test_web_attachments.py::test_pick_attachments_matches_original_shape、"
     "::test_pick_attachments_requires_a_dialog_and_never_fakes_success",
     "通过 —— QFileDialog 多选后按 inspect 判定；超限图片走「只给位置」分支；未注入对话框时抛「未接线」不假装取消")
_put("fs:paste-attachment", BRIDGE,
     "单测 tests/test_web_attachments.py::test_paste_attachment_writes_under_paste_dir_and_dedupes",
     "通过 —— 渲染层 {name,mime,size,data[]} 落盘到粘贴临时目录，sha256 去重；无 data 只判定不写盘")
_put("fs:dropped-entries", BRIDGE,
     "单测 tests/test_web_attachments.py::test_dropped_entries_register_folders_as_roots",
     "通过 —— 目录登记为受信根并回位置、文件按 inspect 判定、取不到路径的条目回 null")
_put("fs:attachment-image", BRIDGE,
     "单测 tests/test_web_attachments.py::test_attachment_image_channel_returns_data_url_only_for_allowed_images",
     "通过 —— 白名单内图片回原图/缩略图 data URI；未授权、非图片、空串、非字符串一律 null")
_put("fs:open-folder", BRIDGE,
     "单测 tests/test_web_attachments.py::test_open_folder_trusts_the_directory",
     "通过 —— getExistingDirectory 选中即 trust_root 并回 {path,name}；取消回 null")
_put("fs:reveal-folder", BRIDGE,
     "单测 tests/test_web_attachments.py::test_reveal_folder_only_accepts_trusted_directories",
     "通过 —— 只接受受信目录，否则 {ok:false}；xdg-open 失败回 {ok:false}（不假成功）")
_put("fs:read-dir", BRIDGE,
     "单测 tests/test_web_attachments.py::test_read_dir_is_guarded_sorted_and_skips_symlinks",
     "通过 —— 过 WorkspaceGuard（越界抛「拒绝访问」）、按名排序、跳过符号链接并标类型")
_put("fs:read-file", BRIDGE,
     "单测 tests/test_web_attachments.py::test_read_file_reports_too_large_and_binary",
     "通过 —— >2MB 回 tooLarge、前 8000 字节含 0 回 binary、否则回 {path,content}")
_put("fs:write-file", BRIDGE,
     "单测 tests/test_web_attachments.py::test_write_file_does_not_create_parent_directories",
     "通过 —— 按原版语义不预建父目录（缺目录抛 FileNotFoundError），成功回 {ok:true}")

# ── browser（16）：只有三条空态通道注册了，其余是真实能力缺口 ────────────
_put("browser:state", BRIDGE, T_BROWSER,
     "已知差异 —— 回空态 open:false/pinned:false/tabs:[]/handoff:{}；内置浏览器（Electron BrowserView）未移植，键集照契约给全以免白屏")
_put("browser:ready", BRIDGE, T_BROWSER_SHAPE,
     "已知差异 —— 与 browser:state 同一空态；原版此处还标记视图握手完成，本工程无第二视图可握手")
_put("browser:preview-pinned", BRIDGE, T_BROWSER_SHAPE,
     "已知差异 —— 恒回 {ok:true} 且不校验标签是否存在（契约允许），但本工程没有可钉的预览视图，属空实现")
_BROWSER_GAPS = {
    "browser:open": "未实现 —— 需要新建独立视图与浏览器面板 UI，本工程只有聊天页一个 QWebEngineView",
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
_put("chat:send", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_send_streams_text_and_finishes_with_done、"
     "tests/test_web_e2e_stream.py::test_chat_send_from_page_streams_reply（真 provider）",
     "通过 —— 同步回 turnId，回合在后台线程跑；turn_start 先行、正文流式、done{stopReason,durationMs} 收尾，用户与助手消息落盘")
_put("chat:abort", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_abort_stops_the_turn_and_reports_aborted",
     "通过 —— 按 turnId 直接作用于本轮取消标记，以 stopReason:'aborted' 收尾，半截正文已落盘；未知 turnId 无副作用仍回 ok")
_put("chat:compact", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_compact_returns_turn_id_and_finishes_with_done",
     "通过 —— 立即回 turnId，后台跑 compact_now，推 compacted{scope:'manual',status} 与 done{end_turn}；会话不存在抛错")
_put("chat:create-session", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_create_session_persists_empty_session",
     "通过 —— ensure_session 后立即 save（空对话跨重启存活）并推 chat:sessions-changed")
_put("chat:set-model", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_set_model_and_effort_and_focus_write_session、"
     "::test_set_model_on_missing_session_reports_false",
     "通过 —— 写会话 modelRef 并落盘；未建档回 {ok:false} 且不动 updatedAt")
_put("chat:set-effort", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_set_effort_illegal_level_is_still_ok",
     "通过 —— 合法档位写 session.effort；非法档位不动但按原版恒回 {ok:true}")
_put("chat:set-focus", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_set_model_and_effort_and_focus_write_session、"
     "::test_list_sessions_trusts_focus_roots",
     "通过 —— 写 session.focusRoot；该根在 chat:list-sessions 时登记为受信根，重启后 fs/git 才不报拒绝访问")
_put("chat:rename-session", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_rename_session_returns_trimmed_title",
     "通过 —— 空白折叠后写标题并推 sessions-changed；空标题回落首条用户消息自动标题；未建档回 null")
_put("chat:set-archived", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_set_archived_toggles_and_hides_from_visible_list",
     "通过 —— 归档后从 visible_sessions 消失、取消归档即回；忙碌会话拒绝归档回 {ok:false}")
_put("chat:delete-session", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_delete_session_removes_file_and_returns_ok",
     "通过 —— 先中止该会话进行中回合再删文件与索引，恒回 {ok:true}")
_put("chat:reset", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_reset_clears_messages",
     "通过 —— 清空 messages 与回合边车并刷新 updatedAt；会话不存在也回 {ok:true}")
_put("chat:delete-turns", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_delete_turns_returns_display_messages",
     "通过 —— 按真实用户轮切分删除，返回重建后的 DisplayMessage[]，并推 todos 事件")
_put("chat:todos", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_todos_returns_active_list_shape",
     "通过 —— 折叠快照日志给出当前清单 {active:{id,title,items,...}}；无清单回 {active:null}")
_put("chat:todo-cancel", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_todo_cancel_marks_list_and_hides_it",
     "通过 —— 不忙时把清单 id 记入 todoCancelled，返回 {active:null}；忙碌时只回当前状态")
_put("chat:list-sessions", BRIDGE, T_REGISTERED,
     "通过 —— 读已落盘会话（排除未 save 的惰性会话），字段与 ChatSessionMeta 一致，并登记各 focusRoot")
_put("chat:load-session", BRIDGE,
     "单测 tests/test_web_attachments.py::test_chat_attachment_image_channel_reads_from_store",
     "通过 —— display_messages 复刻 toDisplayMessages 的合并与 tool_result 回填规则")
_put("chat:attachment-image", BRIDGE,
     "单测 tests/test_web_attachments.py::test_chat_attachment_image_channel_reads_from_store",
     "通过 —— 解析 msgIndex:partIndex:指纹 取原图/缩略图；指纹不符、越界、未知会话一律 null")
_put("chat:attach-session", BRIDGE,
     "单测 tests/test_web_chat_write.py::test_attach_session_reports_running_turn",
     "通过 —— 同一时刻取出历史与进行中回合；有回合时回真实 turnId 与 startedAt，空闲回 null")
_put("chat:insert", "—", T_NONE,
     "未实现 —— 阻塞于回合内插入队列：需要 pendingInserts 与 insertableTurns 判定（定时任务/压缩/回滚期间不可插入），ChatViewModel 尚无该入口")
_put("chat:withdraw-inserts", "—", T_NONE,
     "未实现 —— 阻塞于与 chat:insert 同一份 pendingInserts 队列，队列本身未建立")
_put("chat:resolve-proposal", "—", T_NONE,
     "未实现 —— 阻塞于提案边车（session.proposals）与 card_resolved 事件；渲染层有卡片，宿主侧没有写入端")
_put("chat:resolve-autotask", "—", T_NONE,
     "未实现 —— 阻塞于自动任务边车（session.autotasks）与卡片状态落盘，未移植")
_put("chat:remove-member", "—", T_NONE,
     "未实现 —— 阻塞于群成员会话（parentId 链路）未移植，没有成员注册表可删")
_put("chat:stop-subagent", "—", T_NONE,
     "未实现 —— 阻塞于子智能体（子会话）未移植，没有按 toolUseId 停止的入口")
_put("chat:rewind-list", "—", T_NONE,
     "未实现 —— 阻塞于回滚点（checkpoints）只有读取、没有生成逻辑，清单必为空")
_put("chat:rewind-preview", "—", T_NONE,
     "未实现 —— 阻塞于 checkpoint 快照缺失，无法比较工作区文件差异")
_put("chat:rewind-apply", "—", T_NONE,
     "未实现 —— 阻塞于 checkpoint 快照缺失；该通道会改写会话与工作区文件，不能做半套")
_put("chat:rewind-undo", "—", T_NONE,
     "未实现 —— 阻塞于回滚前快照缺失，撤销无数据可依")
_put("chat:ask-response", "—", T_NONE,
     "未实现 —— 阻塞于交互请求注册表（ask 边车）；工具层 ask_user 目前直接拒绝，没有待答请求可回")
_put("chat:plan-response", "—", T_NONE,
     "未实现 —— 阻塞于计划审批边车与「先到者生效」语义，未移植")
_put("chat:mount-response", "—", T_NONE,
     "未实现 —— 阻塞于工作区挂载卡：本工程改为启动时 DEVA_APP_WORKSPACE 登记受信根，没有运行期挂载请求")

# ── config（3）───────────────────────────────────────────────────────────
_put("config:get-sync", "app/assets/renderer/shim.js:121",
     "单测 tests/test_web_shell_modules.py::test_shell_shim_source_substitutes_placeholders",
     "通过 —— 原版是 ipcMain.on + sendSync 同步取配置；本工程由 shim 直接返回注入的 __CONFIG_JSON__，无跨进程往返")
_put("config:get", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_config_set_merges_top_level_and_persists",
     "通过 —— 返回 SettingsService 的配置深拷贝（get_config_sync），写后读回一致")
_put("config:set", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_config_set_merges_top_level_and_persists、"
     "::test_config_set_none_deletes_key、::test_config_set_rejects_non_object",
     "通过 —— 顶层浅合并、None 删键、非对象入参抛错、落盘失败抛出（不静默）")

# ── clipboard（2）────────────────────────────────────────────────────────
_put("clipboard:read-text", BRIDGE, T_CLIP,
     "通过 —— 走 QClipboard.text()，粘贴回环用例验证读回写入值")
_put("clipboard:write-text", BRIDGE, T_CLIP,
     "通过 —— 非字符串入参按空串处理（与原版 typeof 判定一致）")

# ── deliverables（4）─────────────────────────────────────────────────────
for _ch, _why in {
    "deliverables:inspect": "未实现 —— 阻塞于交付物清单（本轮产出的文件卡片）未移植，没有 toolUseId→文件映射表",
    "deliverables:thumbnail": "未实现 —— 阻塞于交付物缩略图生成与缓存目录，未移植",
    "deliverables:open": "未实现 —— 阻塞于系统默认程序打开文件（QDesktopServices）未接入交付物链路",
    "deliverables:reveal": "未实现 —— 阻塞于在文件管理器里定位交付物，未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── git（24）─────────────────────────────────────────────────────────────
for _ch, _why in {
    "git:available": "未实现 —— 阻塞于 git 服务层未移植（检测可执行文件与版本）",
    "git:status": "未实现 —— 阻塞于 git 服务层未移植（porcelain 解析与三栏分组）",
    "git:diff": "未实现 —— 阻塞于 git 服务层未移植（单文件 diff 与 staged 变体）",
    "git:stage": "未实现 —— 阻塞于 git 服务层未移植（按路径 add）",
    "git:unstage": "未实现 —— 阻塞于 git 服务层未移植（reset HEAD 语义）",
    "git:discard": "未实现 —— 阻塞于 git 服务层未移植；该操作会丢改动，不能做半套",
    "git:commit": "未实现 —— 阻塞于 git 服务层未移植（提交并回 oid）",
    "git:set-config": "未实现 —— 阻塞于 git 服务层未移植（user.name/email 写入）",
    "git:branches": "未实现 —— 阻塞于 git 服务层未移植（本地/远端分支列举）",
    "git:checkout": "未实现 —— 阻塞于 git 服务层未移植（切换分支与失败分类）",
    "git:create-branch": "未实现 —— 阻塞于 git 服务层未移植（建分支并可选中切换）",
    "git:checkout-remote": "未实现 —— 阻塞于 git 服务层未移植（检出远端并建跟踪分支）",
    "git:merge": "未实现 —— 阻塞于 git 服务层未移植（合并且返回冲突分类）",
    "git:merge-abort": "未实现 —— 阻塞于 git 服务层未移植（中止合并）",
    "git:delete-branch": "未实现 —— 阻塞于 git 服务层未移植（删分支含 force）",
    "git:rename-branch": "未实现 —— 阻塞于 git 服务层未移植（重命名分支）",
    "git:delete-remote-branch": "未实现 —— 阻塞于 git 服务层未移植（远端分支删除与 safeRef 校验）",
    "git:log": "未实现 —— 阻塞于 git 服务层未移植（提交列表 depth 1..500）",
    "git:init": "未实现 —— 阻塞于 git 服务层未移植（初始化仓库）",
    "git:fetch": "未实现 —— 阻塞于 git 服务层未移植（fetch --prune）",
    "git:pull": "未实现 —— 阻塞于 git 服务层未移植（pull）",
    "git:push": "未实现 —— 阻塞于 git 服务层未移植（push / push -u）",
    "git:generate-commit-message": "未实现 —— 阻塞于 diff 摘要 + 模型流式生成 + 中断链路，均未移植",
    "git:cancel-commit-message": "未实现 —— 阻塞于进行中生成请求注册表，生成链路本身未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── mcp（9）──────────────────────────────────────────────────────────────
for _ch, _why in {
    "mcp:list": "未实现 —— 阻塞于 mcp.json 配置读写与运行期连接状态，未移植",
    "mcp:get": "未实现 —— 阻塞于单条 MCP 配置读取，未移植",
    "mcp:upsert": "未实现 —— 阻塞于名称去空白、slug 生成唯一 id 的写路径，未移植",
    "mcp:remove": "未实现 —— 阻塞于撤运行态 + 删配置 + 清 mcp:<id>: 前缀密钥，未移植",
    "mcp:set-roles": "未实现 —— 阻塞于角色白名单写入，未移植",
    "mcp:set-enabled": "未实现 —— 阻塞于启停写入并触发 reconcile，未移植",
    "mcp:retry": "未实现 —— 阻塞于重连并回最新视图，未移植",
    "mcp:set-secret": "未实现 —— 阻塞于 mcp:<id>:<field> 密钥写入（密钥库本身可用，缺 MCP 配置层）",
    "mcp:has-secret": "未实现 —— 阻塞于 mcp:<id>:<field> 密钥存在性查询，缺 MCP 配置层",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── memory（4）───────────────────────────────────────────────────────────
for _ch, _why in {
    "memory:list": "未实现 —— 阻塞于记忆文件（全局/项目作用域）读写服务，未移植",
    "memory:write": "未实现 —— 阻塞于去重、字数上限与总量预算判定，未移植",
    "memory:delete": "未实现 —— 阻塞于按 id 删除记忆，未移植",
    "memory:clear": "未实现 —— 阻塞于清空作用域记忆，未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── personas（8）─────────────────────────────────────────────────────────
_put("personas:list", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_persona_upsert_creates_then_overwrites",
     "通过 —— PersonaStore.list_personas 返回 frontmatter 解析后的列表，含启用位、排序与 avatarImage")
_put("personas:get", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_personas_get_returns_record_or_null",
     "通过 —— 按 id 取角色（带 avatarImage）；不存在或非法 id 回 null")
_put("personas:upsert", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_persona_upsert_creates_then_overwrites、"
     "::test_persona_upsert_blank_name_falls_back",
     "通过 —— 有 id 覆盖、无 id 生成安全 slug；空名回落 id；写 config.json 启用位")
_put("personas:remove", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_persona_remove_is_idempotent_and_cleans_config",
     "通过 —— 删角色文件并清 config 里的启用位/排序；不存在也回 {ok:true}")
_put("personas:set-enabled", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_persona_set_enabled_and_reorder",
     "通过 —— 写启用位并落盘，list 立刻反映")
_put("personas:reorder", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_persona_set_enabled_and_reorder",
     "通过 —— 按传入 id 序列写排序，list 顺序随之改变")
_put("personas:set-avatar-image", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_persona_avatar_round_trip、"
     "::test_persona_avatar_rejects_bad_payload",
     "通过 —— data URI 落盘为 avatars/<id>.png 并回读；非 data URI 或非法 id 回空串")
_put("personas:clear-avatar-image", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_persona_avatar_round_trip",
     "通过 —— 删头像文件并回 {ok:true}")

# ── profile（3）─────────────────────────────────────────────────────────
_put("profile:get", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_profile_get_returns_default_avatar",
     "通过 —— 返回 Humation 头像 spec，缺省为 DEFAULT_USER_AVATAR（与原版首帧一致）")
_put("profile:set-avatar", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_profile_set_avatar_round_trip、"
     "::test_profile_set_avatar_too_long_clears",
     "通过 —— 写 config.profile.avatar；超 4096 字节视为清除，回落默认头像")
_put("profile:set-avatar-image", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_profile_avatar_image_round_trip",
     "通过 —— data URI 落盘 profile/avatar.png 并回读；空串删文件并回空串")

# ── provider（1）─────────────────────────────────────────────────────────
_put("provider:list-models", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_list_models_returns_sorted_ids、"
     "::test_list_models_failure_is_reported_not_faked",
     "通过 —— 异步通道（最长 15s）在后台线程跑探针，经 finish 回 {ok,models?,kind?,message?}；失败回 ok:false 不假成功")

# ── remote（10）──────────────────────────────────────────────────────────
_put("remote:get-state", BRIDGE,
     "单测 tests/test_web_shell_modules.py::test_remote_state_is_bots_only",
     "已知差异 —— 形状已与契约对齐（只回 {bots:[]}）；远端接入（飞书/Telegram 机器人）未移植，空清单即当前事实")
for _ch, _why in {
    "remote:scan-start": "未实现 —— 阻塞于局域网扫码配对（二维码/等待态）未移植",
    "remote:scan-cancel": "未实现 —— 阻塞于配对扫描流程未移植",
    "remote:set-enabled": "未实现 —— 阻塞于远端机器人启停与 hub 注册，未移植",
    "remote:set-reply-mode": "未实现 —— 阻塞于回复模式（stream/final）设置，未移植",
    "remote:set-scope": "未实现 —— 阻塞于作用域（全部/按角色/按会话）设置，未移植",
    "remote:delete-bot": "未实现 —— 阻塞于删除远端机器人与其状态，未移植",
    "remote:pair-code": "未实现 —— 阻塞于配对码生成，未移植",
    "remote:pair-cancel": "未实现 —— 阻塞于取消配对，未移植",
    "remote:remove-user": "未实现 —— 阻塞于移除已授权用户，未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── secrets（5）──────────────────────────────────────────────────────────
_put("secrets:set", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_secrets_round_trip_through_vault",
     "通过 —— 写密钥库（空串=删除）；明文不落盘，磁盘只有 secrets.enc；无密钥库回 {ok:false,available:false}")
_put("secrets:has", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_secrets_round_trip_through_vault",
     "通过 —— has_secret(providerId)；无密钥库时回 false")
_put("secrets:delete", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_secrets_delete_is_idempotent",
     "通过 —— 删除并回 {ok:true}，键不存在也成功；无密钥库时显式抛「未接线」")
_put("secrets:list", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_secrets_round_trip_through_vault",
     "通过 —— list_keys() 读 secret-names.json 侧车，只回键名不回密钥")
_put("secrets:available", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_secrets_round_trip_through_vault",
     "通过 —— describe_backend()/available()：keyring 或 file 后端为真，none 为假")

# ── skills（6）───────────────────────────────────────────────────────────
_put("skills:list", BRIDGE, T_SKILLS,
     "通过 —— 三条内置技能 create-skill/create-agent/create-mcp 顺序稳定，自定义技能按名排序")
_put("skills:get", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_skills_get_returns_body_or_null",
     "通过 —— 按 id 取技能记录（含 instructions）；不存在回 null")
_put("skills:remove", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_skill_remove_deletes_dir_and_toggles",
     "通过 —— 删自定义技能目录并清启用位；目录不存在回 ok，内置 id 回 {ok:false}")
_put("skills:set-enabled", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_skill_set_enabled_toggles_and_persists、"
     "::test_skill_set_enabled_on_builtin_is_noop_but_ok",
     "通过 —— 写启用位落盘；内置技能不改但按原版回 ok")
_put("skills:set-roles", BRIDGE,
     "单测 tests/test_web_settings_write.py::test_skill_set_roles_normalizes、"
     "::test_skill_set_roles_rejects_builtin",
     "通过 —— 角色白名单去重归一后落盘；内置技能拒绝修改")
_put("skills:import", "—", T_NONE,
     "未实现 —— 阻塞于从文件/目录导入 SKILL.md 并解析 frontmatter 的写路径，未移植")

# ── tasks（8）────────────────────────────────────────────────────────────
for _ch, _why in {
    "tasks:list": "未实现 —— 阻塞于定时任务调度器（tasks.json + cron 解析），未移植",
    "tasks:get": "未实现 —— 阻塞于单条任务读取，未移植",
    "tasks:create": "未实现 —— 阻塞于校验 tz/cron/once 并计算 nextRun，未移植",
    "tasks:update": "未实现 —— 阻塞于局部更新且非法 schedule 静默忽略的语义，未移植",
    "tasks:delete": "未实现 —— 阻塞于删任务并清理其会话，未移植",
    "tasks:set-status": "未实现 —— 阻塞于 active 时清零错误计数并重算 nextRun，未移植",
    "tasks:preview": "未实现 —— 阻塞于 cron 描述生成与下次运行时间预览，未移植",
    "tasks:run-now": "未实现 —— 阻塞于立即运行与「已在运行」回报，未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── terminal（5）─────────────────────────────────────────────────────────
for _ch, _why in {
    "terminal:list-shells": "未实现 —— 阻塞于终端面板（xterm.js + pty）未移植，没有 shell 清单",
    "terminal:create": "未实现 —— 阻塞于 pty 主进程与会话 id 注册表，未移植",
    "terminal:input": "未实现 —— 这条是 ipcMain.on 单向通道，阻塞于 pty 写入端不存在",
    "terminal:resize": "未实现 —— 阻塞于 pty TIOCSWINSZ 调整，未移植",
    "terminal:dispose": "未实现 —— 阻塞于关闭 pty 并清理注册表，未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

# ── update（4）───────────────────────────────────────────────────────────
_put("update:get-state", BRIDGE,
     "单测 tests/test_web_shell_modules.py::test_update_state_uses_phase_key",
     "已知差异 —— 形状已对齐契约的 {phase:'idle'}；自动更新（electron-updater）未移植，永远停在 idle")
for _ch, _why in {
    "update:check": "未实现 —— 阻塞于发布源与 electron-updater，未移植",
    "update:download": "未实现 —— 阻塞于更新包下载流程，未移植",
    "update:install": "未实现 —— 阻塞于安装并重启流程，未移植",
}.items():
    _put(_ch, "—", T_NONE, _why)

assert len(STATUS) == 158, len(STATUS)

EVENT_ROWS = [
    ("chat:event",
     "`{turnId, sessionId, event}`，event 为 camelCase 判别联合（text_delta/tool_call/…/done{stopReason}）",
     "app/src/mvvm/webui/bridge.py:140（emit_event）→ shim.js:91（__devaEmit）",
     "通过 —— 宿主经 bridge.emit_event 推 turn_start/text_delta/tool_call/tool_result/done；"
     "形状转换在 host.to_chat_event，用例 test_send_streams_text_and_finishes_with_done、"
     "test_tool_call_events_carry_ids_matching_results；真页面实跑见 test_web_e2e_stream.py"),
    ("chat:sessions-changed",
     "无 payload；会话增删改归档后推送，渲染层据此 refreshSessions",
     "app/src/mvvm/webui/bridge.py:140（emit_event，无 payload 时推 null）",
     "通过 —— 建会话/改名/归档/删除/压缩收尾都调用 emit_sessions_changed；"
     "用例 test_create_session_persists_empty_session 断言推了该事件"),
]
