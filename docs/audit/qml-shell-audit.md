# 界面重写（路线 B：QML 壳 + QTextDocument 正文）现状审计

只读审计。本文件不改动任何代码，先对账再动手。所有行号取自本次审计时的 HEAD
（`e2b93925dac6fd8c34f32f16d91e46fcc4f2d9cf`，分支 `develop`）。

审计口径：只写能直接跑出来/读出来的事实。没跑过的不写结论。

---

## 0. 一句话现状

**当前真正发布的界面不是 Qt 控件，而是 QtWebEngine 承载的原版 React 产物。**

- 打包入口：`app/pyproject.toml:53` → `entry = "main.py"`；
- 入口模块：`app/src/main.py:58 _create_window()` → `DevaWebWindow`（原 `deva_web.py`
  已于 2026-11-15 整段并入 `main.py` 并删除，见 `docs/BUILD-PROGRESS.md` §1.16）；
- 承载窗口：`app/src/mvvm/views/web_shell_window.py:120 class DevaWebWindow(QMainWindow)`，
  1280x820（`:140`），`QWebEngineView`（`:143`），加载 `assets_root()/renderer/index.html`
  （`:195`），`QWebChannel` 注册 `DevaBridge`（`:184`），无边框 + `TitleBarOverlay`（`:200–207`）；
- 数据/事件：`app/src/mvvm/webui/bridge.py:62 class DevaBridge(QObject)`（789 行），
  `app/src/mvvm/webui/host.py:75 class ChatHost`（615 行）；
- 渲染层资产：`app/assets/renderer/`（`index.html`、`shim.js`、`qwebchannel.js`、
  打包好的 JS/CSS），即 Deva 工程构建产物的只读拷贝。

也就是说：**QML 目前在这个仓库里一行都没有**（`find app -name '*.qml'` 为空），
`qt_prune.py` 里的 QML 分支只在裁剪时需要判断“有没有 QtQml/QtQuick 模块”，
而当前应用根本不 import 它们。路线 B 要补的正是这一整层。

### 0.1 与旧文档的关系

`docs/BUILD-PROGRESS.md` §0.2 记录的选型是“复用原版渲染层 + QtWebEngine”。
那是上一轮的结论，本轮用户已改选路线 B（QML 壳 + QTextDocument 正文），
本文档是这条新路线的起点对账，**不推翻**上一轮的桥/宿主/服务层——它们仍是
数据与业务的唯一来源，本轮只是换掉“显示层”。

### 0.2 基线测试（真实输出）

```text
$ cd app && ../.venv/bin/python -m pytest -q
989 passed, 5 skipped in 24.18s
```

原始日志：`out/qml-baseline-pytest.log`。

任务书写的基线是 988 passed / 5 skipped，实际多 1 条通过（仓库在这之后合入过用例）。
本轮以 **989 passed / 5 skipped 为下限**，只增不减。

---

## 1. 现有界面代码清单（Qt 控件版，非发布路径）

这一组窗口仍在仓库里、仍被单测覆盖，但**不在启动入口上**。路线 B 落地后它们
继续保留（不删测试、不删被覆盖的代码），QML 窗口是新的发布路径。

### 1.1 主窗口与三栏骨架

| 位置 | 内容 |
| --- | --- |
| `app/src/mvvm/views/deva_main_window.py:40` | `class DevaMainWindow(ViewBase)`，装配后的主窗口 |
| `:28` | `SPLIT_SIZES = (280, 780)`，左会话列/右内容列的初始宽度 |
| `:66` | `QtWidgets.QSplitter(Horizontal)`，唯一的分栏容器 |
| `:90` | `QStackedWidget`，内容区在「对话 / 设置」两页间切换 |
| `:95` | `splitter.setSizes(list(SPLIT_SIZES))` |
| `:100` | `window.resize(1080, 720)` |
| `:115/:118/:121` | `chat_pane()` / `session_pane()` / `settings_pane()` 供测试与截图脚本取控件 |
| `:133–148` | `_show_chat` / `_back_to_chat` / `_show_settings`，页面切换 |
| `:150–225` | 会话切换、新建、重命名（`QInputDialog`）、归档、删除（`QMessageBox`） |
| `:227–251` | `_fetch_models_async`，后台线程拉模型清单 |

