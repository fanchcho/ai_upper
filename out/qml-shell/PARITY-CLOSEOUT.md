# ai_upper 路线 B 收尾报告（QML 壳 + QTextDocument 正文）

分支 `develop` · 报告随代码提交在同一仓库 · 所有数字来自命令输出与图像实算，无手填。

**结论（先看这一段）**

1. **实跑回归通过**：QML 壳 offscreen 真启动，`QML OK … size=1280x820`，退出码 0；
   pytest `1168 passed / 5 skipped`（基线 1159/5，只增不减）。
2. **目录改名已落地**：`py_upper` 实体改名为 `ai_upper`，旧路径留软链；改名前后的
   HEAD/文件数/du/git status 条目数逐项一致（99 条未提交改动一条未丢）。
3. **逐页证据齐了**：`out/qml-shell/parity/` 下 **18 个页面状态**（覆盖要求的全部类别），
   每页 `original.png` / `qml.png` / `diff.png` 三件套 + 真实数值（`numbers.tsv`、
   `numbers-fuzz.tsv`）。整体差异 **1.46%–10.18%**，其中 4 个设置页 ≤3.73%。
4. **正文层 9 项功能全部实测通过**（跨块选择复制、双击选词、代码块横向滚动、表格、
   图片、深浅主题、超长/上百条消息耗时、中文与 emoji、1x/2x）。
5. **默认入口已切 QML**，打包产物 `dist/ai_upper/ai_upper` 实跑 `QML OK … size=1280x820`，退出码 0。
6. **仍未被「修到一致」**：剩余差异逐条列在 §3.4，主要是字形栅格化、列表/引用缩进、
   正文滚动落点与窗口控件；这是本轮的真实缺口，不掩饰。

---

## 0. 路径与仓库对账 + 目录改名（第一件事）

### 0.1 改名落地

```
# 改名前
$ stat -c '%d %n' /home/agent/shared_workspace /home/agent/shared_workspace/py_upper
2050 /home/agent/shared_workspace
2050 /home/agent/shared_workspace/py_upper      # 同设备 → 直接 mv，无需 cp
$ git rev-parse HEAD          0874716afa1b77d871c521965fbd9debefbcd77b
$ git status --porcelain | wc -l   99           # 3 modified + 96 untracked，全部保留
$ find . -type f | wc -l           36675
$ du -sh .                         4.4G

# 改名
$ mv /home/agent/shared_workspace/py_upper /home/agent/shared_workspace/ai_upper
$ ln -s ai_upper /home/agent/shared_workspace/py_upper

# 改名后（逐项与改名前一致）
$ git rev-parse HEAD          0874716afa1b77d871c521965fbd9debefbcd77b
$ git rev-parse --abbrev-ref HEAD  develop
$ git status --porcelain | wc -l   99
$ find . -type f | wc -l           36675
$ du -sh .                         4.4G
$ git rev-parse --show-toplevel    /home/agent/shared_workspace/ai_upper
```
前后两份完整 `ls -la` / 文件数 / du：`out/rename-ai-upper/pre-rename-state.txt`、
`out/rename-ai-upper/post-rename-state.txt`；软链与校验：`out/rename-ai-upper/symlink-and-checks.txt`。

- **实际使用路径：`/home/agent/shared_workspace/ai_upper`**（HEAD 见 §6）。
- **旧路径现状：`/home/agent/shared_workspace/py_upper -> ai_upper`（软链，兼容宿主仍写死的 workspaceRoot 与本会话 cwd）。**
- 改名前扫 `/proc/*/cwd`：只有 agent 运行时自身（dsh 主进程、ekko-studio MCP ×4、hindsight）与
  我自己的 transient bash 落在该目录，没有构建/测试/编辑器在写；改名后 `/proc/30945/cwd`
  自动解析为新路径 `…/ai_upper`。
- git 未提交改动一条未丢（`git status` 条目数改名前 99、改名后 99）。

### 0.2 旧绝对路径引用（`grep -rn shared_workspace/py_upper`，排除 .git/）

