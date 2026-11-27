# 飞书与 Web 出站推送

原版真实存在：remote/feishu.ts:48 FeishuAdapter，:76 tenantAccessToken.internal，:160-180 interactive 消息 create/patch，:190 sendNotice；remote/web/push.ts:121 sendPush，:86 encryptPushPayload；remote/web/adapter.ts:539-542 遍历配对设备调用推送。

本轮移植 Feishu tenant token + interactive 卡片 POST，以及 Web RFC8291 aes128gcm 负载、VAPID 签名和 HTTPS 推送，接 remote_bots.publish_notice 的平台路由。HTTP 结果和无凭据错误均返回明确状态，queued 不等于 sent。

channels.log 为真实无凭据结果：飞书 App ID 或 App Secret 未配置；Web Push 浏览器订阅不存在；未完成配对。没有向外部发送消息。webpush-payload.log 使用真实密钥库落盘读回与 cryptography，收端私钥解密验证生产加密负载，未使用外部服务替身，不作为外部发送成功证据。

未完成：飞书入站长连接/配对、Web 配对服务器/设备订阅入口、浏览器设备完整存储布局接入与失效订阅删除。当前出站路径需要已有记录；无真实凭据/订阅，生产成功态未验证。加密实现需要环境已有 cryptography，未改依赖 pin；无该库的部署仍未验证。
