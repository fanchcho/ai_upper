# 成员工具逐项复核

参考根目录 `/home/agent/shared_workspace/deva/apps/desktop/src/`，始终只读。

原版工具由主进程模型工具表提供，不是 preload IPC。`main/services/members.ts:371` 定义 mainMemberTools；`chat-members-core.ts:742` mainMemberTool 执行；`:784` memberSideTool 执行。preload 的成员专用管理桥为 `preload/index.ts:862` chat:remove-member → `main/services/chat.ts:716`。没有独立 member_list/member_update 工具，不新增虚构工具。

|工具/入口|原版定义|移植实现与验证|
|---|---|---|
|create_member|main/services/members.ts:374|members.py create/install；无预建成员，模型协议请求实际调用后生成主名单、独立成员会话和 parentId。支持 folder、pick_folder；目录选择真实 Qt FolderDialog 后重新开存储核对 focusRoot。|
|member_send|同文件:400|同文件 send；task/message/report_to_me；忙碌时插入工作线程，在下一次模型请求前写盘；openTasks 记录各项。|
|member_stop|同文件:427|真实 ChatHost.abort；验证 C 任务被停止而未输出 SHOULD_ABORT。|
|member_status|同文件:436|真实会话读出成员状态、任务与结论；模型调用结果落盘。|
|read_main|同文件:451|成员侧读取主对话；支持 before/round/offset。|
|report_to_main|同文件:473|成员结束排队唤醒主回合；实测 FINAL_A → SUMMARY_A。|
|reply_task|同文件:500；chat-members-core.ts:968|成员忙碌期间收到 B，提前交 EARLY_B，再完成 A；只允许已送达、未交回的任务，剩一项拒绝提前交。|
|移除成员|preload/index.ts:862 → main/services/chat.ts:716|后台列表真实鼠标点击移除；重新打开存储核对 removedAt，独立成员会话保留。|
|新建成员候选|shared/mention.ts；chat-members-core.ts:1134|members.log 与 members.json：键盘输入 @新建 → 鼠标选中 → create_member → member_send → 重新打开主/子存储。|

`member-tools-final.log`/`out/final-four/member-tools.json`：两主题均经过真实 QML 键鼠事件、生产宿主与七种工具。`member-folder.log`/`out/final-four/member-folder.json`：真实目录选择窗口中键盘导航、鼠标选目录和 Open，工具恢复后重新打开存储验证。截图为 out/final-four/member-{candidate,result,tools,remove,folder-prompt,folder-picker}-{dark,light}.png。

证据边界：模型响应使用明确标识的协议 fixture，用来确定调用序列；没有替换 create_member/member_send、存储或回合执行回调。没有真实外部模型凭据，不能把这些证据称为“真实外部模型自主决定创建成员”。该外部模型自主场景仍未验证。环境键存在性检查 ANTHROPIC_API_KEY=False、OPENAI_API_KEY=False；没有读取真实用户目录寻找凭据。

并发：外部执行创建并推送 41cbfeb，收录了本执行尚在验证的七工具/目录/移除代码。本执行保留该提交，单列其来源，不冒领该 Git 操作。后续本执行的目录验证及错误回报修正另外提交。

补充：member-creation-rules.log 验证同名拒绝、相对目录创建、不存在绝对路径拒绝、恢复移除成员并读盘。missing-model.log 是未配置真实宿主的原始错误，不使用模型替身证明在线自主行为。

未完成的原版分支：chat-members-core.ts:766-775 将 member_send/member_stop 作用于名单中的定时任务的回退路径，当前仍只处理真实成员；本轮没有将这条分支标为可用。成员工具名全集已接不等于所有跨功能分支完全等价。