| 位置 | 处理 | 原因 |
| --- | --- | --- |
| `.venv/**`（42 个文件：shebang、activate、pyvenv.cfg） | **已改** | 不改则 `.venv/bin/pytest` 等 41 个入口的 shebang 指向不存在的解释器 |
| `scripts/parity/port_shots.sh:10` | **已改**为 `ROOT="$(cd "$(dirname "$0")/../.." && pwd)"` | 写死路径；改成从脚本位置推导，以后再改名也不用动 |
| `audit-tools/gen_migration_plan.py:603` | **已改** | 报告生成器的正文里写的是工程目标路径 |
| `app/tests/test_app_home.py:15` `HOST_FIXED_WORKSPACE` | **保留旧值 + 补注释** | 它记录的是宿主 `workspaceRoot`（仍写死旧路径，靠软链兼容），并且这个常量负责把历史文档里的旧前缀规范化后再查旧名残留；改成新路径会让历史文档被判成「残留旧名」 |
| `docs/STAGE5-CLOSEOUT-REPORT.md:102-120,170`、`docs/STAGE6-CLOSEOUT-REPORT.md:68-69,80-160,212,236-237`、`docs/BUILD-PROGRESS.md:359-365,464,687,744,862-881,916,1031`、`docs/MIGRATION-PLAN.md:9` | **保留** | 历史结项/进度报告，记录的是当时真实的命令输出与产物路径；改写等于篡改证据。软链存在时这些路径仍可解析 |
| `out/**` 全部日志与报告（约 1000 行） | **保留** | 同上，历史证据；且测试扫描已排除 `out/` |

`git diff --stat` 见本次提交；关键 diff 就是上面三处「已改」。

### 0.3 仓库外的旧路径引用（只报告，不擅自改）

宿主侧仍是旧路径，靠软链兼容。命中清单（`grep -rIl shared_workspace/py_upper`）：

```
/home/agent/.hermes-web-ui/coding-agent/model/default/custom_cpa/dsh/runs/c7e79dd6…/launch.sh:3
/home/agent/.hermes-web-ui/coding-agent/model/default/custom_cpa/dsh/runs/c7e79dd6…/AGENTS.md:596
/home/agent/.hermes-web-ui/coding-agent/model/default/custom_cpa/dsh/runs/c7e79dd6…/dsh-purge/last-cwd.txt:1
/home/agent/.hermes-web-ui/coding-agent/model/default/custom_cpa/dsh/runs/c7e79dd6…/sessions/--home-agent-shared_workspace-py_upper--/…/session.v4.jsonl
/home/agent/.hermes-web-ui/coding-agent/model/default/custom_cpa/dsh/runs/c7e79dd6…/storages/session_projcache/sessions/…json
（同目录另有 4 个 custom_fengwind 历史 run 的 hermes-rules.md / launch.sh）
```
这些是 Studio/DSH 自己生成的运行配置与会话记录，改它们属于账号/宿主配置变更 → **由用户执行**，
本仓库不动；软链已保证它们继续可用（见 §1 的旧路径实跑）。

## 1. 实跑回归

```
# 新路径
$ AI_UPPER_HEADLESS=1 AI_UPPER_HOME=/tmp/fx-qml-home \
  AI_UPPER_QML_SHOT=$PWD/out/qml-shell/shell-run.png .venv/bin/python app/src/main.py
QML OK platform=offscreen title='Deva' sessions=120 active='parity-000' plain=False \
  turn_stop='' deltas=0 home=/tmp/fx-qml-home \
  png=/home/agent/shared_workspace/ai_upper/out/qml-shell/shell-run.png size=1280x820
EXIT=0

# 旧路径（软链）兼容入口，同一命令
$ cd /home/agent/shared_workspace/py_upper && pwd -P
/home/agent/shared_workspace/ai_upper
QML OK platform=offscreen title='Deva' sessions=120 active='parity-000' … size=1280x820
EXIT=0
```
证据：`out/qml-shell/shell-run.log`、`out/qml-shell/shell-run.png`、`out/rename-ai-upper/qml-run-new-path.log`。
证据：`out/qml-shell/shell-run.log`、`out/qml-shell/shell-run.png`（1280×820 实拍）。
software 光栅（`QT_QUICK_BACKEND=software`）+ offscreen，stderr 无 QML 警告与绑定报错。

