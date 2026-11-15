# QML 默认入口补齐「消息携带文件输出」：交付卡 + 附件贴片 + 回形针

对象：`/home/agent/shared_workspace/ai_upper`（分支 `develop`）
起点：`ef6ba07`（web 入口交付卡已收口）
对照：`/home/agent/shared_workspace/deva`（Electron + React 原版，**本轮零写入**）
性质：实现 + 实跑 + 回归。报告只写**实际跑出来的**结果；没验证的单列在 §8。

---

## 0. 结论

| 项 | 状态 | 证据 |
| --- | --- | --- |
| QML 正文里的附件行（图片内联 + 文档/文本/文件夹/路径各一行，带真实体积） | **已跑通** | §2；`qml-attachments-deliverables.png` |
| QML 附件贴片（缩略图 + 真实文件名 + 真实体积） | **已跑通** | 同上（`截图-2026-11-16.png 329 B`、`需求说明.pdf 316 B`） |
| QML 交付卡（真实文件名 / 真实体积 / 目录 / 打开 / 定位 / 复制路径） | **已跑通** | 同上（`季度报告.md 3 KB`、`数据汇总.xlsx 5 KB`、`build.py 47 B`、`已移走的报告.md 文件已不存在`） |
| 按钮状态真实（非白名单 / 已不存在 → 禁用） | **已跑通** | `build.py` 无「打开」图标；`已移走的报告.md` 打开/定位均禁用 |
| 打开 / 定位 / 复制路径的实际返回值与失败拒绝 | **已跑通** | §5 槽位探针 + §5.1 默认入口里用 `QMouseEvent` 真点三个按钮（`probe-qml-deliverables.log` 22 条全 PASS）；**桌面会话里真的弹出文件管理器未验证**，见 §8 |
| 回形针真弹 `QFileDialog` 并把选中文件带进消息 | **已跑通** | `qml-file-dialog.png` + `probe-qml-slots.log`（`QML PICK [...]` → `QML SEND {"attachments": [...]}` → 落盘 `['image','text']`） |
| 回归 | **已跑通**：`1251 passed, 5 skipped` | §6（基线 1159，只增不减） |
| 会话「导出为文件」（审计口径 A） | **不在本轮范围**（原版也没有，见审计报告 §1） | — |

本轮提交（`git log --oneline -5`，每个 sha 都对应一次实跑通过）：

```
0c3d46d test(qml-files): 补默认入口实跑证据——真点三按钮/回形针/带附件发送
7b7c2a5 fix(qml-files): 文档附件体积按 base64 解码字节数，界面显示真实 316 B
d0b0425 test(qml-files): 附件/交付卡用例与实跑证据
8c817ae feat(qml-files): QML 画附件贴片与交付卡，回形针真弹选择框并支持带附件发送
d22f329 feat(qml-files): 附件/交付数据层——抽共用判据并给 QML 出附件行与交付行
```

> 提交署名一律是 `Claude Code <noreply@anthropic.com>`。其中 `d22f329` / `8c817ae` / `d0b0425` /
> `7b7c2a5` 四个提交是在同一份 checkout 里由**另一个并发进程**写下的（本会话观察到工作区改动
> 被那批提交收纳）；本会话逐条复核了它们的内容、行号与实跑结果后才继续在其上提交。


---

## 1. 动手前对账（上一轮被停下的半成品怎么处理）

```
$ git log --oneline -3
ef6ba07 fix(deliverables): 打开文件在无桌面插件时按平台起进程（仍以列表参数传路径）
21277d8 feat(files): 交付卡后端接通——写 delivered 边车 + 四条 deliverables 通道
492f8ac docs(parity): CI 终态按 43721721512 逐 job 落实（13 success / 1 skipped / 1 既有红项）

$ git status --porcelain=v1 -uall        # 本轮开工时
 M app/src/mvvm/webui/bridge.py
 M app/src/qml/IconData.qml
 M app/src/qml/Main.qml
 M app/src/qml_shell.py
 M app/src/qml_shell_sessions.py
 M out/ci-fix/closeout/job-table-py38-round2.txt
 M out/ci-fix/closeout/py38-closeout-report-round2.md
 M out/qml-shell/shell-run.png
 M out/qml-shell/shot.png
 M scripts/parity/gen_icons.mjs
?? app/src/mvvm/services/transcript_parts.py
```

