# 第六阶段收尾报告（ai_upper ← Deva 迁移续跑）

日期：2026-11-14　文档：`docs/STAGE6-CLOSEOUT-REPORT.md`　分支：`develop`　HEAD：`abd6e1f`

本轮三件事：① 打包链路接通并真跑；② 台账刷新；③ 全量测试。三件均已落盘并提交。

---

## 一、三档清单（每项附验证方式）

### 档一：已实现并验证

| # | 项 | 验证方式（可复现） |
|---|---|---|
| 1 | 打包产物起的是 `DevaWebWindow`，不是模板窗口 | `tools/build.py build --target linux-arm64` → `EXIT=0`；`strings dist/ai_upper/ai_upper \| grep -c "from deva_web import main"` → `1`；构建日志 `PASS entry module Cythonized: deva_web`（入口已于 2026-11-15 收敛到 `app/src/main.py`：同一命令现在为 `from main import main` → `1`、`PASS entry module Cythonized: main`，见 `docs/BUILD-PROGRESS.md` §1.16） |
| 2 | 产物含 QtWebEngine 运行载荷 | `find dist/ai_upper \( -name '*QtWebEngineCore*' -o -name '*QtWebChannel*' -o -name 'QtWebEngineProcess' \)` → 3 条；helper 权限 `-rwxr-xr-x` |
| 3 | 产物含原版渲染层，且与源逐文件一致 | `diff -rq app/assets/renderer dist/ai_upper/assets/renderer` → `IDENTICAL` |
| 4 | 产物含角色种子资产 | `ls dist/ai_upper/assets/personas` → `general.md` 等 |
| 5 | 产物 headless 真起界面、桥对象在位 | `DEVA_HOME=/tmp/pack-smoke DEVA_APP_HEADLESS=1 QT_QPA_PLATFORM=offscreen ./dist/ai_upper/ai_upper` → `DEVA WEB OK platform=offscreen title='Deva' url=…/assets/renderer/index.html bridge=True`，`EXIT=0` |
| 6 | Chromium locale pak 不再被裁掉 | `ls dist/ai_upper/site-packages/PySide6/Qt/translations/qtwebengine_locales \| wc -l` → `53`；启动日志无 `could not find the translation file` |
| 7 | 158 通道逐条结论表（机器生成） | `docs/audit/IPC-158-LEDGER.md`：158 行，通过 60 / 已知差异 5 / 不适用 0 / 未实现 93；桥内注册 64 条；每行有 `文件:行号` 与测试名 |
| 8 | 写路径（对话/设置）在真窗口里可用 | §1.12；实跑日志 `out/e2e-live/logs/{model,tools,abort,reload}.log` |
| 9 | 界面七页与原版逐页一致 | `scripts/parity/compare.sh`：七页 `fuzz3 = 1`、`maxd = 9`，全部「已一致」（见第三节） |
| 10 | 依赖声明不再漏 | 新增 `test_every_third_party_import_is_a_declared_runtime_dependency()`（AST 扫描），全绿 |

### 档二：已实现未验证

| # | 项 | 为什么没验证 / 怎么验证 |
|---|---|---|
| 1 | Windows / macOS 打包产物 | 本轮只构建并启动 linux-arm64。同一套 `package()` / `qt_prune` 有单测覆盖两平台布局，但没有真产物证据——不拿 linux 结果冒充 |
| 2 | 真实网络调用（Anthropic / OpenAI / Responses） | 无可用密钥，环境不保证出网；离线测试只覆盖事件流解析 |
| 3 | `web_fetch` 真抓网页 | 同上 |
| 4 | 真桌面观感（真显卡 / HiDPI / Wayland） | 容器只有 Xvfb 软渲染，截图结论只对 `1400x900x24 + 软渲染` 成立 |
| 5 | `titleBarOverlay` 按钮真实生效（最小化/最大化/关闭） | 几何与配色有单测，但 Xvfb 无窗口管理器 |
| 6 | 深色主题七页对比 | 只实拍浅色七页 |
| 7 | 流式刷新手感（40ms 节流） | 需长回复 + 人眼观察 |
| 8 | 自定义技能的排序（非 ASCII 名） | `casefold()` 与 ICU `localeCompare` 在中文名上可能不同，未实拍 |

### 档三：未实现

