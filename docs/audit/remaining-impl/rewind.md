# 回滚与技能指令实现

原版依据：Composer.tsx:382 起候选集合与技能过滤；chat.ts:813/823/839/931 列表、预览、应用及撤销；checkpoints.ts:209/454/564/598 文件记录、计划和恢复。

本轮实现真实工具写入前快照（write_file/edit_file）、命令不可撤销提示、宿主列表/预览/应用/撤销、三种回滚模式、外部修改与链接检查。冲突直接拒绝整次操作，不覆盖外部内容。快照在隔离应用 home/data/rewind 中持久化，撤销快照在当前宿主内存中。候选集合包含 compact/rewind，随后启用且允许当前角色的技能，按小写名称去重；技能选中后插入输入框，提交时真实宿主加载正文。

验证脚本 scripts/parity/rewind_interaction.py 使用真实 QML QTest 键鼠，真实 ToolRuntime 写文件、真实 ChatHost 回滚和磁盘读回，暗亮均通过 BEFORE → AFTER → BEFORE → AFTER；外部修改 EXTERNAL 后拒绝回滚且内容保持。技能选择提交后重新打开 ChatSessionStore 读回 SKILL_EXECUTION_MARKER。模型网络响应为离线 fixture，工具、宿主及存储均未替换。证据 out/remaining-impl/rewind.json，日志 rewind-ui.log；截图 rewind-{dark,light}.png、rewind-conflict-{dark,light}.png、skill-{dark,light}.png。

局限必须保留：没有移植原版 blob 的 100 轮保留/GC，以及逐文件强制覆盖选项；目前采用有冲突整次拒绝。大量回合的列表尚未做滚动布局。故不能声称原版回滚所有细节完全等价。成员和任务交接本轮未交付。
