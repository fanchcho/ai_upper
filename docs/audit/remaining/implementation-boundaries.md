# 剩余三项的源码定位（未完成，非验收交付）

本轮只完成独立模块导入修复。以下不是平台阻碍，仍是可移植但未完成的开发工作；不得据此标记已补齐。已验收的 89 项盘点文件不改写。

## 指令

原版 Composer.tsx:382 起：compact / rewind 置顶，其后为本角色可用且启用的技能，小写名去重、内建优先。正文中间仅列技能；选择技能替换光标词，不立即执行内建命令。

chat.ts:813/823/839/931 分别提供列表、预览、应用、撤销。checkpoints.ts:209/454/564/598 负责记录写入前字节、制定计划、执行和撤销；冲突、符号/硬链接及真实路径漂移需要跳过。当前 Python ToolCheckpoint 是工具结果防重放日志，不包含文件原字节，不能当作 rewind 文件快照。尚未新增上述实现、UI 或真实交互证据。

## 提及

chat-members.ts:998 起 handleMentions 排除引用行，排除主角色，优先匹配长名字，恢复或创建成员、继承目录；只有提及无请求时不派任务，有请求时通过 member_send。新建成员特殊词还需 create_member。当前 QML 候选插入不具备上述后台语义。尚未新增成员服务和存储验证。

## 定时任务

handoff.ts 的 deliver_result 只在绑定主对话的任务运行轮提供；needs_action=false 时传递最终回复原文、不唤醒主角色，true 时排队并唤醒；未调用表示没有新情况、不通知。chat-task-handoff.ts:commitHandoffs 在主对话空闲时提交。scheduler.ts:notify 通过 publishAppNotice 推远程通道，与系统通知解耦。仅把任务回复复制成普通用户消息不符合原版。完整详情编辑、交接及远程推送尚未补齐。

## 保留受限项

不重新运行托盘、真实 Telegram 账号、Windows/macOS 代理及像素相位实验。沿用 docs/audit/final-port-report.md 的原始未验证/未归零记录。本轮没有宣称受限项成功。
