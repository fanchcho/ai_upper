# 机器人入口：配置动作已验证，外部连接未验证

原版依据：`remote/index.ts:203-355` 定义列表、Telegram Token 校验/认领、启停、回复模式、范围、删除、移除用户；`remote/store.ts` 使用 config.remote.bots，凭据在 `remote:<id>:<field>`；`remote/telegram-onboard.ts` 72 位一次码、10 分钟过期、getUpdates 私聊认领。

当前实现 `RemoteBots.qml` / `remote_bots.py`：入口打开真实保存的列表；回复模式/范围/停用/删除写回 config，删除清理凭据；Telegram 添加通过真实 getMe、deleteWebhook、一次码链接认领；已配对私聊接入真实 ChatHost，完成或流式结果走 Telegram API。没有用 localhost 的假 Telegram 服务证明外部成功。飞书/Web 的连接适配器尚未实现，启用会返回明确错误，不记为 connected。

验证命令：

```sh
AI_UPPER_HOME=/tmp/ai-upper-bots-ui QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
.venv/bin/python scripts/parity/final_port/bots_ui.py
```

结果 `PASS configuration list/reply/scope/delete; external connection UNVERIFIED (no credentials)`。
`out/final-port/bots-ui.json` 保存真实 QTest 点击后读回的配置；暗亮截图 bots-dark.png / bots-light.png。截图行明确是配置管理 fixture，不是在线机器人。

真实启用错误：`机器人密钥不存在或系统密钥库不可用`。本轮没有提供有效 Telegram / 飞书账号凭据，因此 Telegram 配对、外部收发、流式消息、系统密钥保存及飞书/Web 渠道均 **未验证/未完成**。本项把空入口接成可用配置动作，但完整的机器人页/远程渠道不能记为“已实现且可用”。

兼容层复核：RemoteBots 只在调用入口/启动应用时构造真实 QObject，去掉并发执行引入的空 Signal/Slot 兜底；保持现有 Qt 绑定抽象。bots_ui 暗亮配置读写再次 PASS；外部渠道成功态仍未验证。
