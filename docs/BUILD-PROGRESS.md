# 构建进度台账（每轮更新）

> 规则：只写**实际跑出来的**结果。命令与输出都是真的；没跑过的一律归入「已实现未验证」或
> 「未实现」，不许把没跑通的说成跑通。
> 最近更新：2026-11-14（第五阶段：界面与原版逐页对齐，七页实拍全部判定「已一致」）

## 0. 本轮起点（续跑对账）

### 0.1 第五阶段起点（界面一致性）

上一轮（第四阶段）把 Qt 原生三栏界面做完，但用户**明确作废**了「Qt 原生、观感自定」的方向：
硬要求改为「移植后各页面界面必须与原版完全一致，以原版为准」。本节记录该方向的起点与选型。

起点核对（真实命令）：

```text
$ git log --oneline -3
c08da9d feat(tools): 工具权限判定层（交互轮放行/密封轮拒绝/挂载判据）接入执行入口
ed1a61f docs: 台账刷新到第四阶段收尾（772 passed / 5 skipped）
044cda0 feat(ui): 工具卡 / 内联图片 / 待办胶囊，历史重开后保留工具名与图片

$ git status --porcelain
?? app/assets/  ?? app/src/mvvm/services/persona_store.py
?? app/src/mvvm/views/title_bar_overlay.py  ?? app/src/mvvm/views/web_shell_window.py
?? app/src/mvvm/webui/  ?? scripts/parity/
```

### 0.2 选型（写进台账，用户要求）

**结论：复用原版渲染层资产 + QtWebEngine 承载 + Python 桥接。**

依据：原版界面是 React 18 + Lexical + xterm.js 的产物（富文本输入、代码块、动效、
lucide 图标体系、Humation 头像）。用 Qt 控件重画不可能逐像素一致——这正是用户禁止的
「风格相似」。用户允许「复用原版前端资产」，故：

- `app/assets/renderer/`：deva 工程构建产物的**只读拷贝**（`deva 工程只读，不许改动`，
  本轮未向其中写入任何文件）；
- `app/src/mvvm/webui/bridge.py`：Python 侧实现原版 `window.deva`（替代 Electron preload）；
- `app/src/mvvm/views/web_shell_window.py`：QtWebEngine 承载，窗口几何与原版一致；
- `app/src/mvvm/views/title_bar_overlay.py`：自绘窗口控件，复刻 Electron Linux 的
  `titleBarOverlay`（实色，右上角 96x40）。

被替代的 Qt 原生窗口（`deva_main_window.py` / `chat_pane.py` 等）保留未删——它们仍被既有
单测覆盖，删除属于未要求的改动；但**启动入口与截图对比一律走 Web 承载窗口**。

### 0.3 前四阶段起点（历史）

上一轮在第三阶段结束时全量 `634 passed / 5 skipped`，已交付压缩接线、真实 provider 装配、
流式刷新与停止，Qt 页面只做到「单窗口最小聊天界面」。

第四阶段起点：

```text
$ git log --oneline -4
9548898 feat(ui): 主窗口三栏装配：会话列表、聊天面板、设置页
3061e48 feat(vm): 会话列表与设置页 ViewModel，模型清单探针接通
9109be3 docs: 台账刷新到第三阶段
61053ae feat(ui): 流式刷新与停止按钮

$ git branch -vv
* develop 9548898 [origin/develop: ahead 8]
```

远端关系：`origin` = `git@github.com:fanchcho/ai_upper.git`；`upstream` 为旧远端，只读。
远端 `main` = `f91562b`；本地工作分支 `develop`。

第四阶段完成的可提交单元：

1. 工具全集 + 图片/Office 分支 + 待办清单接入（§1.9，commit `e4b1ed1`）；
2. Qt 页面收尾：工具卡 / 内联图片 / 待办胶囊（§1.10，commit `044cda0`）。

### 0.4 第五阶段实际提交（与本台账一致）

截至代码提交 `e289b45`（本台账与收口报告自身另有一条 docs commit，不计入下列数字）：

```text
$ git log --oneline -6
e289b45 fix(webui): 窗口控制与剪贴板改为真实实现，不再返回假成功
188cfed docs: 第五阶段收口（逐页一致性判定 + 三档报告 + 差异量化）
64a8402 chore(assets): 补齐首启种子角色文件
06841f9 test(webui): 修好全量测试的红灯，豁免项补真实 binding 覆盖
f5e987b feat(ui): QtWebEngine 承载原版渲染层 + Python 桥接 + 逐页截图流水线
4f53a1e feat(ext): 技能服务（内置元技能 + 自定义目录 + frontmatter 解析）

$ git branch -vv
* develop e289b45 [origin/develop: ahead 18]
  main    f91562b [upstream/main] Initial commit
```

远端只做快进：本阶段全程 `git commit`，未 force push、未覆盖远端提交。
`deva` 工程（`/home/agent/shared_workspace/deva`）全程只读，未写入任何文件。

**本轮中断点（若被截断从这里续）：** 界面七页实拍全部判定「已一致」（§1.11）；
全量测试 `845 passed, 5 skipped`；收口报告见 `docs/STAGE5-CLOSEOUT-REPORT.md`。
尚未完成：把新界面的写路径接通、158 通道结论表、打包入口指向 Web 承载窗口并真实构建。

### 0.5 第六阶段起点（功能测试：写路径 + 158 条结论表）

用户判定上一轮（约 2 小时）**只产出了契约文书，功能测试本身没落地**。本轮先产出可核对的
文本事实，再写代码。以下为真实命令输出（2026-11-14 实跑）。

