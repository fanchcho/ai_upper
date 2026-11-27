# 成员创建与分派

原版 chat-members.ts:998 handleMentions；members.ts:25 上限 10；按引用行排除、角色长名优先、仅点名不自动派任务。有需求时主角色通过真实 member_send 工具分派。create_member 创建独立会话，parentId/角色/工作目录持久化。结果在主会话空闲时回写，待提交的报告写盘。

真实验证：scripts/parity/member_dispatch_ui.py，QTest 键盘 @Rev、鼠标选 Reviewer、粘贴需求、Enter。模型传输仅使用离线 SSE fixture，真实解析 member_send 工具请求、创建子回合、调用宿主与存储。暗亮两套均从重新打开的 ChatSessionStore 读回成员、parentId、MEMBER_JOB、MEMBER_RESULT 与主会话 Reviewer 回复。out/member-task-close/members.json 含完整证据；members-ui.log 为原始日志。

截图 member-candidate-{dark,light}.png 与 member-result-{dark,light}.png。关联宿主/MVVM 测试 35 passed。

基线中的外部提交 61c8e2d 保留。执行中新出现 PersonaRoster、qml_shell.py 与 locales 的外部编辑不纳入此提交。
