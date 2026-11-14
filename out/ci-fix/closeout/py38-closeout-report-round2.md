# windows-x86_64 3.8.10 收尾报告（第二轮）

本报告取代上一版 `py38-closeout-report.md` 里「**是**：…已修好」的结论——那一版与
远端实际结果不符，见 `py38-authoritative-run-failure.md`。

提交序列（本轮，均已推送 develop）：
`158a36c` fix(py38) → `c49161b` build(py38) → `28aeec5` test(py38) →
`289749b` chore(evidence) → `d44fac5`/`b7d00c2` docs/evidence 补正。

## 一句话结论

**还没有真绿。** 上一轮「已转绿」的结论是错的（权威 run `43600186928` / commit
`7476558` 的 3.8.10 job `132463066925` 在 `[6/6]` 失败）；本轮修掉三处真实缺陷后，
新权威 run `43605493485`（commit `617427a`）的 3.8.10 job **推进到了 `[4/6]`**，
在那里因 `Qt6WebEngineCore.dll: BluetoothApis.dll` 未解析而失败。该缺口已定位、
修复（`BluetoothApis.dll` 是 System32 的 Web Bluetooth 实现，6.6.3 载入期直接导入，
6.11.2 已不再导入），本地真 3.8.20 验证与守卫用例均通过，但**修复本身还没跑过一次
真实 CI**，所以在拿到新 run 的终态之前不声称转绿。

## 1. 上一版为什么错

| 上一版的说法 | 实际 |
|---|---|
| 「3.8.10 四处运行期兼容缺陷已修好，leg 已转绿」 | run `43600186928` 结论 **failure**；3.8.10 job 在 `[6/6]` 失败 |
| HEAD `bccaee8` | 实际 `7476558` |
| pytest 985 / 984 | 实际 988 / 987（新增 3 条守卫用例） |
| 有「逐 job 结论表」 | 文末为空 |

上一轮修的四类缺陷（`typing.Annotated`、PEP 585 模块级赋值、PEP 604 模块级联合、
`str.removesuffix`）**都是真的**，也都被守卫用例锁住了（见第 7 节变异记录）。但它们
只覆盖到「解释器能导入模块」这一层；打包产物冒烟是在**另一层**失败的，上一轮没有跑
到判决点就下了结论。

## 2. 本轮的真实缺陷

计三处：前两处（2.1、2.2）是上一轮漏掉的、在权威 run `43600186928` 的 `[6/6]`
暴露的运行期问题；第三处（2.4）是本轮修完之后，新 run `43605493485` 在 `[4/6]`
暴露的原生依赖闭包缺口。

### 2.1 `QWebEngineScript` 落在哪个子模块，随 binding 变

`web_shell_window.py` 类体直接写死 `QtWebEngineCore.QWebEngineScript`：

- Qt6（PySide6）：`QWebEngineScript` / `QWebEngineSettings` 在 `QtWebEngineCore`，
  `QWebEngineView` 在 `QtWebEngineWidgets`；
- Qt5（PySide2）：这三个类**全部**在 `QtWebEngineWidgets`，`QtWebEngineCore` 只有
  `QWebEngineCookieStore` / `QWebEngineHttpRequest` / `QWebEngineUrlRequest*` 那一批。

于是只要那条 leg 用 PySide2，`import mvvm.views.web_shell_window` 就在类体求值阶段抛
ImportError，冒烟直接失败。修复：`_webengine_class(name)` 按名字在两个子模块里探测，
都没有时抛 ImportError（不返回 None，避免把缺件推迟到更远处才炸）；捕获
`(AttributeError, ImportError)`，因为 Qt 的模块代理对缺失名字抛的是 ImportError。

### 2.2 `runJavaScript` 对布尔值的转换随版本变

readiness 探测原本执行 `!!(window.deva && window.deva.chat)` 并直接按真假判断：

- PySide6 6.6.3：JS `true` 回来是**空串** `''`；
- PySide6 6.11.2：回来是 `True`；
- PySide2 同样不给 bool。