```text
$ git log --oneline -10
8e78123 docs: 第五阶段收口数据复核（845 passed / 桥接假成功清理入账）
e289b45 fix(webui): 窗口控制与剪贴板改为真实实现，不再返回假成功
188cfed docs: 第五阶段收口（逐页一致性判定 + 三档报告 + 差异量化）
64a8402 chore(assets): 补齐首启种子角色文件
06841f9 test(webui): 修好全量测试的红灯，豁免项补真实 binding 覆盖
f5e987b feat(ui): QtWebEngine 承载原版渲染层 + Python 桥接 + 逐页截图流水线
4f53a1e feat(ext): 技能服务（内置元技能 + 自定义目录 + frontmatter 解析）
c08da9d feat(tools): 工具权限判定层（交互轮放行/密封轮拒绝/挂载判据）接入执行入口
ed1a61f docs: 台账刷新到第四阶段收尾（772 passed / 5 skipped）
044cda0 feat(ui): 工具卡 / 内联图片 / 待办胶囊，历史重开后保留工具名与图片

$ git status --porcelain
?? audit-tools/screenshot_app.py
?? audit-tools/verify_demo_page.py
?? audit-tools/xvfb_run.py
?? core
?? docs/audit/
?? out/about-window-xvfb.png
?? out/about-window.png
?? out/demo-page-reset.png
?? out/demo-page.png
?? out/main-window-xvfb.png
?? out/main-window.png
?? out/parity/deva/01-under-xvfb.png
?? out/parity/proto-shell.png
?? out/ui/

$ ls docs/audit/
contracts-browser-terminal-deliverables-remote-update.md
contracts-chat.md
contracts-fs-secrets-personas-skills-config-profile-provider-window-clipboard.md
contracts-git-tasks-memory-mcp.md

$ for f in docs/audit/*.md; do grep -c '^### ' "$f"; done
39  contracts-browser-terminal-deliverables-remote-update.md
33  contracts-chat.md          # 31 条 invoke + chat:event / chat:sessions-changed 两条事件
43  contracts-fs-secrets-personas-skills-config-profile-provider-window-clipboard.md
45  contracts-git-tasks-memory-mcp.md
# 合计 160 条小节 = 158 条 invoke（154 handle + 4 on）+ 2 条事件推送

$ cd app && ../.venv/bin/python -m pytest -q --collect-only | tail -3
850 tests collected in 1.92s

$ cd app && ../.venv/bin/python -m pytest -q | tail -3
845 passed, 5 skipped in 21.63s
```

**对账结论（与用户指出的三点逐一对上，全部成立）：**

| 用户指出的缺口 | 起点实测 | 证据 |
|---|---|---|
| 写路径未接通 | 成立。`app/src/mvvm/webui/bridge.py` 只注册约 30 条只读通道；`chat:send`/`abort`/`create-session` 等 31 条 chat 通道**一条都没注册**；`web_shell_window.py` 没有 store/gateway/tools/VM 装配 | `bridge.py:136-172`（`_register_defaults`）、`web_shell_window.py:68-129`（构造里只建 bridge） |
| 158 条结论表未合并 | 成立。`docs/audit/` 只有四份**分域契约**台账（原版侧入参/出参/错误边界），没有「移植版实现位置 + 测试方式 + 实测结果」的合并表 | `docs/audit/` 目录清单 |
| 测试未补 | 成立。`850 collected` 中与写路径相关的为 0：`test_web_shell_modules.py` 的 10 个用例全部只测只读通道、窗口几何、shim 占位符 | `app/tests/test_web_shell_modules.py` |

**本阶段暂不推翻的既有工作：** 界面七页一致性判定（§1.11）继续有效；`deva` 工程保持只读。

**本阶段中断点（若再次被截断从这里续）：** 结论表见 `docs/audit/IPC-158-LEDGER.md`；
写路径实现见 §1.12；测试与端到端证据见 §1.12 各小节。

## 1 档一：已实现并验证

### 1.1 远端接入与工程基础

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 1 | 新远端 `origin` = `git@github.com:fanchcho/ai_upper.git`，本地 `develop` 跟踪 `origin/develop` | `git remote -v`、`git branch -vv`（见 §0） |
| 2 | 不强推、不 rebase 覆盖远端；`upstream` 不推不改 | 全程只用 `git commit`；`origin/develop` 仅依赖快进合并（本轮尚未推送，本地 ahead 18，见 §0.4） |
| 3 | 迁移计划落库（158 唯一通道 = 154 `ipcMain.handle` + 4 `ipcMain.on`） | `docs/MIGRATION-PLAN.md`，生成脚本 `audit-tools/scan_deva_ipc.py` |

### 1.2 阶段 A：骨架与纵向切片

| # | 项 | 验证方式 |
|---|---|---|
| 4 | 会话持久化（建/追加/重启读回/索引自愈/读 Deva 旧数据） | `pytest tests/test_chat_session_store.py -q` → `22 passed` |
| 5 | Provider 抽象 + 错误归一（401/403/429/5xx/context） | `pytest tests/test_provider_tools.py -q` |
| 6 | 路径守卫（越界 / `..` / 符号链接穿越） | 同上；不能建链接的平台 skip 并注明 |
| 7 | `read_file` 文本分支（行号 / 2000 行 / 2000 字符 / 100k 输出护栏） | 同上 |
| 8 | 纵向切片端到端（发送 → 假 provider → 工具允许/拒绝 → 落盘 → 重启读回） | `pytest tests/test_chat_vm.py -q` → `9 passed` |
| 9 | 应用入口与装配（服务/ViewModel/View 注册） | `pytest tests/test_deva_app.py -q` → `3 passed` |
| 10 | 真实 Qt offscreen 启动新入口 | `DEVA_HOME=/tmp/deva-smoke3 QT_QPA_PLATFORM=offscreen DEVA_APP_HEADLESS=1 PYTHONPATH=app/src .venv/bin/python -m deva_app` → exit 0，`DEVA GUI OK offscreen session=main title=''` |
| 11 | 切片真机脚本 | `PYTHONPATH=app/src .venv/bin/python scripts/deva_slice.py` → `SLICE PASS` |

