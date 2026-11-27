# 回滚保留与逐文件覆盖

原版 checkpoints.ts:282 enforceCap 保留有原内容快照的最近 100 轮；:564 applyFiles 逐文件跳过/强制冲突；:598 undoFiles 只撤销未再次修改的文件。

本实现仍用 inline base64 journal，释放 pre/post 后原子重写即回收字节，不额外复制 blob 目录。最近 100 个持有原内容的轮保留，超出及超过 30 天的 payload 释放、元信息保留并标 blob_missing。强制路径只允许预览中已有冲突文件；链接、缺快照、超限不可强制。应用和撤销均逐文件处理，返回 skipped。大量回合使用 Flickable 与滚动条。

scripts/parity/rewind_retention_ui.py：真实写入 105 轮验证持有 100、释放 5；键鼠勾选冲突文件并覆盖、撤销恢复外部内容；两主题截图 rewind-force-*.png。另建 150 轮窗口通过真实滚轮滚动验证并截图 rewind-scroll-*.png。证据 out/member-task-close/rewind.json 与 rewind-ui.log。

外部提交 ba0debf/674ecd8 已包含本执行对 qml_shell.py 的四参数 rewind 槽变更；不回退外部提交，当前实现提交仅包含剩余回滚文件，特此记录，不能冒领外部提交。