**判定：可用，接着做。** 这十项正是「QML 侧附件/交付卡」的实现骨架（数据层、桥槽位、Main.qml
卡片、external-link 图标），没有半途而废的脏改动：

- `transcript_parts.py` 把原来埋在 `bridge.py` 里的 `_attachment_chips/_image_ref/_base36/_base64_bytes`
  抽成共用纯函数，web 入口改为 import——**不是新链路，是把两入口的判据收成一份**；
- `bridge.py` 只删了搬走的私有函数、改调用点，`git diff` 里没有行为变化；
- `qml_shell_sessions.py` / `qml_shell.py` / `Main.qml` 是同一功能的 Python 数据层、槽位与界面。

复核手段：`py_compile` 六文件通过；全量 pytest 在**未改任何测试**的情况下先跑通（见 §6）。
另外两处与本任务无关的既存脏文件（`out/ci-fix/closeout/*`、`out/qml-shell/*.png`）**没有动、也不进本轮提交**，
理由是它们是早前 CI/截图轮次留下的产物，不属于本轮交付内容。

---

## 2. QML 数据层（`app/src/qml_shell_sessions.py`）

正文仍走 `QTextDocument`（`markdown.body`），没有改渲染路线；只补「喂给它的 Markdown」：

| 位置 | 内容 |
| --- | --- |
| `qml_shell_sessions.py:34` | `format_bytes()`：逐字对齐原版 `formatSize`（`0 B / 221 B / 1 KB / 1.5 MB`） |
| `qml_shell_sessions.py:166` | `_attachment_lines()`：图片 → `![name](data:<mime>;base64,…)`（`markdown/document.py` 的 image_resolver 会解码成文档资源）；document/文本/文件夹/只给位置 → 一行「附件：名（真实体积）」 |
| `qml_shell_sessions.py:204` | `transcript_markdown()`：用户消息的附件行排在提问正文**之前**；只有附件没有正文的消息不再被跳过 |
| `qml_shell_sessions.py:239` | `delivery_tool_use_ids()`：只认 `name == "present_files"` 的工具调用 id（去重） |
| `qml_shell_sessions.py:260` | `delivery_rows()`：id → 边车 `session.delivered` → 真实 `os.stat`；行带 `sizeText / missing / openable / toolUseId` |
| `qml_shell_sessions.py:284` | `attachment_rows()`：贴片行（名称/类型/真实体积/图片 data URI/消息下标），图片直接从落盘消息取 base64，不额外读盘 |

文档体积按 base64 解码后的字节数算（`transcript_parts.base64_bytes`），不是 base64 串长度——
夹具里的 `需求说明.pdf` 是 316 B，界面就显示 `316 B`（此前误用串长度会显示 424 B，已在
`app/tests/test_qml_chat_files.py::test_document_line_reports_decoded_size_not_base64_length` 钉住）。

共用判据只有一份：`app/src/mvvm/services/transcript_parts.py:55`（`attachment_chips`）、`:49`（`image_ref`）、
`:125`/`:143`（`delivery_rows`/`delivery_row`）；web 入口在 `app/src/mvvm/webui/bridge.py:29` 改为 import 它，
`:674` 调 `attachment_chips(...)`。**同一份边车、同一份体积算法，两个入口不会各算一套。**

安全不变式（与 web 侧 `deliverables:inspect` 相同，见 `app/src/mvvm/services/deliverables.py` 文件头）：
交付路径**只**从边车 `session.delivered` 取；边车没有的旧会话宁可不出卡，也不回落到历史消息里的
`tool_use.input.paths` 字符串。

---

## 3. QML 界面（`app/src/qml/Main.qml`）

