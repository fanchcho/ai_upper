# 追加审计：聊天记录导出（A） / 消息携带文件输出（B）

审计对象：`/home/agent/shared_workspace/ai_upper`（分支 `develop`，HEAD `492f8ac`）
对照对象：`/home/agent/shared_workspace/deva`（Electron + React 原版，**只读**，未做任何写入）
性质：**只读**。本轮只新增 `out/audit-model-path/` 下的报告、日志、脚本与截图，并写了 `/tmp/audit-files-home`；仓库已跟踪文件无改动（见 §7）。

用户原话：「聊天记录可以带文件输出吗？原来的可以」——按两种口径分别查：
**A 聊天记录导出成文件**、**B 消息本身携带文件输出**。

---

## 0. 结论

| 口径 | deva 原版 | ai_upper（web 兜底入口） | ai_upper（默认 QML 入口） |
| --- | --- | --- | --- |
| **A 聊天记录导出为文件（md/json/html/txt + 选导出路径）** | **完全缺失** | **完全缺失** | **完全缺失** |
| **B-1 用户随消息发出的附件/图片（持久化 + 界面可见）** | **已有且可用** | **已有且可用** | **完全缺失**（不显示、也不能发） |
| **B-2 工具产出的文件交付（交付卡：文件名/大小/缩略图/打开/定位）** | **已有且可用** | **只有界面壳，未接通** | **完全缺失** |

三句话：

1. **A 这一条，原版并没有**。deva 的 154 条 IPC 通道里没有任何导出/保存/下载类通道，全仓库没有 `showSaveDialog`，渲染层也没有「导出」文案，会话右键菜单只有 `新对话 / 重命名 / 归档 / 删除` 四项。用户记忆里的「原来的可以」最可能是下面三件事之一（见 §1.4），但**不是应用内的导出功能**。
2. **B 这一条原版确实可以**：`present_files` 工具的交付卡（缩略图/大小/打开/定位/复制路径）+ 附件贴片（图片带 ref 缩略图）。ai_upper 的 web 入口把这两套前端**都继承下来了**，但交付卡那一套**后端没接**——卡片画得出来，只是每个文件显示 `0 B`、按钮点了没反应，实测报 `通道未接入：deliverables:inspect`。
3. **默认 QML 入口两头都空**：没有导出入口；正文层只渲染纯文本（`transcript_markdown` 只取 `message.text()`），附件不显示、交付卡不存在，输入框旁的附件图标与 `Mount workspace` 都是装饰。

证据截图：
- `web-deliverables-card.png` —— web 入口的交付卡（`Deliverables / 1 file / report.md / 0 B`，注意 `0 B` 就是后端没接的痕迹）
- `qml-session-attachment-invisible.png` —— 同一条会话在 QML 里：用户那句话在，附件图与交付文件一概不见

---

## 1. 口径 A：聊天记录导出为文件

### 1.1 deva 原版：没有这个功能（命令与输出）

`ipcMain.handle` 全量 154 条，按关键词过滤只剩更新下载：

```
$ grep -rn "ipcMain.handle(" --include=*.ts apps/desktop/src/main | wc -l
154
$ grep -rn "ipcMain.handle(" --include=*.ts apps/desktop/src/main \
    | grep -iE "export|save|download|share|markdown|\.md'|html|txt"
apps/desktop/src/main/services/updater.ts:272:  ipcMain.handle('update:download', () => download())
```

原生保存对话框一处都没有：

```
$ grep -rn "showSaveDialog\|saveDialog\|dialog.save" --include=*.ts --include=*.tsx apps/desktop/src
（无输出）
```

渲染层也没有导出文案/下载动作：

```
$ grep -rn "导出\|Export\b" --include=*.tsx apps/desktop/src/renderer/src
（仅 3 条注释「故导出」，是 TS 模块导出，不是功能）
$ grep -rn "download|saveAs|a\.click\(\)|URL\.createObjectURL" --include=*.tsx apps/desktop/src/renderer/src
（无输出）
```

会话右键菜单四项（无导出）：

```
apps/desktop/src/renderer/src/redesign/ChatFirstShell.tsx:2597  { label: t('cf.newChat') … }
                                             :2602  { label: t('cf.renameChat') … }
                                             :2607  { label: t('cf.archive') … }
                                             :2619  { label: t('cf.deleteChat') … }
```

`apps/web`（deva 的另一端）同样没有：`grep -rniE "导出|saveAs|download" apps/web/src` 无输出。

