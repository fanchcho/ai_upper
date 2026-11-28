# 手机计划、挂载与现有授权交互

原版依据：`deva/apps/desktop/src/main/services/remote/web/adapter.ts:193-194,451-469` action；`remote/hub.ts:1274-1313` 问答、计划 approve/keep/ignore、挂载跳过；`shared/remote-views.ts:8-11,59-80` 动作与卡片；`workspace-mount.ts:20-42,47-94` 与 `agent-loop.ts:1218-1231` 的真实 mount_workspace 工具。原版手机挂载仅能传 null 跳过，不能把手机路径当电脑目录。

实现 `phone_cards.py`：同一个持久化 Interactions 服务供桌面/手机应答；请求须在机器人会话范围内且仍 pending；重复、过期、错类型与越界都拒绝。正在等待的计划、挂载及提问通过存储轮询发布，手机重连可重新读取。手机对话启用 mount_workspace 工具，跳过后本运行时不重复弹出；不中断工具回合、不伪造授权。

说明：原版当前交互式文件工具是零审批策略（`main/services/tools.ts`，本地对照 `tool_policy.py` 的已有说明）；ai_upper 已有额外 approvalEnabled 宿主授权。这里将其 approved/denied 也映射到同一手机界面，不声称这是原版新增权限协议。

真实执行：
```
AI_UPPER_HOME=/tmp/ai-upper-cards-run QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/phone_extended_evidence.py cards
```
LAN/relay × 暗亮四组键鼠点击：mount_workspace → 暂不挂载；exit_plan → 批准；write_file → 允许，真实写出 APPROVED_WRITE；第二次 write_file → 拒绝，文件不存在，工具结果为审批未通过。调用均由本机 HTTP 模型 fixture 发出，真实 ChatHost/工具执行。`cards/cards-{theme}-{via}.json` 为重开文件读取的四种交互决定、plans 边车及完整工具结果。`cards/phone-browser-{skipped,approve,approved,denied}-{theme}-{via}.png` 为点击前真实卡片；最终回复截图无待决卡。`cards/run.log` 原始运行结果。

新增安全测试验证会话越界与重放拒绝：2 passed（含既有 scope 测试）。本机 fixture，不是外部模型/真机/公网成功。先前真实键鼠覆盖批准、挂载跳过、执行允许/拒绝。恢复核验补齐 keep/ignore，两者分别在 cards-keep 与 cards-ignore 目录保留 LAN/relay × 暗亮的真实鼠标选择、plans 与交互存储读回、宿主工具结果及截图。问答不是本轮新增交互验收项。

远端复核：该项提交 `b3885d0470fd1ce8207acd4aee6297ca98a72559` 已包含在 `origin/develop` 的 `6c62ff9891c2b8dd0b5036fbf2608677a1331c68` 祖先链中，未重写。