**没有 QSS。** `grep -rn "setStyleSheet" app/src` 为空——当前控件版界面用的是
Qt 默认 Fusion 风格，没有任何样式表、没有主题切换、没有圆角/阴影/图标。
这也是为什么它从未被当作“与原版一致”的交付物。

### 1.2 逐页结构

| 页面 | 位置 | 控件与几何 |
| --- | --- | --- |
| 会话列表 | `app/src/mvvm/views/session_list.py:25` `SessionListPane` | `:54 QListWidget`；`:55 EMPTY_HINT = "还没有对话"`（`:22`）空态 QLabel；`:132` 每行 `title\nsubtitle` 两行文本；`:74` 空态提示与列表同列 |
| 会话行按钮 | 同上 `:57–66` | 新建/重命名/归档/删除/设置五个 `QPushButton`，分三行 `QHBoxLayout`（`:68–72`） |
| 聊天面板 | `app/src/mvvm/views/chat_pane.py:50` `ChatPane` | `:61 QTextBrowser` 正文；`:87 input_box.setFixedHeight(72)`；待办胶囊 `:64–80`；流式区 `:62`；状态/错误标签 `:81–83`；发送/停止按钮 `:84–86` |
| 设置页 | `app/src/mvvm/views/settings_pane.py:55` `SettingsPane` | 三页 `QStackedWidget`（`:113–115`）：服务商列表 `:124 _build_list_page`、服务商详情 `:144 _build_provider_page`、模型详情 `:215 _build_model_page`；思考等级下拉 `:82–86`（档位来自 `EFFORT_LEVELS`，文案见 `:46–53`）；`widgets()` `:258` 给测试/截图取控件 |
| 首启/空态 | `session_list.py:55` + `:140` `_show(self._hint, not sessions)` | 只有一句“还没有对话”，没有卡片、插图、引导操作 |
| 滚动条 | 无自定义 | 用平台默认滚动条；`chat_pane.py:61` 的 `QTextBrowser` 自带纵向+横向滚动 |
| 图标资产 | 无 | `find app/assets -name '*.svg' -o -name '*.png'` 只命中 `app/assets/renderer/assets/feishu-*.svg`（React 产物里的一个文件）；Qt 控件版不使用任何图标 |
| 标题栏 | `app/src/mvvm/views/title_bar_overlay.py:38` `TitleBarOverlay(QWidget)` | `:27 TITLEBAR_HEIGHT = 40`、`:28 BUTTON_WIDTH = 32`；`:61` 三个按钮的矩形；`:98 paintEvent` 自绘最小化/最大化/关闭 |

### 1.3 主题

- 配置键：`app/src/mvvm/services/settings_service.py:29 THEME_KEY = "theme"`、
  `:30 LANGUAGE_KEY = "language"`、`:31 LAYOUT_KEY = "layout"`；
- 控件版界面**不读这两个键**——没有主题切换、没有语言切换的实现；
- 唯一消费主题的是 Web 路径：`bridge.py:455 _set_overlay` 与
  `web_shell_window.py:207 self.bridge.set_overlay_callback(self.overlay.set_dark)`，
  只用来给右上角三个按钮换深浅色。

---

## 2. 正文渲染现状

### 2.1 控件版（非发布路径）

| 位置 | 内容 |
| --- | --- |
| `app/src/mvvm/views/chat_pane.py:184` | `self._transcript.setHtml(transcript_html(entries))` |
| `app/src/mvvm/views/transcript_render.py:129` | `transcript_html(entries)`，纯函数、不依赖 Qt |
| `:88` | `_tool_card()`：工具条目画成**单格 `<table>`**（`cellpadding=8`、1px 边框、错误态红底） |
| `:118` | `_message()`：`［角色］` 加粗行 + 正文段，正文走 `_preserve()`（`:48`，转义 + 换行→`<br>`） |
| `:68 decode_images` / `:64 image_placeholder` | 内联图片：先把 base64 解出来，再 `QTextDocument.addResource` 注册成文档资源（`chat_pane.py:186–203`），`<img src="deva-image:0">` |
| `:150 transcript_plain_text` | 纯文本投影（日志/测试用） |

**结论：控件版没有任何 Markdown 渲染。** 助手回复里的 `**粗体**`、`#` 标题、列表、
代码围栏、表格、链接全部按纯文本显示，换行仅靠 `_preserve` 的 `<br>`。

### 2.2 Web 路径（当前发布路径）

