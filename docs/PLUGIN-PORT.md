# deva 插件能力的 QML/Python 入口

当前实现是桌面应用的等价能力，不是可安装到 Studio 的 JavaScript 插件。完整逐文件清单与验证结果见 [移植报告](../out/chrome-upgrade/port/REPORT.md)。

## 模型

设置 → Models → 自定义模型网络，或左侧 Custom model。填写 Base URL、模型名称和 API Key。

- 保存后下一轮由 Python 直接请求 `POST {Base URL}/chat/completions`，错误直接显示，不回退到宿主模型。
- 清空地址恢复会话原有模型。切换地址会清除旧密钥；需要为新地址重新填写。
- 读取设置只返回 `hasKey`；界面显示“已设置”，不读取已存密钥。密码框保存成功后清空。
- 本地作用域是 OS 用户与 Profile，启动器可通过 `AI_UPPER_USER_ID`、`AI_UPPER_PROFILE` 注入作用域。环境变量不是远程用户认证，应用尚无 Studio 已认证身份的接入协议。

## MCP

设置 → MCP：选择服务器或填写新 ID，保存、删除、切换 Enabled、保存或清除凭据。

- stdio：填 Command 和 Arguments JSON 数组，凭据可填 JSON 环境变量映射。
- Streamable HTTP：填 Base URL；凭据可以是 Bearer token 或 JSON HTTP header 映射。
- 服务器在下一轮工具发现时连接。关闭 Enabled、修改配置或删除时停止已有连接；回合完成、取消和应用退出也会关闭连接并回收 stdio 子进程。
- 已实现 initialize、initialized、tools/list 分页、tools/call、JSON/SSE 响应、超时和取消。尚未实现旧版独立 SSE endpoint、OAuth 交互授权、Studio 工具目录注入及资源/提示词能力。
- MCP 工具结果目前按文本返回，上限 30000 字符；图片块等非文本内容返回 JSON 描述，未接入图片展示管线。

## Persona 与命令

Personas 页面编辑 Markdown（支持现有 frontmatter）。生产身份来源固定为 `~/.deva/personas`，不存在时创建；已有文件是唯一来源，不从旧插件配置覆盖。编辑页、快速启动列表和聊天 system prompt 使用同一来源。聊天每次请求读取文件新内容。

- `/deva:identity` 或 `/deva:identity list`：查看当前身份与候选目录。
- `/deva:identity coder`：设置本会话身份，不请求模型。
- `/deva:identity default`：清除会话覆盖，回到共享默认值。
- `@deva:coder 消息`：切换身份并移除前缀后发送消息。
- `/resume`：重新关联中断时尚未执行的审批/提问；已完成工具恢复保存的结果，执行状态未知的操作不自动重放。

旧 `deva-agent/` 布局在使用共享身份目录时迁移，先备份再写入，全部写入成功后才移除旧目录。共享 config/mcp 已有键优先。迁移后的 MCP 文件保留在共享布局中；应用 MCP 设置目前使用自身按 Profile 隔离的配置，尚未自动导入共享 mcp.json。

## 审批与提问

MCP 设置页可开启命令、写文件与 MCP 调用前审批，默认关闭，与上游 opt-in 策略一致。启用后只接受明确“允许”；拒绝、关闭、超时、取消都不会执行。`ask_user` 支持 1–5 个问题与每题最多 6 个选项，也可自由输入。提问及审批绑定当前会话和操作 ID，默认等待 300 秒，状态落盘，可跨控制器重启重新关联。

## 恢复和测试隔离

工具执行日志按用户/Profile、会话、操作 ID 隔离。执行前独占创建记录，完成后原子保存结果和 revision；同 ID 不同参数拒绝执行。若进程在副作用发生后、结果保存前中断，状态为 unknown，不重试。

开发验证必须设置 `AI_UPPER_HOME=/tmp/<独立目录>`。身份源随之隔离到该目录的 `deva/`，不会读取真实 `~/.deva` 或 `~/.ai_upper`。测试命令见 [VERIFY.sh](../out/chrome-upgrade/port/VERIFY.sh)。

## 未接通的宿主接口

Studio 登录身份/Profile namespace、ctx/RPC 注入、插件注册与安装生命周期、assetId 解析与交付确认、state.user 记忆命名空间、Agent/subagent 创建接口尚未注入桌面应用。编码会话能调用 Studio MCP 不代表桌面程序具有这些接口。相关测试的 skip 是未验证声明，不能算功能通过。

macOS 未真机验证。本轮未复现或修改会话图标重影。