### 1.3 阶段 D：密钥与配置（commit `99fdb2c`）

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 12 | 密钥存储：keyring 优先，缺失/不可用时退 AES-256-GCM 加密文件 | `pytest tests/test_secrets_vault.py -q` → `20 passed` |
| 13 | 明文绝不出服务层：对外只有 `has_secret`；`get_secret` 不映射成界面命令 | 同文件（含「描述后端不泄露密钥」用例）+ `describe_backend()` |
| 14 | `config.json` 服务：顶层浅合并、`None` 删键、写失败不静默 | `pytest tests/test_settings_service.py -q` → `16 passed` |
| 15 | 密钥不进代码/不进明文日志 | `grep` 检查无硬编码密钥；`secrets.enc` + `.secrets.key` 分开落盘（0600） |

### 1.4 阶段 C：真实 provider 适配器（commit `ec9a7ad`）

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 16 | Anthropic 适配器（httpx + SSE 事件流解析：`content_block_delta` / `tool_use` / `usage`） | `pytest tests/test_anthropic_provider.py -q` → `14 passed` |
| 17 | OpenAI Chat 兼容适配器（流式 delta、`tool_calls` 拼接） | `pytest tests/test_openai_provider.py -q` → `18 passed` |
| 18 | Responses 协议适配器 | `pytest tests/test_responses_provider.py -q` → `12 passed` |
| 19 | 跨适配器共性与错误归一（三协议同一套事件） | `pytest tests/test_provider_adapters.py -q` → `26 passed` |
| 20 | 模型引用解析（`providerId:modelId`，按首个冒号切分，兼容 Ollama 的 `qwen3:8b`） | 同 `test_provider_adapters.py` |
| 21 | 服务商注册表：密钥最后一刻注入、UA 自报、opencode 会话头、模型清单探针 | 同上 + `provider_registry.py` |

**事件流解析全部用离线假传输测试**（`tests/scripted_transport.py` 注入字节），**不发真实网络**。

### 1.5 阶段 E：上下文压缩子系统（commit `7738aab`）

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 22 | 上下文窗口 / 输出预算（内置表、`-128k`/`-1m` 后缀、非 Claude 封顶 256K、learned 缓存） | `pytest tests/test_context_window.py -q` → `12 passed` |
| 23 | 模型视图（标记、轮起点、轮中 head、`insert_text`、复读检测、待办清单） | `pytest tests/test_model_view_and_todos.py -q` → `23 passed` |
| 24 | 压缩主流程（边界吸附、轮中切、转录、摘要重试/致命/中止/超时、两道把关、提示位移动） | `pytest tests/test_compaction.py -q` → `38 passed` |
| 25 | `.jsonl` 拆分写出（前缀不变就追加、变了就换文件、载入拼回、缺块不误删） | `pytest tests/test_chat_session_store.py -q` → `22 passed` |
| 26 | 全量回归 | `pytest -q` → `613 passed, 5 skipped`（基线 428/5，新增 185 例） |

原始输出（逐字）：

```text
$ cd app && ../.venv/bin/python -m pytest -q
........................................................................ [ 93%]
..........................................                               [100%]
613 passed, 5 skipped in 18.91s
```

### 1.6 阶段 F：压缩接进对话回合（commit `50e4459`）

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 27 | 轮首自动压缩：`needs_compaction` 过线 → `compact_session` 插入摘要、不删原文 | `pytest tests/test_chat_vm_compaction.py -q` → `6 passed` |
| 28 | 轮中压缩：工具结果回灌后、下一步发送前再查一次 `needs_compaction_mid_turn` | 同上（工具调用与结果不被拆散、无悬空 tool_use） |
| 29 | 手动 `/compact`：`compact_now()`，事件 `scope=manual`；无压缩模型时明确失败 | 同上 |
| 30 | 压缩失败不阻断回合；界面事件 `compacting`（开始/结束）与 `compacted` | 同上 |
| 31 | 回合移入后台线程：worker 只入队、UI 线程 `drain()` 执行属性写入 | 同上 + `pytest tests/test_chat_vm.py tests/test_deva_app.py -q` |
| 32 | 全量回归 | `pytest -q` → `619 passed, 5 skipped` |

### 1.7 阶段 G：真实服务商装配（commit `ba20847`）

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 33 | `ModelGateway`：`config.json` 模型段 → 模型引用解析 → 密钥库 → 按 adapter 造适配器 | `pytest tests/test_provider_setup.py -q` → `13 passed` |
| 34 | 会话定格模型优先；悬空引用回落全局默认；都没有则明确报「尚未配置」 | 同上 |
| 35 | 缺密钥继续、按空串发请求（本地 Ollama 等可无钥）；密钥不进 VM / 不进日志 | 同上 |
| 36 | 思考档位：会话定格值 > `models.activeEffort` > 默认（不发思考参数） | 同上 |
| 37 | 压缩模型、模型段、压缩配置、思考参数全部「每轮现查」：设置页改动下一轮生效 | 同上 + `ChatViewModel._*_now()` |
| 38 | 入口 `python -m deva_app` 不再用 `FakeProvider` | 见 #10 的 offscreen 启动（本轮重跑通过） |

### 1.8 阶段 H：流式刷新与停止（commit `61053ae`）

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 39 | 流式正文在回合**进行中**就能到达界面（`streaming` 属性 + 事件队列） | `pytest tests/test_chat_streaming.py -q` → `3 passed` |
| 40 | 停止按钮 → `cancel()`：回合在下一个检查点收尾，状态「已停止」，半截正文落盘并展示 | 同上 |
| 41 | 修复两处中止语义：适配器无 `Done` 收流时补判取消；中止正文不再被重复追加 | 同上 |
| 42 | 聊天窗口：流式区（空时收起）、停止按钮（busy 可用）、40ms `drain` 定时器 | `pytest tests/test_deva_app.py -q` |
| 43 | 全量回归 | `pytest -q` → `634 passed, 5 skipped` |