### 1.2 唯一与“导出”沾边的：会话本身就是磁盘文件

deva 把每条对话独立存成 `<DEVA_HOME>/data/chats/<id>.json`（压缩边界另有 `<id>.compacted-<ts>.jsonl`）：

```
apps/desktop/src/main/services/chat-store.ts:24   「对话…各自独立成文件 <DEVA_HOME>/data/chats/<id>.json」
apps/desktop/src/main/services/chat-store.ts:251-252  chatsDir() = getDevaHome()/data/chats
apps/desktop/src/main/services/chat-store.ts:368  「拆分文件名：<id>.compacted-<时间>.jsonl」
```

也就是说，用户能“把一个文件拿走”的路径是**去数据目录拷 JSON**，不是应用里的导出。ai_upper 沿用同一布局：`<AI_UPPER_HOME>/data/chats/<id>.json`（实测 `verify_files_live.log`：`会话文件 = /tmp/audit-files-home/data/chats/audit-files.json`）。

### 1.3 若真要导出：图片在两种落盘里的形态完全不同（重要）

| | deva | ai_upper |
| --- | --- | --- |
| 会话 JSON 里的图片 | `{type,mediaType,name,blob:"<sha256>"}` 引用 | `{type:"image",mediaType,name,data:"<base64>"}` 内联 |
| 字节存哪 | `<DEVA_HOME>/data/media/<sha256>`（原始字节） | 就在会话 JSON 里（base64） |
| 依据 | `main/services/media-store.ts:8-13`（文件头说明）、`:120-150`（`hydrateMessages`）、`chat-store.ts:488` | `app/src/mvvm/services/attachments.py:462/468`；实测 `content[0].data 长度 = 100` |
| 载入时 | 按 hash 读回，内存里仍是 base64（`media-store.ts:120-150`） | 直接可用 |

所以「导出物里图片是路径、base64 还是链接」这个问题的答案是：**目前两边都没有导出物**；从磁盘素材看，deva 是「媒体文件 + 哈希引用」，ai_upper 是「base64 内联」。做导出时这会直接决定实现路径（ai_upper 反而更简单：基64 现成，可直接内联进 md）。

### 1.4 ai_upper：③ 完全缺失

web 入口实测的桥通道清单（64 条）里没有导出类：

```
$ .venv/bin/python out/audit-model-path/verify_files_live.py
== 桥已注册通道数 == 64
== 通道名里含 export/save/download/md 的 ==
    []
```

QML 入口没有任何菜单/对话框入口（`grep -rn "Menu\b|ContextMenu" app/src/qml/Main.qml` 只命中一个**纯展示**的右键面板，见 §2.4）。唯一像“导出”的原语没有调用者：

```
$ grep -rn "copy_session_file" --include=*.py app/src app/tests | grep -v __pycache__
app/src/mvvm/services/chat_session_store.py:518:    def copy_session_file(...)
（调用者 0 条；docstring 自称「备份/导出用」）
```

**关于「原来的可以」**，按代码证据，原版能给人“导出感”的只有三条，且都不是导出功能：
1. 会话是磁盘上的 JSON 文件，可手动拷走（§1.2）；
2. 原版能把**文件**带进聊天（交付卡 / 附件贴片，属 B），容易被记成“聊天记录带文件”；
3. 选中文字右键「复制」到剪贴板（`ChatFirstShell.tsx:5755-5757`，只复制选区文本，不产生文件）。
如果用户指的是某个具体按钮/菜单项，需要给出名称或截图——本仓库（deva 全部 `apps/desktop` + `apps/web`）里没有对应的实现，这一点命令层面是穷举过的。

---

## 2. 口径 B：消息携带文件输出

### 2.1 deva：完整链路（真做了，不是壳）

**B-2 交付卡**（模型/工具产出的成品文件）：

