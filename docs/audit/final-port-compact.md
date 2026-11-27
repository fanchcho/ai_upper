# 指令候选与手动压缩真实验证

复核 68abc0a 后发现原测试把 ChatHost.compact 替换为记录函数，且菜单因父级坐标错误画在屏外，不能据此宣称完整可用。

修复候选菜单父级后，执行：
`AI_UPPER_HOME=/tmp/ai-upper-compact-ui QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/final_port/compact_ui.py`

真实 QML 鼠标选择 /compact → 未替换的 ChatHost.compact → 真正压缩服务 → 保存摘要与分段历史；新建 ChatSessionStore 从磁盘重新载入确认 COMPACT_MARKER。模型输出使用离线 transport fixture，只隔离在线供应商，不替换指令处理函数或存储。暗亮截图 out/final-port/compact-dark.png / compact-light.png，数据 compact-ui.json。

结果 `PASS real click -> unmodified ChatHost.compact -> persisted compaction summary; model transport fixture only`。/rewind 与技能命令集合仍未补齐，F13 组合项继续标未移植，不把 /compact 子集充当完整命令系统。