| 位置 | 内容 |
| --- | --- |
| `Main.qml:434` | `cardsCol`：正文之后追加的附件/交付区（数据来自 `window.attachments` / `window.deliveries`） |
| `Main.qml:444` | `attachFlow`：附件贴片，210×64，缩略图 48×48 + 文件名（ElideRight）+ 真实体积 |
| `Main.qml:508` | `deliveryCard`：「交付文件 · N 个文件」+ 每行图标/文件名/`体积 · 目录` |
| `Main.qml:596-603` | 已不存在 → 副标题固定「文件已不存在」 |
| `Main.qml:618` | 「打开」：`visible: modelData.openable && !modelData.missing`（脚本类与已删除文件不给入口） |
| `Main.qml:626` | 「在文件夹中显示」：`enabled: !modelData.missing` |
| `Main.qml:634` | 「复制路径」：成功后对勾 + 1.2s 复位（`copiedPath` / `copyReset`） |
| `Main.qml:656` | `noticeBar`：真实通道返回 false 时的失败提示条 |
| `Main.qml:678` | `pendingBar`：待发送附件（回形针选中后、发送前可单独移除） |
| `Main.qml:793` | `clipBtn`：回形针由纯 Hover 改为 `MouseArea` → `window.pickAttachments()`（busy 时禁用） |
| `Main.qml:984` | `submit()`：有附件走 `sendWithAttachments`，无附件仍走原 `send(text)` 单参重载 |
| `Main.qml:1017` | `notify()`：失败提示；`deliverableOpen/Reveal/Copy` 把通道 bool 原样上屏，不做假成功 |

截图（1280×820，`grabWindow` 原图）：
`/home/agent/shared_workspace/ai_upper/out/chat-files/qml-attachments-deliverables.png`
`sha256=3c13e03c9711ba0e1ab1b58410592ad9d6725e260a6622e273015357165dd2a2`

图上可直接核对：

- 附件贴片：`截图-2026-11-16.png 329 B`（磁盘 `ls -l` 同样是 329）、`需求说明.pdf 316 B`；
- 交付卡：`季度报告.md 3 KB`、`数据汇总.xlsx 5 KB`、`build.py 47 B`、`已移走的报告.md / 文件已不存在`；
- `build.py` 与「已移走」两行**没有**「打开」图标（白名单 / missing 判定生效）；
- 正文里用户消息的图片以内联缩略图形式出现在「你」段落。

---

## 4. 回形针与带附件发送（真实运行）

脚本：`out/chat-files/probe_qml_slots.py`（独立 HOME `/tmp/chat-files-slots-home`，不污染截图夹具）。
它在 `QFileDialog` 真正弹出后填入 `fileNameEdit` 并 `accept()`——**不是打桩掉对话框**。

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/python out/chat-files/probe_qml_slots.py
This plugin does not support propagateSizeHints()
QML PICK ["/tmp/chat-files-slots-home/ws/截图-2026-11-16.png"]
== pickAttachments() ==
   真的弹出了对话框 = QFileDialog  modal= True  selectedFiles= ['/tmp/chat-files-slots-home/ws/截图-2026-11-16.png']
   对话框截图 = /home/agent/shared_workspace/ai_upper/out/chat-files/qml-file-dialog.png
   返回 = ["/tmp/chat-files-slots-home/ws/截图-2026-11-16.png"]
QML SEND {"sessionId": "slot-probe", "text": "这张图里的文件能给我吗", "attachments": ["/tmp/chat-files-slots-home/ws/截图-2026-11-16.png"]}
QML TURN 8044d604624f439886f104c090d1bb39
QML STREAM {"text": "收到附件"}
QML TURN DONE {"stopReason": "end_turn", "deltas": 1}
== sendWithAttachments() ==
   send 返回 = True  turn stop = end_turn
   落盘用户消息块类型 = ['image', 'text']
```

对话框原图：`out/chat-files/qml-file-dialog.png`（632×408，
`sha256=f9eb4dc8350ffad5c4bd22c651f4e732eb681f9e4f3f76dc2ece06e8575c17ee`）——标题栏、文件列表里
`截图-2026-11-16.png 329 tes`、文件类型下拉是 QML 壳自己的过滤器（`支持的文件 (*.png *.jpg …)`）。

QML 侧槽位：`app/src/qml_shell.py:489`（`sendWithAttachments`）、`:494`（`send` 支持 attachments）、
`:543`（`pickAttachments`）、`:637`（`_pick_files` → `QFileDialog.getOpenFileNames`）。
`send()` 把路径原样交给 `ChatHost.send`，与 web 入口 `chat:send` 同一条链路（`app/src/mvvm/webui/host.py`
的 attachments 分支），不存在第二条附件实现。

---

## 5. 交付卡三个按钮 + 路径白名单（真实返回）

同一探针（打开/定位在本机没有桌面会话，只记录**将要执行的平台命令**，见 §8）：

```
== deliveryItems() ==
    {"name": "季度报告.md", "size": 3087, "sizeText": "3 KB", "openable": true, "missing": false}
    {"name": "数据汇总.xlsx", "size": 5124, "sizeText": "5 KB", "openable": true, "missing": false}
    {"name": "build.py", "size": 47, "sizeText": "47 B", "openable": false, "missing": false}
    {"name": "已移走的报告.md", "size": null, "sizeText": "", "openable": true, "missing": true}