在 6.6.3 上，这条探测即使 shim 正常也永远读不到 `True`，冒烟打印
`bridge=`（空）并退出 1。修复：JS 侧改为 `String(!!(...))`，Python 侧比 `"true"`。

### 2.3 顺带堵死一条「假绿」路径

若为了让类体导入成功而回退到 PySide2：PySide2 5.15 自带 **Chromium 83**，而渲染产物
的 URL 净化路径无保护地用了 `Object.hasOwn`（ES2022，Chromium 93+）。那条路下冒烟
标记（只依赖 shim.js）会打印 OK，应用却在渲染链接时才抛错。所以矩阵改用
**PySide6 6.6.3**（最后一个发布 cp38 wheel 的版本，自带 Chromium 122），而不是 PySide2。

### 2.4 PySide6 6.6.3 的 `Qt6WebEngineCore.dll` 直接导入 `BluetoothApis.dll`

修好 2.1/2.2 之后，新 run `43605493485` 的 3.8.10 job（`132479119483`）**推进到了
`[4/6] Package + native dependency closure`**，在那里失败，注解原文只有一行：

```
ERROR: RuntimeError: Unresolved native dependencies:
  site-packages\PySide6\Qt6WebEngineCore.dll: BluetoothApis.dll
```

`BluetoothApis.dll` 是 Windows 自带的 Web Bluetooth 实现（System32），6.6.3 这一代
Chromium 在**载入期**导入它（不是 delay-load）。`WINDOWS_HOST_LIBRARIES` 里没有它，
闭包就把它当成 wheel 内应有的负载而报未解析。

验证（证据 `out/ci-fix/verify-round3/bluetoothapis-closure.log`，直接读 PE 导入表）：

- 把 6.6.3 的四个 win_amd64 wheel（`PySide6` / `Essentials` / `Addons` / `shiboken6`，
  338 个原生镜像）全解出来算闭包，未解析项里确实有 `BluetoothApis.dll`；
- **6.11.2**（`app/requirements.txt` 的 pin，其余七条 leg 用的就是它）的
  `Qt6WebEngineCore.dll` 已不再导入它——所以只有 3.8.10 这条 leg 会撞上；
- 因此把它加进 `WINDOWS_HOST_LIBRARIES`（与已有的 `hid.dll` / `winusb.dll` 同类：
  OS 自己维护的实现，打包一份等于发一个旧的），并补守卫用例
  `test_windows_web_bluetooth_is_system_provided`（x86_64/arm64 为真、Linux/macOS 为假，
  且闭包为空）。

同一份日志里还能看到另外 18 个未解析项，它们全部落在 `qt = "imports"` 会剪掉的
可选插件里（sqldrivers 的 Mimer/PostgreSQL、multimedia 的 ffmpeg 插件、
QtQuick Controls 样式、VirtualKeyboard）：Windows runner 上 prune 生效，
CI 注解只有 `BluetoothApis.dll` 这一行，正好证明其余项在目标机上已被剪掉。
本机是 Linux、跑不了 windows-x86_64 的目标解释器，`qt_prune` 返回 None 保留全量，
所以这 18 项才会出现在本机日志里。

## 3. 依赖闭包（真 3.8 实跑）

证据：`out/ci-fix/verify-7476558/py38-dependency-resolution.log`

- 真 CPython 3.8.20 venv 上 `pip install --dry-run --ignore-installed` 六个 pin 全部
  可解析，`Would install` 列表完整，`A_EXIT=0`；
- pydantic 2.10.6 声明的下界是 `typing-extensions>=4.12.2`，矩阵钉 4.13.2，满足；
- `typing_extensions` 4.13.2 的 `Requires-Python` 是 `>=3.8`，4.14.0 起是 `>=3.9`，
  所以 4.13.2 正是 3.8 侧的上限；