| # | 项 | 原因 | 风险 |
|---|---|---|---|
| 1 | 158 条里未实现的 93 条 | 桥里没有注册，调用显式 reject（`UnimplementedChannel`），不假成功。分域见第四节 | 内置浏览器、MCP、终端、git、飞书/Telegram 等整域不可用 |
| 2 | 工作区挂载交互轮 | `DEVA_APP_WORKSPACE` 启动时定死 | 运行中不能换工作区 |
| 3 | 子智能体 / `task` 类工具（19 个里的 9 个） | 依赖挂载与多轮编排 | 模型退化为单轮 |
| 4 | 真机人工验收（键盘焦点、IME、拖拽） | 容器无显示服务器 | 只能由人验 |

---

## 二、第 1 件：打包链路（本轮真正做出来的东西）

### 2.1 入口与资产

- 新增 `app/src/deva_web.py`：薄入口，装配 `SettingsService` / `PersonaStore` /
  `ChatSessionStore` / `SecretsVault` 后起 `DevaWebWindow`。`main.py` / `application.py`
  的模板语义**未改**。（2026-11-15 后续：该薄入口整段并入 `app/src/main.py` 并删除，
  见 `docs/BUILD-PROGRESS.md` §1.16。）
- `[tool.ai_upper] entry = "deva_web.py"`（`app/pyproject.toml.example` 与本地 `app/pyproject.toml`）。
  该值现为 `entry = "main.py"`。
- `tools/ai_upper/package.py` 的 `_copy_supporting_trees()` 在 `resources` 之外新增 `app/assets`；
  linux/windows 落 bundle 根，macOS 落 `Contents/Resources`。
- `app/src/utils/paths.py` 新增 `assets_root()`：以 launcher 导出的 `AI_UPPER_HOME`
  为准 → `_project_root()` → `sys.executable` 目录。不再用 `parents[3]`（Cython 合并 + egg 后不可靠）。

### 2.2 构建命令与产物

```text
$ cd /home/agent/shared_workspace/py_upper && PATH=/tmp/ninja-bin:/tmp/buildtools/patchelf/bin:$PATH \
    AI_UPPER_PYTHON=/home/agent/shared_workspace/py_upper/.venv/bin/python-real \
    .venv/bin/python tools/build.py build --target linux-arm64
[1/6] Runtime + SDK
[2/6] Third-party dependencies
Third-party optimization: removed 559 files and 36 directories
[3/6] Target launcher
[4/6] Package + native dependency closure
[5/6] Static verification
SMOKE PASS 5 modules (launcher registers merged bundles)
[6/6] Target runtime smoke
SMOKE PASS launcher
READY: /home/agent/shared_workspace/py_upper/dist/ai_upper
EXIT=0
```

产物：**`/home/agent/shared_workspace/py_upper/dist/ai_upper`**（499 MB）。
完整日志 `/home/agent/shared_workspace/py_upper/out/packaging/build8.log`。

### 2.3 产物内容核对（原始输出）

```text
$ find dist/ai_upper \( -name '*QtWebEngineCore*' -o -name '*QtWebChannel*' -o -name 'QtWebEngineProcess' \) | sort
dist/ai_upper/site-packages/PySide6/Qt/libexec/QtWebEngineProcess
dist/ai_upper/site-packages/PySide6/QtWebChannel.abi3.so
dist/ai_upper/site-packages/PySide6/QtWebEngineCore.abi3.so

$ diff -rq app/assets/renderer dist/ai_upper/assets/renderer && echo IDENTICAL
IDENTICAL

$ ls dist/ai_upper/assets
personas
renderer

$ strings dist/ai_upper/ai_upper | grep -c "from deva_web import main"
1
```

完整输出 `/home/agent/shared_workspace/py_upper/out/packaging/bundle-check8.log`。

### 2.4 产物启动（headless / offscreen）

```text
$ rm -rf /tmp/pack-smoke && mkdir -p /tmp/pack-smoke
$ DEVA_HOME=/tmp/pack-smoke DEVA_APP_HEADLESS=1 QT_QPA_PLATFORM=offscreen timeout 180 ./dist/ai_upper/ai_upper
…
DEVA WEB OK platform=offscreen title='Deva' url=/home/agent/shared_workspace/py_upper/dist/ai_upper/assets/renderer/index.html bridge=True
EXIT=0
```

日志里仍可见的两条**非致命**输出：`Failed to connect to the bus … /run/dbus/system_bus_socket`
（容器无 D-Bus）、`GPUInfo not initialized on GpuInfoUpdate`（`--disable-gpu` 下常规提示）。
完整日志 `/home/agent/shared_workspace/py_upper/out/packaging/launch8.log`。

