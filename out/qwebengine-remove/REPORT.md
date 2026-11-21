# QtWebEngine 移除结项报告（方案 1：唯一界面 = QML 壳 + QTextDocument）

- 日期：2026-11-17（**2026-11-21 在 HEAD `b98d59e` 上复验，见 §9**）
- 分支：`develop`（**只在本地提交，未 push、未建分支**）
- 基线：`1d53e4a`（移除前最后一个提交）
- 舞台提交：`a191a9c` → `749d407` → `0b02bd1` → `6f02994` → `e725c8d` → `7ce85fa` → `4bea1ba`
  → `0433783`（本轮补测）
- 证据目录：`out/qwebengine-remove/logs/`（原始命令输出）、`out/qwebengine-remove/shots/`（18 张实拍 PNG）；
  2026-11-21 复验证据在 `out/qwebengine-verify/`（`logs/01…46`、`shots/`）
- 口径：**每条结论都附真实命令与输出**。没做到的直接写「未完成 + 原因」，不拿对账当成果。
- 本报告**不主张启动变快**。收益是**包体与依赖面收敛**；首帧耗时未测，见 §5.3。

---

## 0. 一句话结论

`PySide6`（元包，连带 `PySide6-Addons` 整套 Chromium）→ `PySide6-Essentials`；承载层
`mvvm/views/web_shell_window.py`、`title_bar_overlay.py`、`DevaBridge`（QtWebChannel）与
`app/assets/renderer/` 全部删除；打包产物 `dist/ai_upper` 从 **522M 降到 256M**（-52%），
产物内 `QtWebEngine*` / `QtWebChannel*` / `QtWebEngineProcess` / `qtwebengine_locales` 命中数
**0**；全量 pytest **1250 passed / 6 skipped → 1219 passed / 5 skipped**（删 100 + 补 56 +
本轮再补 15），**新增失败 0**；
QML 壳 offscreen 实跑打印 `QML OK … size=1280x820`，18 个页面截图 rc 全 0，5 张对比页与基线
**逐像素一致**（md5 相同）。

**2026-11-21 复验**（HEAD `b98d59e`）：以上每一条都重新跑了一遍，结论全部成立。
复验期新增数据：删前产物独立重建 522M / 240M WebEngine 载荷 / `EXIT=0`，删后 256M / 命中 0 /
`QML OK` `EXIT=0`；两侧首屏截图 md5 相同；pytest 基线 1250P/6S → 移除完成点 1219P/5S →
今天 HEAD **1260P/5S**，新增失败 0。复验发现的唯一实质问题是
`docs/STAGE6-CLOSEOUT-REPORT.md` 缺历史台账注（原文 §5.1 声称已加），已补。详见 §9。

---

## 1. 修红 + 清残留

### 1.1 原先红在哪（两条 import 指向已删模块）

| 文件 | 原 import | 处置 |
|---|---|---|
| `app/tests/test_deliverables.py` | `from mvvm.webui.bridge import DevaBridge` 及其 5 条 `test_bridge_*` | 删 5 条桥用例，补 2 条 store 往返用例（29→26） |
| `scripts/parity/port_run.py` | `from mvvm.views.web_shell_window import DevaWebWindow` | **整个脚本删除**（web 承载窗口专属入口，无 QML 对应物） |
| `scripts/parity/live_scenarios.py` | 同上 | **整个脚本删除**（四个场景全部经 `DevaWebWindow` 驱动） |
| `scripts/parity/port_shots.sh` | 调 `port_run.py` | **整个脚本删除**（`qml_pages_all.sh` 是现行截图入口） |
| `audit-tools/make_ipc_ledger.py` / `ipc_status_table.py` | 统计 `DevaBridge` 的 158 条 IPC 通道 | **删除**（被统计的对象已不存在，工具无输入） |

`a191a9c` 的完整删除清单（23 个文件，87010 行删除）：

```
$ git show --stat a191a9c | head -26
app/assets/renderer/assets/browser-C0Lpq-MB.js  |   198 -
app/assets/renderer/assets/browser-C_iNvXeT.css |   315 -
app/assets/renderer/assets/feishu-PHOsC_GZ.svg  |    13 -
app/assets/renderer/assets/index-B94CB8vb.css   |  6094 -
app/assets/renderer/assets/index-feRGkUOb.js    | 55614 ----------------------
app/assets/renderer/assets/text-C9wd0hHJ.js     | 13870 ------
app/assets/renderer/assets/text-CRS9VcOt.css    |  6331 ------
app/assets/renderer/index.html                  |    19 -
app/assets/renderer/qwebchannel.js              |   456 -
app/assets/renderer/shim.js                     |   312 -
app/src/mvvm/views/title_bar_overlay.py         |   123 -
app/src/mvvm/views/web_shell_window.py          |   284 -
app/src/utils/platform_name.py                  |    25 -
app/tests/test_web_attachments.py               |   441 -
app/tests/test_web_chat_write.py                |   485 -
app/tests/test_web_e2e_stream.py                |   186 -
app/tests/test_web_settings_write.py            |   372 -
app/tests/test_web_shell_modules.py             |   481 -
audit-tools/ipc_status_table.py                 |   416 -
audit-tools/make_ipc_ledger.py                  |   237 -
scripts/parity/live_scenarios.py                |   604 -
scripts/parity/port_run.py                      |    60 -
scripts/parity/port_shots.sh                    |    74 -
23 files changed, 87010 deletions(-)
```

> `app/src/utils/platform_name.py` 也在内：它唯一的调用方是 `web_shell_window.py`
> 判定 Electron Linux 窗口装饰，删除后无调用方。

### 1.2 全仓残留扫描（148 行，逐行定性）

扫描口径（`logs/grep-canonical-final.txt` 头部的命令原文）：

```
$ grep -rnE "QtWebEngine|QtWebChannel|DevaBridge|DevaWebWindow|web_shell_window|title_bar_overlay|AI_UPPER_UI" \
    --include=*.py --include=*.yml --include=*.yaml --include=*.toml --include=*.example \
    --include=*.txt --include=*.md --include=*.sh --include=*.qml --include=*.json --include=*.js \
    --include=*.html app tools scripts .github README.md docs audit-tools
```

结果 **148 行命中**。用 AST 取 docstring 区间、用 `tokenize` 取每行覆盖到的 token 类型，
逐行分成五类（`logs/grep-canonical-reclassified.txt`，含每一行的完整清单）：

```
grep 命中行数（去重前）: 148   去重后: 148

=== 文档 (docs/ README): 70
=== 配置/脚本注释: 5
=== Python 注释 (#): 6
=== Python 文档字符串: 25
=== 可执行代码行: 42
```

**「可执行代码 42 行」必须逐条说清，不能笼统说成 0。** 它们分布在 4 个文件，
**没有一行属于应用运行时**：

| 出处 | 行数 | 是什么 |
|---|---|---|
| `tools/ai_upper/qt_prune.py` | 5 | `:464` 插件类别映射、`:588` 模块↔helper 规则、`:647` helper 文件名、`:1149`/`:1245` 「未用该模块则删 resources」判定。**裁剪器自己的通用规则**，与「本应用是否用 WebEngine」无关 |
| `app/tests/test_qt_prune.py` | 34 | 夹具里的假文件路径（`(pyside / "QtWebEngineCore.abi3.so")`）、`prune(site, TARGETS[...], {"QtCore","QtWebEngineCore"})` 这类**构造输入的实参**、以及 `assert not (...).exists()` 断言。测的是裁剪规则 |
| `app/tests/test_mvvm.py:216` | 1 | `for gone in ("views.web_shell_window", "views.title_bar_overlay")` —— **反向守卫**：这两个文件若被加回来，测试立刻失败 |
| `app/tests/test_third_party.py:414,424` | 2 | `zipfile.ZipInfo("demo_pkg/Qt/libexec/QtWebEngineProcess")` 之类的 zip 夹具名，测「execute 位在解包后存活」 |

**真正的「无 WebEngine 引用」证据是 AST 的 import 扫描，不是 grep 行数**：189 个 py 文件里
`import`/`from-import` 的模块名命中 **0 条**（`logs/ast-import-recheck-final.txt`，本轮补跑的
原始输出；`logs/proof-no-webengine-final2.log` 是同一口径的早一轮记录）。
作为对照，`test_qt_prune.py:978` 那行看起来最像 import 的
`f"    from {QT_COMPAT_MODULE} import QtWebEngineCore, QtWebEngineWidgets\n"`，
是被写进**临时文件供扫描器读取的字符串**，它本身不 import 任何东西。

其余四类：

- **70 行文档**：历史台账（`docs/BUILD-PROGRESS.md` 32 行、`docs/STAGE6-CLOSEOUT-REPORT.md` 9、
  `docs/STAGE5-CLOSEOUT-REPORT.md` 7、`docs/audit/IPC-158-LEDGER.md` 3）**刻意不改写**，只加
  「这是历史台账，文中脚本已删除」的顶部说明；现行文档（`README.md`、`docs/ROADMAP-NEXT.md` 4、
  `docs/DEVELOPMENT_GUIDE.md` 2、`docs/audit/qml-shell-audit.md` 11）已在 `6f02994` 改为当前状态。
- **25 行文档字符串 + 6 行 `#` 注释 + 5 行配置/脚本注释**：解释性文字。含
  `app/src/main.py:8` 的「原 `AI_UPPER_UI=web` 的承载窗口已随 … 删除」——**说明历史**，
  不是死指令；以及 `app/pyproject.toml(.example)` / `app/requirements.txt` 里
  「元包会连带装 Addons/WebEngine，所以不声明」的说明。

AST 层面的独立复核（`logs/proof-no-webengine-final2.log`）：

```
### 1) AST 层面的 import / from-import 是否引用 WebEngine/WebChannel 系模块
  扫描 py 文件 189 个，命中 0 条

### 2) 字符串级扫描：import 语句里出现 WebEngine 的行（grep，含测试夹具字符串）
  （可执行 import 行：无命中）
  ——唯一字符串命中（测试夹具源码文本，不是模块 import）：
app/tests/test_qt_prune.py:978:        f"    from {QT_COMPAT_MODULE} import QtWebEngineCore, QtWebEngineWidgets\n"
```