== 交付卡按钮 ==
   open(边车路径)   = True → ['/tmp/chat-files-slots-home/ws/季度报告.md']
   open(伪造路径)   = False → ['/tmp/chat-files-slots-home/ws/季度报告.md']
   reveal(边车路径) = True → ['/tmp/chat-files-slots-home/ws/季度报告.md']
   reveal(/etc/passwd) = False
   copy(边车路径)   = True
   剪贴板内容       = /tmp/chat-files-slots-home/ws/季度报告.md
QML COPY REJECTED "/tmp/chat-files-slots-home/ws/\u9700\u6c42\u8bf4\u660e.pdf"
   copy(伪造路径)   = False
   剪贴板内容(拒绝后不变) = /tmp/chat-files-slots-home/ws/季度报告.md
```

- 伪造路径在磁盘上真实存在（`需求说明.pdf`），但不在边车里 → `open/reveal/copy` 全部 false；
- 拒绝时剪贴板保持上一次内容，不被改写；
- QML 槽位在 `app/src/qml_shell.py:580/585/590`，路径先换成边车序号（`_delivered_index`），
  再由 `mvvm/services/deliverables.py` 的 `open_item/reveal` 复核——渲染层给不出任意路径。

### 5.1 默认入口里真点按钮（`QMouseEvent` 进 `QQuickWindow`）

上一节是直接调槽位。这一节补的是「**默认入口**（`qml_shell.py` + `app/src/qml/Main.qml`）里
鼠标真的点到按钮上」：脚本 `out/chat-files/probe_qml_deliverables.py` 起真 `QApplication` +
`QQmlApplicationEngine` 加载 `Main.qml`，从 QML 控件读回文本，再用 `QCoreApplication.sendEvent`
把真 `QMouseEvent` 送进窗口。

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/python out/chat-files/probe_qml_deliverables.py /tmp/chat-files-qml out/chat-files
QML 交付行文件名 = ["notes.md", "chart.png"]
QML 交付行副标题 = ["53 B · /tmp/chat-files-qml/ws", "740 B · /tmp/chat-files-qml/ws"]
QML 附件贴片     = ["spec.txt", "photo.png"] ["48 B", "1 KB"]
QML 交付卡可见 = True / 附件条可见 = True
截图 = …/out/chat-files/qml-chat-files.png (1280, 820)
按钮点击 open/reveal/copy = {"open": true, "reveal": true, "copy": true}
后端记录到的命令 = [["xdg-open", "/tmp/chat-files-qml/ws/chart.png"], ["xdg-open", "/tmp/chat-files-qml/ws"]]
剪贴板 = "/tmp/chat-files-qml/ws/chart.png"
QML COPY REJECTED "/etc/passwd"
越权 open/reveal/copy/未知路径 = [False, False, False, False]
QML PICK ["/tmp/chat-files-qml/ws/photo.png"]
回形针点击 = True / 对话框创建次数 = 1 / 非原生 = True / 选中 = ["/tmp/chat-files-qml/ws/photo.png"]
QML pendingFiles = ["/tmp/chat-files-qml/ws/photo.png"]
QML SEND {"sessionId": "qml-files-demo", "text": "把这张图也一起看下", "attachments": ["/tmp/chat-files-qml/ws/photo.png"]}
带附件发送 = True / 回合结束 = True / 落盘内容块 = ['image', 'text']
发送后附件贴片 = ["photo.png", "spec.txt", "photo.png"]
---- 断言 ----
… 22 条全部 PASS …
RESULT ALL PASS
painted=True rendered=7
```

- `open/reveal/copy` 三个返回值来自按钮的 `MouseArea` → `deliverableOpen/Reveal/Copy`
  （`Main.qml:1024/1031/1038`）→ 槽位 → 服务层；`_spawn` 被替身记录，上表就是**实际要执行的命令**；
