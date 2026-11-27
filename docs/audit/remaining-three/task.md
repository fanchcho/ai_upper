# 定时任务成员工具回退

原版 apps/desktop/src/main/services/chat-task-handoff-core.ts:247 findOwnedTask、:309 askTask、:362 stopTask、:378 reportTaskAsk；chat-members-core.ts:766-770 的成员优先/任务回退。

实现 members.py owned_task/task_tool：只有 ownerSessionId 相同才可查找；真实成员优先；任务忙碌拒绝；沿用任务会话模型追问，不触发scheduler、不修改日程；停止实际abort当前回合；结果通过主会话队列回写，report_to_me或错误唤醒，停止不唤醒。

scripts/parity/task_fallback_ui.py：暗亮两主题真实键盘输入，经协议fixture产生实际member_send/member_stop调用，宿主任务子回合真实执行；新开ChatSessionStore读主/任务会话，确认TASK_ANSWER回写、停止后无SHOULD_ABORT；tasks.json字节保持不变。模型fixture仅控制工具调用序列，不证明外部模型自主行为。原始task.log，截图与JSON assets/task-*。

基线1e8bf8a为其他执行新增提交，保留；开场工作树干净。没有重做89项盘点。


边界复核补充：任务模型按 auth.modelRef → 全局默认 → 主回合模型解析；追问工具禁止交互，并去除定时执行上轮遗留的 deliver_result。仅本次新消息参与回答，空回复/失败/超限会唤醒主角色，不把历史回复当本次结果。member_stop 停止真实回合后只保存延迟通知，主对话下一轮附带后消费；不自动唤醒、不作为任务回答交付。原版依据 chat-task-handoff-core.ts:309-415。

追加真实键盘回合证明：停止后主会话无“Daily：已停止”回答；下次键盘发送时从重开存储读到延迟说明，队列已清；再转一个空回答任务，宿主原始错误“模型没有返回任何正文”回写并唤醒主回合，历史 Daily：TASK_ANSWER 仅出现一次。tasks.json 全过程字节不变。模型仅使用明确的协议 fixture，不代表外部模型已验证。既有 app/tests 断言未修改。
