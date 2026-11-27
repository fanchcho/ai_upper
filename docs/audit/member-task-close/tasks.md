# 任务编辑与交接

原版 tasks-types.ts:TaskUpdateInput/TaskSchedule/TaskAuthorization，handoff.ts:deliver_result，chat-task-handoff.ts:commitHandoffs，scheduler.ts:notify。

已接标题/内容/单次与 cron/时间与时区/角色与模型/启用/主对话绑定编辑，运行中拒绝编辑。真实定时回合提供 deliver_result，每轮至多一次；false 在结束后把最终回复原文写回，不起主回合；true 在主会话空闲后发交接消息并启动真实主回合。未交接的绑定任务不发通知。待交接记录在 tasks.json，重启可继续处理。

Telegram 远程通知接到现有 scope、users、密钥和真实 API；没有凭据不联网、不声称成功，返回 unverified 原因。飞书/Web 仍未接入。模型驱动 decision 服务尚未接入，update 对 enabled decision 显式拒绝，不能声称全部原版字段都可用。

scripts/parity/task_handoff_ui.py：两主题 × 告知/唤醒，真实鼠标编辑、键盘选择、逐字段读盘、等待 8 秒真实定时器，真实宿主和 deliver_result 工具。模型响应为离线 SSE，仅替换网络输入；工具和宿主没有替身。重新打开存储验证结果；告知主模型请求 0 次，唤醒 1 次。out/member-task-close/tasks.json、task-edit-*.png、task-result-*.png；原始 tasks-ui.log。