Markdown 由原版 React 渲染（`deva/apps/desktop/src/renderer/src/features/chat/Markdown.tsx`），
代码高亮用 highlight.js，样式在 `deva/.../styles/app.css:764–1000`（`.md`、`.md-code`）。

### 2.3 数据形状（正文层的输入契约）

展示条目由 `ChatViewModel._display()` 产出（`app/src/mvvm/view_models/chat_vm.py:772`），
共五类 `role`：`user` / `assistant` / `tool` / `error` / `compaction` / `notice`；
工具条目带 `name`、`is_error`、`images[{mediaType,name,data}]`。
Web 路径另有一套 `display_messages()`（`app/src/mvvm/webui/bridge.py:541`），
按原版 `toDisplayMessages` 合并 assistant 段、回填工具卡状态。

正文层改造只需吃 `_display()` 的条目形状——**不需要**改数据模型。

---

## 3. MVVM 层：QML 能直接绑什么、缺什么

### 3.1 现有机制

| 位置 | 机制 |
| --- | --- |
| `app/src/mvvm/core/observable.py:24` | `class ObservableProperty(Generic[T])` —— Python **描述符**，不是 `Q_PROPERTY` |
| `:36/:40` | `get_value()` / `set_value()`，等值时不发通知 |
| `:49 _notify_changed` / `:62 subscribe` | 变更事件 `PropertyChangedEvent(property_name, old, new)`，订阅返回取消函数 |
| `app/src/mvvm/core/base_view_model.py:10` | `class BaseViewModel`；`:28 _register_property`、`:39 get_property_value`、`:44 set_property_value`、`:73 subscribe_property_changed` |
| `app/src/mvvm/core/factory.py` | `PropertyFactory.create(default, name)` |
| `app/src/mvvm/core/command.py` | `RelayCommand` / `AsyncRelayCommand`，`can_execute` 判定 |
| `app/src/mvvm/views/base_view.py:9` | `MVVMBinding`（ViewModel→控件 setter）；`:82 CommandBinding`；`:112 ViewBase.bind_property/bind_command` |

### 3.2 ViewModel 清单（QML 要绑的属性）

| ViewModel | 属性（`*_property`） | 命令/方法 |
| --- | --- | --- |
| `ChatViewModel`（`chat_vm.py:88`） | `title`(:156)、`transcript`(:159)、`input_text`(:162)、`status`(:165，默认“就绪”)、`error`(:168)、`busy`(:171)、`streaming`(:175)、`todos_state`(:179) | `send`(:285)、`cancel`(:370)、`open_session`(:273)、`drain`(:344)；回合在后台线程跑，UI 写入经 `_ui()` 队列（`:359`） |
| `ChatSessionsViewModel`（`chat_sessions_vm.py:46`） | `sessions`(:57，`[{id,title,subtitle,updated_at,active}]`，见 `:36 _entry`)、`active_id`(:60) | `refresh`(:75)、`new_session`(:83)、`set_active`(:94)、`rename`(:101)、`archive`(:109)、`delete`(:114) |
| `SettingsViewModel`（`settings_vm.py`） | `providers`(:91)、`active_model`(:94)、`active_effort`(:97)、`message`(:100) | `refresh`(:127)、`add_provider`(:160)、`update_provider`(:186)、`remove_provider`(:213)、`add_model`(:234)、`toggle_model`(:264)、`update_model`(:273)、`remove_model`(:305)、`set_active_model`(:321)、`set_active_effort`(:330)、`set_api_key`(:339)、`fetch_models`(:359) |

### 3.3 QML 绑定的缺口（必须补的适配层）

1. **`ObservableProperty` 不是 `Q_PROPERTY`**：QML 绑定引擎看不见描述符。需要一个
   `QObject` 适配层，把选定的属性暴露成 `Property` + `notify` 信号，并在
   ViewModel 的 `subscribe_property_changed` 上挂转发。
2. **没有列表模型**：会话列表、服务商列表、模型列表都是 `list[dict]` 整体替换，
   QML 的 `ListView` 需要 `QAbstractListModel`（或每行一个 `QObject`）。整体替换
   还会让 `ListView` 每次重建，长列表滚动复用要按行 diff 或按 id 增量更新。
3. **命令不是槽**：`RelayCommand.execute` 要在适配层暴露成 `@Slot`，`can_execute`
   要变成 `enabled` 属性 + 变更通知。