```
工具规格与执行        apps/desktop/src/main/services/tools.ts:158（present_files 说明）
                      apps/desktop/src/main/services/tools.ts:1496-1538（核对存在 → delivered: files）
会话边车（落盘）      apps/desktop/src/main/services/chat-store.ts:138-142  delivered?: Record<string, string[]>
                      （按 toolUseId 记绝对路径；messages 里保留模型原样参数）
主进程 IPC（4 条）    apps/desktop/src/main/services/deliverables.ts:69  deliverables:inspect
                      :89  deliverables:thumbnail   （nativeImage 缩略图 → 回落 app.getFileIcon）
                      :108 deliverables:open        （仅 OPENABLE 扩展名）
                      :119 deliverables:reveal      （shell.showItemInFolder）
安全不变式            deliverables.ts:9-12「渲染层只给对话 id + 调用 id + 序号，路径一律主进程按会话取」
返回结构              apps/desktop/src/shared/deliverables.ts:2-11 {path,name,dir,size,openable}
preload 暴露          apps/desktop/src/preload/index.ts:1383-1394
渲染组件              apps/desktop/src/renderer/src/features/chat/DeliverablesCard.tsx:51
                      （缩略图 / 文件名 / formatSize 大小 / 所在目录 / 打开 / 定位 / 复制路径；
                        文件多于 5 个折叠；文件被移走标「已不存在」）
挂载位置              features/chat/blocks.tsx:1983 DeliveryCards（回合结束后排在回复末尾）
                      redesign/ChatFirstShell.tsx:6486 {!active && <DeliveryCards blocks={msg.blocks} />}
```

**B-1 用户附件/图片**：

```
内容块                 main/providers/types.ts:49-66  image / document（base64）
落盘外置               main/services/media-store.ts:8-13（base64 → {blob} + data/media/<sha256>）、:120-150（载入时读回）
历史展示（贴片）       main/services/chat.ts:479-491  AttachmentChip {name,kind,size,path?,ref?}
                      main/services/chat.ts:819-837  由消息块重建贴片；图片带 ref = "消息下标:块下标:指纹"
取图 IPC               main/services/chat.ts:6286-6300  chat:attachment-image(sessionId, ref, full)
                      （校验下标 + 重算指纹，删轮后不会张冠李戴）
渲染                   store/chat.tsx:249（ChatMessage.attachments）、:685 映射
```

### 2.2 ai_upper / web 入口：B-1 ①，B-2 ②（半接通）

**B-1 已接通**（同一套前端 + Python 服务）：

```
内容块        app/src/mvvm/models/chat_models.py:92-103  ImagePart / DocumentPart（data=base64）
附件→块       app/src/mvvm/services/attachments.py:399-468  build_attachment_part()
              （图片/PDF 内联；文本类内联成 `[附件文件] …` 代码块；其他只给路径）
会话追加      app/src/mvvm/webui/host.py:186-235  chat:send 的 attachments 逐条建块，落在用户消息里
展示消息      app/src/mvvm/webui/bridge.py:541-553  display_messages()：图片贴片 {name,kind,size,ref}
取图          app/src/mvvm/webui/bridge.py:265 → :735-771  attachment_image(session, ref, full)
```

实测（`out/audit-model-path/live-files.log`）：

```
== build_attachment_part(openai) ==
   part type = ImagePart   mediaType = image/png  name = shot.png
   data 前缀 = iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf  长度= 100
== 会话文件 = /tmp/audit-files-home/data/chats/audit-files.json
   第 1 条消息 content[0].type = image
   content[0].data 长度 = 100
== display_messages（渲染层拿到的展示消息）==
    {"role":"user","text":"这张图里的文件能给我吗","attachments":[{"name":"shot.png","kind":"image","size":75,"ref":"0:0:2slEQVR4nG"}]}
    {"role":"assistant","blocks":[{"kind":"text","text":"已生成报告。"},{"kind":"tool","id":"tu_present_1",
      "name":"present_files","args":{"paths":["/tmp/audit-files-home/ws/report.md"]},"status":"ok"}]}
== chat:attachment-image（按 ref 取图）==
   缩略图 = data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA  长度= 122
   错误 ref 是否给图 = None
```

**B-2 只有壳**，三处断点：

```
① 工具本身 OK，但 delivered 没人收
   app/src/mvvm/services/tool_runtime.py:862   return ToolResult(..., delivered=files)
   app/src/mvvm/services/tool_runtime.py:91    delivered: Optional[list[str]] = None
   app/src/mvvm/services/tool_results.py:52    ToolResult 在这里被消费（待办/取消），没有读 delivered
   grep -rn "delivered" app/src → 只有 3 处：ToolResult 定义、上面那次 return、StoredSession 字段
② 会话字段有，但没人写
   app/src/mvvm/models/chat_models.py:176      delivered: Optional[Dict[str, List[str]]] = None
   实测：有没有 delivered 边车 = False
③ 渲染层会调 4 条通道，桥里一条也没有
   app/assets/renderer/shim.js:264-268         deliverables.inspect/thumbnail/open/reveal
   app/src/mvvm/webui/bridge.py: 注册清单里没有 deliverables:*
   实测：
   == deliverables:inspect  registered=False（thumbnail/open/reveal 同）
   == 直接调用 deliverables:inspect（渲染层同一条通道）==
      REJECT:通道未接入：deliverables:inspect
```