### 2.5 真跑产物才暴露的 4 个缺陷（源码态测试全绿；均已修 + 回归测试）

| # | 缺陷 | 现象 | 修复 |
|---|---|---|---|
| 1 | pydantic × Cython 方法类型 | 产物一启动 `PydanticUserError: A non-annotated attribute was detected: text = <cyfunction …>` | `chat_models._Model.model_config` 加 `ignored_types=_method_types()` |
| 2 | `QtWebEngineProcess` 丢 execute 位 | `LaunchProcess: failed to execvp: …/QtWebEngineProcess`，窗口空白 | `third_party._apply_wheel_mode()` 按 wheel `external_attr` 补 execute 位；测试 `test_wheel_execute_bits_survive_extraction` |
| 3 | Chromium locale pak 被当 Qt 翻译删掉 | 每次启动 `could not find the translation file for the current locale: en-US.pak` | `qt_prune` 把 `qtwebengine_locales` 按 `QtWebEngineCore` 归属判定，单独走允许清单（`zh_CN`↔`zh-CN` 归一，`en-US` 恒留）；3 条回归测试 |
| 4 | `httpx` 未声明为运行依赖 | 产物装配阶段 `ModuleNotFoundError: No module named 'httpx'` | `pyproject.toml` + `requirements.txt` 补 `httpx==0.28.1`；新增 AST 扫描防回归测试 |

第 4 条的失败发生在更早一次启动，原始日志未落盘（只有终端输出），已在台账 §1.14.5 如实注明。

---

## 三、逐页一致性判定与并排截图

判定口径（`scripts/parity/compare.sh`）：`fuzz3 ≤ 1 且 maxd ≤ 10 → 已一致`。

| 页面 | 原版截图（绝对路径） | 移植版截图（绝对路径） | raw | fuzz3 | maxd | 判定 |
|---|---|---|---|---|---|---|
| 01 首启页 | `/home/agent/shared_workspace/py_upper/out/parity/deva/01-first-run.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/01-first-run.png` | 409 | 1 | 9 | 已一致 |
| 02 设置 › 通用 | `/home/agent/shared_workspace/py_upper/out/parity/deva/02-settings-general.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/02-settings-general.png` | 241599 | 1 | 9 | 已一致 |
| 03 设置 › 模型 | `/home/agent/shared_workspace/py_upper/out/parity/deva/03-settings-models.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/03-settings-models.png` | 241446 | 1 | 9 | 已一致 |
| 04 设置 › 扩展 | `/home/agent/shared_workspace/py_upper/out/parity/deva/04-settings-extensions.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/04-settings-extensions.png` | 241527 | 1 | 9 | 已一致 |
| 05 设置 › 关于 | `/home/agent/shared_workspace/py_upper/out/parity/deva/05-settings-about.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/05-settings-about.png` | 241398 | 1 | 9 | 已一致 |
| 06 关闭设置后主界面 | `/home/agent/shared_workspace/py_upper/out/parity/deva/06-after-settings.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/06-after-settings.png` | 409 | 1 | 9 | 已一致 |
| 07 对话页（带 fixture） | `/home/agent/shared_workspace/py_upper/out/parity/deva/07-chat.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/07-chat.png` | 14033 | 1 | 9 | 已一致 |

四项交互实跑截图（原版窗口 + 真渲染层 + 真 provider）：

- 切模型：`/home/agent/shared_workspace/py_upper/out/e2e-live/01-model-before.png`、
  `/home/agent/shared_workspace/py_upper/out/e2e-live/02-model-after.png`
- 工具审批：`/home/agent/shared_workspace/py_upper/out/e2e-live/03-tool-inside.png`、
  `/home/agent/shared_workspace/py_upper/out/e2e-live/04-tool-outside.png`
- 中断：`/home/agent/shared_workspace/py_upper/out/e2e-live/05-abort-streaming.png`、
  `/home/agent/shared_workspace/py_upper/out/e2e-live/06-abort-just-done.png`、
  `/home/agent/shared_workspace/py_upper/out/e2e-live/07-abort-settled.png`
- 重载：`/home/agent/shared_workspace/py_upper/out/e2e-live/08-reload.png`

原始日志：`/home/agent/shared_workspace/py_upper/out/e2e-live/logs/{model,tools,abort,reload}.log`。

---

## 四、158 条分组条数

总数 **158 = 通过 60 + 已知差异 5 + 不适用 0 + 未实现 93**（桥内注册 64 条）。

