# 「多对话选择」点击卡顿：定位、根因与修复

工作目录：`out/conversation-picker-lag/`。所有数字都是本机真实命令输出（Python 3.13 + PySide6 6.11.2，
`QT_QPA_PLATFORM=offscreen`，`LD_LIBRARY_PATH=/tmp/qtlibs`，`AI_UPPER_HOME` 全部指向 `/tmp/ai-upper-*`）。

## 0. 一句话结论

左栏会话列表点一下，`MouseArea.onClicked → window.activate() → shellBridge.openSession()`
在 **GUI 线程上同步**执行了「把整篇会话正文渲染进 QML 活动文档」这件事，一次点击的耗时随正文
规模超线性增长；并且**同一份正文被渲染了两遍**，高亮器还挂在上一次那份大文档上反复全量重跑。
把正文先渲染到一份**脱离视图的普通 `QTextDocument`**，再**一次性**搬进活动文档后，
400 轮会话从 **40.9 s（p90 71.9 s）降到 2.8 s 量级**（同机同口径实测）。

修复提交：`b513d7c`（实现）、`c67a402`（回归用例）、`ea75897`（`documentMargin` 保真）。
全部在本地 `develop`，未推送、未开分支。

## 1. 窗口定位（穷举结论）

| 搜索面 | 结果 |
|---|---|
| `app/src/qml/*.qml` 里的 `ApplicationWindow` | 只有 1 个根窗口 `Main.qml:16` |
| `app/src/qml/` 里所有弹层 | `SettingsModal`、`ModelPicker`、`ctxMenu`、`confirmLayer`（均非会话多选） |
| 全仓 checkbox / CheckBox / 多选控件 | 无 |
| `out/` 下的原型截图 | 只有 shell 主窗体的整窗截图，无独立「多选」窗体 |
| 只读参考 `deva` | 唯一会话多选 UI 是 `BotsPane.tsx:749 ScopePicker`（i18n `'Choose chats'`），其 `remote:*` 通道在 `docs/MIGRATION-PLAN.md:153` 明确标注「不迁移」 |

因此**本仓库里唯一「在多个对话之间选择」的界面就是左栏会话列表**（`Main.qml:288-319`）。
证据与命令见同目录 `SEARCH-LOG.md`。

## 2. 点击后的同步数据流（文件:行号）

```
Main.qml:313-318   delegate 内 MouseArea.onClicked → window.activate(modelData.id)
Main.qml:978-982   function activate(id) { ... shellBridge.openSession(id) }
                   ← @Slot 调用是 GUI 线程同步执行，返回前不处理任何事件
qml_shell.py:409-416  ShellBridge.openSession()
                        → self._render()
                        → self._publish()
qml_shell.py:738-749  _render()
                        ① self._body.set_markdown(self._markdown())   # 渲染进 BodyDocument 自有文档
                        ② self._body.attach(self._document)           # 一次 insertFragment 搬进 QML 文档
                        ③ self._scroll_to_bottom()
qml_shell.py:727-729  _markdown_base() → store.load_session() → transcript_markdown()
body.py:112-132       set_source() → render() → render_markdown()
body.py:165-201       attach() → 高亮器换到目标文档 → 一次 insertFragment → 补图片资源
document.py:198-216   render_markdown(): document.clear() + setDocumentMargin(0)
                      + render_blocks(...) + _collapse_edge_margins
qml_shell.py:800-823  _publish(): 重算整张会话表并 setProperty("sessions", rows)
```

（上面是**修复后**的数据流。修复前 `attach()` 会以目标文档再整篇重渲染一遍并再
`rehighlight()` 一次，所以第②步本身就是一次完整渲染。）

`_render()` 有 9 处调用点（`qml_shell.py:342/382/405/414/426/552/682/773/829`），
也就是说**任何一次重绘都在走这条路径**，不只是点击会话行；修复前这条路径每走一次
就是两遍完整渲染。

## 3. 根因证据（全部为实测）

### 3.1 点击确实是 GUI 线程同步阻塞

在真实 `Main.qml` + `ShellBridge` 壳里，直接调用与点击等价的 `bridge.openSession(sid)`：

```
PERF {"label":"BEFORE","sessions":120,"turns":400,"rounds":6,
      "openSession_ms":{"median":40936.32,"p90":71892.3,"max":71892.3},
      "publish_ms":{"median":8.39,"p90":8.56,"max":8.56}}
```

`publish` 只有 8 ms —— **不是列表投影的问题**，98% 以上时间在正文渲染。

### 3.2 同一份正文被渲染两遍，且第二遍贵得多