4. **线程**：`ChatViewModel` 的回合在后台线程写属性，`_ui()` 队列由 GUI 线程
   `drain()` 取走（`chat_vm.py:344`）。QML 适配层必须继续走 drain，不能自己在
   后台线程 emit 信号。
5. **流式文本**：`streaming` 是整串替换（`:377 _push_streaming`），正文层要按增量
   追加而不是每帧重排全文档。

### 3.4 Web 桥（可复用，但不走 QML）

`app/src/mvvm/webui/bridge.py:221 _register_defaults` 注册 64 个通道；
`docs/audit/IPC-158-LEDGER.md` 记录 158 条通道的判定（通过 60 / 已知差异 5 / 未实现 93）。
桥是“Web 渲染层 ↔ Python”的通道，**QML 路径不需要它**；但其中的业务转接
（`display_messages`、`list_models_payload`、附件/密钥/配置读写）是现成的，
QML 适配层应复用这些纯函数，不要再写第二份。

---

## 4. 打包链与 CI 现状

### 4.1 配置

| 位置 | 内容 |
| --- | --- |
| `app/pyproject.toml:53` | `entry = "main.py"` |
| `:19` | `version = "0.17.33"`，`:18 name = "ai_upper"`，`:21 requires-python = ">=3.8,<3.14"` |
| `:69` | 目标运行时 `python = "3.13.5"` |
| `:148 [tool.ai_upper.cython]`、`:158 merge = "directory"` | 全部叶子模块合并成一个扩展 |
| `:214 qt = "imports"` | 只保留 `app/src` **静态 import 扫描**得到的 Qt 模块及其闭包 |
| `:129 [tool.ai_upper.egg]` | 加密 egg（`bundle/ai_upper.dat`） |

### 4.2 非 py 资源

| 位置 | 内容 |
| --- | --- |
| `tools/ai_upper/package.py:291 _copy_supporting_trees` | 把 `app/resources` 与 `app/assets` 整体拷到 bundle 根（`:299`、`:303`，`:300–306` 注释） |
| `app/src/utils/paths.py` | `resource_root()` / `assets_root()`（后者优先读 launcher 导出的 `AI_UPPER_HOME`，开发态回落 `app/assets`），`DEVA_ASSETS_DIR` 可覆盖 |
| 现有捆绑资源 | `app/assets/personas/{general,xiaomajiang}.md`（Humation 头像 JSON 在 frontmatter 的 `avatar:` 字段）、`app/assets/renderer/**` |

**QML 文件的缺口**：`package.py` 只拷 `resources` 与 `assets` 两个目录，`app/src` 下的
`.qml` 不会被拷；而 Cython 只编译 `.py`。因此 QML 必须落到 `app/assets/qml/`（或新建
`app/resources/qml/`）才能进产物。

### 4.3 Qt 裁剪的 QML 陷阱（关键风险）

| 位置 | 内容 |
| --- | --- |
| `tools/ai_upper/qt_prune.py:183` | `QML_MODULE_PREFIXES = ("QtQml", "QtQuick")` |
| `:508 qt_module_usage` | 扫描 `app/src` 的 **Python import**，`.qml` 文件里的 `import QtQuick` 完全不可见 |
| `:623 configured_modules` | `qt = "imports"` 时模块集 = 静态 import 闭包 |
| `:895` | `if not any(name.startswith(QML_MODULE_PREFIXES) for name in modules): drop(layout.qml)` |

结论：**如果不显式 import 一个 QtQml/QtQuick 的 Python 模块，整棵 Qt QML 运行时目录
会被裁掉，打包产物启动时 QML 引擎无模块可加载。**（README/CHANGELOG 已记录该限制。）
本轮需要：入口侧显式 import（真实用途，不是占位），并在 `qt_prune.py` 里把 QML
资源的存在也纳入判据——否则“源码态能跑、产物起不来”。

### 4.4 测试与 CI

| 位置 | 内容 |
| --- | --- |
| `.github/workflows/validate.yml:20–25` | 6 个 `build-tool-compat` job：Python 3.8/3.9/3.10/3.11/3.12/3.13 |
| `:113` 起 | native-integration 矩阵：linux x86_64/arm64、windows x86/x86_64/x86_64-py3.8.10/windows-arm64、macOS x86_64/arm64 |
| `:258` | `Unit tests` → `python -m pytest tests -q -ra --tb=long`（工作目录 `app/`） |
| `:404` | `Full integration run`：`AI_UPPER_HEADLESS=1 python tools/build.py --run --target ...` |
| `:440` 附近 | 断言 `'DEVA WEB OK' in text and 'bridge=True' in text` |

