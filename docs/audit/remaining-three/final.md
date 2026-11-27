# 本执行交付结论

本轮不重做89项盘点。既有提交保留，无 force push/分支/tag，无依赖 pin 改动。deva 只读；运行隔离 AI_UPPER_HOME=/tmp/...。

| 功能 | 本执行提交 | 已有真实证据 | 保留边界 |
|---|---|---|---|
| member_send/member_stop 回退定时任务 | 9d05ba0 + e85b23d | 暗亮键盘输入 → 实际工具/任务回合 → 重开主/子会话；日程文件不变；停止延迟通知；空回复唤醒，不重播历史 | 模型输出协议 fixture，不声称外部模型自主行为 |
| 飞书配置与入站路径 | b60ae87 + d00e20f | 暗亮鼠标/键盘配置；重开配置及密钥库；真实平台拒绝；生成配对码 | 有效 wss 入站/配对未验证：code=1000040346, msg=app_id is invalid |
| Web 配对、订阅入口、前台抑制 | d0b4445 | 实际浏览器安全配对、刷新重连、前后台、QML移除设备断线/删密钥；订阅按钮实际调用 | 外部订阅/送达未验证：AbortError: Registration failed - push service not available |

Web 初始代码被外部执行提前纳入528be75；该提交保留但不作为本执行提交交付。d0b4445是在其基础上的实际修正和本轮独立验证。外部 d16d472、9a0c65f、c9775ae（Git面板相关）也保留，不纳入本轮功能验收。当前主审计表/若干搜索证据/build_audit.py 外部未提交变化保持不动，见 external-working-tree.patch。

未完成完整渠道适配器：飞书 OAuth 扫码创建应用与卡片双向交互；Web 跨设备 LAN/relay/安装票据。它们不是这次本机配对和配置路径已可验证的部分，不用“接线完成”代替完整移植。

仍未验证/未归零且未重试：系统托盘/通知宿主 isSystemTrayAvailable=False；Windows/macOS系统代理无对应宿主；正文/阴影像素未归零；真实外部模型自主建人无模型配置；真实外部渠道送达缺有效凭据/PushService。

回归结果：**1461 passed / 9 skipped / 0 failed**，461.85秒。源码固定在 e85b23d663d0e6900bbd9d2cc9aecb90a912d51a，原始 full-final.log。第一轮1456 passed / 9 skipped / 1 failed（Qt兼容层导入约束）原文在full.log，已修实现。中间d0b4445快照主动中断，不作为通过结果。


最终回归命令（cwd 是当前仓库 .tmp 内 git archive e85b23d 形成的只读测试快照，未建分支）：

```sh
AI_UPPER_HOME=/tmp/ai-upper-final-remaining-three-e85 \
TMPDIR=/home/agent/shared_workspace/ai_upper/.tmp/remaining-three \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
LD_LIBRARY_PATH=/home/agent/shared_workspace/ai_upper/.tmp/wm/usr/lib/aarch64-linux-gnu \
.venv/bin/python -m pytest app/tests -q \
--basetemp=/home/agent/shared_workspace/ai_upper/.tmp/remaining-three/pytest-e85
```

八个本轮相关生产文件已与提交和测试快照逐字节核对一致。本执行五个功能提交未改 app/tests 中任何文件；总数增加含外部执行已提交的新测试，不将其冒领为本执行新增测试。既有依赖配置无差异。