在壳内把一次 `_render()` 拆开计时（`out/conversation-picker-lag/profile_attach.py`）：

```
{"to":"long","total_ms":69979.6,"set_markdown":4739.8,"attach":65233.4,
 "render_own":4739.8,"render_qml":56438.9,"rehighlight":0,"scroll":0.1}
{"to":"long","total_ms":70764.1,"set_markdown":4799.2,"attach":65958.4,
 "render_own":4799.2,"render_qml":57177.9,"rehighlight":0,"scroll":0.1}
```

两遍都是同一份 markdown：第一遍 4.7 s，第二遍 **56–57 s**。

### 3.3 关键差异：写进「QML 活动文档」比写进普通文档慢 8–12 倍

同样的内容、同样的渲染器，只换目标文档：

```
{"turns":400,"chars":92978,"bare_ms":1331.6,"textwidth_ms":1321.7,"textwidth_layout_ms":1340.9}
{"turns":400,"chars":92978,"A_bare_ms":1942.3,"B_quick_visible_ms":16340.7,"C_quick_hidden_ms":16853.4}
```

隐藏控件也一样慢（`C_quick_hidden_ms`），所以不是「可见才排」的绘制开销，而是
`QQuickTextEdit` 把 `contentsChange` 接到自己的 size/layout 上后，**每次插入都触发一次
文档级重排**。屏蔽文档信号只是部分缓解（14.8 s → 9.5 s），不能根治——
真正的解法是**不要往活动文档里做多次插入**。

### 3.4 高亮器挂在「上一份巨大文档」上，切换会话时先白跑 2.5 s

`BodyDocument.attach()` 把 `QSyntaxHighlighter` 移到 QML 文档（`body.py:147`）。
下一次 `_render()` 的第①步 `set_markdown()` 只往自有文档里渲染，但结尾会调
`self._highlighter.rehighlight()`（`body.py:104-109`）——此时高亮器仍挂在**上一份**大文档上：

```
{"to":"big->short","rehighlight":[2581.4, 2.8, 3.7],"body_render":[2590.7, 45.6],
 "set_markdown":[2590.8],"body_attach":[252.5]}
```

即点击一个只有 1 轮的短会话，**第一件事是花 2.58 s 把旧的大文档全量重跑高亮**。
这就是「点什么都卡」的直接来源之一。（`profile_rehighlight.py`）

### 3.5 渲染器本身在表格上也偏贵

`cProfile` 400 轮正文（`profile_renderer_cprofile.py`）：`insertTable` 0.515 s + `appendRows` 0.494 s
占 2.1 s 里的近一半。表格由多次 `insertTable/appendRows/setFormat` 组成，
是后续可以单独优化的点，但**不是这次点击卡顿的主因**（只占 4.7 s 里的 1 s）。

## 4. 修复方案（最小、保语义）

只改 `BodyDocument.attach()` 的目标文档写入方式，不动渲染器、不动 QML、不动对外契约：

1. 内容仍然先渲染进 `BodyDocument` 自有的普通文档（原第①步）；
2. 搬进 QML 活动文档时，不再整篇重渲染，而是 **clear + 一次 `insertFragment`**；
3. 把自有文档里的图片资源按名字补注册到目标文档（`insertFragment` 不搬文档级资源，实测会丢图）；
4. 把 `documentMargin` 对齐到自有文档的值（渲染器用 0，QML 文档默认 4）；
5. 高亮器**跟到目标文档**上——`insertFragment` 引起的内容变更会让它逐块着色，
   搬运后**不再显式 `rehighlight()`**（同一份正文重跑 400 轮实测 0.9~1.7 s，纯白给）；
   而 `render()` 只在「高亮器确实挂在这次渲染的目标上」时才重高亮，避免切会话时先对
   上一份大文档全量重跑（§3.4 的 2.5 s）。

### 4.1 保真度（严格重比对，`probe_fidelity_geometry.py` / `probe_margin.py`）

> 更正：本报告早期版本在 §4 写过「`toHtml()` 与直接渲染完全等价」，**那是假阳性**。
> 当时的比对把片段 `insertFragment` 到一个已经渲染过的目标文档上，布局格式是旧的；
> 干净目标上重做后，`QTextLayout` 的 `FormatRange` 根本不会随片段走。

最终结论（同一份正文，`content_width=676`，`setTextWidth(696)` 后比对）：