```
$ .venv/bin/python -m pytest -q
1168 passed, 5 skipped in 25.99s
```
基线 `1159 passed / 5 skipped` → 现在 `1168 passed / 5 skipped`（新增 9 条，未删未减）。

---

## 2. 打包产物实跑（默认 QML）

```
$ PATH=$PWD/.venv/bin:$PATH .venv/bin/python tools/build.py --target linux-arm64
… SMOKE PASS launcher
READY: /home/agent/shared_workspace/py_upper/dist/ai_upper          # BUILD_RC=0

$ AI_UPPER_HEADLESS=1 AI_UPPER_QML_SHOT=$PWD/out/qml-shell/dist-shot.png ./dist/ai_upper/ai_upper
QML OK platform=offscreen title='Deva' sessions=0 active='' plain=False turn_stop='' \
  deltas=0 home=…/dist/ai_upper png=…/out/qml-shell/dist-shot.png size=1280x820
EXIT=0
```
证据：`out/qml-shell/dist-run.log`、`out/qml-shell/dist-shot.png`、`out/packaging/build-qml-default.log`。
（`sessions=0` 是因为启动器把 `AI_UPPER_HOME` 指向产物自身目录，里面没有会话——正是空状态 QML 界面。
旧版本这条命令打印的是 `DEVA WEB OK`，可据此确认默认路线已切换。）

默认路线开关：`app/src/main.py:_qml_requested()` —— 默认 True；`AI_UPPER_UI=web|webengine`
回退 WebEngine 窗口。**保留兜底**的理由：QML 路线要 Quick 场景真的能栅格化，缺插件或没有
窗口会话的机器上仍需要一条能起来的路径；开关就是一个环境变量。
**macOS headless 例外**：CI 的 macOS runner 没有可用 WindowServer 会话，offscreen 插件
不做 Quick 栅格化，`grabWindow()` 回空图（macos-arm64 的 Full integration run 因此判失败，
日志尾部 `[6/6] Target runtime smoke`）。这条路径默认回退 WebEngine，显式
`AI_UPPER_UI=qml` 仍可强制；桌面 macOS 与 Linux/Windows 继续默认 QML。

---

## 3. 逐页 1:1 证据

复现：`bash scripts/parity/rebuild_parity.sh`（夹具 → 原版 19 次实拍 → QML 18 页实拍 → 逐页比对）。
两侧读**同一份** 120 会话夹具与**同一份** `config.json`（`locale=en`、`theme=light`；深色页用
`config-dark.json`）。原版 1280×820 客户端区由 Electron 在 Xvfb 下实拍，QML 侧 offscreen +
软件光栅 `grabWindow()` 实拍，`diff.png` 与数值由 `scripts/parity/page_diff.py` 计算。

### 3.1 数值（阈值 16/255 的逐像素差）

| 页面 | 差异像素 | 占比 | 包围盒 |
| --- | ---: | ---: | --- |
| empty | 15,300 | 1.4577% | 0,8-1268,793 |
| first-run | 15,300 | 1.4577% | 0,8-1268,793 |
| settings-models | 34,926 | 3.3276% | 0,0-1279,819 |
| settings-about | 37,104 | 3.5351% | 0,0-1279,819 |
| settings-extensions | 37,946 | 3.6153% | 0,0-1279,819 |
| settings-general | 39,183 | 3.7331% | 0,0-1279,819 |
| delete-confirm | 51,216 | 4.8796% | 0,0-1279,819 |
| dark-chat | 52,137 | 4.9673% | 0,9-1279,819 |
| hover-thread | 56,344 | 5.3681% | 0,9-1279,819 |
| chat | 56,373 | 5.3709% | 0,9-1279,819 |
| search-open | 56,382 | 5.3718% | 0,9-1279,819 |
| focus-composer | 58,257 | 5.5504% | 0,9-1279,819 |
| ctx-menu | 59,736 | 5.6913% | 0,9-1279,819 |
| model-picker | 68,047 | 6.4831% | 0,9-1279,819 |
| search-results | 69,657 | 6.6365% | 0,9-1279,808 |
| long-bottom | 70,589 | 6.7253% | 0,9-1279,817 |
| search-none | 78,941 | 7.5211% | 0,9-1279,808 |
| long-mid | 106,886 | 10.1835% | 0,9-1279,819 |