- 3.8 兼容由 `test_py38_compat.py` 静态把关（不许 3.9+ 语法）；
- `windows-arm64` 已知红：PySide6 无 win_arm64 wheel（更无 QtWebEngineCore），
  本轮不新增 WebEngine，平台阻塞不变，不重复调查。

### 4.5 现有测试（与界面相关）

| 文件 | 覆盖 |
| --- | --- |
| `app/tests/test_deva_panes.py` | 控件三栏：会话列表/设置页/主窗口的“用户动作 → VM → 控件”链（假 Qt 控件） |
| `app/tests/test_mvvm.py:199–228` | 遍历 `mvvm` 全部模块可导入；3 个需真实 Qt 的模块豁免（`title_bar_overlay`、`web_shell_window`、`webui.bridge`），豁免项必须真实存在 |
| `app/tests/test_web_shell_modules.py` | 豁免项的替代覆盖：真实 binding 下可导入/可构造、缺 WebEngine 时显式报错、shim 组装 |
| `app/tests/test_transcript_render.py` | `transcript_html` / 纯文本投影 |
| `app/tests/test_chat_vm*.py`、`test_settings_vm.py`、`test_chat_sessions_vm.py` | ViewModel 行为 |
| `app/tests/test_qt_prune.py` | 裁剪策略（含 QML 目录删除条件） |
| 截图脚本 | `scripts/parity/{deva_original_shots.sh,port_shots.sh,port_run.py,compare.sh}`，Xvfb 1400x900、窗口 1280x820、`compare` 的 AE/fuzz3%/maxd≤10 |

## 5. 原版视觉基线（取自只读 deva 工程）

这些数值是 QML 壳要对齐的唯一标准。全部来自
`deva/apps/desktop/src/renderer/src/`（只读，本轮不得改动）。

### 5.1 设计 token（`styles/tokens.css:7–112`；浅色 `:41–81`，深色 `:108` 起）

| 类别 | 值 |
| --- | --- |
| 字体 | `--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', Roboto, Helvetica, Arial, sans-serif`；`--font-mono: 'Cascadia Code', 'JetBrains Mono', ui-monospace, Consolas, 'Courier New'` |
| 间距 | 4/8/12/16/20/24 px（`--space-1..6`） |
| 圆角 | 6 / 8 / 12 / 999 |
| 尺寸 | `--titlebar-h 40px`、`--sidepanel-w 264px`、`--control-h 34px` |
| 浅色 | `--bg #ffffff`、`--bg-panel #f7f7f8`、`--bg-elevated #ffffff`、`--bg-inset #f0f0f2`、`--bg-hover rgba(0,0,0,.045)`、`--bg-active rgba(0,0,0,.08)`、`--bg-selected rgba(91,91,214,.12)`、`--fg #1f1f24`、`--fg-muted #5c5c66`、`--fg-subtle #8a8a94`、`--border #e6e6ea`、`--border-strong #d5d5db`、`--accent #5b5bd6`、`--accent-hover #4c4cc4`、`--chat-user-bubble #edeffb` |
| 深色（`:108` 起） | `--bg #1e1e20`、`--bg-panel #252528`、`--bg-elevated #2a2a2e`、`--bg-inset #191919`、`--fg #e4e4e7`、`--fg-muted #a1a1aa`、`--fg-subtle #71717a`、`--accent #7c7cf0`、`--chat-user-bubble #303043` |
| 滚动条 | 宽 8px，滑块 `var(--scrollbar)`，圆角全，透明边框 2px（`styles/app.css:46–60`） |

### 5.2 外壳栅格（`redesign/redesign.css`）

