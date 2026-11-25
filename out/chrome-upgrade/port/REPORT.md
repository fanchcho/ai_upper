# 剩余插件能力移植终态（本轮）

**未全部移植完成。** 本报告按原 out/chrome-upgrade/REPORT.md 的85行逐一给终态，无“待评估”；部分实现和无宿主接口都不是已完成。重影未动，macOS未真机验证。基线 c82d564c598dc680750346bf512bcf4efdf1156a。

## 九项需求结果

|项|终态|实现与缺口|file:line|验证证据|
|---|---|---|---|---|
|1|部分实现|MCP设置列表、增删改、启停和单项凭据保存已实现；尚未接入 MCP initialize/tools/list/tools/call、stdio进程生命周期或Streamable HTTP会话。不是因为协议不可实现，而是运行调度尚未接通。|app/src/mvvm/services/plugin_settings.py:72；app/src/qml/PluginSettingsPane.qml:1|ui-verified.log；targeted.log|
|2|部分实现|新增persona文件编辑、缺失时创建、读取以磁盘为准，无旧插件值覆盖。生产无隔离变量时读 ~/.deva/personas；AI_UPPER_HOME隔离测试时读其deva/personas。现有聊天PersonaStore尚未统一到此源，活跃身份选择、头像编辑和宿主身份绑定未完成。|app/src/mvvm/services/plugin_settings.py:106|ui-verified.log；targeted.log|
|3|部分实现|已有自动/手动压缩和取消；新增重启后闭合悬空工具调用，结果未知不重放。缺少上游完整revision checkpoint、身份/agentSession绑定及已完成回复恢复。|app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:442；app/src/mvvm/services/compaction.py:1|features.log：115 passed，rc=0（包含压缩与重启恢复）|
|4|部分实现；Studio交付无宿主接口|本地附件选择、解析、交付卡、文件打开已有并复验；Studio assetId解析、authorizedRoots、expiresAt、resolve与delivery acknowledgment接口未提供给应用，无法验证宿主附件TTL/累计预算。|app/src/mvvm/services/deliverables.py:1；app/tests/test_qml_chat_files.py:1|features.log；contracts.log 的附件项 skipped|
|5|无宿主接口；本地审批尚未实现|路径守卫可用；尚无持久化审批请求ID、用户回答UI、恢复后重新关联接口。现有ToolRuntime不注册ask_user等工具，不能声称审批已移植。需要宿主approval/interaction RPC适配或完整本地审批控制器。|app/src/mvvm/services/tool_runtime.py:3；app/src/mvvm/services/tool_policy.py:1|features.log（路径策略）；contracts.log 的审批项 skipped|
|6|部分实现|新增QML客户端设置路由及文件编辑；原有ChatHost已有发送/中止/压缩。尚缺插件斜杠命令完整映射、Studio运行入口、原版deva-layout旧目录迁移及备份。|app/src/qml/Main.qml:56；app/src/qml/SettingsModal.qml:128；app/src/mvvm/webui/host.py:437|ui-verified.log；contracts.log 的SDK项 skipped|
|7|本地链路已实现并验证；宿主作用域部分实现|自填Base URL/模型/API Key，下一轮直接OpenAIProvider POST；空地址走会话；失败不回退；公有读取只回hasKey；换地址删旧key。按OS用户+Profile或启动器注入的AI_UPPER_USER_ID/AI_UPPER_PROFILE隔离。尚无已认证Studio用户/profile注入接口；环境值不等价于远端身份认证。|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1|targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|8|部分实现|保留expectedRaw冲突保护；新增作用域hash、URL结构验证、身份ID防路径穿越和文件symlink拒绝。未实现sharedDevaUserId所有权授权、可信网络地址审批、完整POSIX目录权限核验与Windows不可核验提示。|app/src/mvvm/services/settings_service.py:85；app/src/mvvm/services/plugin_settings.py:1|targeted.log；contracts.log 的身份项 skipped|
|9|无宿主接口|应用内无Studio插件注册/激活RPC、agentSession/profile namespace、宿主ctx、签名发布和安装生命周期接口。现有Python打包不等价于Studio插件安装器；未复制JS SDK或伪造可用桥。|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1|contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|

## 接口边界

本编码会话可调用Studio MCP，不代表生成的桌面应用具有用户认证、token管理或同一MCP连接。当前应用对象图在assembly.py只注入SettingsService/Vault/ChatHost；没有Studio ctx适配器。contracts.log的4个skip是明确未验证声明，不是通过测试，也不是对远端接口不存在的证明。MCP本地执行、聊天persona源统一、本地审批UI和完整checkpoint可以继续在本仓库实现，不能归咎于宿主接口缺失。