**三协议真实网络调用仍未验证**（无密钥、容器不保证出网），见 §2。

### 1.9 阶段 I：工具全集 + 图片/Office 读取 + 待办接入（commit `e4b1ed1`）

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 44 | 注册 10 个可离线工具：`read_file` / `list_dir` / `glob` / `grep` / `web_fetch` / `write_file` / `edit_file` / `run_command` / `present_files` / `todo_write` | `pytest tests/test_tools_full.py -q` → `55 passed` |
| 45 | `read_file` 图片分支：按魔数判 mime（不信扩展名）、超大图拒绝、返回 `ImagePart` | 同上（`test_read_file_image_returns_image_part` / `_mime_follows_magic_not_extension` / `_rejects_oversized_image`） |
| 46 | `read_file` Office 分支：docx/xlsx/pptx 自己解 zip+XML 出文本（不引 python-docx / openpyxl），老式二进制给出明确错误 | 同上（`_docx_returns_numbered_text` / `_xlsx_and_pptx` / `_office_legacy_binary_is_clear_error`） |
| 47 | `todo_write` 接入会话：快照折叠、非法载荷明确报错、无 sink 时显式失败 | 同上 + `pytest tests/test_chat_vm_todos.py -q` → `6 passed` |
| 48 | Deva 19 个工具只实现 10 个，其余 9 个（`ask_user` / 需挂载工作区的子代理类等）刻意缺失 | 同上（`test_unknown_tool_and_bad_arguments`）：未知工具明确报错，不静默 |
| 49 | 全量回归 | `pytest -q` → `750 passed, 5 skipped` |

### 1.10 阶段 J：工具卡 / 内联图片 / 待办胶囊（commit `044cda0`）

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 50 | 工具结果在历史里画成卡片（单格 `table`：Qt 富文本只有 table 上的块级背景/边框稳定生效） | `pytest tests/test_transcript_render.py -q` → `17 passed`；`pytest tests/test_deva_panes.py -q` → `28 passed` |
| 51 | 内联图片：`deva-image:N` 占位 URL + `addResource` **先于** `setHtml`（四个绑定上唯一一致顺序） | 同上（`test_chat_pane_registers_inline_image_as_document_resource`）；真 Qt 下 `document().resource(...)` 取回非空 |
| 52 | 待办胶囊：摘要行 + `展开清单` / `收起清单` / `取消清单`，无条目时保持收起 | 同上（`test_chat_pane_todo_capsule_expands_and_collapses` / `test_chat_pane_cancel_button_cancels_active_list`） |
| 53 | 历史重开保留工具名与图片（此前会退化成「工具（成功）」且图丢失）：按 `tool_use_id` 反查前一条 assistant 的 `tool_use` | `pytest tests/test_chat_vm_todos.py -q` → `6 passed`（`test_history_tool_entries_keep_tool_name_and_images`） |
| 54 | 5 张 offscreen 真截图，脚本化 provider 回放 `read_file` + `todo_write`，走完整回合 | 见下方真实输出 |
| 55 | 全量回归 | `pytest -q` → `772 passed, 5 skipped` |

截图脚本真实输出（逐字）：

```text
$ QT_QPA_PLATFORM=offscreen PYTHONPATH=app/src .venv/bin/python scripts/deva_ui_shots.py /tmp/shots1
status: 就绪
transcript head: ['［你］', '帮我把工作区里的笔记过一遍', '［你］']
session count: 2
saved: /tmp/shots1/01-chat.png True (1080, 720)
settings page: list
saved: /tmp/shots1/02-settings-list.png True (1080, 720)
provider page: provider p1
key status: 未配置密钥
models: 2
saved: /tmp/shots1/03-settings-provider.png True (1080, 720)
explain tool session: sess_mwf4my70_28e0b9
tool card present: True
image resource registered: True
todo pill: 待办：整理工作区｜读笔记（已完成 1/3）
saved: /tmp/shots1/04-tool-card-and-todo.png True (1080, 720)
todo details: ['[x] 看图片', '[~] 读笔记', '[ ] 写总结']
saved: /tmp/shots1/05-todo-expanded.png True (1080, 720)
UI SHOTS PASS
```

全量回归原始输出：

```text
$ cd app && ../.venv/bin/python -m pytest -q
........................................................................ [ 74%]
........................................................................ [ 83%]
........................................................................ [ 92%]
.........................................................                [100%]
772 passed, 5 skipped in 21.97s
```

**关于权限确认：** 对照 Deva 源码（`exec-policy.ts` 文件头与 `chat.ts:5160`「权限闸门（纯同步策略，
零弹框）：所有工具一律放行…交互轮唯一的拒绝是「用户暂不挂载工作区」」），Deva 自 2026-10-09 起
**没有**逐工具权限确认弹框。因此不做权限确认 UI——做了就是臆造业务功能。py_upper 的
`WorkspaceGuard` 受信根是已记录的刻意差异（Deva 用挂载工作区，py_upper 用受信根目录）。

### 1.11 阶段 K：界面与原版逐页一致（commit `f5e987b` / `4f53a1e` / `06841f9` / `64a8402`）

#### 1.11.1 选型与载体

用户要求「移植后各页面的界面必须与原版完全一致，以原版为准」，并允许复用原版渲染层资产。
故端口不再自绘，改为 **QtWebEngine 承载 deva 构建产物（`app/assets/renderer`，只读拷贝）+
Python 侧实现 `window.deva`（替代 Electron preload）**。理由：原版界面是 React 18 + Lexical +
xterm.js 的产物，用 Qt 控件重画不可能逐像素一致，正是用户禁止的「风格相似」。