- 越权与未登记路径（`/etc/passwd`、边车外的 `photo.png`）四类调用全 False，进程列表没有新增；
- 回形针是**真点**：`QFileDialog` 每次点击只创建 1 个、`非原生 = True`，选中文件随后进了 `pendingFiles`；
- 「待发附件」与「附件入历史」两张截图：`qml-chat-files-pending.png`（贴片 + ×）、
  `qml-chat-files-after-send.png`（发送后历史里多一条贴片）。

截图哈希（`sha256sum out/chat-files/*.png`）：

| 文件 | sha256 |
| --- | --- |
| `qml-chat-files.png` | `e90776d7baf055be3469e9a7e6a8ef372f443de768bd398256b02c133a626716` |
| `qml-chat-files-pending.png` | `9c5749c71fb99818db1fb6862942af3f75d73e0d0693b1c9ad42e05c737f5ea4` |
| `qml-chat-files-after-send.png` | `d71f71575da18cda7f828e020856ecba1c2fa1dd268f0ae4b98dee2f58a4c3b5` |
| `qml-attachments-deliverables.png` | `3c13e03c9711ba0e1ab1b58410592ad9d6725e260a6622e273015357165dd2a2` |
| `qml-file-dialog.png` | `f9eb4dc8350ffad5c4bd22c651f4e732eb681f9e4f3f76dc2ece06e8575c17ee` |
| `web-deliverables-live.png` | `dd54bdc0131a117ab2254687b25f9466324e2f40fda1d924924b78ec90762f2e` |

> 说明：`qml-chat-files*.png` 每次重跑都会因时间戳/悬停态变化出新哈希；上表是本次入档那一版。

---

## 6. 回归与新增用例

```
$ cd app && QT_QPA_PLATFORM=offscreen ../.venv/bin/python -m pytest tests -q
1251 passed, 5 skipped in 26.74s
```

- 基线 `1159 passed, 5 skipped`（任务书）→ 本轮 `1251`（+92：上一轮交付卡 38 条 + 本轮 54 条），
  skipped 仍 5 条，**没有删/跳任何既有用例**。
- 本轮 54 条分两个文件（`--collect-only` 实测 `54 tests collected`，单独跑 25 + 29 全绿）：
  - `app/tests/test_qml_chat_files_ui.py`（29 条，本轮新写）：附件正文行/贴片体积与缩略图、交付行（真实体积、
    missing、openable、去重、只认 `present_files`、无边车不出卡）、`format_bytes` 分档、回形针（真调
    `QFileDialog.getOpenFileNames` 的入参与取消路径）、带附件发送落成 `image` 内容块、打开/定位/复制路径的
    白名单拒绝；
  - `app/tests/test_qml_chat_files.py`（25 条，接手时未提交的同题用例，含本轮补的文档体积回归）：投影只取落盘与边车、正文不含
    `[附件文件]` 注入块、四个交付通道只认边车、`QJSValue`/str 附件路径归一。合并前复核过：未改动
    既有用例、24 条全绿，因此按「能用就接着做并单独提交」一并纳入。
- 边车写入与 4 条 `deliverables:*` 通道的用例在 `app/tests/test_deliverables.py`（上一提交 `21277d8`），
  本轮随全量一起通过。

日志：`out/chat-files/pytest-full.log`。

---

## 7. 证据清单

| 文件 | 说明 |
| --- | --- |
| `out/chat-files/qml-attachments-deliverables.png` | QML 主截图（附件贴片 + 交付卡，真实名/体积） |
| `out/chat-files/qml-file-dialog.png` | 真 `QFileDialog` 弹出并选中文件的截图 |
| `out/chat-files/qml-chat-files.png` | 默认入口（`qml_shell.py` + `Main.qml`）主截图：贴片 + 交付卡 |
| `out/chat-files/qml-chat-files-pending.png` | 回形针选中后、发送前的待发附件贴片 |
| `out/chat-files/qml-chat-files-after-send.png` | 带附件发送后，历史里出现新附件贴片 |
| `out/chat-files/qml-run.log` | QML offscreen 实跑原始输出（`QML OK … size=1280x820`，exit 0） |
| `out/chat-files/probe-qml-slots.log` | 槽位探针原始输出（回形针/发送/交付卡按钮） |
| `out/chat-files/probe-qml-deliverables.log` | 默认入口探针原始输出（22 条断言全 PASS，真 `QMouseEvent`） |
| `out/chat-files/web-deliverables-live.png` | web 入口交付卡实跑截图（`ef6ba07` 轮次） |
| `out/chat-files/pytest-full.log` | 全量 pytest（1251 passed, 5 skipped） |
| `out/chat-files/fixture.log` | 夹具真实体积（329 / 3087 / 5124 / 47 B）与边车内容 |
| `out/chat-files/make_fixture.py` | 夹具脚本（重建截图数据） |
| `out/chat-files/probe_qml_slots.py` | 槽位探针脚本（重建 §4/§5 输出） |
| `out/chat-files/probe_qml_deliverables.py` | 默认入口探针脚本（重建 §5.1 输出） |
| `out/chat-files/seed_chat_files.py` | 默认入口探针的数据夹具（`qml-files-demo` 会话 + 边车） |
| `out/chat-files/probe_web_deliverables.py` | web 入口交付卡探针脚本 |
| `out/chat-files/web-deliverables-probe.log` | web 入口探针原始输出（卡片 DOM + 四条通道返回） |
复跑：