于是 web 界面上的表现（截图 `web-deliverables-card.png`）：卡片画出来了、文件行也在，但

- 大小显示 **`0 B`**（`DeliverablesCard.tsx:43-49` 的占位逻辑给了 `size: 0`，真实值要 inspect 才有）；
- 缩略图回落成通用文件图标；
- 「打开 / 在文件夹中显示」点了没反应（通道 reject）。

### 2.3 ai_upper / QML 入口：③ 完全缺失

```
正文拼装   app/src/qml_shell_sessions.py:111-133  transcript_markdown() 只取 message.text()
           （Message.text() 只拼 TextPart，见 chat_models.py:127-131）
发送       app/src/qml_shell.py:475  self._host.send({"sessionId": ..., "text": body})   ← 不带 attachments
附件入口   app/src/qml/Main.qml:437-447  回形针：只有 HoverHandler，没有 MouseArea
交付卡     grep -rn "交付|deliverable|present" app/src/qml/*.qml → 无
```

实测截图 `qml-session-attachment-invisible.png`：那条会话里用户消息只有文字「这张图里的文件能给我吗」，**没有**附件缩略图/贴片；助手的 `present_files` 调用**没有任何卡片**，只剩正文「已生成报告。」。

### 2.4 顺带发现：QML 的会话右键菜单四项全是死的

```
app/src/qml/Main.qml:635-690
  四项 {New chat / Rename / Archive / Delete conversation} 的 delegate 只有 Rectangle + Row + Text，
  没有 MouseArea、没有 onClicked —— 和原版同名的菜单，但一项都点不动。
```

（同一文件 `:267` 的会话行 MouseArea 只处理 onClicked → activate，右键也不弹菜单。）

---

## 3. 与原版对照表

| 功能项 | deva 原版位置 | ai_upper 现状 | 证据 |
| --- | --- | --- | --- |
| 会话导出为 md/json/html/txt | **无**（154 通道无导出；无 showSaveDialog；无导出 UI） | **③ 完全缺失**（web/QML 皆无） | §1.1、§1.4；`registered channels=64` 且无 export/save/md |
| 选择导出路径的流程 | 无 | ③ | 同上 |
| 会话磁盘文件（可手动拷走） | `chat-store.ts:24/251-252`（`data/chats/<id>.json`） | ①（同布局） | 实测 `/tmp/audit-files-home/data/chats/audit-files.json` |
| 图片在落盘里的形态 | `media-store.ts:8-13`：`{blob:<sha256>}` + `data/media/<sha256>` | base64 内联（无 media store） | 实测 `content[0].data 长度=100`；`grep blob app/src` 无 media store |
| 用户附件随消息持久化 | `chat.ts:479-491/819-837`（AttachmentChip + ref） | **①**（web：`host.py:186-235` + `bridge.py:541-553`）；QML ③ | 实测 display_messages 输出贴片 |
| 历史里按 ref 取缩略图 | `chat.ts:6286-6300` | **①**（`bridge.py:735-771`） | 实测 `data:image/png;base64,…`，错 ref 返回 None |
| 工具产出文件的交付卡 | `deliverables.ts:69-129` + `DeliverablesCard.tsx:51` + `blocks.tsx:1983` | **② 只有壳，未接通**（web）；QML ③ | 实测卡片渲染 `0 B`；`REJECT:通道未接入：deliverables:inspect` |
| 交付文件的打开/定位/复制路径 | `deliverables.ts:108-129` | ②（按钮在、通道无） | 同上 |
| 交付文件安全不变式（只允许交付过的文件） | `deliverables.ts:9-12` | 未实现（无通道） | — |
| 工具产出图片（tool_result.images） | 持久化有（media-store 也会外置）；渲染层未见使用 | ai_upper 存 tool_result 文本，图片未见 | 未验证渲染（见 §6） |

---

## 4. 最小补齐清单（**只列清单，本轮不实现**）

### 4.1 口径 A：会话导出（新功能；原版也没有，所以是加法不是移植）

