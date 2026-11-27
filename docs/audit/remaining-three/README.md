# 本轮三项补齐证据入口

任务范围按最新请求：定时任务的 member_send/member_stop 回退、飞书入站/配置、Web 安全配对/订阅/前台抑制。89 项已验收盘点不重做。

- checklist.md：逐条要求、已实现与未验证/未完成边界。
- task.md + task.log + assets/task-*：真实工具回退、停止与空回答、会话/任务读盘和暗亮截图。
- feishu.md + feishu.log + assets/feishu-*：配置保存及真实平台拒绝原文、配对码入口和暗亮截图。
- web.md + browser.json/browser.log + web.log + assets/browser-*/web-*：实际浏览器安全配对、重连、前后台、撤销和订阅 API 失败；协议订阅样本明确标注。
- publish.md + push-*.log：本执行各项提交的原始 push 输出及紧随的远端 SHA。
- evidence-manifest.json：19 个持久化证据文件大小和 SHA256。
- external-changes.json + external-working-tree.patch：外部提交与未提交改动。保留，不冒领，不随本执行证据提交主盘点表差异。
- regression-snapshot.json：最后一次全量回归固定的源码。最终结果 full-final.log：1461 passed / 9 skipped / 0 failed，461.85秒。

验证运行均以 AI_UPPER_HOME=/tmp/... 隔离。QML 交互程序使用实际 QTest 鼠标/键盘事件和应用宿主；模型回复采用明确标注的协议 fixture，不代表真实外部模型自主决策。SecretsVault 使用其实际文件后端保存测试数据；本轮不宣称重新验收系统 Secret Service。浏览器实际调用 PushManager，不替换为成功回调。

原始第一轮回归 full.log 的失败（Qt 直接导入）保留，修正为兼容层导入后另跑固定源码全量；d0b4445 的中间回归因任务语义补充主动中断，未计作一次通过。最终不以静态接线或源码定位替代交互结果。