自定义模型HTTP测试使用真实ThreadingHTTPServer，断言POST /custom/chat/completions、model、Authorization；成功返回ok，503返回StreamError，合计两次请求，无模型目录查询或fallback。凭据由Python Vault保存；QML只持有用户输入时的临时明文，保存后清空，读取仅hasKey。尚未做跨用户恶意本地进程隔离测试。

身份编辑并未读取真实用户目录：所有执行都显式AI_UPPER_HOME=/tmp/ai-upper-plugin-port或既有隔离夹具/tmp/ai-upper-frameless-20261125。生产默认~/.deva路径仅代码级证据。

## 页面重拍

before/after-chat.png、settings-general.png、settings-models.png均1280×820。pixels.log：chat变化0像素；General/Models各1266像素（0.120617378%），变化框(303,336)-(419,415)，仅新增左侧三个导航项；旧内容区几何/配色未变化。新页after-settings-custom-model.png、after-settings-mcp.png、after-settings-identities.png为真实offscreen渲染，不是WM截图。当前环境已有CJK缺字方框，未宣称修复。

## 原85行逐一终态

表中的“同第N项”明确继承上表实现位置、测试和缺口。测试/文档/SDK文件归第9项，表示没有照搬对应宿主合约，并非伪造本地等价功能。