- 3.13 侧 `app/requirements.txt` 里该行带 `python_version < "3.9"` 标记，pip 明确
  `Ignoring typing_extensions: markers ... don't match`，由 pydantic 2.14.3 拉
  `typing-extensions>=4.16.0`（实解析到 4.16.0）。两边的门都通。

## 4. 3.8 全量 import 清扫（第三方缺件单列）

证据：`out/ci-fix/verify-round3/py38-import-sweep.log`（本轮重跑，改动的
`tools/ai_upper/native/deps.py` 也在真 3.8 上单独验过：
`out/ci-fix/verify-round3/py38-tools-import.log`）

用真 CPython 3.8.20 遍历 `app/src` 下 78 个模块：

```
modules scanned: 78
IMPORT OK: 78
THIRD-PARTY MISSING (not counted as compat failures): 0
COMPAT FAILURES: 0
```

分类器在 3.8 上可用（`sys.stdlib_module_names` 是 3.10+，不能用）：模块名能解析到
`app/src` 下的文件/目录就算自有代码，否则算第三方。脚本内自带负对照
（`keyring` 必须被判为第三方，否则断言失败），并在日志里补了正对照表。
本 venv 未装 `keyring`，但清扫里没有出现该缺件——因为 `keyring` 只在
`secrets_vault.py` 的函数体内按需导入，导入期不触发。

## 5. 两组全量 pytest

证据：`out/ci-fix/verify-round3/pytest-with-patchelf.log`、
`out/ci-fix/verify-round3/pytest-without-patchelf.log`（两份都带 `-rs` 与 `EXIT=`）。

| 组 | 结果 |
|---|---|
| 有 patchelf（`/usr/bin/patchelf` 存在） | **989 passed, 5 skipped**，`EXIT=0` |
| 无 patchelf（PATH 里移除了 patchelf） | **988 passed, 6 skipped**，`EXIT=0` |

无 patchelf 组多出的那条 skip 是
`tests/test_native_deployment.py:177: requires cc, patchelf and readelf` —— 环境缺件的
既有跳过，在 `-rs` 汇总里直接可见，不是本轮新增的 skip。两组都没有删除或跳过任何用例。
数字比上一版各 +4：本轮新增的三条 Qt binding/readiness 守卫用例，加上第四节
`test_windows_web_bluetooth_is_system_provided`。

> 做法说明：无 patchelf 组不能靠放一个假的 `patchelf` 可执行文件来模拟——跳过判定用的是
> `shutil.which`，假二进制会让它「找到」，随后以 127 失败（第一次尝试即这样失败：
> `1 failed, 987 passed, 5 skipped`，失败点
> `test_linux_bundled_external_chain_loads_after_removing_source`）。最终做法是建一个
> 把 `/usr/bin`、`/usr/local/bin` 等目录里除 `patchelf` 外全部符号链接过去的临时 PATH 再跑。

## 6. 打包链路与产物启动

证据：`out/ci-fix/verify-round3/packaging-build.log`（在 HEAD `91d934e` 上重跑，
`deps.py` 的改动已在其中）、`out/ci-fix/verify-round3/packaged-launch.log`

- 六阶段全跑完（`[1/6]`…`[6/6]`）：`SMOKE PASS 6 modules`、
  `SMOKE PASS launcher`、`READY: .../dist/ai_upper`，`BUILD_EXIT=0`；
- `[2/6]` 的 pip download 有完整输出（`Ignoring typing_extensions: markers ...
  don't match your environment` 也在，证明 3.9+ 侧环境标记按预期生效），
  `[5/6]` 静态校验 `PASS native binaries checked=114`、逐模块 PASS，`[6/6]` 两个 SMOKE PASS；
- 单次耗时约 27s——命中 pip 缓存与既有 build 目录，**不是从零冷构建**（这一点如实记录，
  以免把「增量构建很快」误读成「全量构建已证明很快」）；
- 产物名 `ai_upper`（`dist/ai_upper/ai_upper`，154344 字节）；
- 产物 headless 启动：`DEVA WEB OK platform=offscreen title='ai_upper'
  url=.../dist/ai_upper/assets/renderer/index.html bridge=True`，`LAUNCH_EXIT=0`。