后端（必做，能独立验证）：
1. 新增 `app/src/mvvm/services/session_export.py`
   - `render_markdown(session) -> str`：标题/时间/角色分段；用户消息的 `image`/`document` 块按需 `![name](data:<mime>;base64,…)` 内联或写到同级 `<name>.media/` 目录并写相对链接（二选一，建议默认内联，体积大时再外置）；
   - 附件贴片以 `- 附件：shot.png（75 B）` 文本行列出；`present_files` 的 tool_use 以 `- 交付：report.md（路径）` 列出（与 B 共用路径来源）；
   - `render_json(session) -> str`：直接 `session.model_dump_json()`（已含 `messages`/`delivered`）。
2. `app/src/mvvm/webui/bridge.py`：新增 `chat:export-session`（参数 `sessionId, format("md"|"json"), targetPath`）；同步更新 `_deferred` 名单（同步写盘，不需要 deferred）。
3. `app/src/mvvm/views/web_shell_window.py`：把「保存对话框」并入现有注入点 `host.attachments.set_file_dialogs(...)`，新增 `save_file` 回调 = `QFileDialog.getSaveFileName(self, "导出对话", "<标题>.md", "Markdown (*.md);;JSON (*.json)")`。
4. QML 侧入口：`app/src/qml_shell.py` 增 `@Slot(str, result=bool) def exportSession(self, session_id)`（内部调 3 的服务 + 保存对话框，Qt 用 `QtQuick.Dialogs.FileDialog` 或 `QtWidgets.QFileDialog`），`app/src/qml/Main.qml:635` 的 ctxMenu 加第五项 `Export conversation…` **并把 delegate 的 `MouseArea/onClicked` 补上**（现有四项都没接）。
5. 测试：`app/tests/test_session_export.py`（md 里含图片 data URI、交付文件行、中文不转义）+ `test_qml_shell.py` 增加槽位存在性断言。

不做也可以接受的最小版本：只加 `chat:export-session`（web 用），QML 侧靠“打开数据目录”代替——但那就不是“选导出路径”。

### 4.2 口径 B-2：交付卡接通（移植缺失，deva 有）

1. `app/src/mvvm/view_models/chat_vm.py` 的工具结果落库处（与 `tool_results.py:52` 同一处理点）：
   - 若 `result.delivered` 非空 → `session.delivered[tool_use_id] = list(result.delivered)`，随后 `store.save(session_id)`（字段已在 `chat_models.py:176`，`save()` 会序列化，无需改模型）。
2. `app/src/mvvm/webui/bridge.py` 注册 4 条通道（新文件 `app/src/mvvm/services/deliverables.py` 承载逻辑更干净）：
   - `deliverables:inspect(sessionId, toolUseId)` → `[{path,name,dir,size,openable}]`；`openable` 用 deva 的 `OPENABLE` 白名单（`deva/.../deliverables.ts:17-34`，脚本类一律 false）；
   - `deliverables:thumbnail(...)` → `QImage(p).scaled(128,128,KeepAspectRatio)` → data URI；失败回落 `QFileIconProvider().icon(QFileInfo(p)).pixmap(64)`；
   - `deliverables:open(...)` → `QDesktopServices.openUrl(QUrl.fromLocalFile(p))`，**仅白名单扩展名**；
   - `deliverables:reveal(...)` → `xdg-open <dir>`（macOS `open -R`，Windows `explorer /select,`）；
   - 参数与顺序必须照 `app/assets/renderer/shim.js:264-268`（`sessionId, toolUseId[, index]`）。
3. 安全：**不要**让 `deliverables:open/reveal` 接受任意路径——路径只从 `session.delivered` 取（等价于 deva 的不变式），并对 `FocusRoot` 之外的文件做只读处理即可（原版没有工作区限制，但也没有任意路径入口）。
4. QML 侧（若要 QML 也有交付卡）：`app/src/qml_shell_sessions.py` 增 `deliverable_rows(messages)`（按 tool_use id 取 `session.delivered`），`app/src/qml_shell.py` 暴露 `@Slot(str, result=list) def deliverables(self, session_id)`、`@Slot(str, str, result=bool) def openDeliverable(self, session_id, tool_use_id)`；`app/src/qml/Main.qml` 在正文底部加一张卡（16px 文件图标 / 名称 / `formatSize` 大小 / 「在文件夹中显示」按钮）。
5. 测试：`app/tests/test_deliverables.py`（inspect 取边车、错 toolUseId 返回空、`open` 拒绝 .py/.sh、缩略图回落不为 None）+ 一张 QML 截图回归。