`AI_UPPER_UI` 这个环境变量在**代码里已经彻底不存在**了：

```
$ grep -rn "AI_UPPER_UI" --exclude-dir=out --exclude-dir=.git .
app/src/main.py:8:装配（原 `AI_UPPER_UI=web` 的 QtWebEngine 承载窗口已随 `mvvm.views.web_shell_window`
$ grep -rn "AI_UPPER_UI" --include=*.py --exclude-dir=out --exclude-dir=.git . | wc -l
1
```

唯一一行是注释里的历史说明。`scripts/parity/qml_page_shot.sh` 里那句 `AI_UPPER_UI=qml`
已删（`6f02994`）。

### 1.3 被误伤服务的复核（没有连带删除）

| 能力 | 复核证据 |
|---|---|
| `services/deliverables.py` | 文件仍在（13299 B，2026-11-16），**头文件外的改动只有一次**：`git log --oneline -1 -- app/src/mvvm/services/deliverables.py` → `ef6ba07`（早于本轮）。QML 壳仍在 import：`app/src/qml_shell.py:34 from mvvm.services.deliverables import open_item, reveal`、`:606/:615 delivered_paths`、`app/src/qml_shell_sessions.py:26`。 |
| `mvvm/webui/bridge.py` 里 QML 壳**仍在用**的部分 | 精简到 140 行，只剩 `BridgeError` / `NOTIFY_MARKER` / `display_messages`。`app/src/mvvm/webui/host.py:46 from mvvm.webui.bridge import BridgeError, display_messages`，在 `:168/:171/:174/:206/:317/:446/:448` 抛 `BridgeError`、在 `:360/:415/:504/:594` 调 `display_messages` 与 `index_base`，均在线。 |
| `AttachmentService` | 从 12 个方法收缩到 4 个（`set_file_dialogs` / `inspect` / `pick_attachments` / `build_attachment_part`），**QML 壳走的就是这 4 个**。8 条 `fs:*` 通道的唯一调用方是已删的 `DevaBridge`，删得有据（模块 docstring 里写明）。 |
| `ChatHost` 会话/回合能力 | `test_host_write.py`（26 条）直接打 `ChatHost`，`app/src/qml_shell.py:40 from mvvm.webui.assembly import build_chat_host` 仍是唯一装配入口。 |

### 1.4 QML 壳与 markdown→QTextDocument 的行为/外观未变

**代码层面**：`markdown/` 与 `qml/` 目录自基线以来**零改动**——

```
$ git diff --stat 1d53e4a..HEAD -- app/src/markdown/ app/src/qml/
（空输出）
```

qml_shell 的改动全部是「删掉 web 专用分支 + 注释改写 + 上一轮的会话列表批量载入」，
Slot 数量 23 个不变（`grep -c "@QtCore.Slot" app/src/qml_shell.py` → `23`）。
`git diff --stat 1d53e4a..HEAD -- app/src/qml_shell.py app/src/qml_shell_sessions.py` →
`38 insertions(+), 31 deletions(-)`，逐行看只有：docstring/注释措辞、删 `_pick_directory`、
`set_file_dialogs` 少传一个参数、`visible_sessions()` 只取一次（上一轮 `e725c8d` 的优化）。

**像素层面**（`logs/appearance-before-after.log`）：同一个页面、同一份 fixture config，
基线工作树 `/tmp/qwe-baseline` 与 HEAD 各拍一张，逐字节比：

```
== chat (config=config.json)
   baseline exit=0 stderr=0B
   head     exit=0 stderr=0B
   IDENTICAL md5=16efd3b52fef50c19700500525eed888
== settings-general
   IDENTICAL md5=12a7243019c97c9a1038ded91ca4e034
== dark-chat
   IDENTICAL md5=fc62b2eca19a90bd67af184d08e4fd8e
== model-picker
   IDENTICAL md5=e408e4c39934ca1a49efd82cead63538
== ctx-menu
   IDENTICAL md5=ae1e527719f2246ca9e74a5b2eed1daa
```

5 张全 `IDENTICAL`，且两轮的 `stderr` 都是 `0B`（逐文件 `stat -c%s` 核对过，不是没检查）。

> **另有一处必须说明的差异（不是渲染差异）**：`out/qwebengine-remove/shots/` 里的 18 张图
> 拍摄于 10:07（HEAD=`0433783`），与更早两轮 HEAD 截图（08:32、09:31）逐字节不同。
> 逐像素比对后，差异**全部**落在 `x=289..295`、`y=70..779` 这条 6–7px 竖带内，
> 该列正是会话列表里的相对时间标签：三轮分别显示 `21 hr ago` / `22 hr ago` / `23 hr ago`。
> 把该处裁切放大后肉眼确认：除这几个字形像素外，两轮完全相同。判定：**fixture 会话的时间戳
> 相对显示跨过整点**，不是渲染差异。证据：`logs/shots-reltime-diff-explained.txt`
> （含 final2 vs final3 的逐页 diff 像素数与 bbox）。
> **基线 vs HEAD 的结论只看上面 5 张 parity 页**（同一轮、同一时刻拍摄，md5 逐字节相同），
> 与这三轮「HEAD 自己跟自己比」的差异是两回事。
> 更稳的做法是把 fixture 时间戳固定成绝对时间；本轮没改 fixture（不在范围，且会动到
> `scripts/parity/make_qml_home.py` 的固定数据）。

> **已知遗留缺陷（不是本轮引入）**：`app/src/qml/SettingsModal.qml:372`
> `text: shellBridge ? shellBridge.extensionsSummary() : ""` 调了一个**不存在**的 Slot，
> 运行时报 `TypeError: Property 'extensionsSummary' of object ShellBridge(...) is not a function`
> （见 `/tmp/qml-pages-final/settings-extensions.err`）。已在基线核对：
> `git show 1d53e4a:app/src/qml/SettingsModal.qml | sed -n 372p` 输出**同一行**，
> `git show 1d53e4a:app/src/qml_shell.py | grep -c "extensionsSummary"` → `0`。
> 即**基线就有的既有 bug**，本轮未引入、也未顺手修（不在授权范围）。页面仍能渲染
> （`settings-extensions` 截图 rc=0）。

---

## 2. 依赖面

### 2.1 Pin 前后（`logs/pin-diff.log`）

```
### 基线 1d53e4a
--- app/requirements.txt
5:PySide6==6.11.2

### HEAD
--- app/requirements.txt
5:# 界面只需要 QtCore/QtGui/QtWidgets/QtQml/QtQuick，全部在 PySide6-Essentials 里；
6:# 元包 PySide6 会连带装 PySide6-Addons（含 QtWebEngine 等整套 Chromium，约 240 MiB），
8:PySide6-Essentials==6.11.2
```

`tools/requirements.txt`（构建机工具链）与 `app/pyproject.toml.example`（入库模板，
design 上只写注释示例）**均无 pin 变化**——`pin-diff.log` 里两者的基线/HEAD 段逐行相同。

### 2.2 全仓无 WebEngine import

见 §1.2：AST 扫 189 个 py 文件，`QtWebEngineWidgets` / `QtWebEngineCore` /
`QtWebEngineQuick` / `QtWebChannel` 的 import **0 条**。

### 2.3 纯 Essentials 环境的真实测量

用**只装了 `PySide6-Essentials==6.11.2` + `shiboken6`** 的独立 venv
（`/tmp/qwe-ess-venv`，`pip list` 里没有 `PySide6-Addons`）：

```
$ cat logs/essentials-modules-proof.log
PySide6 6.11.2 from /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/__init__.py
ok  PySide6.QtCore /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/QtCore.abi3.so
ok  PySide6.QtGui /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/QtGui.abi3.so
ok  PySide6.QtWidgets /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/QtWidgets.abi3.so
ok  PySide6.QtQml /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/QtQml.abi3.so
ok  PySide6.QtQuick /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/QtQuick.abi3.so
ok  PySide6.QtSvg /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/QtSvg.abi3.so
ok  PySide6.QtNetwork /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/QtNetwork.abi3.so
distributions: ['PySide6_Essentials', 'Pygments', 'SecretStorage', … 共 30 个]
                ↑ 列表里没有 PySide6_Addons，也没有元包 PySide6
```

```
$ cat logs/essentials-import-proof.log
=== 2026-11-17T08:13:38+08:00 纯 Essentials venv: 6.11.2 ===
--- 五个界面模块导入 ---
ok PySide6.QtCore ...QtCore.abi3.so
ok PySide6.QtGui ...QtGui.abi3.so
ok PySide6.QtWidgets ...QtWidgets.abi3.so
ok PySide6.QtQml ...QtQml.abi3.so
ok PySide6.QtQuick ...QtQuick.abi3.so
sys.path ok
--- WebEngine 模块在纯 Essentials 下不存在 ---
ImportError: No module named 'PySide6.QtWebEngineWidgets'
```

QML 模块（QML 文件真正 import 的 5 个 + Templates）也在：

```
$ cat logs/essentials-qml-modules.log
qml root: /tmp/qwe-ess-venv/lib/python3.13/site-packages/PySide6/Qt/qml exists: True
ok   QtQuick
ok   QtQuick/Controls
ok   QtQuick/Layouts
ok   QtQuick/Shapes
ok   QtQuick/Templates
ok   QtQuick/Window
QtWebEngine QML 目录: 无
```

纯 Essentials 下把壳跑起来（`logs/final-essentials-launch.log`）：

```
$ cd app/src && AI_UPPER_HOME=/tmp/qwe-ess-home-final AI_UPPER_HEADLESS=1 \
    AI_UPPER_QML_SHOT=/tmp/qwe-ess-final.png /tmp/qwe-ess-venv/bin/python main.py
QML OK platform=offscreen title='Deva' sessions=0 active='' plain=False turn_stop='' deltas=0 \
  home=/tmp/qwe-ess-home-final png=/tmp/qwe-ess-final.png size=1280x820
EXIT=0
-rw-r--r-- 1 root root 23873 Nov 17 08:30 /tmp/qwe-ess-final.png
```

