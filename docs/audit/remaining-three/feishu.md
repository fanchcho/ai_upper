# 飞书配置及长连接路径（部分验证）

原版 services/remote/feishu.ts:74-99 注册 im.message.receive_v1 与 WSClient；SDK lib/index.js:102313-102368 发现 /callback/ws/endpoint，:102579 ping，:102665 事件分片/应答。hub.ts:166-238 配对码6位/10分钟/错5次失效，/pair加入白名单。

本轮新增 feishu_inbound.py：沿用真实HTTP transport发现wss地址，QtWebSocket连接和错误状态、protobuf二进制帧、ping、分片、重复事件过滤、应答及重连。remote_bots接p2p文本、白名单及/pair；密钥走SecretsVault，配对码只放内存。机器人页新增App ID/Secret/domain、连接与生成配对码入口。

真实键鼠验证仅为：暗亮点击无凭据连接 → 明确返回“未验证：飞书 App ID 或 App Secret 未配置”，读盘未创建假机器人。日志feishu.log、out/remaining-three/feishu-missing-*.png和feishu-config.json。

未验证：有效配置保存后长连接、真实平台事件和配对；没有凭据，没有用模拟连接成功冒充。尚未完成原版扫码创建应用OAuth设备授权、卡片回调与完整双向回复；因此第2项不能整体标为完成。现有配置/入站代码路径保留，生产平台兼容性未验收。
