# QML 壳接真实数据与真实发送
改动：`app/src/qml_shell_sessions.py`（新，纯 Python：`session_rows` 从 `ChatSessionStore.visible_sessions()` 出列表行、`transcript_markdown` 按落盘顺序拼正文、`TurnState` 追加流式增量）、`app/src/qml_shell.py`（去假数据，接 `build_chat_host`；`ShellBridge` 的 attach/openSession/send + 队列 `tick()`，回合线程事件只在 GUI 线程落界面）、`app/src/qml/Main.qml`（列表绑真实 model、正文 Flickable 自动贴底、TextArea Enter 发送/Shift+Enter 换行、双空状态）、`app/tests/test_qml_shell.py`（新，27 例：列表/正文/状态机纯函数 + `ScriptedTransport` 驱动的真实 `ChatHost` 往返与落盘）。
- 真实数据：`out/qml-shell/seed_home.py` 用现有服务层灌 3 条会话（已实跑输出 `sessions: ['qml-real-1','qml-real-2','qml-real-3']`）；截图 `/home/agent/shared_workspace/py_upper/out/qml-shell/shot-real.png`（含 python 代码块 + 三行表格，`sessions=3`）
- 空状态：`/home/agent/shared_workspace/py_upper/out/qml-shell/shot-empty.png`（中列「还没有会话／发一条消息就会出现在这里」+ 正文「这里还没有任何对话」，`sessions=0`）
- 真实往返（走真实 provider，不是 FakeProvider）：本机 `ANTHROPIC_BASE_URL` → `127.0.0.1:6060` 的 Claude Code 代理，`adapter=anthropic`、`model=deepseek-v4.1-flash`、密钥经 `SecretsVault(backend=file)`；原始日志 `out/qml-shell/run2.log`
  - `QML SEND {"sessionId": "qml-mwhcd1m51451d9", "text": "只说三个字：收到。"}` → `QML TURN 0fc449b2c468423c8d966cf319297c7f` → `QML STREAM {"text": "收到"}` / `QML STREAM {"text": "。"}` → `QML TURN DONE {"stopReason": "end_turn", "deltas": 2}`
  - 落盘：`home-empty/data/chats/qml-mwhcd1m51451d9.json` 内 `user: 只说三个字：收到。` / `assistant: 收到。`（重开仍可读回，`title` 已由 ViewModel 写好）
- 原始输出（run2.log 内三次 `QML OK`，EXIT 全 0）：`QML OK platform=offscreen ... plain=False turn_stop='end_turn' deltas=2 ... png=out/qml-shell/shot-turn.png size=1280x820`
- pytest（`app/` 下 `python -m pytest tests -q -ra --tb=long`，未删用例、未改跳过原因）：**1150 passed, 5 skipped**（基线 1123 passed / 5 skipped，新增 27 例），EXIT 0