### 2.4 7 个发布目标逐行：为什么都不需要 Addons

读 **9 个 wheel 的 ZIP 中央目录**（HTTP Range，不整包下载）得到的谓词表，
`logs/wheel-qml-predicates-essentials.log`：

| 发布目标（`tools/ai_upper/config.py:141` 的 `TARGETS`） | Essentials wheel | QtQuick / Controls / Layouts / Shapes / Window / Templates | 需要 Addons？ | 理由 |
|---|---|---|---|---|
| `linux-x86_64` | `manylinux_2_34_x86_64` | 6/6 YES + `libQt6Quick.so.6` + `libQt6Qml.so.6` | **否** | 壳只 import QtCore/QtGui/QtWidgets/QtQml/QtQuick；QML 文件只 import QtQuick 系 5 个模块 |
| `linux-arm64` | `manylinux_2_39_aarch64` | 6/6 YES + 两个 .so | **否** | 同上 |
| `macos-x86_64` / `macos-arm64` | `macosx_13_0_universal2`（两者共用） | 6/6 YES + `QtQuick.framework` + `QtQml.framework` | **否** | 同上 |
| `windows-x86_64` | `win_amd64` | 6/6 YES + `Qt6Quick.dll` + `Qt6Qml.dll` | **否** | 同上 |
| `windows-arm64` | `win_arm64` | 6/6 YES + `Qt6Quick.dll` + `Qt6Qml.dll` | **否** | 同上；且此 wheel 连 `QtWebEngineCore.pyi` 都没有 |
| `windows-x86`（32 位） | **PySide6 不发 32 位 Windows wheel** | — | — | 该 CI 行本来就不装 PySide6（只用 `pyserial==3.5` 验 32 位工具链），见 `.github/workflows/validate.yml:63` 的注释 |
| **py38 兼容行**（非发布目标，`artifact: py38-compat-windows-x86_64`） | `PySide6_Essentials-6.6.3-cp38-abi3-win_amd64` | 6/6 YES + `Qt6Quick.dll` + `Qt6Qml.dll` | **否** | 见下 |

py38 那一行的依据（`logs/pypi-essentials-wheels.log`）：

```
=== PySide6-Essentials 6.6.3 wheels (PyPI JSON) ===
PySide6_Essentials-6.6.3-cp38-abi3-macosx_11_0_universal2.whl
PySide6_Essentials-6.6.3-cp38-abi3-manylinux_2_28_x86_64.whl
PySide6_Essentials-6.6.3-cp38-abi3-manylinux_2_31_aarch64.whl
PySide6_Essentials-6.6.3-cp38-abi3-win_amd64.whl      ← cp38-abi3 存在
```

**一个必须说清的口径细节**：Essentials wheel 里**有** `PySide6/QtWebEngineCore.pyi`
（类型存根，5 个 6.11.2 wheel 里有 4 个、`win_arm64` 没有），但**没有** `QtWebEngineCore.abi3.so`
（5/5 没有），也**没有** `QtWebEngineProcess`（5/5 没有）。也就是说：
**「Essentials 里没有 WebEngine」准确说法是「没有可加载模块、没有 Chromium 载荷」，
不是「连一个字节都没有」。** 对比 Addons 的 aarch64 wheel（`logs/wheel-contents.log`）：
它有真的 `QtWebEngineCore.abi3.so` + `libQt6WebEngineCore.so.6` + `QtWebEngineProcess`。

### 2.5 没有删到 CI 变红

CI 的三处改动都在 `0b02bd1`：

1. **py38 行**：`'["PySide6==6.6.3", …]'` → `'["PySide6-Essentials==6.6.3", …]'`，其余 pin 不动。
2. **Linux runner 的 apt 列表**：Chromium 运行库那一段从 **40 个包收缩到 23 个**，
   净删 17 个（删 30、增 13）。删掉的是 `libnss3` / `libnspr4` / `libopus0` / `libminizip1t64` /
   `libsnappy1v5` / `libvpx9` / `libdbus-1-3` / `libcups2t64` / `libasound2t64` / `libgbm1` /
   `libwebp*` / `libharfbuzz*` / `libicu74` 等；增回的是 QML 壳真正要的
   `libxkbcommon-x11-0`、`libxcb-cursor0`、`libxcb-icccm4`、`libxcb-image0`、`libxcb-keysyms1`、
   `libxcb-randr0`、`libxcb-render-util0`、`libxcb-shape0`、`libxcb-sync1`、`libxcb-xfixes0`、
   `libxcb-xinerama0`、`libxcb-xkb1`、`libxrender1`。
   （`libegl1` 仍保留，只是在**另一行**单独安装，见 `validate.yml:214`——不在这段列表里。）
3. **smoke 标记断言**：原来是「`QML OK` **或** `DEVA WEB OK … bridge=True`」取并集，现在只剩
   `ok = 'QML OK' in text and 'size=1280x820' in text`（`validate.yml:437`）。

配套的静态测试也同步改了（否则 CI 自己会红）：
`app/tests/test_build_tool_compat.py:328` 断言 py38 行必须含 `"PySide6-Essentials==6.6.3"`，
`app/tests/test_ci_tail.py:168` 的日志样例从 `DEVA WEB OK bridge=True` 改成 `QML OK size=1280x820`。
实测这两条在 HEAD 全量 pytest 里是绿的（见 §4.2）。

> **未验证（如实记）**：本轮**没有**重新触发 GitHub Actions。CI 工作流是静态断言 + 全量 pytest
> 覆盖的，但「7 个 target 在真实 runner 上全绿」这件事，本轮**没有实跑证据**，只有
> 上一轮运行 `run-43610671432`（commit `e2b9392`，`git merge-base --is-ancestor e2b9392 HEAD`
> → 是 HEAD 祖先，但 `e2b9392` **不含**本轮删除提交）。原因：本机没有向远端推送的授权
> （硬约束「不 push」），无法用本轮 HEAD 触发官方 CI。**风险**：py38 与 arm 两行的
> Essentials 切换只在 wheel 中央目录层面验证过，没有在该 runner 上装过。

---

## 3. 打包链

### 3.1 打包链里还剩哪些「WebEngine」字样（都是通用契约，不是本应用在用）

`tools/ai_upper/qt_prune.py` 保留了这些**通用裁剪规则**：

| 位置 | 内容 | 为什么保留 |
|---|---|---|
| `:464` | `MODULE_PLUGIN_CATEGORIES["QtWebEngineCore"] = {"webview"}` | 裁剪器的模块→插件类别映射表；删掉会让「有人真用 WebEngine 时」漏删插件 |
| `:588` | `MODULE_HELPERS = {"QtWebEngineProcess": "QtWebEngineCore"}` | 「模块与它 spawn 的 helper 必须同留同删」的规则 |
| `:493` 附近 | `WEBENGINE_LOCALES_DIR = "qtwebengine_locales"` | Chromium locale pak 的归属判定 |
| `:647` | `helpers=(pyside / "QtWebEngineProcess.exe",)` | Windows 侧 helper 的文件名 |
| `:1149` / `:1245` | `if "QtWebEngineCore" not in modules:` → 删 `resources` / locales | 未用该模块时删掉 Chromium 载荷 |

（上面的 5 行即 §1.2 里 `qt_prune.py` 的 5 条「可执行代码命中」。）

`0b02bd1` 只把这些注释从「当前行为」改成「通用规则」，**规则本身一条没动**——
原因：`app/tests/test_qt_prune.py` 里 34 条断言/夹具的输入就是这些规则（§1.2），
删掉规则 = 删掉裁剪器的回归保护，且会让裁剪器在真遇到 Addons 时失效。

### 3.2 真实构建（HEAD 全量重建）

```
$ PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tools/build.py --target linux-arm64
（日志：logs/build-final3.log）
...
Qt pruning: removed 232 file(s) and 87 director(ies), freed 100 MB
PASS native binaries checked=109
SMOKE PASS 6 modules (launcher registers merged bundles)
SMOKE PASS launcher
READY: /home/agent/shared_workspace/ai_upper/dist/ai_upper
EXIT=0
```

> **环境事实（记下来，免得下次再踩）**：README 写的是 `python tools/build.py`，但本容器的
> `ninja` 只存在于 `.venv/bin/ninja`（pip 装的 `ninja` 包），不在 `PATH` 上。直接跑会得到
> `CMake Error: CMake was unable to find a build program corresponding to "Ninja"`
> （`logs/build-final.log`、`logs/build-final2.log` 两次失败原文）。必须
> `PATH="$PWD/.venv/bin:$PATH"`。**这条没有写进 README**（不在本次授权范围；如果要写，
> 应作为独立的文档修正）。

### 3.3 体积前后（真实 `du`）

```
$ cat logs/du-before.txt        # 基线产物（移除前）
534630463	dist/ai_upper
522M	dist/ai_upper

$ cat logs/du-after-final.txt   # HEAD=4bea1ba 全量重建后
# 权威重建（HEAD=4bea1ba，命令：PATH=.venv/bin:$PATH .venv/bin/python tools/build.py --target linux-arm64）
# 日志：build-final3.log，EXIT=0
256453593	dist/ai_upper
256M	dist/ai_upper
```

**522M → 256M，减 278,176,870 B（约 265 MiB），降幅 52.1%**
（278176870 / 534630463 = 52.03%）。

被删掉的载荷逐字节清单（`logs/dist-webengine-before.txt`，共 19 行）：

