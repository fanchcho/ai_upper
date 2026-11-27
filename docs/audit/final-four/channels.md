# 飞书与 Web 出站推送：部分实现，外部成功态未验证

原版根 `/home/agent/shared_workspace/deva/apps/desktop/src/`，只读。

- main/services/remote/feishu.ts:48 FeishuAdapter，:76 tenantAccessToken.internal，:160-180 interactive 消息 create/patch，:190 sendNotice。原版启动还注册接收事件和 WSClient（:83-99），不是只有 HTTP 发送。
- main/services/remote/web/push.ts:52 vapidOf；:86 encryptPushPayload；:121 sendPush。
- main/services/remote/web/devices.ts:32 listDevices：设备存在 bot.users；:71 patchDevice 持久化订阅修改。
- main/services/remote/web/adapter.ts:535 notifyDevices → :542 sendPush；gone 删除订阅，前台设备跳过。:708 sendNotice。

移植已有 Feishu tenant token + interactive 卡片 POST；Web RFC8291 aes128gcm、VAPID 签名和 HTTPS 推送。接入 remote_bots.publish_notice，沿用原版 bot.users 设备布局。后台结果进入 Qt 主线程保存 lastDelivery，404/410 去掉失效 push 订阅；queued 只表示进入发送队列，绝不等于 sent。没有凭据/订阅时保留原始 unverified 原因。

原始无凭据执行输出 channels.log：
```
feishu {'status': 'unverified', 'reason': '飞书 App ID 或 App Secret 未配置'}
web {'status': 'unverified', 'reason': 'Web Push 浏览器订阅不存在；未完成配对'}
```
空渠道保持 `未配置可用的已配对远程渠道`。没有尝试 Telegram 配对、没有向真实外部接收人发送消息。

scripts/parity/webpush_payload_evidence.py 使用真实 SecretsVault 写盘/读回与 cryptography；独立接收端私钥解密生产生成的负载，验证内容一致。webpush-payload.log 是加密算法与密钥持久化证据，不是外部通道连通证据。没有用替身HTTP成功响应充当飞书/Web送达。

**未完成**：飞书入站长连接和配对/新增配置流程；Web 安全配对传输与浏览器订阅入口、连接前台状态抑制。不能把完整 FeishuAdapter/PhoneAdapter 标为已移植可用。

**未验证**：真实飞书凭据及接收用户、真实浏览器订阅和推送服务送达；未安装 cryptography 的部署。没有有效渠道凭据，不能继续验证外部成功态。未改依赖 pin。

首批5f17215由本执行推送。bot.users/lastDelivery/gone 修正被并发外部提交00fa741收录，保留该提交但不冒领其 Git 操作。
