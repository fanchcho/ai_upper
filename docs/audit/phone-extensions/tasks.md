# 手机任务列表、详情与操作

原版依据：`deva/apps/desktop/src/main/services/remote/web/tasks.ts:9-87`（手机第一版只看不改，列表按 active/error/paused/completed 排序，详情含日程、运行记录、角色/模型、主会话与任务会话）；`remote/web/adapter.ts:180-183,232-234,656` 的 tasks 推送与 task 操作。

移植 `phone_tasks.py`，复用真实 ScheduledTasks 服务与 tasks.json，支持暂停、恢复、立即运行、删除和查看任务对话。已完成一次性任务拒绝恢复，重复运行返回正在运行；任务详情状态变化通过现有连接刷新。原版手机无创建/字段编辑，不额外制造。

执行：
```
AI_UPPER_HOME=/tmp/ai-upper-tasks-run QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/phone_extended_evidence.py tasks
```
四组 LAN/relay × 暗亮：真实浏览器鼠标打开任务详情 → 暂停 → 恢复 → 立即运行 → 查看任务对话 → 删除。ChatHost 真实调用本机模型 HTTP fixture，任务对话有 TASK_REAL_HOST 和 LOCAL_MODEL_REPLY；重新打开 ChatSessionStore 读回任务回合，同时读取 tasks.json 验证 paused/active/runs 和最终删除。`tasks/tasks-{theme}-{via}.json` 保存状态变化与读盘结果，`tasks/phone-browser-tasks-{theme}-{via}.png` 详情截图，`tasks/run.log` 原始结果。新增完成任务恢复拒绝与非法动作测试，结合卡片/范围测试为 3 passed。

只证明本机端点与真实宿主闭环，不是公网、真机或外部模型/推送成功。运行期间删除仍遵循宿主现有拒绝规则，不中断正在执行的任务。