```
190606336  PySide6/Qt/lib/libQt6WebEngineCore.so.6
 11698477  PySide6/Qt/resources/qtwebengine_devtools_resources.pak
  2452411  PySide6/Qt/resources/qtwebengine_resources.pak
   702456  PySide6/QtWebEngineCore.abi3.so
   203488  PySide6/QtWebEngineWidgets.abi3.so
   199336  PySide6/Qt/lib/libQt6WebEngineWidgets.so.6
   197297  PySide6/Qt/resources/qtwebengine_resources_200p.pak
   151476  PySide6/Qt/resources/qtwebengine_resources_100p.pak
   132945  PySide6/Qt/libexec/QtWebEngineProcess
   136680  PySide6/QtWebChannel.abi3.so
   264976  PySide6/Qt/lib/libQt6WebChannel.so.6
    16054  assets/renderer/qwebchannel.js
locales: 44977323 B, files=53
renderer: 3309588 B, files=10
```

合计 `206761932 + 44977323 + 3309588 = 255048843 B ≈ 243 MiB`，与 `du` 的 265 MiB 差值来自
目录块对齐与同时被裁掉的其他 Essentials 子模块——量级吻合，不是估算。

### 3.4 产物里 WebEngine 命中数 = 0

```
$ find dist/ai_upper \( -name '*QtWebEngine*' -o -name '*QtWebChannel*' -o -name 'QtWebEngineProcess' \
    -o -name 'qtwebengine*' -o -name '*qwebchannel*' \) | wc -l
0
```

产物 `site-packages/PySide6` 顶层模块（只剩 Essentials 那 8 个）：

```
QtCore.abi3.so   QtGui.abi3.so   QtNetwork.abi3.so   QtOpenGL.abi3.so
QtQml.abi3.so    QtQuick.abi3.so QtQuickControls2.abi3.so QtWidgets.abi3.so
dist-info: PySide6  pyside6_essentials-6.11.2.dist-info  shiboken6  shiboken6-6.11.2.dist-info
```

`dist/ai_upper/assets/` 从 `personas qml renderer` 变成 `personas qml`。

### 3.5 真实产物启动

```
$ AI_UPPER_HEADLESS=1 AI_UPPER_HOME=/tmp/qwe-final-pkg-home AI_UPPER_QML_SHOT=/tmp/qwe-final-pkg2.png \
    dist/ai_upper/ai_upper
Detected locale "C" with character encoding "ANSI_X3.4-1968", which is not UTF-8.
Qt depends on a UTF-8 locale, and has switched to "C.UTF-8" instead.
QML OK platform=offscreen title='Deva' sessions=0 active='' plain=False turn_stop='' deltas=0 \
  home=/home/agent/shared_workspace/ai_upper/dist/ai_upper png=/tmp/qwe-final-pkg2.png size=1280x820
EXIT=0
-rw-r--r-- 1 root root 23873 Nov 17 09:31 /tmp/qwe-final-pkg2.png
```

源码树启动（`logs/final-source-launch2.log` 是 `4bea1ba`；`logs/final-source-launch3.log`
是补测后的 `0433783`，两次打印一致）：

```
$ AI_UPPER_HEADLESS=1 AI_UPPER_HOME=/tmp/qwe-final3-home AI_UPPER_QML_SHOT=/tmp/qwe-final3-src.png \
    .venv/bin/python app/src/main.py
QML OK platform=offscreen title='Deva' sessions=0 active='' plain=False turn_stop='' deltas=0 \
  home=/tmp/qwe-final3-home png=/tmp/qwe-final3-src.png size=1280x820
EXIT=0
23873 /tmp/qwe-final3-src.png        md5 dbdddec9793656631b9041db4d2b3030
```

18 个页面的实拍（`logs/shots-final3.log` / `shots-final3-sizes.log`）：

```
$ bash scripts/parity/qml_pages_all.sh /tmp/qml-pages-final3 /tmp/fx-qml-home
ok   empty  rc=0 ... ok   settings-models  rc=0        ← 18 个 ok，0 个 FAIL
每页 1280x820；合计 1511782 B；图片已拷进 out/qwebengine-remove/shots/
```

> 基线产物体积 `534630463` 的 `du` 取自 2026-11-17 07:12（`du-before.txt` 的 mtime），
> 对应的是本轮**动手前**仓库里的 `dist/ai_upper`。为了不被「时间戳久 = 数据不可信」质疑，
> 本轮额外从 `1d53e4a` 工作树（`/tmp/qwe-baseline`）重跑了一次同样的构建来交叉验证，
> 结果见 §3.6。

### 3.6 基线产物的独立重建（交叉验证）

在 `/tmp/qwe-baseline`（`git rev-parse HEAD` → `1d53e4a2357cf101f1e0502f0b10f839b1bd380e`，
工作树无改动）上用同一条命令重建基线产物：

```
$ cd /tmp/qwe-baseline && PATH="$PWD/.venv/bin:/home/agent/shared_workspace/ai_upper/.venv/bin:$PATH" \
    .venv/bin/python tools/build.py --target linux-arm64
（日志：logs/build-baseline-repro.log，686 行）
...
Qt pruning: removed 496 file(s) and 141 director(ies), freed 258 MB
Trim (site-packages): removed 48 file(s) and 0 director(ies), freed 3.5 MB
Third-party optimization: removed 546 files and 142 directories
PASS native binaries checked=142
SMOKE PASS 6 modules (launcher registers merged bundles)
SMOKE PASS launcher
READY: /tmp/qwe-baseline/dist/ai_upper
EXIT=0
```

对照 HEAD 的同一条日志行：

```
HEAD  (build-final3.log:98):   Qt pruning: removed 232 file(s) and  87 director(ies), freed 100 MB
基线  (build-baseline-repro.log:106): Qt pruning: removed 496 file(s) and 141 director(ies), freed 258 MB
差值：                              -264 file        -54 dir            -158 MB
```

**裁剪器自己报告的差值：264 个文件 / 54 个目录 / 158 MB**，正是 `QtWebEngineCore` +
`QtWebEngineWidgets` + `QtWebChannel` + locales(53 文件) + helper 的量级。
`PASS native binaries checked` 也从 142 降到 109——少掉的 33 个就是 WebEngine 侧的 .so/dylib/dll。

重建产物的真实体积（`logs/du-before-repro.txt`）：

```
534873044	/tmp/qwe-baseline/dist/ai_upper
522M	/tmp/qwe-baseline/dist/ai_upper
```

与 `du-before.txt` 记录的 `534630463 / 522M` 相差 **242,581 B（0.045%）**，
来源是构建时间戳等非内容字段。**两者互相印证：基线的 522M 不是笔误。**
因此「522M → 256M」的两端都有独立测量，不是单点数据。

> 为让基线工作树能构建，做了三件**只影响 `/tmp` 沙箱、不影响仓库**的事：
> ① 把 `runtimes/` 与 `.cache/pbs-sdk` 复制进去（基线构建要 PBS SDK 才能走 runtime 阶段）；
> ② `.cache/pbs-sdk` 的拷贝避开了容器里 `zstd` 缺失导致的 `.tar.zst` 解压失败；
> ③ `build/host-tools/` 复制进去（容器 `/usr/bin/python3.13` 没有 pip，构建机 Cython 装不上），
> 并把 `/tmp/qwe-baseline/app/pyproject.toml`（git-ignored 的工作副本，内容等于 HEAD 的 Essentials
> 版本）的依赖块改回基线 pin `PySide6==6.11.2`——否则构建出来的是 Essentials，不是基线。
> 这些都写在 `build-baseline-repro.log` 里，可复现。

---

## 4. 用例与 CI

### 4.1 删掉的 5 个 web 测试文件：各自的覆盖损失与 QML 侧对位

用例数用 AST 在删除前的提交上数出来（`logs/deleted-test-counts.log`）：

```
test_web_attachments.py  26
test_web_chat_write.py   23
test_web_e2e_stream.py    1
test_web_settings_write.py 30
test_web_shell_modules.py  20
```

| 文件 | 条数 | 测的是什么 | QML 侧是否有等价 | 结论 |
|---|---|---|---|---|
| `test_web_attachments.py` | 26 | 8 条 `fs:*` 通道（paste-attachment / dropped-entries / attachment-image / read-dir / read-file / write-file / open-folder / reveal-folder）+ 发送时附件读入 | **已补齐（本轮）**。`test_qml_chat_files.py` 从 25 条增至 **40 条**：原有 25 条覆盖投影 / 交付卡 / 白名单 / 发送，新增 15 条钉住 `inspect()` 的 4 条拒绝原因、边界值、只给位置降级、以及发送侧 7 条 note 文案。`test_qml_chat_files_ui.py`(18) 覆盖侧车路径不变式与 QML 属性。 | **只剩 `内容未展开`（死分支）** |
| `test_web_chat_write.py` | 23 | `chat:send` / `abort` / 会话增删改 / `compact` / `todos` / 事件形状 | **是**。`test_host_write.py`(26) 直接调 `ChatHost`（QML 壳同一条路径），比原文件多 3 条 | **完全补齐** |
| `test_web_e2e_stream.py` | 1 | 真 provider 端到端流式（需 `DEVA_E2E_PROVIDER=1`） | **否** | **真实损失**，见下 |
| `test_web_settings_write.py` | 30 | `config:set` / `secrets:*` / `list_models` / persona 增删改与头像 / skill 增删改 / `profile:*` | **大部分是**。`test_settings_write.py`(30) 补 `PersonaStore`/`SkillStore` 写语义（此前 `PersonaStore` 无任何直接用例）；`config/secrets/list_models` 由 `test_settings_service.py`(16)、`test_secrets_vault.py`(21)、`test_settings_vm.py`(18)、`test_provider_setup.py`(14)、`test_provider_adapters.py`(26) 覆盖 | **有缺口**，见下 |
| `test_web_shell_modules.py` | 20 | WebEngine 类查找 / 窗口 overlay 几何 / 桥通道注册 / shim 占位符替换 | **否，也不应补** | 测的对象已删除（`web_shell_window` / `title_bar_overlay` / `DevaBridge` / `shim.js`）。`test_mvvm.py:216` 新增守卫：这两个模块若被加回来，测试立刻失败 |

#### 4.1.1 两处仍未补的缺口（+ 一处本轮已补）