#### 1.11.2 截图流水线（两轮，原因见下）

| 轮次 | 目的 | 数据 | 说明 |
|---|---|---|---|
| 第一轮 | 首启页 + 设置四个子页 | 空 `DEVA_HOME` | 无会话时进不了对话页；空库才能稳定拍到首启页 |
| 第二轮 | 对话页 | 带 `parity-fixture`（一个会话） | 有会话时首屏直接是对话页，拍不到首启页 |

两轮都有一条前置：**截图前把指针移到中立位置 `xdotool mousemove 200 700`**。Xvfb 的指针默认
停在屏幕中心 (700,450)，正好压在首启页的「智谱 · GLM」提供方卡片上，原版会因 `:hover` 画出
强调色边框；两边指针位置不一致时首启页永远无法逐像素比较（曾实测 fuzz3 = 11948，全部来自这一处）。

#### 1.11.3 逐页一致性判定（实拍，1280×820）

截图取的是 1400×900 的根窗口（窗口本体 1280×820 贴左上角，四周是 Xvfb 的空白桌面）。
判定口径见 `scripts/parity/compare.sh`：`raw` = `compare -metric AE`（无容差）；
`fuzz3` = 容差 3% 下的 AE；`maxd` = 差值图 **RGB 三通道**最大差（0..255）。
**fuzz3 ≤ 1 且 maxd ≤ 10 → 已一致。**

> `maxd` 最初是先转灰度再取最大值，会把三通道的差平均掉（灰度法得 7，真实单通道差是 **9**）。
> 脚本已修正，下表与下段输出都是修正后的口径。

| 页面 | 原版截图（绝对路径） | 移植版截图（绝对路径） | raw | fuzz3 | maxd | 判定 |
|---|---|---|---|---|---|---|
| 01 首启页（未配置提供方） | `/home/agent/shared_workspace/py_upper/out/parity/deva/01-first-run.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/01-first-run.png` | 409 | 1 | 9 | 已一致 |
| 02 设置 › 通用 | `/home/agent/shared_workspace/py_upper/out/parity/deva/02-settings-general.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/02-settings-general.png` | 241599 | 1 | 9 | 已一致 |
| 03 设置 › 模型 | `/home/agent/shared_workspace/py_upper/out/parity/deva/03-settings-models.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/03-settings-models.png` | 241446 | 1 | 9 | 已一致 |
| 04 设置 › 扩展 | `/home/agent/shared_workspace/py_upper/out/parity/deva/04-settings-extensions.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/04-settings-extensions.png` | 241527 | 1 | 9 | 已一致 |
| 05 设置 › 关于 | `/home/agent/shared_workspace/py_upper/out/parity/deva/05-settings-about.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/05-settings-about.png` | 241398 | 1 | 9 | 已一致 |
| 06 关闭设置后的主界面 | `/home/agent/shared_workspace/py_upper/out/parity/deva/06-after-settings.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/06-after-settings.png` | 409 | 1 | 9 | 已一致 |
| 07 对话页（带 fixture） | `/home/agent/shared_workspace/py_upper/out/parity/deva/07-chat.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/07-chat.png` | 14033 | 1 | 9 | 已一致 |

判定脚本真实输出：

```text
$ bash scripts/parity/compare.sh out/parity/deva out/parity/py
PAGE                          raw    fuzz3   maxd  VERDICT
01-first-run                  409        1      9  已一致
02-settings-general        241599        1      9  已一致
03-settings-models         241446        1      9  已一致
04-settings-extensions     241527        1      9  已一致
05-settings-about          241398        1      9  已一致
06-after-settings             409        1      9  已一致
07-chat                     14033        1      9  已一致
```

差异拆解（`scripts/parity/measure_diff.py` 的真实输出，阈值 1200..1280 × 0..40 视为「✕ 字形块」）：

```text
$ .venv/bin/python scripts/parity/measure_diff.py out/parity/deva out/parity/py
PAGE                       total    ✕块      正文    正文=1   正文>=2   正文max          正文>=2 的包围盒
01-first-run                 409    58     351     343       8       3       18,53-900,458
02-settings-general       241599    58  241541  241507      34       2       14,20-978,686
03-settings-models        241446    58  241388  241363      25       2       14,20-978,686
04-settings-extensions    241527    58  241469  241447      22       2       14,20-978,686
05-settings-about         241398    58  241340  241320      20       2       14,20-794,686
06-after-settings            409    58     351     343       8       3       18,53-900,458
07-chat                    14033    58   13975   13965      10       3       18,53-456,126

各级灰度像素数（通道最大差；✕块 / 正文分开列）：
  01-first-run             ✕块: 1:17 2:8 3:7 4:7 5:9 6:6 7:3 9:1
                           正文: 1:343 2:7 3:1
  02-settings-general      ✕块: 1:17 2:8 3:7 4:7 5:9 6:6 7:3 9:1
                           正文: 1:241507 2:34
  03-settings-models       ✕块: 1:17 2:8 3:7 4:7 5:9 6:6 7:3 9:1
                           正文: 1:241363 2:25
  04-settings-extensions   ✕块: 1:17 2:8 3:7 4:7 5:9 6:6 7:3 9:1
                           正文: 1:241447 2:22
  05-settings-about        ✕块: 1:17 2:8 3:7 4:7 5:9 6:6 7:3 9:1
                           正文: 1:241320 2:20
  06-after-settings        ✕块: 1:17 2:8 3:7 4:7 5:9 6:6 7:3 9:1
                           正文: 1:343 2:7 3:1
  07-chat                  ✕块: 1:17 2:8 3:7 4:7 5:9 6:6 7:3 9:1
                           正文: 1:13965 2:9 3:1
```

#### 1.11.4 残余差异（必须说清楚，不允许写成「零差异」）

**不是逐像素完全相同。** 七页没有一页的 `raw` 为 0。差异分两类，已分别定位：

