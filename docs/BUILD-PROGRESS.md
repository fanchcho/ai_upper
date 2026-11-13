# 构建进度台账（每轮更新）

> 规则：只写**实际跑出来的**结果。命令与输出都是真的；没跑过的一律归入「已实现未验证」或
> 「未实现」，不许把没跑通的说成跑通。
> 最近更新：2026-11-13（第三阶段：压缩接线、真实 provider 装配、流式刷新与停止）

## 0. 本轮起点（续跑对账）

上一轮在 1 小时上限处被系统中断，中断时全量测试 `613 passed / 5 skipped`，正在接压缩。

本轮（第三阶段）起点：

```text
$ git log --oneline -8
50e4459 feat(chat): 压缩接进对话回合，回合移入后台线程并加事件队列
7738aab feat(compaction): 上下文压缩与 .jsonl 拆分存盘
a7a39c9 docs: 台账按三档重写
ec9a7ad feat(provider): 三协议真实适配器
...

$ git status --porcelain
 M app/src/deva_app/__main__.py
 M app/src/mvvm/view_models/chat_vm.py
?? app/src/mvvm/services/provider_setup.py
?? app/tests/test_provider_setup.py

$ git branch -vv
* develop 50e4459 [origin/develop: ahead 3]
```

远端关系：`origin` = `git@github.com:fanchcho/ai_upper.git`；`upstream` 为旧远端，只读。
远端 `main` = `f91562b`；本地工作分支 `develop`。

本轮完成两个可提交单元并各有一条 commit：真实服务商装配（§1.7）、流式刷新与停止（§1.8）；
台账在每个单元后刷新，保证任何时刻被截断都能凭台账续上。

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


---

## 2 档二：已实现未验证

| 项 | 现状 | 为什么没验证 / 怎么验证 |
|---|---|---|
| 真实网络调用（Anthropic / OpenAI / Responses） | 适配器与装配线都完整，事件流解析有离线测试 | **无可用密钥**，本环境也不保证出网。接上密钥后跑一次真实请求即可确认；绝不以离线测试冒充真实成功 |
| 真实窗口（有显示服务器）下的人工交互 | 只跑了 offscreen | 容器无 X/Wayland。真控件 + 真信号已覆盖装配与绑定；可 `xvfb-run` 截图 |
| 打包后的应用能起新应用入口 | 未跑 | 打包入口仍指向旧 `main.py`；改入口是破坏性变更，待确认后执行 |
| `read_file` 的图片 / Office 分支 | 未实现（仅文本） | 需 Pillow / docx 等依赖；工具描述已声明只读文本 |
| 流式刷新在真窗口里的观感（40ms 节流） | 逻辑与假控件都有测试 | 需要真 Qt 事件循环 + 长回复；offscreen 下可跑脚本截图，真人手感无法验证 |

## 3 档三：未实现（原因与阻塞）

| 项 | 原因 | 风险 |
|---|---|---|
| 会话列表/设置/工具卡片/状态栏页面 | 未做 | 只有单窗口最小聊天界面；设置页是「改模型/密钥下一轮生效」的唯一入口 |
| 工具全集与权限确认 | 只有 `read_file` + 允许/拒绝 | 模型只能读文本 |
| 158 通道逐条结论表 | 未做 | 迁移契约没有闭环 |
| 打包入口指向新应用 | 未改 | 打出来的仍是旧应用 |

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

## 5. 下一轮入口

当前起点：全量 `634 passed / 5 skipped`；`origin/develop` 落后本地 `6` 个 commit（未推送）。

1. Qt 页面：会话列表（新建/切换/改名/删除/归档）、设置页（服务商/模型/密钥/BaseURL + 拉模型清单）、
   工具卡片、状态栏。ViewModel 侧的后端能力（`ChatSessionStore`、`SettingsService`、`SecretsVault`、
   `ModelGateway`、`provider_registry.list_models`）都已具备，只差界面与命令。
2. 工具全集与权限确认：按 `tools.ts` 的 19 个工具名逐一对位，`write_file` / `run_command` 之类
   必须走权限确认。
3. `read_file` 图片分支（Pillow）与 Office 分支（docx），加依赖前先评估能否自己解析 zip XML。
4. 158 通道结论表：重写项给「通道 → 新实现文件:行号 → 覆盖测试」；44 条待定逐条判定；82 条丢弃给替代路径。
5. 打包入口指向 `deva_app` 并实际构建。