**缺口 A：附件限额的「原因文案」原本没有任何断言 —— 本轮已补齐 15 条。**

删除前，`AttachmentService.inspect()` 的 4 个拒绝分支（`暂不支持的文件类型` /
`图片过大（>5MB）` / `PDF 过大（>20MB）` / `文本过大（>512KB）`）以及发送侧 7 条 note
在 HEAD 的测试里**一条断言都没有**：

```
$ for s in "已忽略未授权文件" "文件已不存在" "读取失败已忽略" "图片过大已忽略" \
           "已忽略不支持的文件" "PDF 过大已忽略" "文本过大已忽略" "内容未展开" "内容没有直接放进消息"; do
    printf "%-24s " "$s"; grep -rl "$s" app/tests/*.py | xargs -r -n1 basename | tr '\n' ' '; echo; done
已忽略未授权文件         test_qml_chat_files.py
文件已不存在
读取失败已忽略
图片过大已忽略
已忽略不支持的文件
PDF 过大已忽略
文本过大已忽略
内容未展开
内容没有直接放进消息
```

**已补并跑绿。** 在 `app/tests/test_qml_chat_files.py` 末尾新增 15 条（10 个测试函数，
其中两个是 parametrize）：

| 新用例 | 钉住什么 |
|---|---|
| `test_inspect_rejects_with_the_reason_the_shell_shows`（4 parametrize） | 4 条拒绝原因原文 + 拒绝时**不进**可读白名单 |
| `test_inspect_accepts_exactly_at_the_limit`（3 parametrize） | 边界值（`==` 上限）是「允许」而非「超限」 |
| `test_oversized_file_selected_by_path_is_attached_as_a_location_only` | 选择框路径超限 → 降级 `kind="file"`，只记 `allowed_files` |
| `test_build_attachment_part_notes_when_the_location_only_file_vanished` | `文件已不存在：`（位置白名单文件消失） |
| `test_build_attachment_part_reports_a_vanished_readable_file_as_a_read_failure` | `读取失败已忽略：`（可读白名单文件消失）——与上一条是**两条不同分支** |
| `test_build_attachment_part_notes_a_path_only_attachment_without_the_body` | `内容没有直接放进消息`，且正文不含文件内容 |
| `test_build_attachment_part_notes_an_oversized_selected_text_file` | 发送时二次判体积 → `文本过大已忽略` |
| `test_build_attachment_part_notes_an_unreadable_authorised_file` | `读取失败已忽略`（用 `monkeypatch` 让 `read_bytes` 抛 `OSError`，三平台可跑） |
| `test_build_attachment_part_notes_an_image_whose_bytes_exceed_the_limit` | `图片过大已忽略`（类型合规但字节超限） |
| `test_build_attachment_part_notes_a_pdf_that_openai_protocol_cannot_read` | OpenAI 协议下跳过 PDF 的说明文案 |

仍未覆盖的只剩 `内容未展开`（`[附件文件夹]` 分支）与 `已忽略不支持的文件`（图片魔数嗅探失败）
——这两条本轮**没有**补：前者当前**没有任何路径**会往 `allowed_dirs` 写（模块 docstring
已写明），测它只能手工塞集合，等于测死分支；后者需要构造一个扩展名是图片、内容却不是
任何已知图片魔数的文件，属于边界构造，收益低于上面 9 条用户实际会撞到的文案。
两条都留在「未完成 + 原因」里，不假装覆盖。

> 补测过程发现并修正了一处**我自己的**错误假设（不是产品 bug）：`.txt` 走可读白名单，
> 文件消失时报的是 `读取失败已忽略`；只有位置白名单（`allowed_files`）才报 `文件已不存在`。
> 两条分支现在各有一条用例钉着。

**缺口 B：`profile:*` 三条通道在 QML 侧没有对位实现。**
基线 `bridge.py` 注册了 `profile:get` / `profile:set-avatar` / `profile:set-avatar-image`。
HEAD 里 `grep -rn "profile" app/src/mvvm --include=*.py` **无命中**（只有 persona 头像）。
即：**「用户自己的头像」这个能力整体消失了**，不是覆盖问题而是能力缺失。
`test_settings_write.py:158-186` 只覆盖 persona 头像（`persona_avatar_round_trip` /
`persona_clear_avatar_image_removes_all_extensions`）。
**这是删除带来的真实能力损失**，需产品侧确认是否需要补一个 QML 端入口。

**缺口 C：端到端真 provider 流式用例变成 0 条。**
`test_web_e2e_stream.py` 只有 1 条，且默认是 skip（需 `DEVA_E2E_PROVIDER=1` + 真 key）。
它删除后，**仓库里不再有任何「真 provider → 真 UI 更新」的自动化入口**。
`docs/ROADMAP-NEXT.md` 的 R3 已在 `6f02994` 记明这一点。本轮**未重写**——原因：
重写需要真 key，本环境没有，写了也只能是 skip，等于没测。

#### 4.1.2 其余能力去向对照（`chat:*` / `config:` / `secrets:` 等）

| 基线通道 | HEAD 的对位 | 覆盖它的用例 |
|---|---|---|
| `chat:send` / `abort` / `compact` / `todos` / 会话 CRUD / `attach` | `ChatHost` 同名方法 | `test_host_write.py` 26 条 |
| `config:set` | `SettingsService` | `test_settings_service.py` 16 条 |
| `secrets:*` | `SecretsVault` | `test_secrets_vault.py` 21 条 |
| `provider:list-models` | `ProviderGateway.list_models` | `test_provider_adapters.py` 26 条 |
| `personas:*` / `skills:*`（写） | `PersonaStore` / `SkillStore` | `test_settings_write.py` 30 条（新增）；读路径 `test_skill_store.py` 19 条 |
| `profile:*` | **无** | **无**（缺口 B） |
| `fs:*` 8 条 | 直接调 `AttachmentService` 4 个方法 / `ToolRuntime` 自己的守卫 | **已补齐**（`test_qml_chat_files.py` 40 条，见缺口 A） |

### 4.2 全量 pytest：前 / 后真实计数

两次都从 `app/` 目录、`env -u AI_UPPER_HOME` 跑，排除环境变量干扰。

**基线（`/tmp/qwe-baseline`，commit `1d53e4a`）** — `logs/pytest-baseline-authoritative.log`：

```
SKIPPED [1] tests/test_build_tool_compat.py:1697: the auto-link pragma belongs to the Windows pyconfig.h
SKIPPED [1] tests/test_build_tool_compat.py:1751: handle inheritance for GUI-subsystem children belongs to Windows
SKIPPED [1] tests/test_e2e_local.py:447: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_e2e_local.py:488: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_native_deployment.py:177: requires cc, patchelf and readelf
SKIPPED [1] tests/test_web_e2e_stream.py:131: 端到端实跑需要真 provider：...
1250 passed, 6 skipped in 27.52s
EXIT=0
```

**HEAD（`4bea1ba`）** — `logs/pytest-head-authoritative.log`：

```
SKIPPED [1] tests/test_build_tool_compat.py:1699: the auto-link pragma belongs to the Windows pyconfig.h
SKIPPED [1] tests/test_build_tool_compat.py:1753: handle inheritance for GUI-subsystem children belongs to Windows
SKIPPED [1] tests/test_e2e_local.py:447: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_e2e_local.py:488: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_native_deployment.py:177: requires cc, patchelf and readelf
1204 passed, 5 skipped in 26.08s
EXIT=0
```

**HEAD + 本轮补齐的 15 条附件用例** — `logs/pytest-head-after-gapA.log` / `-skips.log`：

```
SKIPPED [1] tests/test_build_tool_compat.py:1699: the auto-link pragma belongs to the Windows pyconfig.h
SKIPPED [1] tests/test_build_tool_compat.py:1753: handle inheritance for GUI-subsystem children belongs to Windows
SKIPPED [1] tests/test_e2e_local.py:447: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_e2e_local.py:488: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_native_deployment.py:177: requires cc, patchelf and readelf
1219 passed, 5 skipped in 26.14s
EXIT=0
```

三个数字的关系：1250（基线）→ 1204（`4bea1ba`，纯删除阶段的终值）→ **1219**（本轮补测后）。
**交付结论用 1219**；1204 是补测之前的中间态，保留它是为了让删除阶段的归因算式和
`749d407` 的提交信息（`1148 → 1204`）能对上。

**逐条归因**（`logs/pytest-delta-explained.log`）：

```
### 逐文件用例数：基线 1d53e4a vs HEAD
15c15
<      29 tests/test_deliverables.py
---
>      26 tests/test_deliverables.py
19a20
>      26 tests/test_host_write.py
48a50
>      30 tests/test_settings_write.py
56,60d57
<      26 tests/test_web_attachments.py
<      23 tests/test_web_chat_write.py
<       1 tests/test_web_e2e_stream.py
<      30 tests/test_web_settings_write.py
<      20 tests/test_web_shell_modules.py

### 合计
基线 collected: 1256
HEAD  collected: 1209

### 换算
删除：26 + 23 + 1 + 30 + 20 = 100
新增：26 + 30 = 56
test_deliverables：29 -> 26（-3，删掉 5 个 bridge 用例，补 2 个 store 往返用例）
净计：1256 - 100 + 56 - 3 = 1209

passed = 1250 - 99 + 56 - 3 = 1204 ；skipped = 6 - 1 = 5 ；新增失败 = 0
```

补测之后再补一行（`test_qml_chat_files.py` 25 → 40，+15）：

```
1219 = 1204 + 15 ；skipped 仍为 5 ；新增失败 = 0
```

- 删掉的 100 条里，只有 `test_web_e2e_stream` 那 1 条原本是 skip（真 provider），其余 99 条原本 passed。
- **新增失败：0**。三次运行（基线 / `4bea1ba` / 补测后）全部 `EXIT=0`，没有 `failed` 字样。
- 唯一变化的 skip 是 `test_web_e2e_stream.py:131`——该文件已删，skip 也随之消失。
  剩下 5 条 skip 全部与 Qt/平台/环境有关，与本次改动无关。