**（1）关闭按钮 ✕ 的字形抗锯齿——每页都是同一处，58 个像素**

| 灰度级 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 9 |
|---|---|---|---|---|---|---|---|---|
| 像素数 | 17 | 8 | 7 | 7 | 9 | 6 | 3 | 1 |

- 位置：`10x10+1259+15`（窗口右上角 ✕ 的笔画），七页位置与像素数**完全一致**。
- 最大 **9/255**（唯一那 1 个像素：原版 `(122,125,129)` vs 移植版 `(113,118,121)`）。
  这是全图唯一的 ≥8 级差异点，因此 `maxd` 七页都是 9。
- 原因：Electron 用一个位图字形、Qt 用 `QPainter` 画线，两者对这条斜线的覆盖度采样不同。
  已用离屏渲染核对控件本身：`TitleBarOverlay` 在 96×40 区域对原版实拍的 `>8` 级差异像素为 0，
  几何与原版逐值相同（`(20.25,15.75)-(11.75,24.25)`、线宽 2.1、`#5F6368`）。
- 结论：肉眼不可见，但**确实存在**，不写成「零像素差」。

**（2）页面正文——绝大多数只差 1 级，极少数差 2～3 级**

| 页面 | 正文差异像素 | 其中 1 级 | 其中 ≥2 级 | 正文最大级差 | ≥2 级分布 |
|---|---|---|---|---|---|
| 01 首启页 | 351 | 343 | 8 | 3 | 卡片图标与彩色渐变边缘 |
| 02 设置 › 通用 | 241541 | 241507 | 34 | 2 | 侧栏/说明文字的抗锯齿边 |
| 03 设置 › 模型 | 241388 | 241363 | 25 | 2 | 同上 |
| 04 设置 › 扩展 | 241469 | 241447 | 22 | 2 | 同上 |
| 05 设置 › 关于 | 241340 | 241320 | 20 | 2 | 同上 |
| 06 主界面 | 351 | 343 | 8 | 3 | 同 01 |
| 07 对话页 | 13975 | 13965 | 10 | 3 | 用户气泡与头像边缘 |

- 设置四页的十万级数字**不是结构差异**：整片半透明遮罩的底色差了 1 级——
  原版 `(144,144,144)`、移植版 `(143,143,144)`，占 178498 像素（73.9%），
  另有 `(140,140,141)→(139,139,140)` 41753 像素（17.3%）。这是同一条遮罩
  `rgba(0,0,0,α)` 在两端不同的合成取整，肉眼不可分辨。
- 对话页的 12564 像素同理：用户气泡底色 `(228,228,244)` → `(228,228,243)`，差 1 级。
- **没有任何一处是布局、字号、颜色、圆角、图标、控件形态、滚动条或空/错状态的差异**：
  `≥2` 级的像素全部落在文字/图标的抗锯齿边缘，最大 3 级。
- 结论：判定「已一致」；但**不等于零像素差**，故逐页给出实测数字。

#### 1.11.5 本阶段修掉的两个真实差异

1. **设置页叠加层被遮罩压暗**（差异块 `96x40+1184+0`）：原版在 Linux 上的 `titleBarOverlay`
   是**实色**矩形（`#ffffff` / `#1e1e20`），画在网页内容之上，弹框遮罩压不暗它。
   端口此前用了半透明叠加层，被 dim 成 `#949494`。改为不透明并按 96×40 摆放。
2. **「设置 › 扩展」显示 `No extensions`**：`skills:list` 未接入。新增 `skill_store.py`
   （内置三技能 + 自定义目录 + frontmatter 解析 + 启用/角色配置语义），逐条对齐
   `skills.ts` / `frontmatter.ts` / `ext-roles.ts`；内置技能正文与描述与原版常量**逐字校验一致**。
   19 条单测覆盖（`app/tests/test_skill_store.py`）。

#### 1.11.6 可复现命令（全部实跑过）

```bash
# 1) 原版启动 + 截图（空库：首启页与设置页）
cd /home/agent/shared_workspace/py_upper
bash scripts/parity/deva_original_shots.sh /tmp/deva-shots /tmp/deva-home

# 2) 原版启动 + 截图（带 fixture：对话页）
bash scripts/parity/deva_original_shots.sh /tmp/deva-shots-chat /tmp/deva-home-chat /tmp/parity-fixture

# 3) 移植版启动 + 截图（同样的两轮）
bash scripts/parity/port_shots.sh /tmp/py-shots /tmp/py-home
bash scripts/parity/port_shots.sh /tmp/py-shots-chat /tmp/py-home-chat /tmp/parity-fixture

# 4) 对齐判定
bash scripts/parity/compare.sh /tmp/deva-shots /tmp/py-shots

# 4b) 差异拆解（把「raw」拆成 ✕ 字形块 / 正文，并给逐级灰度数）
.venv/bin/python scripts/parity/measure_diff.py /tmp/deva-shots /tmp/py-shots

# 5) 只启动移植版窗口（人工观察 / 截图前调试）
DISPLAY=:96 DEVA_HOME=/tmp/py-home QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu" \
  .venv/bin/python scripts/parity/port_run.py

# 6) 技能服务单测
cd app && ../.venv/bin/python -m pytest tests/test_skill_store.py -q
# → 19 passed in 0.18s

# 7) Web 承载层（真实 binding）单测
cd app && ../.venv/bin/python -m pytest tests/test_web_shell_modules.py -q
# → 12 passed in 0.40s
```

截图流水线内部固定：Xvfb `1400x900x24`（原版 `:95`、端口 `:96`），窗口 `windowmove 0 0` +
`windowsize 1280 820`，`import -window root` 取根窗口后按 1280×820 比较；点击坐标两边完全一致
（设置齿轮 `27,787`；设置导航 `340,246 / 340,275 / 340,305`；关闭 `965,152`）。