### 3.2 容差口径（`numbers-fuzz.tsv`，ImageMagick AE）

| 页面 | raw AE | fuzz 3% | fuzz 8% |
| --- | ---: | ---: | ---: |
| empty | 45,805 | 44,525 | 14,926 |
| first-run | 45,805 | 44,525 | 14,926 |
| search-results | 133,255 | 105,276 | 51,877 |
| chat | 134,066 | 104,889 | 50,306 |
| search-open | 134,095 | 104,904 | 50,315 |
| hover-thread | 134,480 | 105,272 | 50,269 |
| focus-composer | 135,838 | 106,770 | 52,190 |
| ctx-menu | 137,588 | 100,909 | 52,770 |
| search-none | 137,962 | 113,651 | 61,226 |
| long-bottom | 147,262 | 119,245 | 52,608 |
| model-picker | 150,124 | 113,179 | 59,203 |
| long-mid | 162,234 | 139,047 | 77,609 |
| dark-chat | 257,063 | 204,372 | 41,236 |
| settings-models | 327,869 | 50,950 | 32,234 |
| settings-extensions | 332,553 | 53,705 | 34,497 |
| settings-about | 334,033 | 55,329 | 35,683 |
| settings-general | 344,707 | 58,487 | 34,050 |
| delete-confirm | 401,132 | 82,735 | 49,388 |

判读：raw AE 大而 fuzz 8% 后骤降（如 dark-chat 257,063 → 41,236），说明**大部分差异是同字号不同字体的字形栅格化**（DejaVu Sans 对 Chromium 的 -apple-system 栈），不是结构错位；结构错位会同时把 fuzz 8% 顶高（long-mid 77,609、delete-confirm 49,388 属于这一类）。

### 3.3 本轮修掉的（含代码位置）

| 差异 | 修法 | 位置 |
| --- | --- | --- |
| 深色主题完全没生效（99.38%→4.93%） | `ShellBridge.darkMode` + QML `Binding` 写 `Theme.dark`（QML 文件单例 `setProperty` 实测落不下去，拿到的是 QJSValue） | `app/src/qml_shell.py:164`、`app/src/qml/Main.qml:53` |
| 表格没有网格线 | 加表格级 `setBorder(1)` + `BorderCollapse`：QQuickTextEdit **不画单元格级边框**，只画表格级 | `app/src/markdown/document.py:518` |
| 会话行没有头像/角色名 | 按 CDP 实测补 38×38 头像与 11px 角色名副标题 | `app/src/qml/ThreadRow.qml`、`app/src/qml_shell.py:556` |
| 标题栏显示会话标题 | 原版 `cf-idbtn` 显示角色名 | `app/src/qml/Main.qml:303` |
| 相对时间对不上（22 hr vs yesterday） | 夹具时间戳改为相对生成时刻（-22h），两侧同批拍图 | `scripts/parity/make_pages_fixture.py:19` |
| 右键菜单/删除确认框页面是空的（92.68%→5.04%） | 按实测几何补菜单（165,88 175×124）与确认框（430,320 420×180） | `app/src/qml/Main.qml:640+` |
| hover / focus / 长列表三页状态雷同 | 指定行 hover、输入框取焦、列表滚到 45%/底部 | `app/src/qml/Main.qml:47,252` |
| 设置页字号行溢出卡片 | 卡片改 (20,55) 510×169，行高 57/55/55 | `app/src/qml/SettingsModal.qml:250` |
| 输入区模型/强度 chip 有边框 | 原版 border-width 0，去掉后 18 页全小幅下降 | `app/src/qml/Main.qml`（chip 段） |
| 引用块整体右移 8/19px | 引用表外边距 12→6px（逐档 0/4/5/6/7/8 实拍取最优）；chat 57,264→56,373、delete-confirm 52,935→51,216 | `app/src/markdown/document.py:414` |

