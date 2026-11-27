# 飞书入站与配对配置核验

原版依据：`apps/desktop/src/main/services/remote/feishu.ts:74-99` 注册 im.message.receive_v1 与 WSClient；SDK `node_modules/@larksuiteoapi/node-sdk/lib/index.js:102313-102368` 获取 /callback/ws/endpoint，:102579 ping，:102665 事件分片与应答。`services/remote/hub.ts:166-238` 是六位配对码、十分钟有效、错误五次失效及 /pair 入白名单。

已实现：App ID、App Secret、feishu/lark 入口，密钥走 SecretsVault；实际 HTTP 发现、wss 连接、protobuf 帧、ping、分片、去重、应答、断线重连；p2p 文本入站和 /pair 白名单保存。停用作废待配对码并停连接；重连对象不会被错误状态丢弃。Qt 导入统一走既有兼容层。

真实交互脚本 scripts/parity/feishu_config_ui.py：暗、亮分别真实鼠标点击并键盘粘贴明确无效测试值 cli_invalid_parity / invalid-not-a-credential，选择 lark，点击连接。重开配置文件和 SecretsVault 验证 App ID/domain/密钥保存，JSON 无明文 Secret，用户列表为空。真实请求 open.larksuite.com/callback/ws/endpoint 返回：

```
未验证：pullConnectConfig failed: code=1000040346, msg=app_id is invalid
```

未填凭据点击返回：`未验证：飞书 App ID 或 App Secret 未配置`。真实点击生成配对码成功，未伪造入站用户或已配对成功态。日志 feishu.log；截图、读盘 JSON 在 assets/feishu-*。证据以本报告及原始日志为准，不以并发审计表结论替代。

未验证：有效凭据下 wss 成功、平台真实入站事件、平台用户 /pair 成功和外部发送。当前无有效凭据，平台明确拒绝测试 App ID；没有用测试帧冒充线上成功。原版扫码创建应用 OAuth、卡片交互及完整双向回复不属于这次配置/入站闭环，仍未完成完整适配器对等。