依赖：`xvfb`、`xdotool`、`imagemagick`；原版另需 Electron 运行库与 `fonts-noto-cjk`。

#### 1.11.7 全量测试（原始输出）

```text
$ cd app && ../.venv/bin/python -m pytest -q
........................................................................ [  8%]
..........ss............................................................ [ 16%]
........................................................................ [ 25%]
...........................ss........................................... [ 33%]
........................................................................ [ 42%]
.s...................................................................... [ 50%]
........................................................................ [ 59%]
........................................................................ [ 67%]
........................................................................ [ 76%]
........................................................................ [ 84%]
........................................................................ [ 93%]
..........................................................               [100%]
845 passed, 5 skipped in 21.51s
```

5 条 skip 的原文原因（`-q -rs` 原样抄录）：

```text
$ cd app && ../.venv/bin/python -m pytest -q -rs
SKIPPED [1] tests/test_build_tool_compat.py:1615: the auto-link pragma belongs to the Windows pyconfig.h
SKIPPED [1] tests/test_build_tool_compat.py:1669: handle inheritance for GUI-subsystem children belongs to Windows
SKIPPED [1] tests/test_e2e_local.py:432: set PY_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_e2e_local.py:470: set PY_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_native_deployment.py:177: requires cc, patchelf and readelf
845 passed, 5 skipped in 21.35s
```

这 5 条都是**环境型**跳过（Windows 专属 2 条、需显式开关的完整构建 E2E 2 条、需
`cc/patchelf/readelf` 的原生部署 1 条），不是为了让检查变绿而跳过。**没有**用跳过、
注释或 `@ts-ignore` 之类的手段掩盖红灯——本轮唯一的红灯是真实缺陷，见 §1.11.8。

#### 1.11.8 本轮唯一的红灯与修复（如实记录）

Web 承载层三个模块在**类体求值**时即需 Qt（继承 `QWidget` / `QMainWindow` / `QObject`，且类体里调
`Signal(...)`），而该用例用空 submodule 的假 binding 遍历整棵树 → 红。修复方式：把三者列入显式
豁免名单（并断言名单内文件真实存在，防重命名后豁免悄悄失效），同时新增
`tests/test_web_shell_modules.py` 用**真实 binding** 覆盖被豁免的部分（导入、叠加层几何 96×40 与
不透明底色、深色切换、桥接契约通道、未知通道显式 reject、`browser:state` 键集、`skills:list`、
承载窗口 1280×820/最小 940×600 与叠加层位置、shim 占位符替换）。commit `06841f9`。

#### 1.11.9 桥接层「假成功」清理（commit `e289b45`）

收口后复核频道表时发现两条**静默假成功**，已改为真实实现并补用例：

| 通道 | 之前 | 现在 | 覆盖用例 |
|---|---|---|---|
| `window:minimize` / `window:toggle-maximize` / `window:close` | 空 lambda：界面点了没反应，但 Promise resolve | 由承载窗口注入 `set_window_actions(...)` 真调 `showMinimized` / `showMaximized` / `close`；**没注入就抛 `UnimplementedChannel`**（前端 reject） | `test_window_actions_are_wired_or_raise_not_fake_success` |
| `clipboard:read-text` / `clipboard:write-text` | 写死空串 / `{"ok": true}` | 走 Qt 剪贴板；非字符串入参照原版按空串处理 | `test_clipboard_round_trip_uses_qt_clipboard` |

`pytest tests/test_web_shell_modules.py -q` → **12 passed in 0.40s**；全量 **845 passed, 5 skipped**。
注意：这只证明**通道被调用后的 Python 行为正确**，Xvfb 无窗口管理器，最小化/最大化的**视觉结果**
仍需真桌面验（见 §2）。

---

## 2 档二：已实现未验证

| 项 | 现状 | 为什么没验证 / 怎么验证 |
|---|---|---|
| 真实网络调用（Anthropic / OpenAI / Responses） | 适配器与装配线都完整，事件流解析有离线测试 | **无可用密钥**，本环境也不保证出网。接上密钥后跑一次真实请求即可确认；绝不以离线测试冒充真实成功 |
| `web_fetch` 真实抓网页 | 只测了非 http 拒绝、缺 url、HTML→文本；无真网络用例 | 同上（不出网）。离线可测的部分已覆盖 |
| Web 承载窗口在真桌面（真显卡、HiDPI、Wayland）下的观感 | 已在 Xvfb 软渲染下实拍七页并与原版逐像素比对（§1.11） | 容器只有 Xvfb。真显卡/缩放的合成差异无法在容器验证；截图结论只对 `1400x900x24 + 软渲染` 这一配置成立 |
| `titleBarOverlay` 的窗口控制（最小化/最大化/关闭真实生效） | 叠加层画得与原版一致，按钮几何有测试 | 截图对比只能证明**画对**，证明不了**点了有效**；Xvfb 无窗口管理器，最小化/最大化行为需要真桌面验 |
| 深色主题下的七页对比 | 叠加层深色切换有单测（`OVERLAY_BG_DARK`） | 只实拍了浅色七页；深色需要原版切主题再拍一轮，本轮时间不够 |
| 打包后产物能起 Web 承载窗口 | 打包裁剪已保留 `QtWebEngineCore`/`QtWebChannel`（`qt_prune.used_qt_modules` 扫得到），入口尚未切到 Web 窗口 | 见 §3；入口没切之前，打包产物跑的仍是 Qt 原生窗口 |
| 流式刷新在真窗口里的观感（40ms 节流） | 逻辑与假控件都有测试 | 需要长回复 + 真人观察；Xvfb 能跑但看不出手感 |
| 技能目录里**自定义**技能的排序 | 按 `casefold()` 排，ASCII 名与原版 `localeCompare` 等价 | 非 ASCII 名（中文）在 `localeCompare` 默认 ICU 排序下与 `casefold()` 可能不同，未实拍对比 |