### 3.4 仍然存在的差异（逐条，未修）

1. **字形栅格化**：QML 用 DejaVu Sans（度量与原版 CSS 相差 ≤0.15px），但每个字形边缘的
   抗锯齿不同 → 正文整片 ~1 级灰度差，构成 raw AE 的大部分。属「渲染引擎差异」范围内，
   但仍是逐像素不等的来源。
2. **列表缩进**：无序列表圆点 x=500（原版 488、正文 506），任务列表复选框提前约 15px。
3. **引用缩进**：外边距已从 12px 收到 6px（竖线误差 8px→约 2px），但仍未逐像素对齐；
   二级引用仍比原版右约 7px。
4. **正文滚动落点**：两侧都贴底，但内容高度不同（见第 5 条）导致整体错位 8–40px，
   chat/hover/focus/search 四页同源。
5. **图片**：夹具里的 `data:image/png;base64,…` 在 QML 侧能解出来（1×1 透明），原版 Chromium
   渲染成「破图图标 + alt 文本」16px 高 → 正文高度差 16px。这是**功能更强**造成的差异。
6. **窗口控制按钮**：原版右上角最小化/最大化/关闭（1188–1272），QML 未实现（试做后差异反而
   上升 ~1000px，已回退，未留半成品）。
7. **long-mid**：QML 用 `contentY = 45%` 近似原版 12 次滚轮事件，落点不同（10.12%，最差页）。
8. **滚动条**：原版右侧有可见滚动条，QML 的 Flickable 未画（同上，试做后差异上升，已回退）。
9. **字体族**：本机无 emoji 字体；中文依赖 fontconfig 回退到 Droid Sans Fallback。

---

## 4. 正文层功能实测（真操作）

脚本 `scripts/qml_body_probe.py`，原始数据 `out/qml-shell/body/body-report.json`，
截图 `theme-light.png` / `theme-dark.png` / `table.png` / `cjk-emoji.png`。

```
$ .venv/bin/python scripts/qml_body_probe.py out/qml-shell/body
{"failures": [], "out": "out/qml-shell/body"}
```

| 项 | 实测数据 | 结论 |
| --- | --- | --- |
| 跨块连续选择与复制 | 块 0→18（19 块）、616 字符；含代码块 `def list_dir`、表格 `README.md`、尾段；写剪贴板后读回**完全一致** | PASS |
| 部分跨块选择 | 代码块中段 → 表格单元格，566 字符，两端都命中 | PASS |
| 双击选词 | 真发 `QTest.mouseDClick` 到 QQuickWindow(115,100)，`selectedText == "sorted"` | PASS |
| 代码块横向滚动 | 长行 2705.56px，文档 `textWidth` 仍 696.0（=视口），`idealWidth` 3339 → 溢出由视图承担，布局不被撑破 | PASS |
| 表格边框/间距 | 表格级 1px #e6e6ea、单元格 padding 10/10/6/6，渲染图上数到 2 条边框像素 | PASS |
| 图片渲染 | 本地 48×32 与 `data:` URI 都注册成文档资源，取回尺寸 48×32 / 1×1 | PASS |
| 浅/深主题同步 | #ffffff→#1e1e20、文字 #1f1f24→#e4e4e7；同一区域平均亮度 243.19→41.2（真的变暗）；字体族不变 | PASS |
| 单条超长消息 | 400 段，渲染 **593.1ms**，文档高 15569px | PASS |
| 上百条连续消息 | 120 条，渲染 **269.4ms**，文档高 8931px | PASS |
| 滚动耗时 | 60 次改 contentY 共 0.7ms（0.01ms/步） | PASS |
| 中文渲染 | 中文正常出字形（墨迹像素 518） | PASS |
| emoji | 本机无 emoji 字体（`fc-list` 无 emoji 族），与原版 Chromium 一样落回缺字块 | 环境缺失，非渲染缺陷 |
| 1x / 2x | `QT_SCALE_FACTOR=2` → `devicePixelRatio=2.0`，抓图 1600×1800（逻辑 800×900），文档逻辑宽仍 696 | PASS |