| 项目 | 直接渲染 | scratch + insertFragment | 结论 |
|---|---|---|---|
| 块数 / 字符数 | 19 / 243 | 19 / 243 | 一致 |
| 每个块的块高、行高、字体、字重、颜色 | —— | —— | 逐块一致（`same_geometry_and_chars: true`） |
| 表格结构、列宽 | —— | —— | 一致（`tables_equal: True`） |
| `documentMargin` | 0 | 4（QML 默认） | **已修**：搬运时对齐为 0 |
| `toHtml()` | —— | 只差 `-qt-user-state:0` | 该属性不参与排版，仓内无代码使用 |
| 代码着色 | 高亮器直接写 | 目标文档自己的高亮器补算 | 颜色一致，行高不塌 |

关键约束：`QTextLayout` 上的着色**不能跨文档搬**。实测把源文档的 `FormatRange`
（或复制品）`setFormats` 进目标 `QTextLayout` 后，那些块高度变成 0，代码整段不可见
（`toPlainText()` / `toHtml()` 却完全正常）。唯一可行路径是目标文档自己的高亮器重算。

端到端效果（`profile_variants.py`，同一进程同一正文）：

```
{"turns":100,"current_ms":2554.9,"v1_hl_stays_on_scratch_ms":382.5}
{"turns":400,"current_ms":21972.9,"v1_hl_stays_on_scratch_ms":2468.2}
```

### 4.2 修复后实测（同机同口径，`probe_click_visible.py 120 400 4`）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| `openSession` 同步段中位数 | 42345.3 ms | **2805.6 ms** |
| `openSession` 同步段最大值 | 74640.3 ms | **5652.9 ms** |
| 点击后首帧（中位 / 最大） | 417.4 / 752.7 ms | 411.2 / 738.1 ms（无回归） |
| `openSession_ms` 中位 / p90（壳内直调） | 39765.3 / 70292.5 ms | 3003.5 / 6106.2 ms |

首帧时间基本不变是预期的：同步段变短后，剩下的是 `_publish()`（8 ms）与首帧绘制。

真实壳截图（`after-session-1.png` = 400 轮大会话，`after-session-2.png` = 切到 1 轮短会话）：
正文、代码着色、表格、1/2/3 有序列表都在，切会话后内容完整替换、无残留。

## 5. 复现脚本

```bash
# 修复前基线（需先切到 b513d7c~1）
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/probe_baseline.py 120 400 6 BEFORE
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/probe_click_visible.py 120 400 4 AFTER
# 分阶段计时 / 高亮器 / 保真度
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/profile_attach.py 60 400
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/profile_rehighlight.py 30 200
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/profile_variants.py
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/probe_fidelity_geometry.py
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/probe_margin.py
```

（全部自带 `AI_UPPER_HOME=/tmp/ai-upper-*` 临时 home，不碰真实 `~/.ai_upper`。）

## 6. 回归与验证

- 全量 pytest：**1233 passed, 5 skipped**（`LD_LIBRARY_PATH=/tmp/qtlibs QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`，27.7s）。
- 新增/改写的用例：
  - `test_markdown_body.py::test_attach_moves_the_highlighter_to_the_shown_document`
  - `test_markdown_body.py::test_rendering_does_not_rehighlight_a_document_that_is_not_shown`
  - `test_markdown_body.py::test_attach_keeps_block_heights`
  - `test_markdown_body.py::test_attach_matches_the_rendered_document_geometry`
  - `test_markdown_body.py::test_detach_returns_the_highlighter_to_the_owned_document`
  - `test_qml_shell.py::test_open_session_renders_once_and_replaces_the_body`
  - `test_qml_shell.py::test_open_session_carries_highlight_formats_into_the_qml_document`

## 7. 未解决 / 已知残留

1. **同步段仍是 2.8 s（400 轮超大会话）**。这次只消除了「渲染两遍 + 对旧大文档白跑高亮
   2.5 s」，渲染器本身仍然贵：`cProfile` 显示表格 `insertTable/appendRows` 占 400 轮正文
   2.1 s 里的近一半（§3.5）。要再往下压得改渲染器（或把渲染挪到工作线程、只把
   `QTextDocumentFragment` 交回 GUI 线程），属于另一件事。
2. **`setDocumentMargin` 之外的文档级属性**目前只对齐了两个（margin、图片资源）。
   如果以后渲染器开始用 `documentLayout` 的默认字体或 `defaultStyleSheet`，需要在
   `attach()` 里一并同步——用例 `test_attach_matches_the_rendered_document_geometry`
   会直接抓住几何层面的偏差，但不覆盖纯样式属性。
3. `toHtml()` 仍差一个 `-qt-user-state:0`（不参与排版，仓内无代码读取）。