| 域 | 通道数 | 通过 | 已知差异 | 未实现 |
|---|---|---|---|---|
| `chat:` | 31 | 18 | 0 | 13 |
| `git:` | 24 | 0 | 0 | 24 |
| `browser:` | 16 | 0 | 3 | 13 |
| `remote:` | 10 | 0 | 1 | 9 |
| `mcp:` | 9 | 0 | 0 | 9 |
| `fs:` | 9 | 9 | 0 | 0 |
| `tasks:` | 8 | 0 | 0 | 8 |
| `personas:` | 8 | 8 | 0 | 0 |
| `window:` | 5 | 5 | 0 | 0 |
| `skills:` | 6 | 5 | 0 | 1 |
| `terminal:` | 5 | 0 | 0 | 5 |
| `secrets:` | 5 | 5 | 0 | 0 |
| `update:` | 4 | 0 | 1 | 3 |
| `memory:` | 4 | 0 | 0 | 4 |
| `deliverables:` | 4 | 0 | 0 | 4 |
| `config:` | 3 | 3 | 0 | 0 |
| `profile:` | 3 | 3 | 0 | 0 |
| `clipboard:` | 2 | 2 | 0 | 0 |
| `provider:` | 1 | 1 | 0 | 0 |
| `app:` | 1 | 1 | 0 | 0 |
| **合计** | **158** | **60** | **5** | **93** |

逐条明细（入参/出参/原版位置/移植位置/测试/实测结果）：`docs/audit/IPC-158-LEDGER.md`。

---

## 五、本轮新增 commit

```text
bbb0f5a chore(evidence): 落盘打包与全量测试原始日志
0293c9c docs: 第六阶段收尾报告（三档清单 + 158 条分组 + 逐页判定 + 全量测试原始输出）
abd6e1f docs: 台账刷新到打包实测（新增 §1.14，三档与下一轮起点按现状重写）
9384804 feat(package): 打包产物起真实 Web 界面，入口切到 deva_web
```

（本报告与上方 `bbb0f5a` 这两条 docs/evidence 提交即本轮收尾；`9384804` 是代码提交。）

---

## 六、全量测试原始输出

```text
$ cd /home/agent/shared_workspace/py_upper/app && ../.venv/bin/python -m pytest -q -rs
........................................................................ [  7%]
...
938 passed, 6 skipped in 22.66s

$ PATH=/tmp/buildtools/patchelf/bin:$PATH ../.venv/bin/python -m pytest -q -rs
...
939 passed, 5 skipped in 22.86s
```

两次差别只有一条：`test_native_deployment.py:177`（`requires cc, patchelf and readelf`）
找不到 `patchelf` 时跳过；把 `patchelf` 放进 `PATH` 后变绿。构建机本来就要求 `patchelf`，
**以 939 passed / 5 skipped 为基线**。

剩下 5 条 skip 的原文：

```text
SKIPPED [1] tests/test_build_tool_compat.py:1615: the auto-link pragma belongs to the Windows pyconfig.h
SKIPPED [1] tests/test_build_tool_compat.py:1669: handle inheritance for GUI-subsystem children belongs to Windows
SKIPPED [1] tests/test_e2e_local.py:447: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_e2e_local.py:488: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_web_e2e_stream.py:131: 端到端实跑需要真 provider：设 DEVA_E2E_PROVIDER=1 并提供 ANTHROPIC_BASE_URL / ANTHROPIC_API_KEY / ANTHROPIC_MODEL（或 DEVA_E2E_* 同名变量）
```

原始日志：`/home/agent/shared_workspace/py_upper/out/packaging/pytest-full.log`、
`/home/agent/shared_workspace/py_upper/out/packaging/pytest-full-patchelf.log`。

**没有为了变绿做任何跳过或注释。** 两条 E2E skip 与一条 provider skip 需要外部条件
（完整构建开关、真密钥），本轮不具备，如实保留。

---

## 七、约束遵守情况

- `/home/agent/shared_workspace/deva` 全程只读，未写入任何文件。
- 未 force push；本轮只做本地 commit（远端同步不在本轮范围）。
- 未通过跳过测试 / 注释代码让检查变绿：本轮新增 10 条测试（资产定位 2、依赖声明 1、
  产物资产拷贝 1、WebEngine helper 归属 2、WebEngine locale 裁剪 3、解包 execute 位 1），
  全部真跑。
- 密钥未以明文出现在命令、日志或测试参数中（真实 provider 类测试全部 skip）。