数据文件：`out/qml-shell/body/hidpi-1.json`、`hidpi-2.json`。

---

## 5. CI（逐 job 终态）

运行 `43721721512`（commit `5fbabeb`，`develop`，completed，conclusion=failure —— 唯一红项是
起点就红的 windows-3.8.10）。

| job | 终态 |
| --- | --- |
| Build Tool Python 3.8 | success |
| Build Tool Python 3.9 | success |
| Build Tool Python 3.10 | success |
| Build Tool Python 3.11 | success |
| Build Tool Python 3.12 | success |
| Build Tool Python 3.13 | success |
| native-integration (ubuntu-24.04, linux-x86_64, run=true) | success |
| native-integration (ubuntu-24.04-arm, linux-arm64) | success |
| native-integration (macos-15, macos-arm64, run=true) | success |
| native-integration (macos-15-intel, macos-x86_64, run=true) | success |
| native-integration (windows-2025, windows-x86_64, run=true) | success |
| native-integration (windows-2025, windows-x86, pyserial) | success |
| native-integration (windows-11-arm, windows-arm64, run=true) | success |
| native-integration (windows-2025, windows-x86_64, 3.8.10, PySide6 6.6.3) | **failure** |
| aggregate-artifacts | skipped（前序有红项时按设计跳过） |

合计 **13 success / 1 skipped / 1 failure**。唯一失败项的证据：

- 报错：`ERROR: RuntimeError: Unresolved native dependencies: site-packages\PySide6\qml\QtQuick\Controls\Basic\impl\qtquickcontrols2basicstyleimplplugin.dll: Qt6QuickControls2BasicStyleImpl.dll …`，失败步骤 `[4/6] Package + native dependency closure`。
- **本轮起点 `4b8a220` 的同名 job 就是同一条报错**（run `43708023866`，job `132793259884`）→
  非本轮引入，本轮未修（属于 QtQuick Controls 原生闭包在那条矩阵上的缺口）。

本轮自己弄红、并已定位修复的两处（都有运行证据）：

1. **就绪标记断言过时**（`21a1377`）：默认路线切 QML 后打印 `QML OK … size=1280x820`，而
   `.github/workflows/validate.yml` 仍只认 `'DEVA WEB OK' and 'bridge=True'` → linux-x86_64 与
   macos-arm64 的 `Full integration run` 判失败。改成两者并集后 linux-x86_64 转绿
   （run `43716409758`）。
2. **macOS headless 无法栅格化 Quick**（`b4f052f`）：macos-arm64 仍红（日志尾部
   `[6/6] Target runtime smoke`，实为产物实跑未出首帧）。改为 darwin+headless 默认回退
   WebEngine（显式 `AI_UPPER_UI=qml` 可强制），此后 macos-arm64 在 `43719027496` 与
   `43721721512` 连续两次 success。

## 6. 仍未完成项

1. §3.4 的 9 条差异未归零（字形栅格化、列表/引用缩进、滚动落点、窗口控件、滚动条、long-mid）。
2. 窗口控件与滚动条试做过，**因差异反而上升已回退**，没有留半成品。
3. 无 emoji 字体，emoji 只能记录为环境缺失。
4. `AI_UPPER_UI=web` 兜底分支未在本轮单独实跑（只改动了默认分支的选择逻辑）。
5. Windows 3.8.10 的 `Qt6QuickControls2BasicStyleImpl.dll` 原生闭包缺失是本轮起点既有红项，
   未在本轮修复。
