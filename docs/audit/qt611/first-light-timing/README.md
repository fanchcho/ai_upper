# 第一轮亮色：截图时点偏晚，不能作为 preedit 截图

本目录完整保留第一轮亮色日志、会话与截图。该轮真实 fcitx preedit/commit 和消息读盘均通过，但固定定时器拍摄 light-preedit.png 时，文字已经被 fcitx 提交为“你好”。因此这张图只证明提交后的文字，不能据其文件名宣称 preedit 截图通过。

随后将截图改为随真实 preeditTextChanged 状态触发，仅补跑亮色。最终可验收的亮色 preedit 图、会话与 D-Bus 日志在上一级目录。暗色无需补跑。
