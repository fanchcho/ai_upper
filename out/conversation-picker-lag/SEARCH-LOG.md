# 「多对话选择」窗口定位·搜索日志（真实命令与输出）

时间：2026-11-18　仓库：/home/agent/shared_workspace/ai_upper（develop）

## 1. 关键词全仓搜索（排除 .venv/dist/build/runtimes/out/qml-shell/packaged）
```bash
rg -n -i "多对话|多选|多会话|选择对话|选择会话|choose chats|select chats|scopePick|ScopePicker|bots-pick|pickmodal" <repo>
```

```text
./audit-tools/gen_migration_plan.py:310:        "QFileDialog（多选）",
./out/chat-files/REPORT.md:325:4. **多个附件同时选择**：`getOpenFileNames` 的过滤器与多选路径已通过单测替身覆盖，真实对话框只验证了
./out/chat-files/REPORT.md:326:   单选；同一批多选未实跑。
./docs/audit/IPC-158-LEDGER.md:46:| 10 | `fs:pick-attachments` | 无（preload `pickAttachments()`） | `Promise<PickedAttachment[]>` | main/services/attachments.ts:223（handle） | app/src/mvvm/webui/bridge.py:267 | 单测 tests/test_web_attachments.py::test_pick_attachments_matches_original_shape、::test_pick_attachments_requires_a_dialog_and_never_fakes_success | 通过 —— QFileDialog 多选后按 inspect 判定；超限图片走「只给位置」分支；未注入对话框时抛「未接线」不假装取消 |
./docs/MIGRATION-PLAN.md:166:| `fs:pick-attachments` | `main/services/attachments.ts:223` | `services/attachment_service.py::AttachmentService.pick_attachments` | 待定（P2） | QFileDialog（多选） | P1 不做附件 |
./out/audit-model-path/REPORT.md:230:| Add model 面板（输入 + 服务端清单多选 + 全选/清空 + 拉取中/失败提示） | `:604-690` | 无 | 有 |
```

## 2. 候选窗口枚举（源代码层面穷举）

命令：`rg -n "QQuickView|QQmlApplicationEngine|QMainWindow|QDialog" app/src`

结论：应用默认入口只有 **1 个 QML 根窗口**（`app/src/qml/Main.qml:16 ApplicationWindow`），
QML 里的弹层只有 `SettingsModal.qml`、`ModelPicker.qml`、`ctxMenu`、`confirmLayer`
（`Main.qml:961/970/1054/1109`）。Python 侧窗口只有 `about_window.py`（QDialog）、
`chat_window.py` / `main_window.py`（参考实现，非入口）、`deva_main_window.py`（测试装配用）。

命令：`rg -n -i "checkbox|checkable|checked|setSelectionMode|ExtendedSelection|MultiSelection" -g '*.qml' -g '*.py' app scripts audit-tools`

结论：**没有任何多选控件**。唯一的 `QCheckBox` 是设置页「启用该服务商」
（`settings_pane.py:156`），且属于参考实现，不在 QML 壳里。

命令：`rg -n -i "多对话|多选|多会话|选择对话|选择会话" <repo>` → 只命中附件多选
（`fs:pick-attachments` / `QFileDialog.getOpenFileNames`）与文档里的历史记录，
**没有「多对话选择」窗口的实现**。

deva 原版（只读参考）里唯一的会话多选 UI 是 `BotsPane.tsx:749-800 ScopePicker`
（i18n `scopePickTitle.sessions = 'Choose chats'`），而该面板依赖的
`remote:*` 通道在本仓库被明确判为「不迁移」（`docs/MIGRATION-PLAN.md:153`）——
ai_upper 里没有对应实现。

## 3. 用户所指窗口的判定

在本仓库里，唯一承担「在多条对话之间点选切换」的界面是 **左侧会话列表**
（`Main.qml:288-319` ListView + `ThreadRow.qml` 委托），点击行为是 `window.activate(id)`
→ `shellBridge.openSession(id)`（`Main.qml:978-982`）。除此之外没有第二个候选。

## 4. 数据流（点一下到底同步触发了什么）

QML：`Main.qml:316` `onClicked: window.activate(modelData.id)`
→ `Main.qml:978-982` `function activate(id)`：`if (id === activeId) return` 否则
`shellBridge.openSession(id)`（**同步跨语言调用**）。

Python：`qml_shell.py:408-416`
```
def openSession(self, session_id):     # @QtCore.Slot(str, result=bool)
    self._active = ...                 # 1. 换 active
    self._render()                     # 2. _markdown_base() → store.load_session() 读盘
                                       #    → transcript_markdown() 拼整篇 → BodyDocument.set_markdown()
                                       #      → parse_markdown() + render_blocks() 写进 QTextDocument
    self._publish()                    # 3. store.visible_sessions() + session_rows()
                                       #    （**把全部会话逐条 load_sessions** 只为取预览）
                                       #    → window.setProperty("sessions", rows) 整表替换
```

`_publish`（`qml_shell.py:798-821`）每次点击都：
- `self._rows()`（`:783`）→ `store.visible_sessions()`（`chat_session_store.py:591`，
  对每条会话做一次 `session_path(m.id).exists()` 磁盘 stat）
- → `session_rows(store, ...)`（`qml_shell_sessions.py:163`）→ `store.load_sessions(...)`
  → 对每条会话 `load_session` 并 `preview_text()`（`qml_shell_sessions.py:91`）
- → `window.setProperty("sessions", rows)`：整表替换，ListView 全量重建委托。
