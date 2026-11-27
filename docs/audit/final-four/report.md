# 本轮四项实现与验证记录

本轮不重做89项盘点，不回退09de966/9e5c29d/a7ee565/649f93f。deva只读；应用和测试的AI_UPPER_HOME均使用/tmp隔离目录，辅助副本/临时脚本目录为仓库.tmp。本轮没有修改依赖pin、既有测试文件或断言，没有force push或建分支/tag。

## 逐项交付

| 项目 | 本执行提交 | 真实验证 | 限制 |
|---|---|---|---|
|成员工具与新建候选|5e98ccf、52db4ec、bd9b463|七工具实际执行；键鼠选新建候选/移除/目录；新开ChatSessionStore核对members、parentId、分派与回复；同名/目录规则真实磁盘验证|外部模型自主建人未验证；member_send/member_stop转发定时任务未完成。41cbfeb由外部执行提交，不冒领。|
|启动独立GC|e71e03c|启动真实app/src/main.py子进程，106条元信息保留，7条快照payload释放；不调用GC替身、不等待下一次工具写入|沿用已验收inline journal布局，不声称与原版blob目录布局相同。|
|自动决策provider/threshold|012dfb1、634db76|暗亮键鼠配置provider与阈值，读config；真实loopback HTTP允许/拒绝/15秒超时；只有允许执行任务；立即运行拒绝后保留nextRunAt|原版确有用户能力，非不适用。外部Jev服务未验证。00fa741由外部执行提交，不冒领。|
|外部推送|5f17215、c105390|Feishu/Web生产出站路径，真实无凭据错误；Web负载独立解密和密钥写盘读回|完整配对/订阅入口和飞书入站未完成；外部送达未验证。不得把queued、保存配置、加解密成功当送达。|

逐个push原始输出与紧随的远端行：pushes.md。第0步原始git输出、残留处置、外部提交：baseline.md。各项原版文件:行号、调用链、验证命令与证据边界：member-inventory.md、gc.md、decision.md、channels.md。

## 可复现命令

所有UI脚本使用真实QML窗口、QTest键鼠事件和grabWindow；离线模型协议fixture被明确标注，不作在线模型自主能力证据。

```sh
AI_UPPER_HOME=/tmp/ai-upper-members QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" .venv/bin/python scripts/parity/member_creation_ui.py
AI_UPPER_HOME=/tmp/ai-upper-member-tools QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" .venv/bin/python scripts/parity/member_tools_ui.py
AI_UPPER_HOME=/tmp/ai-upper-member-folder QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" .venv/bin/python scripts/parity/member_folder_ui.py
AI_UPPER_HOME=/tmp/ai-upper-gc QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" .venv/bin/python scripts/parity/startup_gc_evidence.py
AI_UPPER_HOME=/tmp/ai-upper-decision QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" .venv/bin/python scripts/parity/decision_ui.py
AI_UPPER_HOME=/tmp/ai-upper-decision-manual QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" .venv/bin/python scripts/parity/decision_manual_ui.py
AI_UPPER_HOME=/tmp/ai-upper-webpush DEVA_SECRETS_BACKEND=file .venv/bin/python scripts/parity/webpush_payload_evidence.py
AI_UPPER_HOME=/tmp/ai-upper-no-model DEVA_SECRETS_BACKEND=file .venv/bin/python scripts/parity/missing_model_evidence.py
```

UI/读盘JSON共27文件，ui-evidence.zip；artifacts.json记录SHA256。外部操作可能再次修改共享out目录，以包内文件及manifest为固定证据。

## 回归

最终回归：**1457 passed / 9 skipped / 0 failed，451.26秒**。SHA为bd9b463，见regression-sha.txt；完整原始输出regression-final.log。使用git archive固定源码副本，避免外部并发改动污染：

```sh
AI_UPPER_HOME=/tmp/ai-upper-final-four-bd9b463-regression \
TMPDIR=/home/agent/shared_workspace/ai_upper/.tmp/final-four \
LD_LIBRARY_PATH=/home/agent/shared_workspace/ai_upper/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-final-four-bd9b463-tests
```

工作目录：仓库 `.tmp/final-four/verified-final`。后续生产源文件与该SHA比较无差异时，才适用本次结果。

首批5f17215源码完整运行：1457 passed / 9 skipped / 0 failed，full.log。634db76运行因后续成员语义修正主动中止，regression-634db76-interrupted.log不算成功结果。

独立导入测试本轮实际结果为1 passed，import-alone.log；基线外部98b5f69已修改其fixture，本轮没有修改断言，不将其旧修改冒领为新修复。

## 未完成 / 未验证 / 未归零

1. **未完成**：成员工具作用于“定时任务名单”的回退分派路径（原版chat-members-core.ts:766-775）。七个工具正常成员分支已验证，不等于所有跨功能分支等价。
2. **未验证**：真实外部模型自行决定create_member再派单。真实宿主无配置返回：`Not configured yetAvailable models (select a default model in settings): Please go to the settings page to fill in the service address, model and API key`（missing-model.log）。现有fixture证明宿主执行与落盘，不证明在线模型自主性。
3. **未完成**：飞书入站长连接/配对配置入口、Web安全配对与浏览器订阅入口、连接前台状态抑制。**未验证**：飞书/Web实际送达，原始原因分别为“飞书 App ID 或 App Secret 未配置”“Web Push 浏览器订阅不存在；未完成配对”。外部Jev账号成功态也未验证。
4. 按用户要求不重试：托盘/通知成功态仍`isSystemTrayAvailable=False`；Windows/macOS系统代理缺对应宿主，未验证；正文与阴影栅格/合成残差未归零，未改token/未加坐标补偿。Telegram真实账号配对收发不重试。
5. 外部41cbfeb与00fa741、盘点文件残留保留，独立记录于baseline.md/external-residual.diff；不声称这些是本执行发出的commit/push。
