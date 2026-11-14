# windows-x86_64 3.8.10 收尾报告（第二轮）

HEAD 在本次提交前为 `7476558`（develop）。本报告取代上一版
`py38-closeout-report.md` 里「**是**：…已修好」的结论——那一版与远端实际结果不符，
见 `py38-authoritative-run-failure.md`。

## 一句话结论

**否——上一轮的「已转绿」结论是错的。** 权威 run `43600186928`（commit `7476558`）
的 `windows-x86_64 3.8.10`（job `132463066925`）在 `[6/6] Target runtime smoke`
失败，原因是 Qt binding 的类布局差异与 `runJavaScript` 的布尔转换差异，而非类型兼容
问题。两处缺陷已在本轮定位、修复，并在真实 CPython 3.8.20 + PySide6 6.6.3 上复现与
验证通过；CI 终态以本轮推送后的新 run 为准（见文末，结论表格在 run 结束后回填）。

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

## 2. 本轮的两处真实缺陷

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

证据：`out/ci-fix/verify-7476558/py38-import-sweep.log`

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

证据：`out/ci-fix/verify-7476558/pytest-with-patchelf-missing.log`（无 patchelf 组）、
本轮前述 patchelf 组（988 passed / 5 skipped，`EXIT=0`）。

| 组 | 结果 |
|---|---|
| 有 patchelf（`/usr/bin/patchelf` 存在） | **988 passed, 5 skipped**，`EXIT=0` |
| 无 patchelf（PATH 里移除了 patchelf） | **987 passed, 6 skipped**，`EXIT=0` |

无 patchelf 组多出的那条 skip 是
`test_native_deployment.py:177: requires cc, patchelf and readelf` —— 环境缺件的
既有跳过，不是本轮新增的 skip。两组都没有删除或跳过任何用例；数字比上一版各 +3，
即本轮新增的三条守卫用例（`test_webengine_class_lookup_follows_the_binding_not_a_fixed_submodule`、
`test_readiness_probe_reads_a_string_not_a_javascript_boolean`、
`test_readiness_probe_interprets_the_string_result`）。

> 做法说明：无 patchelf 组不能靠放一个假的 `patchelf` 可执行文件来模拟——跳过判定用的是
> `shutil.which`，假二进制会让它「找到」，随后以 127 失败（第一次尝试即这样失败：
> `1 failed, 987 passed, 5 skipped`，失败点
> `test_linux_bundled_external_chain_loads_after_removing_source`）。最终做法是建一个
> 把 `/usr/bin`、`/usr/local/bin` 等目录里除 `patchelf` 外全部符号链接过去的临时 PATH 再跑。

## 6. 打包链路与产物启动

证据：`out/ci-fix/verify-7476558/packaging-build.log`、
`out/ci-fix/verify-7476558/packaged-launch.log`

- 六阶段全跑完（`[1/6]`…`[6/6]`）：`SMOKE PASS 6 modules`、
  `SMOKE PASS launcher`、`READY: .../dist/ai_upper`，`BUILD_EXIT=0`；
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

对照 `py38-compat-audit.md` 的条目：

- 第 2.1 节归入「Qt binding 差异」；
- 第 2.2 节归入「运行期 API/转换差异」；
- 矩阵 pin 变更归入「依赖闭包（3.8 侧最后一版）」；
- 上一版已列的四类（`Annotated` / PEP 585 / PEP 604 / `removesuffix`）不变。

没有删除任何既有注释；`web_shell_window.py` 顶部那段原本写着「PySide2 也没有」
（对 `QWebEngineScript` 而言是错的）的注释已按事实更正。

## 9. CI 逐 job 结论

见 `out/ci-fix/closeout/job-table-py38-round2.txt`，由推送后的新 run 回填。

已知项：`windows-11-arm windows-arm64` 保持**已知平台阻塞**——PySide6 从未发布带
`QtWebEngineCore` 的 win_arm64 wheel，矩阵条目保留、不加 skip、不放宽
`requires-python`。

## 10. 一处未处理但已判定不影响本目标的差异

`app/src/mvvm/views/title_bar_overlay.py:78,89` 用 `event.position().toPoint()`，
这是 Qt6 的 `QMouseEvent` 接口；Qt5 只有 `pos()` / `localPos()`。

**本轮不修**，理由是本目标下没有任何 leg 走 Qt5：矩阵里 3.8.10 已改用 PySide6 6.6.3，
其余 leg 用 `app/requirements.txt` 的 PySide6 6.11.2。也就是说这条路径在**当前矩阵**
里不可达，修它属于未被要求的扩展，按「实现用户所要求的，不添加未被要求的功能」不做。
若日后真有人用 PySide2 跑窗口层，这里会先于 WebEngine 的类查找问题暴露——
届时按同一个 `qt_major()` 分支处理即可。