### 4.3 CI 里的 web 相关任务/步骤

`.github/workflows/validate.yml` 在基线里**没有**独立的 web job；web 相关的内容只有三处，
已全部处理（见 §2.5）：py38 行的 pin、Linux apt 的 Chromium 库、smoke 的并集断言。
`git show 1d53e4a:.github/workflows/validate.yml | grep -niE "webengine|deva web"` 命中 **5 行**
（`:213/:216/:222` 讲 Chromium 的库依赖，`:444/:447` 是 smoke 的并集断言），
HEAD 里只剩 `:84` 与 `:218` 两处**注释**（解释为什么不用 Addons、为什么不再需要 Chromium 库）。
`:84` 处是新增的说明，`:218` 是原 :213/:216/:222 三行的改写结果。

---

## 5. 文档

### 5.1 现行文档（`6f02994`，9 个文件 +83/−55）

| 文件 | 改了什么 |
|---|---|
| `README.md` | 目录树注释「装配并启动主窗口」→「装配并启动 QML 壳」；安装示例 `PySide6==6.11.2` → `PySide6-Essentials==6.11.2` 并加一段解释 Addons/WebEngine；「Qt 裁剪」段说明 Addons 一档才含 WebEngine；「验证」段从「打开承载原版渲染层的 Qt 主窗口」改为「打开 QML 三栏壳（正文是 `QTextDocument`）；**仓库里没有第二条界面路线**」 |
| `docs/DEVELOPMENT_GUIDE.md` | 三处 pin 示例改 Essentials；§9.3 补「本应用只声明 Essentials，Addons 根本不会被下载」；§9.5 补「（两者只有 Addons 才带，本应用不再声明它）」 |
| `docs/ROADMAP-NEXT.md` | R1「补 Web 层覆盖」→「补 QML 页面覆盖」；R3 记明 `test_web_e2e_stream.py` 已删、当前无真 provider 自动化入口；R12 删掉「改用 `QWebEngineView.grab()`」这条已不可能的退路；§414 改为「本工程已彻底移除 QtWebEngine」 |
| `docs/BUILD-PROGRESS.md` | 顶部加「2026-11-17 注：本文件是历史台账」+ 指向本报告的说明 |
| `docs/STAGE5-CLOSEOUT-REPORT.md` | 顶部加历史台账说明 |
| `docs/STAGE6-CLOSEOUT-REPORT.md` | **当时漏了**（此处原文写「同样加历史台账说明」与事实不符，2026-11-21 复验发现并已补，见 §9.6） |
| `docs/audit/IPC-158-LEDGER.md` | 顶部说明「通道统计对象 `DevaBridge` 已删」 |
| `docs/audit/qml-shell-audit.md` | §4.5 覆盖表去掉已删用例，补 QML 附件/交付用例行，截图入口改正 |
| `scripts/parity/deva_original_shots.sh` | 去掉 `AI_UPPER_UI` 相关传参 |
| `scripts/parity/qml_page_shot.sh` | 删掉 `AI_UPPER_UI=qml` 那行 |

### 5.2 死指令清扫结果

「按 `AI_UPPER_UI=web` 启动 web 界面」这类**可执行指令**在仓库里**已经 0 条**：

```
$ grep -rn "UI=web\|ui=web\|--ui\b\|DEVA_UI" --exclude-dir=out --exclude-dir=.git .
README.md:492:应用入口是 `app/src/main.py`…；仓库里没有第二条界面路线。 …
app/src/main.py:8:装配（原 `AI_UPPER_UI=web` 的 QtWebEngine 承载窗口已随 …
app/src/mvvm/services/attachments.py:19:能力差异要如实记：QML 壳只有一个「回形针」入口，**没有**拖入与粘贴附件（web 入口当年
app/tests/test_qml_chat_files.py:7:… 与 web 入口同一条不变式 …
app/tests/test_qml_chat_files.py:299:…（web 入口踩过同一个坑）。
app/tests/test_mvvm.py:215:谁把同功能文件加回来，这条会立刻失败，而不是多出一条没人测的界面路线。
app/tests/test_qml_chat_files_ui.py:3:这条链路与 web 入口共用同一份服务 …
```

全部是**解释「web 入口当年怎样」的散文/注释**，没有一条是让人照着做的指令。

### 5.3 关于「启动变快」的说法

**本报告不主张启动变快，也没有测首帧耗时。** 本轮的实际收益是：
包体 522M → 256M、依赖面从「整个 Qt + Chromium」收敛到 Essentials、
产物里不再有 190 MB 的 `libQt6WebEngineCore.so.6` 与 53 个 Chromium locale pak。
启动耗时未测——原因：测量口径（冷启动 / 热启动 / 首帧 / 进程退出）不同结论会差很多，
在没有基线对照实验的情况下给数字属于编造。

---

## 6. 逐条结项表

| # | 要求 | 状态 | 关键证据 |
|---|---|---|---|
| 1 | 修红 + 清残留 | **完成** | 5 个 web 测试文件 + 3 个 parity 脚本 + 2 个 audit 工具删除；148 行残留逐行定性：**70 文档 / 11 注释 / 25 docstring / 42 可执行（全在裁剪器与其夹具，应用运行时 0 行）**；AST 扫 189 py 文件 `import` **0 命中**；`services/deliverables.py` 与 `bridge.py` 的 `display_messages` 均在用；`markdown/`+`qml/` 零改动，5 张对比页 md5 与基线逐字节相同 |
| 2 | 依赖面 | **完成（CI 实跑未验证）** | pin 差异见 `pin-diff.log`；纯 Essentials venv 7 个模块导入 OK、`QtWebEngineWidgets` ImportError；9 个 wheel 中央目录 6/6 QML 谓词全 YES；7 个发布目标逐行说明均不需 Addons；**未验证**：本轮 HEAD 未触发真实 CI（`e2b9392` 不含本轮删除提交） |
| 3 | 打包链 | **完成** | `build-final3.log` EXIT=0；`Qt pruning: … freed 100 MB`；`du` 522M→256M；`find` WebEngine/WebChannel/Process/locales 命中 **0**；产物实跑 `QML OK … size=1280x820` EXIT=0 |
| 4 | 用例与 CI | **完成（2 处缺口已如实记）** | pytest 1250P/6S → **1219P/5S**（删 100 / 补 56 / 再补 15），`EXIT=0`，新增失败 0，算式 `1256-100+56-3=1209` 与 `1219=1204+15`；5 个被删文件逐条给出覆盖损失；附件限额文案**本轮已补齐 15 条**；仍缺 `profile:*`（能力缺失）与真 provider E2E，写明原因 |
| 5 | 文档 | **完成（2026-11-21 修正一处）** | 9 个文件 +83/−55；「`AI_UPPER_UI=web` 启动」类**可执行指令 0 条**；四条历史台账加了「不改写」的顶部说明；ROADMAP 三处与现状对齐。**更正**：`STAGE6-CLOSEOUT-REPORT.md` 当时**没有**加注（本条原写「已加」），2026-11-21 复验时补上，见 §9.6 |

### 6.1 明确「未完成 + 原因」

| 项 | 状态 | 原因 |
|---|---|---|
| `[附件文件夹]`（`内容未展开`）与 `已忽略不支持的文件`（图片魔数嗅探失败）两条分支 | **未完成** | 前者当前**没有任何路径**会往 `allowed_dirs` 写（模块 docstring 已写明），测它只能手工塞集合 = 测死分支；后者需构造「扩展名是图片、内容不是任何已知魔数」的边界文件。其余 9 条附件原因文案**已补并跑绿** |
| `profile:get` / `profile:set-avatar(-image)` 的 QML 对位 | **未完成** | 需要产品决策（QML 壳要不要「用户头像」入口）；本轮无权扩大范围 |
| 真 provider 端到端用例 | **未完成** | 需真 key，本环境没有；写了也只能 skip |
| 本轮 HEAD 的 GitHub CI 实跑 | **未验证** | 硬约束「不 push」，无法触发；只有 wheel 级静态验证 |
| 首帧启动耗时对比 | **未测** | 无基线对照实验，不给编造数字 |
| `SettingsModal.qml:372` 的 `extensionsSummary` TypeError | **未修（基线既有）** | 不在授权范围；已在 §1.4 标注为**非本轮引入**。2026-11-21 复验仍未修，结论不变（`out/qwebengine-verify/logs/27-extensions-issue.log`） |

---

## 7. 提交清单（全部本地，`develop`，未 push）

```
a191a9c refactor(webengine): 删除 QtWebEngine 承载层、QtWebChannel 桥与渲染层资产
        23 files changed, 87010 deletions(-)
749d407 refactor(webengine): 附件服务去死通道，补回宿主与设置写路径的用例
        13 files changed, 839 insertions(+), 1191 deletions(-)
        全量：1148 passed / 5 skipped → 1204 passed / 5 skipped
0b02bd1 build(webengine): 依赖面收口到 PySide6-Essentials，打包链不再产 WebEngine
        12 files changed, 103 insertions(+), 86 deletions(-)
6f02994 docs(webengine): 文档改为当前真实状态，去掉已删除入口的死指令
         9 files changed, 83 insertions(+), 55 deletions(-)
e725c8d perf(sessions): 列表首屏批量载入，目录只扫一遍
         1 file changed, 58 insertions(+), 6 deletions(-)   ← 上一轮未提交的启动优化，保留
7ce85fa chore(evidence): 更新 QML 壳 offscreen 实跑截图（删 WebEngine 后重拍）
4bea1ba chore(evidence): py38 收尾报告补第二次权威 run 的逐 job 结论
0433783 test(attachments): 补回被删 web 用例守住的限额与原因文案   ← 本轮补测
         1 file changed, 152 insertions(+)
         全量：1204 passed / 5 skipped → 1219 passed / 5 skipped
```

`1d53e4a..HEAD` 总计 **64 files changed, 1400 insertions(+), 88387 deletions(-)**。
（`0433783` 之前是 63 / 1248；本报告自身与证据文件在下一个提交里。）
仓内除 `out/` 与本轮新增测试外无改动。