```bash
cd /home/agent/shared_workspace/ai_upper
rm -rf /tmp/chat-files-home /tmp/chat-files-slots-home
CHAT_FILES_HOME=/tmp/chat-files-home  QT_QPA_PLATFORM=offscreen .venv/bin/python out/chat-files/make_fixture.py
CHAT_FILES_HOME=/tmp/chat-files-slots-home QT_QPA_PLATFORM=offscreen .venv/bin/python out/chat-files/make_fixture.py
QT_QPA_PLATFORM=offscreen .venv/bin/python out/chat-files/probe_qml_slots.py
cd app/src && AI_UPPER_HOME=/tmp/chat-files-home AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 \
  AI_UPPER_QML_PAGE=chat AI_UPPER_QML_SHOT=$PWD/../../out/chat-files/qml-attachments-deliverables.png \
  ../../.venv/bin/python -c "from main import main; raise SystemExit(main())"
cd /home/agent/shared_workspace/ai_upper
# 默认入口（qml_shell.py + Main.qml）真点按钮：先灌夹具，再跑探针
rm -rf /tmp/chat-files-qml
QT_QPA_PLATFORM=offscreen .venv/bin/python out/chat-files/seed_chat_files.py /tmp/chat-files-qml
QT_QPA_PLATFORM=offscreen .venv/bin/python out/chat-files/probe_qml_deliverables.py \
  /tmp/chat-files-qml out/chat-files
# 回归
cd app && QT_QPA_PLATFORM=offscreen ../.venv/bin/python -m pytest tests -q
```

---

## 8. 未验证 / 未完成（如实）

1. **桌面会话里真的弹出文件管理器 / 默认应用**：本机是 offscreen 无桌面，`open` / `reveal` 只验证到
   「边车路径 → 平台命令（`xdg-open` / `open -R` / `explorer /select,`），伪造路径被拒」这一层；
   实际窗口是否出现**未验证**。
2. **鼠标点按钮的端到端**：已在 offscreen 下用真 `QMouseEvent` 送进 `QQuickWindow` 验证（§5.1，
   `open/reveal/copy` 三个按钮的 `MouseArea` 都被真实命中、后端命令与剪贴板随之变化），但
   **没有在真实显示服务器（X11/Wayland）的窗口里用手点过**——offscreen 平台的命中测试与真窗口
   理论上一致，实际窗口合成未验证。
3. **macOS / Windows**：只在 Linux offscreen 跑过；macOS headless 走 WebEngine 回退（既有行为），
   QML 交付卡在 macOS 桌面会话、Windows 上的样式与对话框未验证。
4. **多个附件同时选择**：`getOpenFileNames` 的过滤器与多选路径已通过单测替身覆盖，真实对话框只验证了
   单选；同一批多选未实跑。
5. **会话「导出为文件」**：审计结论是原版也没有此功能，本轮不做（不在任务清单内）。

## 9. 已知风险

- 交付卡数据每次 `_publish` 都按当前会话现算（`ChatSessionStore` 有内存缓存，`os.stat` 只对已交付文件），
  长历史 + 大量交付文件时会有额外 stat；未做基准测试。
- 图片附件在正文里以 `data:` URI 内联，超大图会抬高 Markdown 体积（与 web 侧 display 语义一致）。
- QML 与 web 共用 `transcript_parts`，任何一方改变判据都会同时影响两个入口——这是刻意收口，
  但改动时需同时回归两边（全量 pytest 已覆盖）。
