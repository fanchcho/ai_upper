# 自动决策：确认存在并实现

原版用户入口 renderer/src/redesign/TasksPane.tsx:752-755、812-832、917-922；TaskDecisionField.tsx:19-32。主进程 scheduler.ts:154 调 evaluateTaskDecision；task-decision.ts:7-40 校验 purpose=decision/adapter=jev/enabled，threshold 优先任务、其次 provider、默认0.6；decision.ts:70 超时15秒、:153起 POST /v1/systemone。故不是不适用。

移植在编辑任务增加启用/provider/threshold，执行前后台线程请求真实 HTTP，结果回到调度器队列；拒绝/超时写 skipped 且不启动任务会话，允许才执行。配置中途改变或暂停，旧结果丢弃。

scripts/parity/decision_ui.py：真实鼠标键盘修改保存阈值0.7，真实 ThreadingHTTPServer loopback 接收请求，按0.9/0.1/16秒延迟覆盖 allowed/denied/timeout。超时使用生产15秒，没有缩短或替换判定函数。两主题×三态均通过；任务会话仅 allowed 有消息。模型执行响应离线 fixture，决策 HTTP 与调度器没有替身。

out/final-four/decision.json 含6组任务及所有 HTTP 请求；decision-*-*.png 为真实截图；原始 decision.log。

局限：已有 purpose=decision/adapter=jev 配置可选，本轮没有补通用服务商新增表单中的 Jev 类型创建入口；完整新用户配置流程仍未完成。
