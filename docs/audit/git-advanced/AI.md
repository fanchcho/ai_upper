# AI生成/停止边界
上游GitWidget.tsx:755–770显示生成/停止按钮，生成逻辑取消通过AbortController。当前ShellBridge.generateCommitMessage启动真实工作线程及ModelGateway；此前cancel_event仅在流返回后检查，阻塞响应不能及时结束。本轮用asyncio任务50ms轮询取消并取消collect任务，释放真实网络流。
ai-dark/light.json：实际HTTP POST /v1/messages含真实git diff；界面停止生成→点击→AI生成；pending=0，服务器尚未释放响应时_generate_commit_worker线程已不存在。日志与running/stopped截图完整。本机127.0.0.1阻塞端点只用于证实请求与取消，未返回任何模型文本。
未验证真实模型返回：没有配置可用外部模型凭据；不将本地端点当外部模型成功。
