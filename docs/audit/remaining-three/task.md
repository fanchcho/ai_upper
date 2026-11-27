# 定时任务成员工具回退

原版 apps/desktop/src/main/services/chat-task-handoff-core.ts:247 findOwnedTask、:309 askTask、:362 stopTask、:378 reportTaskAsk；chat-members-core.ts:766-770 的成员优先/任务回退。

实现 members.py owned_task/task_tool：只有 ownerSessionId 相同才可查找；真实成员优先；任务忙碌拒绝；沿用任务会话模型追问，不触发scheduler、不修改日程；停止实际abort当前回合；结果通过主会话队列回写，report_to_me或错误唤醒，停止不唤醒。

scripts/parity/task_fallback_ui.py：暗亮两主题真实键盘输入，经协议fixture产生实际member_send/member_stop调用，宿主任务子回合真实执行；新开ChatSessionStore读主/任务会话，确认TASK_ANSWER回写、停止后无SHOULD_ABORT；tasks.json字节保持不变。模型fixture仅控制工具调用序列，不证明外部模型自主行为。原始task.log，截图与JSON out/remaining-three/task-*。

基线1e8bf8a为其他执行新增提交，保留；开场工作树干净。没有重做89项盘点。
