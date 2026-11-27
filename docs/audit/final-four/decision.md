# 自动决策：用户能力存在，配置与执行路径验证

原版根 `/home/agent/shared_workspace/deva/apps/desktop/src/`，只读。
- renderer/src/redesign/TasksPane.tsx:752-755、812-832、917-922；TaskDecisionField.tsx:19-32：用户任务自动决策开关/provider/threshold。
- renderer/src/features/settings/ModelSettings.tsx:381：新增 decision 服务商；:613 默认 threshold 输入。
- main/services/scheduler.ts:154 fireOnce → task-decision.ts:7-40 evaluateTaskDecision → decision.ts:70（15秒）、:153（POST /v1/systemone）。手动立即运行同样经过 gate。
- main/services/tasks.ts:405 applyRunResult：拒绝消费触发；超时/错误计失败；once 错误不重试，周期累计5次停止。手动执行不更改下次计划。

因此该能力不是“不适用”。移植的任务页提供决策服务商配置弹窗：新增/编辑名称、HTTP服务地址、密钥、默认阈值、启用状态与删除；任务详情选择 provider/threshold。普通对话模型列表继续只显示文本模型，决策服务商在独立入口管理。

生产执行前请求 Jev HTTP；允许才执行，拒绝不执行，15秒超时写 error（lastDecision=timeout）；等待期间任务改变则丢弃旧决策并记 aborted。立即运行也消费 gate，拒绝后保留原 nextRunAt。

验证：scripts/parity/decision_ui.py 两主题真实键鼠从空配置创建 provider（密钥经 SecretsVault）并读 config.json，设置默认0.65/任务覆盖0.7。真实 loopback HTTP 返回0.9允许/0.1拒绝/16秒延迟，生产15秒超时不替换。6组均通过，只有允许态创建模型消息。decision-final.log；out/final-four/decision.json 含HTTP请求、任务读盘与状态。decision_manual_ui.py 两主题真实点“立即运行”，拒绝后没有模型消息且 nextRunAt 不变；decision-manual.log。

暗亮截图：out/final-four/decision-provider-*.png、decision-*-{allowed,denied,timeout}.png、decision-manual-*.png。

证据边界：服务端为可控 loopback 协议 fixture，验证的是实际 HTTP、超时及执行门控；不是商业 Jev 账号的在线服务验收。外部 Jev 可用性未验证。任务文本模型也为离线响应。

并发外部提交00fa741收录了本执行尚在验证的配置与消费逻辑修改；保留、不冒领其 Git 操作。首批门控实现提交012dfb1由本执行推送，本报告记录后续独立复核结果。