## 3 档三：未实现（原因与阻塞）

| 项 | 原因 | 风险 |
|---|---|---|
| 158 通道逐条结论表 | 本轮时间用尽（用户已明确「时间不够就只把阻塞原因写准，不要虚报」） | 迁移契约尚未闭环；`docs/MIGRATION-PLAN.md` 仍是逐条清单，没有判定列。桥接层已实现的是渲染层实际调用的那一批通道（`config:*` / `chat:*` / `skills:*` / `browser:state` / `window:set-overlay`），其余通道在桥边界显式 reject（不假成功），但**没有逐条列出「已落地 / 不适用 / 阻塞」的结论表** |
| 打包入口指向 Web 承载窗口并真实构建一次 | 同上，本轮未做 | 当前 `deva_app` 入口起的仍是 Qt 原生窗口；Web 窗口只能经 `scripts/parity/port_run.py` 启动。打包产物因此**没有**被证明能起新界面 |
| 聊天/工具/待办等**写路径**通道接通 | Web 承载层本轮只做到「七页渲染正确」，`chat:send` 一类写通道尚未接到 `ChatViewModel` | 新界面目前只能看，不能发消息。这是第五阶段最大的功能缺口 |
| 工作区挂载交互轮 | Deva 的挂载卡是交互轮唯一闸门，py_upper 改为启动时 `DEVA_APP_WORKSPACE` | 运行中不能换工作区；需要做挂载卡才能对齐 |
| 子智能体 / `task` 类工具（Deva 19 工具里的 9 个） | 依赖挂载工作区与多轮编排，未迁移 | 模型拿不到这几个工具时会退化为单轮 |
| 真机人工验收（键盘焦点、IME、拖拽） | 容器无显示服务器 | 只能由人验 |

## 4. commit 列表

| commit | 内容 |
|---|---|
| `76d4009` | docs: Deva→py_upper 迁移计划（158 通道契约主轴） |
| `a7fba52` | feat(chat): pydantic 对话模型与 Deva 兼容的会话存储 |
| `d4ac576` | feat(services): provider 抽象 + 离线假实现、路径守卫与 read_file |
| `76bed55` | test(services): provider 错误映射、假 provider、守卫越界 |
| `7155647` | feat(chat): ChatViewModel 串起发送→回复→工具→落盘→重启读回 |
| `b8311a7` | feat(app): deva_app 入口与 Qt 原生聊天窗口 |
| `a269fae` | build: 记录运行依赖并补齐 deva_app 包标记 |
| `65ac492` | feat(scripts): 纵向切片真机脚本 |
| `aafac0e` | docs: 应用骨架说明 |
| `ad1105d` | test(qt): 真实 PySide6 offscreen 界面冒烟脚本 |
| `2f8fb17` | fix(build): 模板 dependencies 恢复为空 |
| `c70b0ec` | docs: 构建进度台账 |
| `145b431` | chore: 清理未使用的 import 与动态 import |
| `2787a00` | docs: 台账补齐 commit 列表 |
| `99fdb2c` | feat(secrets): 钥匙串优先 + AES-GCM 回退；config.json 服务 |
| `ec9a7ad` | feat(provider): 三协议真实适配器 + SSE/传输层 + 模型引用解析 |
| `a7a39c9` | docs: 台账按三档重写，记录续跑起点与远端关系 |
| `7738aab` | feat(compaction): 上下文压缩与 `.jsonl` 拆分存盘 |
| `50e4459` | feat(chat): 压缩接进对话回合，回合移入后台线程并加事件队列 |
| `ba20847` | feat(app): 真实服务商装配，入口改用配置+密钥+适配器 |
| `61053ae` | feat(ui): 流式刷新与停止按钮 |
| `e4b1ed1` | feat(tools): 工具全集（10 个）+ read_file 图片/Office 分支 + todo_write 接入会话 |
| `044cda0` | feat(ui): 工具卡 / 内联图片 / 待办胶囊，历史重开后保留工具名与图片 |
| `c08da9d` | feat(tools): 工具权限判定层（交互轮放行/密封轮拒绝/挂载判据）接入执行入口 |
| `4f53a1e` | feat(ext): 技能服务（内置元技能 + 自定义目录 + frontmatter 解析） |
| `f5e987b` | feat(ui): QtWebEngine 承载原版渲染层 + Python 桥接 + 逐页截图流水线 |
| `06841f9` | test(webui): 修好全量测试的红灯，豁免项补真实 binding 覆盖 |
| `64a8402` | chore(assets): 补齐首启种子角色文件 |

## 5. 下一轮入口

当前起点（真实命令）：

```text
$ git branch -vv
* develop e289b45 [origin/develop: ahead 18]
  main    f91562b [upstream/main] Initial commit

$ cd app && ../.venv/bin/python -m pytest -q
845 passed, 5 skipped in 21.51s
```

按优先级：

1. **把新界面的写路径接上**（最大功能缺口）：`chat:send` / `chat:cancel` / `chat:answer`
   等通道接到 `ChatViewModel`，让 Web 承载窗口能真发消息；这是 §3 第三行。
2. 158 通道结论表（唯一硬缺口）：重写项给「通道 → 新实现文件:行号 → 覆盖测试」；
   逐条判定已落地 / 不适用 / 阻塞。
3. 打包：入口指向 `web_shell_window.DevaWebWindow` 并实际构建一次
   （linux-arm64 跑通后，Windows/macOS 仍未验）。
4. 深色主题七页对比 + 窗口控制按钮的真实生效验证（需真桌面）。
5. 工作区挂载交互轮（对齐 Deva 的挂载卡），完成后才能谈子智能体类工具。
6. 真实密钥接上后跑一次三协议真实请求，把 §2 第一行落到档一。