本机环境两处偏差（不涉及被改代码，记录备查）：

1. `.venv/bin/python` 指向 `/usr/bin/python3.13`（无 pip），打包工具因此
   `No module named pip`。用真 venv 解释器 `.venv/bin/python-real` 并通过
   `AI_UPPER_PYTHON` 指给构建工具解决；
2. 本机没有 `ninja`（上一轮用的是 `/tmp/ninja-bin/ninja`），不装它 cmake 无法
   生成构建目录。首次失败日志保留为
   `packaging-build-attempt1-ninja-missing.log`。

## 7. 变异记录（五组，守卫 + 真 3.8）

生成脚本：`/tmp/mutate_all.sh`；脚本按当前代码的**精确锚点**改写后复跑，锚点不唯一
即断言失败。每组两行：守卫（CPython 3.13）与真结果（CPython 3.8.20 venv，
pydantic 2.10.6 / typing_extensions 4.13.2）。

| # | 变异 | 守卫 | 真 3.8 |
|---|---|---|---|
| 0 | 对照（未改动） | `GUARD_EXIT=0`（5 passed） | `IMPORT38_EXIT=0`、`BASELINE_CALL_EXIT=0` |
| 1 | 裸 `from typing import Annotated` | `GUARD_EXIT=1`（2 failed） | `IMPORT38_EXIT=1` ImportError |
| 2 | `LevelMap = dict[str, str]` | `GUARD_EXIT=1` | `IMPORT38_EXIT=1` TypeError |
| 3 | 模块级 `A \| B` 联合 | `GUARD_EXIT=1` | `IMPORT38_EXIT=1` TypeError |
| 4 | `str.removesuffix` | `GUARD_EXIT=1` | `CALL_EXIT=1` AttributeError |
| 5 | pydantic 字段 `Optional[list[...]]` | `GUARD_EXIT=1` | `IMPORT38_EXIT=1` TypeError |

还原证明：`py38-mutation-restore-check.log` 中 `git diff --stat` 对被变异的四个文件
为空，`RESTORE_CHECK_EXIT=0`。

两条记录的处理细节（上一版在这里是错的）：

- 变异 4 在函数体内，`import` 根本不执行它，所以「真 3.8」必须**真调一次**
  `_dist_name()` 才有判决力。上一版记的是 `IMPORT38_EXIT=0`，即缺陷被 import
  掩盖；现在是 `CALL_EXIT=1`，对照组同一个调用是 `BASELINE_CALL_EXIT=0`。
- 所有「真 3.8」记录都改用带第三方包的 `/tmp/venv38`；上一版有一半用裸
  `/tmp/py38`（无 pydantic），记出来的是 `ModuleNotFoundError`，不是真缺陷。

## 8. 改动清单（按主题）

| commit | 主题 | 文件 |
|---|---|---|
| `158a36c` | fix(py38) | `app/src/deva_web.py`、`app/src/mvvm/views/web_shell_window.py` |
| `c49161b` | build(py38) | `.github/workflows/validate.yml` |
| `28aeec5` | test(py38) | `app/tests/test_web_shell_modules.py`、`app/tests/test_build_tool_compat.py` |
| `289749b` | chore(evidence) | `out/ci-fix/closeout/*`、`out/ci-fix/verify-7476558/*` |
| `d44fac5`/`b7d00c2`/`617427a` | docs(py38)/chore(evidence) | 报告与清查表补正 |
| `fix(py38)` 第三处 | `tools/ai_upper/native/deps.py`（`BluetoothApis.dll` 进宿主库清单） |
| `test(py38)` 第三处 | `app/tests/test_native_deployment.py`（`test_windows_web_bluetooth_is_system_provided`） |

对照 `py38-compat-audit.md` 的条目：