|原清单文件|对应项|终态|位置与验证|
|---|---|---|---|
|`plugins/deva-agent/.gitignore`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/AGENTS.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/INSTALL-WINDOWS.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/INSTALL.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/LICENSE`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/README.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/client.mjs`|6|部分实现；具体缺口同第6项|app/src/qml/Main.qml:56；app/src/qml/SettingsModal.qml:128；app/src/mvvm/webui/host.py:437；ui-verified.log；contracts.log 的SDK项 skipped|
|`plugins/deva-agent/contracts/plugin.json`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/docs/CONTRACTS.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/docs/FIELD_REFERENCE.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/docs/OPERATIONS.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/docs/SDK-NOTICE`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/docs/STUDIO_CTX.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/docs/STUDIO_RETURNS.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/lib/agent.mjs`|6|部分实现；具体缺口同第6项|app/src/qml/Main.qml:56；app/src/qml/SettingsModal.qml:128；app/src/mvvm/webui/host.py:437；ui-verified.log；contracts.log 的SDK项 skipped|
|`plugins/deva-agent/lib/approval.mjs`|5|无宿主接口；本地审批尚未实现；具体缺口同第5项|app/src/mvvm/services/tool_runtime.py:3；app/src/mvvm/services/tool_policy.py:1；features.log（路径策略）；contracts.log 的审批项 skipped|
|`plugins/deva-agent/lib/attachments.mjs`|4|部分实现；Studio交付无宿主接口；具体缺口同第4项|app/src/mvvm/services/deliverables.py:1；app/tests/test_qml_chat_files.py:1；features.log；contracts.log 的附件项 skipped|
|`plugins/deva-agent/lib/checkpoint.mjs`|3|部分实现；具体缺口同第3项|app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:442；app/src/mvvm/services/compaction.py:1；features.log：115 passed，rc=0（包含压缩与重启恢复）|
|`plugins/deva-agent/lib/commands.mjs`|6|部分实现；具体缺口同第6项|app/src/qml/Main.qml:56；app/src/qml/SettingsModal.qml:128；app/src/mvvm/webui/host.py:437；ui-verified.log；contracts.log 的SDK项 skipped|
|`plugins/deva-agent/lib/compression.mjs`|3|部分实现；具体缺口同第3项|app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:442；app/src/mvvm/services/compaction.py:1；features.log：115 passed，rc=0（包含压缩与重启恢复）|
|`plugins/deva-agent/lib/custom-model-network.mjs`|7|本地链路已实现并验证；宿主作用域部分实现；具体缺口同第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1；targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|`plugins/deva-agent/lib/desktop-models.mjs`|8|部分实现；具体缺口同第8项|app/src/mvvm/services/settings_service.py:85；app/src/mvvm/services/plugin_settings.py:1；targeted.log；contracts.log 的身份项 skipped|
|`plugins/deva-agent/lib/deva-fs.mjs`|8|部分实现；具体缺口同第8项|app/src/mvvm/services/settings_service.py:85；app/src/mvvm/services/plugin_settings.py:1；targeted.log；contracts.log 的身份项 skipped|
|`plugins/deva-agent/lib/deva-home.mjs`|6|部分实现；具体缺口同第6项|app/src/qml/Main.qml:56；app/src/qml/SettingsModal.qml:128；app/src/mvvm/webui/host.py:437；ui-verified.log；contracts.log 的SDK项 skipped|
|`plugins/deva-agent/lib/deva-layout.mjs`|6|部分实现；具体缺口同第6项|app/src/qml/Main.qml:56；app/src/qml/SettingsModal.qml:128；app/src/mvvm/webui/host.py:437；ui-verified.log；contracts.log 的SDK项 skipped|
|`plugins/deva-agent/lib/interact.mjs`|5|无宿主接口；本地审批尚未实现；具体缺口同第5项|app/src/mvvm/services/tool_runtime.py:3；app/src/mvvm/services/tool_policy.py:1；features.log（路径策略）；contracts.log 的审批项 skipped|
|`plugins/deva-agent/lib/loop.mjs`|3|部分实现；具体缺口同第3项|app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:442；app/src/mvvm/services/compaction.py:1；features.log：115 passed，rc=0（包含压缩与重启恢复）|
|`plugins/deva-agent/lib/mcp-secrets.mjs`|1|部分实现；具体缺口同第1项|app/src/mvvm/services/plugin_settings.py:72；app/src/qml/PluginSettingsPane.qml:1；ui-verified.log；targeted.log|
|`plugins/deva-agent/lib/mcp-store.mjs`|1|部分实现；具体缺口同第1项|app/src/mvvm/services/plugin_settings.py:72；app/src/qml/PluginSettingsPane.qml:1；ui-verified.log；targeted.log|
|`plugins/deva-agent/lib/mcp.mjs`|1|部分实现；具体缺口同第1项|app/src/mvvm/services/plugin_settings.py:72；app/src/qml/PluginSettingsPane.qml:1；ui-verified.log；targeted.log|
|`plugins/deva-agent/lib/memory.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/lib/model-selection.mjs`|7|本地链路已实现并验证；宿主作用域部分实现；具体缺口同第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1；targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|`plugins/deva-agent/lib/model.mjs`|7|本地链路已实现并验证；宿主作用域部分实现；具体缺口同第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1；targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|`plugins/deva-agent/lib/persona-avatar.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`plugins/deva-agent/lib/persona-file.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`plugins/deva-agent/lib/persona-store.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`plugins/deva-agent/lib/prompt.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/lib/selection.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/lib/session-identities.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`plugins/deva-agent/lib/shared-deva-model.mjs`|7|本地链路已实现并验证；宿主作用域部分实现；具体缺口同第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1；targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|`plugins/deva-agent/lib/skills.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/lib/storage-contracts.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/lib/studio-mcp.mjs`|1|部分实现；具体缺口同第1项|app/src/mvvm/services/plugin_settings.py:72；app/src/qml/PluginSettingsPane.qml:1；ui-verified.log；targeted.log|
|`plugins/deva-agent/lib/studio-model.mjs`|7|本地链路已实现并验证；宿主作用域部分实现；具体缺口同第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1；targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|`plugins/deva-agent/lib/subagents.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/lib/tools.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/package.json`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/plugin.json`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/sdk/NOTICE`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/sdk/docs/FIELD_REFERENCE.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/sdk/docs/STUDIO_CTX.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/sdk/docs/STUDIO_RETURNS.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/sdk/src/agents.ts`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/sdk/src/contexts.ts`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/sdk/src/core.ts`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/server.mjs`|6|部分实现；具体缺口同第6项|app/src/qml/Main.qml:56；app/src/qml/SettingsModal.qml:128；app/src/mvvm/webui/host.py:437；ui-verified.log；contracts.log 的SDK项 skipped|
|`plugins/deva-agent/tests/agent-studio-mcp.test.mjs`|1|部分实现；具体缺口同第1项|app/src/mvvm/services/plugin_settings.py:72；app/src/qml/PluginSettingsPane.qml:1；ui-verified.log；targeted.log|
|`plugins/deva-agent/tests/agent.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/cancellation.test.mjs`|3|部分实现；具体缺口同第3项|app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:442；app/src/mvvm/services/compaction.py:1；features.log：115 passed，rc=0（包含压缩与重启恢复）|
|`plugins/deva-agent/tests/client.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/completion-attachments.test.mjs`|4|部分实现；Studio交付无宿主接口；具体缺口同第4项|app/src/mvvm/services/deliverables.py:1；app/tests/test_qml_chat_files.py:1；features.log；contracts.log 的附件项 skipped|
|`plugins/deva-agent/tests/completion-recovery.test.mjs`|3|部分实现；具体缺口同第3项|app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:442；app/src/mvvm/services/compaction.py:1；features.log：115 passed，rc=0（包含压缩与重启恢复）|
|`plugins/deva-agent/tests/completion-sdk.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/completion-secrets.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/completion-storage.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/contracts.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/desktop-models.test.mjs`|7|本地链路已实现并验证；宿主作用域部分实现；具体缺口同第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1；targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|`plugins/deva-agent/tests/deva-home.test.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`plugins/deva-agent/tests/ekko-protocol.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/fixtures/README.md`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/fixtures/memory-v1.json`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/fixtures/subagents-v1.json`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/identity.test.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`plugins/deva-agent/tests/mcp.test.mjs`|1|部分实现；具体缺口同第1项|app/src/mvvm/services/plugin_settings.py:72；app/src/qml/PluginSettingsPane.qml:1；ui-verified.log；targeted.log|
|`plugins/deva-agent/tests/memory.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/model.test.mjs`|7|本地链路已实现并验证；宿主作用域部分实现；具体缺口同第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1；targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|`plugins/deva-agent/tests/persona-avatar.test.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`plugins/deva-agent/tests/persona-editor.test.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`plugins/deva-agent/tests/skills.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/studio-compatibility.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/studio-mcp.test.mjs`|1|部分实现；具体缺口同第1项|app/src/mvvm/services/plugin_settings.py:72；app/src/qml/PluginSettingsPane.qml:1；ui-verified.log；targeted.log|
|`plugins/deva-agent/tests/studio-model.test.mjs`|7|本地链路已实现并验证；宿主作用域部分实现；具体缺口同第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/PluginSettingsPane.qml:1；targeted.log：本地真实HTTP成功/503请求断言；ui-verified.log：真实QML按钮保存|
|`plugins/deva-agent/tests/subagents.test.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|
|`plugins/deva-agent/tests/support/deva-home.mjs`|2|部分实现；具体缺口同第2项|app/src/mvvm/services/plugin_settings.py:106；ui-verified.log；targeted.log|
|`scripts/install-deva-agent.mjs`|9|无宿主接口；具体缺口同第9项|app/src/mvvm/webui/assembly.py:1；app/tests/test_plugin_host_requirements.py:1；contracts.log：4 skipped，rc=0；全量日志中的现有打包测试仅验证桌面包|

