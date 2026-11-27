# 成员工具原版逐项依据

原版工具不经过 preload；由主回合工具表提供。主进程定义 members.ts:371 mainMemberTools，执行 chat-members-core.ts:742 runMainMemberTool；成员工具执行 chat-members-core.ts:784 runMemberTool。preload 唯一成员专用管理 IPC 为 index.ts:862 chat:remove-member，主进程 chat.ts:716，不能虚构 member_list/member_update IPC。

| 工具 | 原版定义 | 本轮状态 |
|---|---|---|
|create_member|main/services/members.ts:374|已接；模型自建后分派实证见 members.log|
|member_send|同文件:400|已有实现；补 report_to_me 支持|
|member_stop|同文件:427|接真实宿主 abort|
|member_status|同文件:436|返回列表、忙碌、当前任务与最近结果；没有另造 list/update 工具|
|read_main|同文件:451|成员会话中提供正文分页读取|
|report_to_main|同文件:473|成员回合结束后排队唤醒主会话|
|reply_task|同文件:500|未完成：当前不支持成员忙碌时插入多个独立任务，不能假装实现提前交单项|
|chat:remove-member|preload/index.ts:862 → main/services/chat.ts:716|原版存在，本轮尚未补可达 UI|

新建成员候选按 shared/mention.ts 与 chat-members-core.ts:1134 补入。pick_folder 仍明确报未接入，未声称工具全集完全等价。
