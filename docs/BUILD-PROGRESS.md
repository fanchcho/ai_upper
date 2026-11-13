# 构建进度台账（每轮更新）

> 规则：只写**实际跑出来的**结果。命令与输出都是真的；没跑过的一律归入「已实现未验证」或
> 「未实现」，不许把没跑通的说成跑通。
> 最近更新：2026-11-13（第二阶段：压缩模块 + 真实 provider 适配器；续跑轮）

## 0. 本轮起点（续跑对账）

上一轮在 1 小时上限处被系统中断，中断时全量测试已跑通 `613 passed, 5 skipped`，但**没有**
产生最终交付报告。本轮从磁盘现状续跑，起点如下（真实命令与输出）：

```text
$ git log --oneline -6
ec9a7ad feat(provider): 三协议真实适配器 + SSE/传输层 + 模型引用解析
99fdb2c feat(secrets): 密钥存储改「钥匙串优先 + AES-GCM 加密文件回退」，并补 config.json 服务
2787a00 docs: 台账补齐 commit 列表
145b431 chore: 清理未使用的 import 与动态 import
c70b0ec docs: 构建进度台账
2f8fb17 fix(build): 模板 dependencies 恢复为空，应用依赖只写 app/requirements.txt

$ git status --porcelain
 M app/src/mvvm/services/chat_session_store.py
 M app/tests/test_chat_session_store.py
?? app/src/mvvm/services/compaction.py
?? app/src/mvvm/services/context_window.py
?? app/src/mvvm/services/model_view.py
?? app/src/mvvm/services/repetition.py
?? app/src/mvvm/services/todos.py
?? app/tests/test_compaction.py
?? app/tests/test_context_window.py
?? app/tests/test_model_view_and_todos.py

$ git branch -vv
* develop ec9a7ad [origin/develop] feat(provider): 三协议真实适配器 …
  main    f91562b [upstream/main] Initial commit

$ git rev-list --left-right --count origin/develop...HEAD
0       0        # 本地 develop 与 origin/develop 完全同步（上一轮已推）
```

远端关系：`origin` = `git@github.com:fanchcho/ai_upper.git`（本轮接入的新远端），
`upstream` = `git@github.com:upper-endcomputer/py_upper.git`（旧远端，**只读参考，不推不动**）。
远端 `main` = `f91562b`（Initial commit）。本地工作分支是 `develop`，已跟踪 `origin/develop`。

**未提交改动**：压缩子系统（`compaction.py` + 4 个叶子模块 + 3 个测试文件 + 会话存储的
`.jsonl` 拆分写出）。这部分已在上一轮写完并通过测试，本轮第一条 commit 就是它。

---

## 1 档一：已实现并验证

### 1.1 远端接入与工程基础

| # | 项 | 验证方式（真实输出） |
|---|---|---|
| 1 | 新远端 `origin` = `git@github.com:fanchcho/ai_upper.git`，本地 `develop` 跟踪 `origin/develop` | `git remote -v`、`git branch -vv`（见 §0） |
| 2 | 不强推、不 rebase 覆盖远端；`upstream` 不推不改 | `git rev-list --left-right --count origin/develop...HEAD` → `0 0`（快进关系） |
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

### 1.5 本轮新增：上下文压缩子系统（未提交，见 §0）

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

---

## 2 档二：已实现未验证

| 项 | 现状 | 为什么没验证 / 怎么验证 |
|---|---|---|
| 真实网络调用（Anthropic / OpenAI / Responses） | 适配器代码完整，事件流解析有离线测试 | **无可用密钥**，本环境也不保证出网。接上密钥后跑一次真实请求即可确认；绝不以离线测试冒充真实成功 |
| 真实窗口（有显示服务器）下的人工交互 | 只跑了 offscreen | 容器无 X/Wayland。真控件 + 真信号已覆盖装配与绑定；可 `xvfb-run` 截图 |
| 打包后的应用能起新应用入口 | 未跑 | 打包入口仍指向旧 `main.py`；改入口是破坏性变更，待确认后执行 |
| `read_file` 的图片 / Office 分支 | 未实现（仅文本） | 需 Pillow / docx 等依赖；工具描述已声明只读文本 |
| 会话列表、设置页界面 | 未做 | 界面在后续阶段 |

## 3 档三：未实现（原因与阻塞）

| 项 | 原因 | 风险 |
|---|---|---|
| 压缩接进对话循环 | 压缩模块本身已可用，但 `ChatViewModel` 还没调用 `compact_session` | 长对话不会自动压缩；接线是纯逻辑改动，下一步就做 |
| 真实 provider 替换 `FakeProvider` | `DevaApplication` 仍装配 `FakeProvider` | 应用起来后不能真聊；需要配置 + 密钥 + 模型解析三件套 |
| 逐字流式刷新界面 | 回合同步跑 | 长回复界面卡住；`run_turn()` 已是异步入口 |
| 会话列表/设置/工具卡片/状态栏页面 | 未做 | 只有单窗口最小聊天界面 |
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

## 5. 下一轮入口

1. 提交压缩子系统（当前未提交改动）。
2. 压缩接进对话循环：轮首 `needs_compaction` → `compact_session`；轮中 `needs_compaction_mid_turn`；
   手动 `/compact`；压缩提示进 transcript。
3. 真实 provider 装配：`SettingsService` + `SecretsVault` + `model_resolve` → `provider_registry.build_provider`。
4. 流式刷新（工作线程 + Qt 信号）。
5. Qt 页面：会话列表 / 设置 / 工具卡片 / 状态栏。
