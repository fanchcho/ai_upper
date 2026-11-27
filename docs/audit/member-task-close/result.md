# 本轮交付与边界

用户已验收的 89 项盘点，本执行未重做。外部执行在 3847b4e 重写了该盘点并收走本轮部分中间证据文件，保留外部提交但不接受其计数为本轮验收。

## 本执行提交

- 09de966499a7e7fb04930d0bc8e8f9c1e9f86cd1：提及角色自动建独立成员、member_send 真工具分派、子回合结束后排队回写主对话；暗亮键鼠、重新打开主/子存储读回通过。
- 9e5c29d8c0ce31068ef6d5d091d449e46bbd5d83：任务常用详情字段编辑、密封定时运行 deliver_result 告知/唤醒、Telegram 远程通知路径；暗亮四组编辑读盘及到时执行通过。
- a7ee565df9ab0b28cae0688a15a6fde1f1c49322：回滚 100 轮快照保留、逐文件跳过/强制覆盖/撤销、150 轮滚动；暗亮真实交互、105 次真实工具写入及双文件边界通过。

原始 git push 输出和对应 ls-remote SHA 在 pushes.txt。每项说明分别 members.md/tasks.md/rewind.md，脚本 scripts/parity/member_dispatch_ui.py、task_handoff_ui.py、rewind_retention_ui.py。截图及机器证据在 out/member-task-close。

## 回归

在 .tmp/member-task-close/verified 的 a7ee565 固定源码快照运行；258 个源码/测试文件逐个比对完全一致（source-manifest.json）。复制既有未跟踪 app/pyproject.toml 配置，复用本机 venv 和 Qt 运行库，无依赖 pin 变化。

```sh
AI_UPPER_HOME=/tmp/ai-upper-member-task-final TMPDIR=/home/agent/shared_workspace/ai_upper/.tmp/member-task-close LD_LIBRARY_PATH=/home/agent/shared_workspace/ai_upper/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-member-task-final-tests
```

```text
1452 passed, 9 skipped in 459.55s (0:07:39)
```

failed=0，exit=0；full.log 是完整原始输出。该结果不认证后来的外部更新下载和盘点提交。

## 未完成/未验证

- 任务 decision 自动决策 provider/threshold 未接，显式拒绝启用；因此不能称全部原版任务详情完整等价。
- 远程通知只有 Telegram 路径，飞书/Web 未实现；无凭据本轮真实返回 unverified/未配置可用的已配对远程渠道，外部成功态未验证。
- 成员服务覆盖提及角色自动创建、create_member/member_send 与结果回写；尚未覆盖原版全部成员管理工具、目录选择交互与特殊“新建成员”候选。未单独验证纯模型自行 create_member（已验证 handleMentions 自动创建）。
- 回滚实现用 inline journal 释放字节，非原版 hash blob 布局；30 天策略在 journal 写入时清理，尚无独立启动扫描闲置会话的 GC。
- 托盘/通知宿主、Telegram 真实账号、Windows/macOS 代理、像素归零不重试，原始未验证/未归零结论保留。

## 外部写入

基线已有 61c8e2d；执行中出现 ba0debf（角色）、674ecd8（模型列表）、355f77c（Git）、6114854（更新）、3847b4e（盘点）。全部保留，不冒领。外部角色/模型提交还收走了本执行 qml_shell.py 的 rewind force 参数槽改动，本轮提交补齐对应服务与 UI；外部盘点提交收走了本轮正在写入的 full.log 等文件，本轮最终提交只完成该日志与本报告。未改既有测试断言。