- 第 2.1 节归入「Qt binding 差异」；
- 第 2.2 节归入「运行期 API/转换差异」；
- 矩阵 pin 变更归入「依赖闭包（3.8 侧最后一版）」；
- 上一版已列的四类（`Annotated` / PEP 585 / PEP 604 / `removesuffix`）不变。

没有删除任何既有注释；`web_shell_window.py` 顶部那段原本写着「PySide2 也没有」
（对 `QWebEngineScript` 而言是错的）的注释已按事实更正。

## 9. CI 逐 job 结论

权威 run：`43605493485`（commit `617427a`，`in_progress` → `completed/failure`，
2026-11-14T15:00:21Z）。完整快照 `out/ci-fix/run-43605493485/{run,jobs}.json`，
逐 job 表 `out/ci-fix/closeout/job-table-py38-round2.txt`。

| job | 结论 | 说明 |
|---|---|---|
| Build Tool Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | ✅ 6/6 success | 构建工具 + 兼容性测试全绿 |
| native-integration (ubuntu-24.04, linux-x86_64) | ✅ success | |
| native-integration (ubuntu-24.04-arm, linux-arm64) | ✅ success | |
| native-integration (macos-15, macos-arm64) | ✅ success | |
| native-integration (macos-15-intel, macos-x86_64) | ✅ success | |
| native-integration (windows-2025, windows-x86) | ✅ success | 仅 `pyserial==3.5` 的 32 位链路 |
| native-integration (windows-2025, windows-x86_64) | ✅ success | 3.13 + 应用完整依赖 |
| **native-integration (windows-2025, windows-x86_64, 3.8.10)** | ❌ failure | step 15 `[4/6] Package + native dependency closure`：`BluetoothApis.dll` 未解析 |
| native-integration (windows-11-arm, windows-arm64) | ❌ failure | 已知平台阻塞，见下 |
| aggregate-artifacts | — skipped | 上游有 job 失败时不汇总 |

**3.8.10 已推进但未转绿。** 相对 run `43600186928`（`[6/6]` 失败）本轮修掉的两处
让 job 前进到了 `[4/6]`；第 4 阶段的原生闭包缺口（2.4 节）已修，但**修复本身尚未
经过一次真实 CI 运行验证**，因此现在不能声称「3.8.10 真绿」。

**`windows-arm64` 保持已知平台阻塞**：PySide6 的 win_arm64 wheel **里没有
`Qt6WebEngineCore.dll`**（6.11.2 与 6.6.3 都一样，已核 wheel 内容），而
`app/src/mvvm/views/web_shell_window.py` 在类体阶段就要这个类。矩阵条目保留、
不加 skip、不放宽 `requires-python`。该 job 的注解是 `[6/6]` 下的
`qt_compat.py` ImportError 链——与 3.8.10 当时不同的失败点，且根因是上游不发轮子。

**副作用（须知）**：`.github/workflows/validate.yml` 没有 `concurrency:` 组，因此
每推一次都会新起一整轮 14 个 job。本轮为了补证据推了 `d44fac5`/`b7d00c2`/`617427a`，
产生了 `43605158930`/`43605423736`/`43605493485` 三轮重叠。`43605493485` 被指定为
权威；后续修复提交会再起一轮，以最后那一轮为准。

## 10. 一处未处理但已判定不影响本目标的差异

`app/src/mvvm/views/title_bar_overlay.py:78,89` 用 `event.position().toPoint()`，
这是 Qt6 的 `QMouseEvent` 接口；Qt5 只有 `pos()` / `localPos()`。

**本轮不修**，理由是本目标下没有任何 leg 走 Qt5：矩阵里 3.8.10 已改用 PySide6 6.6.3，
其余 leg 用 `app/requirements.txt` 的 PySide6 6.11.2。也就是说这条路径在**当前矩阵**
里不可达，修它属于未被要求的扩展，按「实现用户所要求的，不添加未被要求的功能」不做。
若日后真有人用 PySide2 跑窗口层，这里会先于 WebEngine 的类查找问题暴露——
届时按同一个 `qt_major()` 分支处理即可。
