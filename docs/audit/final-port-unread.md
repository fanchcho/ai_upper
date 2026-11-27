# 未读与待处理状态复核

原版 store/chat.tsx:308-315 定义 unread/attention，Rail.tsx:1124-1155 用两者决定非当前、非归档行的红点。

独立复核 dfd6c05 后发现两个缺口：后台宿主事件（没有 _turn_session）虽然加入 _unread，却返回 False，不触发 QML 发布；attention 未接。现已修复背景完成事件发布，并从真实 Interactions.pending 取得待处理状态，ThreadRow 显示 unread 或 attention。

真实交互证据：
`AI_UPPER_HOME=/tmp/ai-upper-attention QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/final_port/unread_attention.py`

结果：`PASS actual pending request, click/read/answer, background host completion and published unread`。真实 request 写待处理文件，QTest 点击会话，回答后写盘读回 yes，等待红点状态清除；直接 ChatHost 发起另一会话的后台回合，确认完成后 QML sessions 属性获得 unread=true。输出 out/final-port/unread-attention.json，暗亮截图 attention-dark.png / attention-light.png。