## 验证说明

初次全量 full-pytest.log 为1371 passed、5 skipped、1 failed，rc=1；失败是test_qt_prune测试与显式PYTHONPATH=app/src冲突。未改断言，按conftest的正常导入路径取消该环境覆盖重跑，终态以full-final.log为准。

独立QML回归终态以qml-final.log为准。新增凭据冲突保护与三个编辑器的最后补充复验见conflict-final.log：7 passed、0 skipped、rc=0；全量启动后新增的该冲突测试单独记录，不伪装成已被更早收集的全量覆盖。

features.log：115 passed、0 skipped、rc=0，覆盖本地压缩、恢复、附件、交付及路径策略。contracts.log：4 skipped、rc=0，明确声明应用内Studio接口缺失，不能算实现通过。

本轮只读deva；收尾deva-status.log出现5项既存/外部并行修改，除先前3个web文件外还包括apps/web/README.md和暂存删除的favicon.svg，本轮没有写入该目录，未替外部改动做回滚。

## 实际测试终态

|范围|实际结果|rc|日志|
|---|---|---|---|
|全量 app/tests|1373 passed、9 skipped|0|full-final.log / full-final.rc|
|独立 QML 回归|206 passed、0 skipped|0|qml-final.log / qml-final.rc|
|最后补充：配置冲突、HTTP、作用域、MCP/persona编辑器|7 passed、0 skipped|0|conflict-final.log / conflict-final.rc|
|压缩/中断恢复/附件/交付/路径策略|115 passed、0 skipped|0|features.log / features.rc|
|应用内宿主接口缺口声明|4 skipped|0|contracts.log|

9个全量skip包含4个明确缺宿主合约的声明与5个原有环境条件skip；没有把skip计入已实现。全量启动后补充的凭据冲突用例单独在最后7项复验记录，不混加测试数量。pytest输出、失败尝试、重拍图和差异统计均保留。提交推送后生成publish.log核对本地与远端hash。