### 4.3 口径 B-1：QML 入口补附件显示与发送（可选，但用户问的是“聊天记录带文件”）

1. `app/src/qml_shell_sessions.py:111-133`：`transcript_markdown()` 里对 `image` 块输出 `![name](data:<mime>;base64,…)`（`markdown.body` 已有 `image_resolver`，见 `app/src/markdown/document.py:203-213`），对 `document` 输出一行 `- 文档：name（size）`。
2. `app/src/qml_shell.py:475`：`send()` 接受 `attachments` 参数并透传给 `host.send`；`Main.qml:437-447` 的回形针补 `MouseArea` → 调 `shellBridge.pickAttachments()`（新槽，内部用 `AttachmentService.pick_attachments`，对话框由 QML 侧 `QtQuick.Dialogs.FileDialog` 提供）。

---

## 5. 未验证项

1. **deva 实机验证**：本轮对 deva 是**只读代码审计**（没有安装、没有启动 Electron 原版），交付卡与附件贴片的实际渲染是按代码路径确认的，未截图实跑。
2. **`tool_result.images`（工具截图）在 deva 渲染层是否显示**：`media-store` 会持久化，但 `grep "images"` 在 renderer 里只命中附件查看器，未找到消息内渲染逻辑；**未验证**是否有其他路径（如 display 层转换）会显示它们。
3. **`deliverables:thumbnail` 在 Linux 的表现**：deva 代码注释说 Linux 不支持 `createThumbnailFromPath` 会回落文件图标；ai_upper 若照搬需另写 Qt 缩略图实现，实际效果未验证。
4. **导出物里图片体积**：ai_upper 是 base64 内联，一张几 MB 的截图会让 md 膨胀 ~33%，未实测导出体积上界（因为导出功能尚未存在）。
5. **Windows / macOS 的保存对话框与「在文件夹中显示」**：本轮 Linux offscreen，未验证跨平台行为。

---

## 6. 复跑方式

```bash
cd /home/agent/shared_workspace/ai_upper

# B：附件 → 消息块 → 落盘 → display_messages → 按 ref 取图；并检查交付通道是否注册
rm -rf /tmp/audit-files-home && mkdir -p /tmp/audit-files-home
AUDIT_HOME=/tmp/audit-files-home .venv/bin/python out/audit-model-path/verify_files_live.py

# web 入口打开带附件的会话：看附件贴片、交付卡、以及 deliverables:inspect 的拒绝原因
AI_UPPER_HOME=/tmp/audit-files-home DEVA_ASSETS_DIR=$PWD/app/assets \
  AUDIT_HOME=/tmp/audit-files-home .venv/bin/python out/audit-model-path/probe_web_files.py

# QML 入口同一会话（附件与交付卡都不显示）
cd app/src && AI_UPPER_HOME=/tmp/audit-files-home AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 \
  AI_UPPER_QML_SHOT=/tmp/audit-files-home/qml-attachment.png AI_UPPER_QML_PAGE=chat \
  ../../.venv/bin/python -c "from main import main; raise SystemExit(main())"
```

日志：`live-files.log`、`web-files-probe.log`；截图：`web-deliverables-card.png`、`qml-session-attachment-invisible.png`。

---

## 7. 只读保证

```
$ git status --porcelain=v1 > /tmp/gitstatus_round2.txt
$ diff /tmp/gitstatus_after.txt /tmp/gitstatus_round2.txt     # 上一轮审计结束时的快照
（无差异）
```

即：本轮**没有新增任何已跟踪文件的修改**，`out/audit-model-path/` 仍是未跟踪目录（`??`），真实 `~/.ai_upper` 未被访问。

deva 侧零写入的核对（它的工作树在审计前就有既存改动，与本轮无关）：

```
$ cd /home/agent/shared_workspace/deva && git status --porcelain=v1 | wc -l
14                       # 既存：M apps/desktop/src/main/services/git.ts / package.json / pnpm-lock.yaml，?? .dockerignore / apps/web/ …
$ ls -l --time-style=full-iso apps/desktop/src/main/services/git.ts package.json pnpm-lock.yaml .dockerignore
2026-11-12 22:59  .dockerignore
2026-11-13 08:55  apps/desktop/src/main/services/git.ts
2026-11-12 22:50  package.json
2026-11-12 22:50  pnpm-lock.yaml          # 全部早于本次审计（2026-11-15 23:1x 起）
```
