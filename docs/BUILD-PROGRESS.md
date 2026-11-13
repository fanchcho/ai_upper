# 构建进度台账（每轮更新）

> 规则：只写**实际跑出来的**结果。命令与输出都是真的；没跑过的一律归入「已实现未验证」或
> 「未实现」，不许把没跑通的说成跑通。
> 最近更新：2026-11-13（第四阶段收尾：工具卡 / 内联图片 / 待办胶囊已提交，全量 `772 passed, 5 skipped`）

## 0. 本轮起点（续跑对账）

上一轮在第三阶段结束时全量 `634 passed / 5 skipped`，已交付压缩接线、真实 provider 装配、
流式刷新与停止，Qt 页面只做到「单窗口最小聊天界面」。

本轮（第四阶段）起点：

```text
$ git log --oneline -4
9548898 feat(ui): 主窗口三栏装配：会话列表、聊天面板、设置页
3061e48 feat(vm): 会话列表与设置页 ViewModel，模型清单探针接通
9109be3 docs: 台账刷新到第三阶段
61053ae feat(ui): 流式刷新与停止按钮

$ git status --porcelain
 M app/src/mvvm/services/tool_runtime.py
?? app/src/mvvm/services/glob_match.py
?? app/src/mvvm/services/image_prep.py
?? app/src/mvvm/services/office_text.py

$ git branch -vv
* develop 9548898 [origin/develop: ahead 8]
```

远端关系：`origin` = `git@github.com:fanchcho/ai_upper.git`；`upstream` 为旧远端，只读。
远端 `main` = `f91562b`；本地工作分支 `develop`。

本轮完成的可提交单元：

1. 工具全集 + 图片/Office 分支 + 待办清单接入（§1.9，commit `e4b1ed1`）；
2. Qt 页面收尾：工具卡 / 内联图片 / 待办胶囊（§1.10，commit `044cda0`）。

台账在每个单元后刷新，保证任何时刻被截断都能凭台账续上。

**当前状态（真实命令输出）：**

```text
$ git log --oneline -3
044cda0 feat(ui): 工具卡 / 内联图片 / 待办胶囊，历史重开后保留工具名与图片
e4b1ed1 feat(tools): 工具全集（10 个）+ read_file 图片/Office 分支 + todo_write 接入会话
9548898 feat(ui): 主窗口三栏装配：会话列表、聊天面板、设置页

$ git branch -vv
* develop 044cda0 [origin/develop: ahead 10]
  main    f91562b [upstream/main] Initial commit

$ git status --porcelain
 M docs/BUILD-PROGRESS.md
?? audit-tools/screenshot_app.py
?? audit-tools/verify_demo_page.py
?? audit-tools/xvfb_run.py
?? out/
```

**本轮中断点（若被截断从这里续）：** 工具层、Qt 页面（工具卡 / 图片 / 待办胶囊）均已提交并全绿。
尚未完成：158 通道结论表、打包入口指向 `deva_app` 并真实构建、最终中文报告落盘。

---

## 1 档一：已实现并验证

### 1.1 远端接入与工程基础

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 1 | 新远端 `origin` = `git@github.com:fanchcho/ai_upper.git`，本地 `develop` 跟踪 `origin/develop` | `git remote -v`、`git branch -vv`（见 §0） |
| 2 | 不强推、不 rebase 覆盖远端；`upstream` 不推不改 | 全程只用 `git commit`；`origin/develop` 仅依赖快进合并（本轮尚未推送，本地 ahead 6） |
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

---

## 2 档二：已实现未验证

| 项 | 现状 | 为什么没验证 / 怎么验证 |
|---|---|---|
| 真实网络调用（Anthropic / OpenAI / Responses） | 适配器与装配线都完整，事件流解析有离线测试 | **无可用密钥**，本环境也不保证出网。接上密钥后跑一次真实请求即可确认；绝不以离线测试冒充真实成功 |
| `web_fetch` 真实抓网页 | 只测了非 http 拒绝、缺 url、HTML→文本；无真网络用例 | 同上（不出网）。离线可测的部分已覆盖 |
| 真实窗口（有 X/Wayland）下的人工观感 | 只跑了 offscreen（`/tmp/shots1/*.png`，1080×720 真实渲染） | 容器无显示服务器。可 `xvfb-run` 再截一次；真人手感（滚动、字体、DPI）无法在容器验证 |
| 打包后产物能起新应用入口 | 本轮补齐入口与构建（§3.4），产物能跑 | 只在容器（linux-arm64）构建过；Windows/macOS 打包未验证 |
| 流式刷新在真窗口里的观感（40ms 节流） | 逻辑与假控件都有测试 | 需要长回复 + 真人观察；offscreen 能跑但看不出手感 |

## 3 档三：未实现（原因与阻塞）

| 项 | 原因 | 风险 |
|---|---|---|
| 158 通道逐条结论表 | 本轮未完成 | 迁移契约尚未闭环；`docs/MIGRATION-PLAN.md` 仍是逐条清单，没有判定列 |
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

## 5. 下一轮入口

当前起点：全量 `772 passed / 5 skipped`；`origin/develop` 落后本地 `10` 个 commit（未推送）。

1. 158 通道结论表（唯一硬缺口）：重写项给「通道 → 新实现文件:行号 → 覆盖测试」；
   44 条待定逐条判定；82 条丢弃给替代路径。
2. 打包：入口指向 `deva_app` 并实际构建一次（linux-arm64 跑通后，Windows/macOS 仍未验）。
3. 工作区挂载交互轮（对齐 Deva 的挂载卡），完成后才能谈子智能体类工具。
4. 真实密钥接上后跑一次三协议真实请求，把 §2 第一行落到档一。
