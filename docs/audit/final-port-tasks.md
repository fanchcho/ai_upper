# 定时任务入口与调度实证

原版依据：`apps/desktop/src/main/services/tasks.ts` 的 create/update/set-status/delete/run-now；`schedule.ts` 五段 cron、IANA 时区及 DST；`tasks-types.ts` 的独占 session、status/runs；原版任务页对应用户可达入口。

新增 `app/src/qml/ScheduledTasks.qml`，railTasks 打开真实列表，支持创建一次/cron 任务、暂停/恢复、立即运行、查看最近执行结果、打开真实任务对话、删除。`scheduled_tasks.py` 原子写 tasks.json；一秒调度，ChatHost.send 真实运行，监听完成事件记录最多 50 条历史；应用启动即初始化调度，单实例防重复执行。

验证：

```sh
AI_UPPER_HOME=/tmp/ai-upper-tasks-ui QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
.venv/bin/python scripts/parity/final_port/tasks_ui.py
```

结果：`PASS real create/pause/resume/automatic timer/host turn/persisted history/open/delete in both themes`。

证据 `out/final-port/tasks-ui.json`：两主题真实鼠标/键盘填写，在真实时钟到期后自动发起 ChatHost 回合，任务记录和对话用户/助手消息写入隔离的 /tmp home，点击打开对话和删除后再次读盘。模型响应使用现有离线 transport fixture；它只证明调度到真实宿主和落盘链路，不代表已验证任何在线模型供应商。暗亮截图 `out/final-port/tasks-dark.png` / `tasks-light.png`。

仍未实现原版的完整任务详情编辑、主对话交接与远程推送。本项完成的是用户要求优先补齐的任务入口、创建/启停/删除及真实调度，不能把整个任务子系统记成全部等价。

兼容层复核：控制器改为 QApplication 创建后再构建真实 QObject，模块导入不再依赖原生 Qt 类求值；不使用空 Signal/Slot 替身。无效时区明确拒绝，Python 3.8 仅 UTC 可用，不静默回退本地时区。tasks_ui 暗亮真实交互再次 PASS。