| 位置 | 内容 |
| --- | --- |
| `:7 .cf-shell`（`:19 --cf-main: 780px`）（正文列宽） |
| `:27 .cf-body` | `grid-template-columns: var(--cf-rail-w,56px) var(--cf-side,300px) minmax(0,1fr)`；列宽过渡 0.16s |
| `:115 .cf-iconrail` | 列宽 56px（由 `.cf-body` 的 `--cf-rail-w` 决定）；`padding: 20px 0 12px`，底色 `--bg-inset`，右边框 1px |
| `:133 .cf-navbtn` | 40x40，圆角 8，选中态 `--bg-active` + `--accent`，左侧 3x18 强调条（`:175 .cf-navbtn.is-active::before`） |
| `:188 .cf-rail` | 会话列，底色 `--bg-panel`，右边框 1px |
| `:532 .cf-rail__top` | `padding: 12px`，含搜索框 |
| `:541 .cf-search` | 高 32，圆角 8，1px 边框，底色 `--bg` |
| `:741 .cf-list` | `padding: 0 8px 8px`，纵向滚动 |
| `:749/.cf-thread` | `grid: 38px minmax(0,1fr)`，`gap 12`，`padding 8px 12px`，圆角 8；hover `--bg-hover`，选中 `--bg-selected` |
| `:996 .cf-conv` | 中列，底色 `--bg` |
| `:1003 .cf-conv__head` | 头部条，右侧留 140px 给窗口控件，底边 1px |
| `:1598 .cf-msgs` | 滚动区，`padding: 20px 0`，`scrollbar-gutter: stable` |
| `:1722 .cf-msgs__inner` | `max-width: 780px`，居中，左右 20px，条目间距 20px |
| `:1730 .cf-msg` | `grid: 32px minmax(0,1fr)`，`gap 12` |
| `:1747 .cf-msg__name` | 13px / 700 |
| `:1752 .cf-msg__text` | `font-size: calc(13.5px * var(--cs))`，行高 1.62 |
| `:1815 .cf-msg.is-user` | 用户消息右对齐，`max-width: 80%`，气泡 `--chat-user-bubble`、`padding 10px 14px`、圆角 12（右上 6） |
| `:2123 .cf-composer` | `padding: 12px 16px 16px`，上边框透明 |
| `:2150 .cf-composer__inner` | `max-width: 780px` 居中 |
| `:2505 .cf-box` | 输入盒：1px `--border-strong`、圆角 12、`padding 12`、`box-shadow: 0 6px 24px rgba(0,0,0,.12)`；`focus-within` 变 `--accent` |
| `:2531 .cf-draft` | 最小高 44，13.5px / 1.5 |
| `:2671 .cf-send` | 高 32，最小宽 68，圆角 8，底色 `--accent`，禁用 0.45 透明度；停止态中性底色 |
| `:2895 .cf-empty` | `padding: 20`，居中，12px / 1.8，`--fg-subtle` |
| `:2999 .cf-modal__backdrop` | 全屏 `rgba(0,0,0,.42)` 遮罩，居中 |
| `:3008 .cf-modal` | 最大宽 720，高 `min(560px, 82vh)`，圆角 12，底色 `--bg-panel` |
| `:3044 .cf-modal__body` | `grid: 168px minmax(0,1fr)`（设置左导航 + 右内容） |

### 5.3 Markdown 正文（`styles/app.css:764–1000`）

| 元素 | 规则 |
| --- | --- |
| `.md` | 14px（× 倍率 `--cs`），行高 1.65，`word-break: break-word` |
| `p` | `margin: 0 0 12px` |
| `ul/ol` | `margin: 0 0 12px; padding-left: 1.5em` |
| `li` | 上下 2px；标记色 `--fg-subtle` |
| `h1` | 1.5em；`h2` 1.3em + 下边框 1px；`h3` 1.15em；`h4` 1em；`h5/h6` 0.9em 且 `--fg-muted` |
| 标题外边距 | 上 16px / 下 8px，行高 1.3，字重 650 |
| `a` | `--accent`，无下划线，hover 加下划线 |
| `blockquote` | 左 3px `--border-strong` 竖线，`padding: 2px 0 2px 12px`，字色 `--fg-muted` |
| `hr` | 1px `--border`，上下 16px |
| `img` | 最大宽 100%，圆角 6 |
| `table` | `display:block; width:max-content; max-width:100%; overflow-x:auto`，合并边框，13px，底边距 12px |
| `th/td` | 1px `--border`，内边距 `6px 10px`，左对齐；`th` 底色 `--bg-panel`、600；偶数行 `--bg-hover` |
| 任务列表 | 复选框右距 6px，所在 `li` 去掉标记并左移 1.2em |
| 行内代码 `.md-inline` | 等宽字体 0.88em，`padding: 1px 5px`，圆角 4，底色 `--bg-inset`，1px 边框 |
| 代码块 `.md-code` | 1px 边框 + 圆角 8，底色 `--bg-inset`；头部 `.md-code__head` 底色 `--bg-panel`、`padding: 4px 6px 4px 12px`、语言名 11px 等宽小写、右侧“复制”按钮 11px；正文 `padding: 12px`、`overflow-x: auto`、12.5px / 1.55、`white-space: pre` |