---

## 8. 证据文件索引（`out/qwebengine-remove/logs/`）

| 文件 | 内容 |
|---|---|
| `pytest-baseline-authoritative.log` / `pytest-head-authoritative.log` / `pytest-head-after-gapA.log` | 基线 / `4bea1ba` / 补测后 三次全量 pytest 原始输出 |
| `pytest-head-after-gapA-skips.log` | 补测后那次的 5 条 skip 原因（`-rs`） |
| `pytest-delta-explained.log` | 逐文件用例数差异与算式 |
| `pin-diff.log` | pin 前后原文 + diff |
| `wheel-qml-predicates-essentials.log` | 9 个 Essentials wheel 的 QML 谓词表（HTTP Range 读中央目录） |
| `wheel-contents.log` | Addons aarch64 wheel 里真实的 WebEngine 载荷对照 |
| `essentials-import-proof.log` / `essentials-modules-proof.log` / `essentials-qml-modules.log` | 纯 Essentials venv 的导入与 QML 目录测量 |
| `final-essentials-launch.log` | 纯 Essentials 下 QML 壳实跑 |
| `grep-canonical-final.txt` / `grep-canonical-reclassified.txt` | 148 行残留原文 + 逐行定性（含 42 条「可执行」清单） |
| `ast-import-recheck-final.txt` | 独立补跑：189 个 py 文件 import 命中 0 |
| `proof-no-webengine-final2.log` | AST 扫描 + 产物检查 |
| `dead-instructions-final.txt` | §5.2 死指令扫描的原始输出 |
| `build-final3.log` | HEAD 全量构建（EXIT=0） |
| `build-baseline-repro.log` | 基线 `1d53e4a` 独立重建（交叉验证） |
| `du-before.txt` / `du-before-repro.txt` / `du-after-final.txt` / `dist-webengine-before.txt` | 体积与载荷清单（含基线重建的复核值） |
| `final-source-launch2.log` / `final-source-launch3.log` / `final-packaged-launch2.log` | 源码树（`4bea1ba` / `0433783`）与产物两条启动路径的原始 `QML OK` |
| `appearance-before-after.log` | 5 张对比页的基线 vs HEAD 逐字节 md5 |
| `shots-final3.log` / `shots-final3-sizes.log` | 18 页截图 rc 与尺寸/md5（`0433783` 重拍，即 `shots/` 里的当前图） |
| `shots-final2.log` / `shots-final2-sizes.log` | 上一轮（`4bea1ba`）同 18 页的记录，保留用于对比 |
| `shots-reltime-diff-explained.txt` | 多轮 HEAD 截图的 6px 竖带差异归因（相对时间标签） |
| `deleted-test-counts.log` | 5 个被删文件的用例数（AST） |
| `../shots/*.png` | 18 张 offscreen 实拍 PNG（1280×820） |

---

# 9. 复验（2026-11-21，HEAD `b98d59e`）

本节不是重做一遍删除，而是**在今天的 HEAD 上独立复验**上文的结论。上文写于 2026-11-17
（HEAD `0433783`/`4db9671`），此后 `develop` 又前进到 `b98d59e`（渲染优化若干提交）。
复验的目的只有一个：**确认删除结论没有被后续提交悄悄推翻**。

全部原始输出在 `out/qwebengine-verify/logs/`（编号即下文引用号），截图在
`out/qwebengine-verify/shots/`。环境：`aarch64`、Python 3.13.5、pytest 9.2.0、
PySide6 6.11.2（`logs/46-env-facts.log`）。

## 9.1 对账（复验时的真实工作区状态）

```
$ git rev-parse --abbrev-ref HEAD
develop
$ git describe --always --dirty
v0.17.28-165-gb98d59e-dirty
$ git status --porcelain | grep -v '^?? out/'
(none — 除 out/ 下新增证据外工作区干净)
$ git status --porcelain | grep -c '^ M'
0
$ git diff --stat
（空）
$ git diff --stat 1d53e4a..HEAD | tail -1
 364 files changed, 21933 insertions(+), 88480 deletions(-)
$ git log --oneline 1d53e4a..HEAD | wc -l
30
```

（`logs/39-reconcile.log`）基线 `1d53e4a` 到 HEAD 共 30 个提交，其中 8 个属于本次移除
（§7 的提交清单），其余 22 个是 `e725c8d` 之后不同主题的渲染/会话优化。工作区除 `out/`
下本轮新增的证据目录外**没有任何改动**，没有覆盖任何已完成的工作。

## 9.2 依赖面：pin、纯 Essentials 实跑、7 平台

pin 与 2026-11-17 一致，未再变更（`logs/17-pin-diff.log` 是相对 `1d53e4a` 的 diff，只有
`PySide6==6.11.2` → `PySide6-Essentials==6.11.2` 一行 + 3 行注释；`app/pyproject.toml` 的值
见 `logs/19-pins.log:30`）。**本次复验没有改动任何 pin。**

纯 Essentials 环境（`/tmp/qwe-verify-venv`，`pip list` 里只有 `PySide6_Essentials==6.11.2`
与 `shiboken6==6.11.2`，**没有** `PySide6` 元包、**没有** `PySide6_Addons`）：

```
$ /tmp/qwe-verify-venv/bin/python -V
Python 3.14.9
ok  PySide6.QtCore / …/QtCore.abi3.so
ok  PySide6.QtGui / …/QtGui.abi3.so
ok  PySide6.QtWidgets / …/QtWidgets.abi3.so
ok  PySide6.QtQml / …/QtQml.abi3.so
ok  PySide6.QtQuick / …/QtQuick.abi3.so
ok  PySide6.QtSvg / …/QtSvg.abi3.so
ok  PySide6.QtNetwork / …/QtNetwork.abi3.so
absent QtWebEngineWidgets -> ModuleNotFoundError No module named 'PySide6.QtWebEngineWidgets'
absent QtWebEngineCore -> ModuleNotFoundError No module named 'PySide6.QtWebEngineCore'
absent QtWebEngineQuick -> ModuleNotFoundError No module named 'PySide6.QtWebEngineQuick'
absent QtWebChannel -> ModuleNotFoundError No module named 'PySide6.QtWebChannel'
PySide6_Addons present: False
meta PySide6 present: False
```

（`logs/03-essentials-imports.log`）同一 venv 里 QML 壳实跑（`AI_UPPER_HOME=/tmp/qwe-verify-home`）：

```
QML OK platform=offscreen title='Deva' sessions=0 active='' plain=False turn_stop='' deltas=0 \
  home=/tmp/qwe-verify-home png=/tmp/qwe-verify-ess.png size=1280x820
```

（`logs/04-essentials-launch.log`；该 venv 额外装了 `pillow` 用于截图比对，与 Qt 依赖无关。）
这张 `/tmp/qwe-verify-ess.png` 的 md5 与 HEAD 产物启动图、基线产物启动图**三者完全相同**
（`dbdddec9793656631b9041db4d2b3030`），即首屏在删前/删后/纯 Essentials 三种环境里逐字节一致。

7 平台矩阵复核（`logs/28-pypi-wheels.log`，PyPI 文件列表的真实输出）：`PySide6-Essentials
6.11.2` 有 macOS universal2 / manylinux_2_34 x86_64 / manylinux_2_39 aarch64 / win_amd64 /
win_arm64 五个 wheel，`6.6.3.1`（py38 行）有 cp38-abi3 的四个。**没有哪一行因为缺 Essentials
而必须回到 Addons**；py38 行用的是 `PySide6-Essentials==6.6.3.1`，已在 `validate.yml:112`
（`logs/20-ci.log`）。**本次复验未触发真实 CI**（约束「不 push」），见 §9.7。

## 9.3 代码面：没有第二条界面路线

```
$ python ast_scan.py app/src tools scripts launcher
scanned py files: 123
webengine/webchannel imports: 0
```

（`logs/44-final-scan.log` 第 1 段；全仓含 tests 的版本是 `logs/02-ast-imports.log`：190 个 py 文件、0 命中。）

`app/src` 里只剩 3 行**注释/docstring**提到旧结构，没有一行可执行：

```
$ grep -rnE 'QtWebEngine|QtWebChannel|web_shell_window|DevaBridge|AI_UPPER_UI' app/src
app/src/main.py:8:装配（原 `AI_UPPER_UI=web` 的 QtWebEngine 承载窗口已随 `mvvm.views.web_shell_window`
app/src/mvvm/services/attachments.py:14:八条渲染层通道，它们唯一的调用方是已删除的 `DevaBridge`（QtWebChannel）。QML 壳不走
app/src/mvvm/webui/bridge.py:3:本模块原先还承载 QtWebChannel 的桥对象（`DevaBridge`），把原版渲染层的
count=3
```

（`logs/44-final-scan.log` 第 3 段）`AI_UPPER_UI` 全仓只剩 `main.py:8` 这一句历史注释
（`logs/40-doc-and-env-scan.log`、`logs/14-ui-env.log`、`logs/15-dead-instructions.log`）。

仍在被 QML 壳使用的两条能力**没有被连带删除**（`logs/24-bridge-callers.log`）：
`mvvm.webui.bridge.display_messages` 被 `mvvm/webui/host.py:46` 导入、用于 `:360/:415/:504/:594`；
`mvvm.services.deliverables` 被 `qml_shell.py:35`、`qml_shell_sessions.py:26`、`transcript_parts.py:27` 导入。
`BridgeError` 同样在 `host.py:46` 被使用。

## 9.4 打包链：本次会话两边各重建一次

两侧同命令、同 target，都是独立全量构建：

```
# 删后（HEAD b98d59e）
$ PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tools/build.py --target linux-arm64
Qt pruning: removed 232 file(s) and 87 director(ies), freed 100 MB
SMOKE PASS 6 modules (launcher registers merged bundles)
SMOKE PASS launcher
READY: /home/agent/shared_workspace/ai_upper/dist/ai_upper
EXIT=0
```

（`logs/13-build-head.log`）

