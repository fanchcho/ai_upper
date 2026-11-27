# 本轮范围和验收清单

- [x] 保留已验收89项盘点及已推提交。本执行不修改主盘点表；外部对表的修改记录 external-changes.json 与 external-working-tree.patch。
- [x] member_send/member_stop 优先真实成员，回退当前主会话拥有的定时任务；真实工具运行、键盘交互、重新打开存储、日程不变、暗亮截图。
- [x] 任务追问无人值守；空回复不借用历史内容；停止只延迟通知，不唤醒，下一主回合消费。
- [x] 飞书 App ID/Secret/domain 配置入口、密钥保存、连接状态、生成配对码入口；真实无效凭据请求和错误原文，暗亮截图。
- [x] 飞书 wss / protobuf / ping / 分片 / 去重 / 入站白名单和配对代码路径。
- [ ] 未验证：有效凭据的飞书 wss 入站和平台配对，真实错误 app_id is invalid。未尝试外部发送成功态。
- [x] Web 本机短期票据、加密证明、设备保存、刷新重连、重放拒绝、真实前后台状态、移除设备断开和删密钥。
- [x] 浏览器真实 PushManager/Service Worker 订阅入口及错误原文，暗亮截图。
- [ ] 未验证：PushService 订阅成功/外部送达，宿主 Registration failed - push service not available；协议存储样本不是实际订阅证据。
- [ ] 未完成完整手机跨设备适配器：LAN/relay/安装票据、完整飞书 OAuth 扫码与卡片双向回复，未冒充本轮已完成。
- [x] 每项独立提交、非 force push，并记录随后 ls-remote；publish.md 与原始 push logs。
- [x] deva 仅作只读代码/已安装构建工具参考；应用与测试 AI_UPPER_HOME 隔离到 /tmp；未改依赖 pin。
- [x] 本执行未修改 app/tests 既有断言。外部新增/修改测试单列，原样保留。
- [x] 最终固定源码 e85b23d 全量回归：1461 passed / 9 skipped / 0 failed，461.85秒；原始 full-final.log。
- [x] 不重试托盘/通知宿主、Windows/macOS代理、像素归零、真实外部模型自主建人；保持未验证/未归零。