### 5.4 运行时环境事实（影响渲染一致性）

- `.venv`：Python 3.13.5 + PySide6 6.11.2；`PySide6.QtQml/QtQuick/QtQuickControls2` 可用；
  `QQuickTextDocument` 在 **`PySide6.QtQuick`**（不在 `QtQml`）。
- 系统字体：只有 Noto Sans/Serif CJK（SC/HK/JP/KR/TC）、DejaVu、Droid Sans Fallback，
  **没有 emoji 字体**，`fc-match sans-serif` → DejaVu Sans。原版 CSS 首选
  `-apple-system / Segoe UI / Microsoft YaHei`，在 Linux 上同样回落，
  但 Qt 的字体匹配与 Chromium 不同，中文/emoji 需实测后决定是否随包内置字体。
- 3.8 目标：`app/requirements.txt` 用 `typing_extensions` 兜 `Annotated`，
  `chat_models.py:23–28` 有显式版本分支；QML 相关 Python 代码同样不得使用 3.9+ 语法。

---

## 6. 本轮要动的文件（预判，实施时以实际为准）

| 新增/修改 | 作用 |
| --- | --- |
| `app/assets/qml/**.qml`（新增） | QML 壳：主窗口、图标栏、会话列表、对话页、输入区、设置弹框、控件样式 |
| `app/src/mvvm/qml/`（新增） | QML 适配层：`QObject` 属性桥、`QAbstractListModel` 列表、命令槽、正文文档对象 |
| `app/src/mvvm/views/qml_shell_window.py`（新增） | `QQmlApplicationEngine` 承载窗口、无边框叠加层、headless 截图钩子 |
| `app/src/main.py`（修改） | 现有唯一入口；把 `_create_window()` 换成 QML 壳窗口，headless 标记改成 QML 可验证的形态 |
| `app/src/markdown/`（新增） | Markdown → `QTextDocument`（含 `QSyntaxHighlighter`） |
| `tools/ai_upper/qt_prune.py`（修改） | QML 资源存在时保留 QML 运行时；模块判据纳入 `.qml` 的 import |
| `tools/ai_upper/package.py`（改/确认） | QML、字体、图标进产物 |
| `app/tests/test_qml_*.py`、`test_markdown_doc.py`（新增） | 绑定与转换的单元测试 |
| `.github/workflows/validate.yml`（可能修改） | 启动标记与 QML 冒烟断言 |

---

## 7. 未决/风险（实施前先写在这里）

1. **逐像素一致性**：原版是 Chromium 渲染，QML 是 Qt 场景图，字体整形/度量不同，
   逐像素必然有亚像素差。用户已确认「渲染引擎差异导致的亚像素差可接受」，本轮按
   「结构/间距/字号/颜色一致」判定，并在报告里给出 `compare` 的量化值而不是口头结论。
2. **头像**：原版头像由 Humation 的 86 个 SVG 部件在运行时合成（`@humation/core` 的
   `createAvatar`）。QML 侧要么复刻该合成算法（Python 版，纯字符串拼接 SVG），
   要么随包捆绑预算好的头像。选型在 §二 实施时定，原则是不改 deva 工程。
3. **富文本输入**：原版输入框是 Lexical（contentEditable），支持 @ 提及、附件贴片、
   `/` 指令。QML 侧用 `TextArea`，第一版只做纯文本 + 发送键策略，其余按“未实现”显式列出。
4. **QtWebEngine 移除**：路线 B 的硬要求是不引入 QtWebEngine。现有 `web_shell_window.py`
   与 `main.py` 仍在仓库且被测试引用；QML 入口切走后，是否删除旧 Web 路径由后续轮次决定
   （不删测试、不删被覆盖代码）。
5. **`qt = "imports"` 裁剪**：见 §4.3，必须用真实 import 保住 QML 运行时，并在
   `qt_prune.py` 里补判据。这是“源码能跑、产物起不来”最可能的来源。