```
# 删前（/tmp/qwe-baseline-src @ 1d53e4a，pyproject 用 PySide6==6.11.2）
Qt pruning: removed 496 file(s) and 141 director(ies), freed 258 MB
SMOKE PASS 6 modules (launcher registers merged bundles)
SMOKE PASS launcher
READY: /tmp/qwe-baseline-src/dist/ai_upper
EXIT=0
```

（`logs/25-build-baseline.log`）

体积（`logs/38-du-before-after.txt`）：

| | 删前 (1d53e4a) | 删后 (HEAD) | 差 |
|---|---|---|---|
| `du -sh dist/ai_upper` | 522M | 256M | −266M |
| `du -sb dist/ai_upper` | 534860827 | 256543291 | −278317536 B = −265.4 MiB |
| `du -sh site-packages/PySide6` | 406M | 144M | −262M |
| `find … -iname '*WebEngine*' \| wc -l` | **10** | **0** | −10 |

删前那 10 条残留（`logs/36-dist-webengine-baseline.log`）合计 240M，明细里最大的是
`Qt/lib/libQt6WebEngineCore.so.6` 182M、`qtwebengine_locales` 44M、`qtwebengine_devtools_resources.pak` 12M。
（这与 2026-11-17 报告的 522M→256M 完全一致；本次是**重新跑出来的**，不是抄。）

删后产物清点（`logs/42-head-dist-inventory.log`）：

```
$ find dist/ai_upper \( -name '*QtWebEngine*' -o -name '*QtWebChannel*' -o -name 'QtWebEngineProcess' \
    -o -name 'qtwebengine*' -o -name '*qwebchannel*' \) | wc -l
0
$ ls dist/ai_upper/assets
personas
qml
$ ls dist/ai_upper/site-packages/PySide6/*.so
QtCore QtGui QtNetwork QtOpenGL QtQml QtQuick QtQuickControls2 QtWidgets   （8 个，全是 Essentials 的）
```

两条产物都实跑了，**都打印 QML OK**：

```
# 删后产物
QML OK … deltas=0 home=/home/agent/shared_workspace/ai_upper/dist/ai_upper png=/tmp/qwe-verify-pack2.png size=1280x820
EXIT=0                                                                    （logs/23-packaged-launch.log）

# 删前产物（对照）
QML OK … deltas=0 home=/tmp/qwe-baseline-src/dist/ai_upper png=/tmp/qwe-baseline-launch.png size=1280x820
EXIT=0                                                                    （logs/37-baseline-packaged-launch.log）
```

两张截图 md5 相同（`dbdddec9793656631b9041db4d2b3030`）。即：**删掉的 240M 载荷，一个像素都没用到。**

## 9.5 用例与 CI

```
$ cd app && env -u AI_UPPER_HOME -u DEVA_HOME ../.venv/bin/python -m pytest tests -q
1260 passed, 5 skipped in 29.26s
EXIT=0
```

（`logs/45-pytest-final.log`；skip 原因逐条见 `logs/26-pytest-skips.log`：2 条 Windows-only、
2 条需 `AI_UPPER_E2E=1`、1 条需 cc/patchelf/readelf。）

三次全量计数并列：

| 树 | passed | skipped | 出处 |
|---|---|---|---|
| 基线 `1d53e4a` | 1250 | 6 | `logs/06-pytest-baseline.log` |
| 移除完成点 `4db9671` | 1219 | 5 | `logs/34-pytest-at-removal-end.log` |
| 今天 HEAD `b98d59e` | **1260** | **5** | `logs/45-pytest-final.log` |

`4db9671 → HEAD` 的 +41 条全部来自后续渲染/会话工作，逐文件差额：
`test_ci_tail +2`、`test_markdown_body +6`、`test_markdown_chunked +20`、`test_markdown_document +7`、
`test_qml_shell +4`、`test_qt_prune +1`、`test_verify +1`（`logs/35-counts-removal-vs-head.log`）。
**新增失败 0**；三次运行 `EXIT=0`。

替代用例单独跑：`173 passed in 1.45s`（`logs/33-replacement-tests.log`，覆盖
`test_host_write.py` / `test_settings_write.py` / `test_qml_chat_files*.py`）。

CI 侧（`logs/41-ci-scan.log`）：

```
$ grep -nE '^  [a-z0-9_-]+:$' .github/workflows/validate.yml
19:  build-tool-compat:      49:  native-integration:      515:  aggregate-artifacts:
$ grep -nE 'test_web|web_shell|port_shots|port_run|renderer' .github/workflows/*.yml
(0 hits)
```

剩下的 2 行 WebEngine 字样（`validate.yml:228` 附近的注释）是在解释「Linux 依赖里为什么
不需要 Chromium 运行库」，不是要执行的步骤。

## 9.6 文档：死指令复扫

```
$ grep -rn "AI_UPPER_UI" . --exclude-dir=.git --exclude-dir=out --exclude-dir=build \
    --exclude-dir=dist --exclude-dir=.venv --exclude-dir=deva --exclude-dir=.cache
app/src/main.py:8:装配（原 `AI_UPPER_UI=web` 的 QtWebEngine 承载窗口已随 …
```

（`logs/40-doc-and-env-scan.log`）**可执行指令 0 条**，只有一句历史解释。

**本轮发现并补了一处真实遗漏：** `6f02994` 给 `STAGE5-CLOSEOUT-REPORT.md` 加了历史台账注，
但 `docs/STAGE6-CLOSEOUT-REPORT.md` 没有加（原文 §5.1 把它与 STAGE5 并列写成「同样加历史台账
说明」，与事实不符）。该文里有可直接照抄、但现在必然失败的指令：

```
$ strings dist/ai_upper/ai_upper | grep -c "from deva_web import main"
0
$ ls app/tests/test_web_e2e_stream.py app/src/deva_web.py app/src/mvvm/views/web_shell_window.py app/assets/renderer
ls: cannot access …: No such file or directory   （四项全部不存在）
```

（`logs/43-stage6-dead-commands.log`）已在 `docs/STAGE6-CLOSEOUT-REPORT.md` 头部补注，
写明这些命令无法重放、当前入口是 `app/src/main.py` → `qml_shell.run()`。上文 §5.1 的那一行
据此**更正**为：STAGE5 加了注；STAGE6 是本次补加。

现行文档（README / DEVELOPMENT_GUIDE / ROADMAP-NEXT / MIGRATION-PLAN）复扫：
`deva_web`、`port_shots`、`port_run`、`test_web_` 均**0 命中**，只有 `ROADMAP-NEXT.md:147`
一句「`test_web_e2e_stream.py` 已随 QtWebEngine 一并删除」的历史陈述。

**一处需要说明的差异（不是本报告编造，是基线树自己的状态）：** 基线 `1d53e4a` 的 `app/src`
里仍然有 `web_shell_window.py` 与写满 WebEngine 的 `main.py`，而 `tools/ai_upper/qt_prune.py`
按 import 裁剪——它只看到 `PySide6.QtWebEngineWidgets` 被**条件导入**，所以删掉了
496 个文件后仍然**没有**删掉 240M 的 WebEngine 载荷（`Qt/lib/libQt6WebEngineCore.so.6` 等
10 个路径完整留在基线产物里，`logs/36-dist-webengine-baseline.log`）。这正是本轮改动
真正解决的东西：把"条件导入"变成"没有导入"，裁剪器才敢删。

## 9.7 本轮复验的「未完成 / 未验证」

| 项 | 状态 | 原因 |
|---|---|---|
| 真实 GitHub CI 复跑 | **未验证** | 硬约束「只在本地 develop 提交，不 push」，无法触发。本轮只有 wheel 级静态验证（`logs/28-pypi-wheels.log`）与本地全量 pytest |
| 其余 6 个发布目标的**真机构建** | **未验证** | 本机只有 aarch64 Linux 工具链；macOS/Windows/arm64-Windows 只有 wheel 可用性证据，没有交叉构建产物 |
| 首帧启动耗时 | **未测** | 无基线对照实验；给出数字即为编造 |
| 真 provider 端到端 | **未完成** | 无真 key，自 `test_web_e2e_stream.py` 删除后仓库无此类入口（能力损失，见 §4.1 缺口 C） |
| `profile:*` 三条通道的 QML 对位 | **未完成** | 需产品决策，见 §4.1 缺口 B |
| `settings-about` 等 4 页与上一轮截图的 md5 差异 | **已归因，非回归** | 逐像素比对 bbox 全部落在 `x=289–296`（左栏会话列表的相对时间标签），单页最多 490 px / 0.047%，`empty.png`/`first-run.png` 逐字节相同（`logs/16b-pixel-diff-vs-prior.log`） |
| `SettingsModal.qml:372` `extensionsSummary` TypeError | **未修（基线既有）** | 与 2026-11-17 结论一致：基线 `qml_shell.py` 也没有该 slot，非本次引入 |
| 打包产物把 `AI_UPPER_HOME` 覆盖为 entry_dir | **已记录，未改** | `launcher/src/AiUpper.cpp:881` 无条件导出；导致 headless 实测写在 `dist/ai_upper/data/chats`。属 launcher 既有行为，不在本次授权范围 |

## 9.8 本次复验新增/更正的产物

| 路径 | 内容 |
|---|---|
| `out/qwebengine-verify/README.md` | 证据目录说明与命令对照 |
| `out/qwebengine-verify/logs/01…46`（含 `16b`） | 47 份原始日志（对账、AST、Essentials、构建、du、pytest、CI、文档扫描、STAGE6 死命令） |
| `out/qwebengine-verify/shots/*.png` | 18 张 offscreen 实拍 + 1 张 Essentials 启动图 |
| `docs/STAGE6-CLOSEOUT-REPORT.md` | 头部补历史台账注（本轮唯一代码/文档改动） |

**复验结论：6 条结项的结论在 HEAD `b98d59e` 上全部仍然成立，未发现被后续提交推翻的项；
唯一实质修正是 STAGE6 那处遗漏的历史台账注。**
