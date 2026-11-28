# 收尾复核（回归前已落盘）

起点HEAD=origin/develop=f36a99a922224c243c5cf0e3a17823a4e18d0059，status空。应用代码已全部推送，无残留需处置。应用与8b966b6相比无改动；本轮仅文档、证据索引与回归日志。

| 已验收交互 | 暗/亮截图 | 读回JSON与结果 |
|---|---|---|
| 未合并分支二次确认 | force-dark-confirm.png / force-light-confirm.png | force-dark.json / force-light.json：1提交；取消后unmerged仍在、确认后空 |
| 远程删除成功/失败 | remote-dark-confirm.png / remote-light-confirm.png；remote-dark-failure.png / remote-light-failure.png | remote-dark.json / remote-light.json：真实bare remote refs/heads/remote-delete存在→空；失败原文does not appear to be a git repository |
| 冲突与中止 | merge-dark-conflict.png / merge-light-conflict.png | merge-dark.json / merge-light.json：冲突文件a、status空、MERGE_HEAD退出128 |
| 缺身份下拉 | identity-dark-missing.png / identity-light-missing.png；identity-dark-scope.png / identity-light-scope.png | identity-dark.json / identity-light.json：scope=1；/tmp隔离全局配置读回Scope User及邮箱；commit=identity verified |
| AI请求与停止 | ai-dark-running.png / ai-light-running.png；ai-dark-stopped.png / ai-light-stopped.png | ai-dark.json / ai-light.json：真实HTTP /v1/messages含diff；停止后pending=0、workers_after_stop=[] |

以上路径均相对此目录。逐文件大小/SHA256/是否已跟踪见closeout-manifest.json；本轮只读取和核对既有证据，不重新生成交互。AI仅本机阻塞HTTP端点，未返回模型结果；不算外部模型成功。

既有提交及逐次远端回读见PUSHES.txt：dcae462入口证据、9b57100强制删除、62d93ef远程错误、4729c55冲突中止、9b14f47身份下拉、8b966b6生成取消、59cdb28尺寸表。f36a99a既有报告和回归也已远端确认。

既有pytest-final.log结果1486 passed / 9 skipped / 0 failed、560.64秒。本轮按要求重新跑冻结应用代码，另存pytest-closeout.log与pytest-closeout-result.json；不覆盖既有日志。两次中断边界分别见pytest-interrupted-143.log和interruption-429-note.md，429原始服务日志未提供，不能伪造。

未完成：菜单自适应宽度；筛选框严格样式；字体行盒DOM量取；冲突Toast完整外观；原版Electron同状态同DPR像素对照（无macOS宿主）；真实外部模型返回。浅色warning按原版2.494:1保留。历史段错误与首次SIGTERM仍未归因。

本轮最终提交与push输出在closeout-push.log、closeout-remote.txt及用户最终回执；文件在提交后生成，避免递归自引用。最终测试结果完成后追加。

本轮最终全量：1486 passed, 9 skipped in 557.75s (0:09:17)，退出0；外层耗时558.56秒。运行起点f36a99a，AI_UPPER_HOME=/tmp/ai-upper-closeout-51c9ly4b。没有应用代码变更，没有改断言/依赖/token，未复现段错误；不据此宣称历史崩溃已修复。
