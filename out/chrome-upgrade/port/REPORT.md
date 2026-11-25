# deva 剩余插件移植：最终逐项交付与缺口

**部分完成，不是全部移植完成。** 此报告替代第一批交付时的运行链路缺口描述。唯一清单基准仍是上级 REPORT.md 的85行；本表逐行给出已实现、部分实现或无应用内宿主接口的终态，无悬置项。已推送第一批 8de00f088c43d6cb10167ef693ea1859b6962ca4，第二批补齐本地运行链路，最终提交见 runtime-publish.log。

本轮不复现、不修复图标重影。macOS 未真机验证。deva 参考仓库只读。

## 九项结果

|项|终态|实现与具体缺口|等价位置 file:line|针对性验证|
|---|---|---|---|---|
|1|部分实现（本地管理与运行链路已验证）|设置列表/增删改/启停/凭据；stdio 与 Streamable HTTP initialize、tools/list、tools/call、JSON/SSE 响应、分页、取消、子进程回收已接通。启用后下一轮连接，停用立即关闭。缺旧版独立 SSE endpoint、OAuth、Studio 工具注入、非文本结果的专用展示。|app/src/mvvm/services/mcp_runtime.py:193；app/src/mvvm/services/plugin_settings.py:71；app/src/qml/PluginSettingsPane.qml:1|runtime-target-final.log：stdio 1、HTTP JSON/SSE 2、取消 1 个真实传输测试通过；QML 保存测试通过|
|2|部分实现（身份编辑、来源与聊天绑定已验证）|身份编辑、快速启动和 system prompt 统一读取 ~/.deva/personas；测试隔离目录下验证。已有文件不被旧插件值覆盖，磁盘编辑下一次请求生效。支持会话覆盖与默认选择。已有头像读取服务保留，但没有新增头像上传编辑控件或 Studio Agent 身份绑定。|app/src/mvvm/services/plugin_identity.py:10；app/src/mvvm/services/plugin_settings.py:120；app/src/qml_shell.py:710|runtime-target-final.log：真实磁盘变更→模型请求 prompt 断言；QML persona 保存；权限测试|
|3|部分实现（本地恢复已验证）|现有自动/手动压缩、取消继续可用。工具日志 revision 1/2、用户/Profile/会话/操作 ID 分区；完成结果原样恢复，unknown 不重放，参数改变拒绝复用。/resume 可重新关联中断审批后执行一次。缺 Studio agentSession 所有权/远程 completion replay 协议。|app/src/mvvm/services/tool_checkpoint.py:31；app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:443|runtime-target-final.log：未知执行不重放、完成结果恢复、真实中断审批恢复、图片结果往返；features.log：压缩与取消相关测试|
|4|部分实现；Studio交付无应用内宿主接口|本地附件选择/读取、交付卡、打开/定位已有并回归。缺 assetId resolver、authorizedRoots/TTL/累计预算与 delivery acknowledgment；不能把本地路径交付当 Studio 资产协议。|app/src/mvvm/services/deliverables.py:1；app/tests/test_qml_chat_files.py:1|features.log：附件/交付用例通过；contracts-final.log：Studio 附件未验证声明|
|5|本地已实现并验证；Studio RPC 无应用内宿主接口|opt-in 审批策略接入命令、写文件、MCP；ask_user 支持最多5题/6选项。QML 允许/拒绝/输入/关闭，持久化 ID、会话绑定、300秒超时、取消与重新关联。非明确同意不执行。缺 Studio interactions RPC envelope 与跨运行时回调适配。|app/src/mvvm/services/plugin_interactions.py:15；app/src/mvvm/services/tool_runtime.py:460；app/src/qml/InteractionPrompt.qml:1|runtime-target-final.log：审批3种结果、问题关闭/超时/重启、QTest真实点击四条路径全部通过|
|6|部分实现（本地命令和迁移已验证）|/deva:identity 与 @deva: 前缀、QML客户端设置、发送/中止/压缩已接通。旧布局先备份，已有共享键优先，写完才删旧目录。缺 Studio插件Agent入口；迁移出的共享 mcp.json 尚未自动导入按Profile隔离的应用 MCP 设置。|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45|runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|7|本地已实现并验证；Studio认证作用域无应用内接口|Models页可进入自定义网络；Base URL/模型/API Key 持久化，QML只回显hasKey；换地址清旧密钥；空地址回会话；下一轮真实POST且失败不回退。本地OS用户+Profile隔离，启动器可注入作用域。缺经过认证的Studio用户/Profile注入，环境变量不能充当远端认证。|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534|runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|8|部分实现|expectedRaw保护保留；新增URL结构/ID/symlink/POSIX所有者与组/其他用户可写检测。缺 sharedDevaUserId 授权、共享模型凭据代理、可信网络审批、Windows ACL核验提示。POSIX检查只覆盖使用到的身份路径，不声称整个.deva目录树完整审计。|app/src/mvvm/services/settings_service.py:85；app/src/mvvm/services/plugin_identity.py:15|runtime-target-final.log：外部改配置后保存失败且旧key保留；可写权限与symlink拒绝；Windows ACL 未验证|
|9|部分实现；Studio SDK/安装器无应用内宿主接口|操作文档和85行对账已写。应用未注入ctx/RPC、插件注册/激活生命周期、state.user命名空间、agents.run/subagent接口、签名发布/安装；现有Python打包不是Studio插件安装器。没有复制Node实现或宣称stub可用。|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1|contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|

## 真实测试与限制

- `runtime-target-final.log`：24 passed，0 skipped，rc=0，覆盖本轮新增运行链路与实际QML点击。
- `features.log`：115 passed，0 skipped，rc=0，覆盖既有压缩/取消、附件和交付、路径策略。
- `contracts-final.log`：4 skipped，rc=0，仅明确声明尚未验证的Studio宿主契约，不作为实现通过证据。
- 最终全量 `final-all.log` / `final-all.rc`，最终QML `final-qml.log` / `final-qml.rc`，实际数字在下方验收追加段。
- 首次运行曾有测试断言使用可变请求列表、QML隐藏项轮询和旧persona测试夹具路径问题，失败日志保留；修复后重新运行。第一次全量前的NameError属于新测试代码位置错误，已修复并在最终针对性与全量运行中验证。
- MCP HTTP 采用官方[传输规范](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)和[生命周期规范](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)实现所列子集，不声称支持全部MCP能力。
- 本编码会话可调用Studio MCP，不代表桌面程序拥有同一连接、登录身份或ctx。缺口指应用对象图未接入，不是断言远端API不存在。
- 所有应用和测试均在隔离AI_UPPER_HOME下运行；最终验证使用/tmp/ai-upper-plugin-port及其子目录，视觉夹具使用/tmp/ai-upper-frameless-20261125、/tmp/ai-upper-plugin-port-visual。早期针对性测试的tmp_path在仓库.tmp下，仍隔离但不符合“必须/tmp”字面约束，已在最终/tmp运行中全部重验。没有访问真实~/.ai_upper。

## 原85行终态

每行继承对应项的实现、具体缺口和验证；特别的宿主依赖另列。法律/构建元数据不伪装为运行功能，文档以Python桌面入口重写；SDK未被重新分发。

|原清单文件|对应项|终态与原因|file:line及验证|
|---|---|---|---|
|`plugins/deva-agent/.gitignore`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/AGENTS.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/INSTALL-WINDOWS.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/INSTALL.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/LICENSE`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/README.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/client.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/contracts/plugin.json`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/docs/CONTRACTS.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/docs/FIELD_REFERENCE.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/docs/OPERATIONS.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/docs/SDK-NOTICE`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/docs/STUDIO_CTX.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/docs/STUDIO_RETURNS.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/lib/agent.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/lib/approval.mjs`|5|本地已实现并验证；Studio RPC 无应用内宿主接口；其余缺口见第5项|app/src/mvvm/services/plugin_interactions.py:15；app/src/mvvm/services/tool_runtime.py:460；app/src/qml/InteractionPrompt.qml:1；runtime-target-final.log：审批3种结果、问题关闭/超时/重启、QTest真实点击四条路径全部通过|
|`plugins/deva-agent/lib/attachments.mjs`|4|部分实现；Studio交付无应用内宿主接口；其余缺口见第4项|app/src/mvvm/services/deliverables.py:1；app/tests/test_qml_chat_files.py:1；features.log：附件/交付用例通过；contracts-final.log：Studio 附件未验证声明|
|`plugins/deva-agent/lib/checkpoint.mjs`|3|部分实现（本地恢复已验证）；其余缺口见第3项|app/src/mvvm/services/tool_checkpoint.py:31；app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:443；runtime-target-final.log：未知执行不重放、完成结果恢复、真实中断审批恢复、图片结果往返；features.log：压缩与取消相关测试|
|`plugins/deva-agent/lib/commands.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/lib/compression.mjs`|3|部分实现（本地恢复已验证）；其余缺口见第3项|app/src/mvvm/services/tool_checkpoint.py:31；app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:443；runtime-target-final.log：未知执行不重放、完成结果恢复、真实中断审批恢复、图片结果往返；features.log：压缩与取消相关测试|
|`plugins/deva-agent/lib/custom-model-network.mjs`|7|本地已实现并验证；Studio认证作用域无应用内接口；其余缺口见第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534；runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|`plugins/deva-agent/lib/desktop-models.mjs`|8|部分实现；其余缺口见第8项|app/src/mvvm/services/settings_service.py:85；app/src/mvvm/services/plugin_identity.py:15；runtime-target-final.log：外部改配置后保存失败且旧key保留；可写权限与symlink拒绝；Windows ACL 未验证|
|`plugins/deva-agent/lib/deva-fs.mjs`|8|部分实现；其余缺口见第8项|app/src/mvvm/services/settings_service.py:85；app/src/mvvm/services/plugin_identity.py:15；runtime-target-final.log：外部改配置后保存失败且旧key保留；可写权限与symlink拒绝；Windows ACL 未验证|
|`plugins/deva-agent/lib/deva-home.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/lib/deva-layout.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/lib/interact.mjs`|5|本地已实现并验证；Studio RPC 无应用内宿主接口；其余缺口见第5项|app/src/mvvm/services/plugin_interactions.py:15；app/src/mvvm/services/tool_runtime.py:460；app/src/qml/InteractionPrompt.qml:1；runtime-target-final.log：审批3种结果、问题关闭/超时/重启、QTest真实点击四条路径全部通过|
|`plugins/deva-agent/lib/loop.mjs`|3|部分实现（本地恢复已验证）；其余缺口见第3项|app/src/mvvm/services/tool_checkpoint.py:31；app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:443；runtime-target-final.log：未知执行不重放、完成结果恢复、真实中断审批恢复、图片结果往返；features.log：压缩与取消相关测试|
|`plugins/deva-agent/lib/mcp-secrets.mjs`|1|部分实现（本地管理与运行链路已验证）；其余缺口见第1项|app/src/mvvm/services/mcp_runtime.py:193；app/src/mvvm/services/plugin_settings.py:71；app/src/qml/PluginSettingsPane.qml:1；runtime-target-final.log：stdio 1、HTTP JSON/SSE 2、取消 1 个真实传输测试通过；QML 保存测试通过|
|`plugins/deva-agent/lib/mcp-store.mjs`|1|部分实现（本地管理与运行链路已验证）；其余缺口见第1项|app/src/mvvm/services/mcp_runtime.py:193；app/src/mvvm/services/plugin_settings.py:71；app/src/qml/PluginSettingsPane.qml:1；runtime-target-final.log：stdio 1、HTTP JSON/SSE 2、取消 1 个真实传输测试通过；QML 保存测试通过|
|`plugins/deva-agent/lib/mcp.mjs`|1|部分实现（本地管理与运行链路已验证）；其余缺口见第1项|app/src/mvvm/services/mcp_runtime.py:193；app/src/mvvm/services/plugin_settings.py:71；app/src/qml/PluginSettingsPane.qml:1；runtime-target-final.log：stdio 1、HTTP JSON/SSE 2、取消 1 个真实传输测试通过；QML 保存测试通过|
|`plugins/deva-agent/lib/memory.mjs`|9|无应用内宿主接口（功能未实现）；需要对应Studio ctx、state或工具/模型/Agent RPC适配，不能用本地假数据代替|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/lib/model-selection.mjs`|7|本地已实现并验证；Studio认证作用域无应用内接口；其余缺口见第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534；runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|`plugins/deva-agent/lib/model.mjs`|7|本地已实现并验证；Studio认证作用域无应用内接口；其余缺口见第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534；runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|`plugins/deva-agent/lib/persona-avatar.mjs`|2|部分实现（身份编辑、来源与聊天绑定已验证）；其余缺口见第2项|app/src/mvvm/services/plugin_identity.py:10；app/src/mvvm/services/plugin_settings.py:120；app/src/qml_shell.py:710；runtime-target-final.log：真实磁盘变更→模型请求 prompt 断言；QML persona 保存；权限测试|
|`plugins/deva-agent/lib/persona-file.mjs`|2|部分实现（身份编辑、来源与聊天绑定已验证）；其余缺口见第2项|app/src/mvvm/services/plugin_identity.py:10；app/src/mvvm/services/plugin_settings.py:120；app/src/qml_shell.py:710；runtime-target-final.log：真实磁盘变更→模型请求 prompt 断言；QML persona 保存；权限测试|
|`plugins/deva-agent/lib/persona-store.mjs`|2|部分实现（身份编辑、来源与聊天绑定已验证）；其余缺口见第2项|app/src/mvvm/services/plugin_identity.py:10；app/src/mvvm/services/plugin_settings.py:120；app/src/qml_shell.py:710；runtime-target-final.log：真实磁盘变更→模型请求 prompt 断言；QML persona 保存；权限测试|
|`plugins/deva-agent/lib/prompt.mjs`|6|部分实现（本地命令和迁移已验证）；仅persona正文已进入system，完整上游能力/记忆索引提示模板尚未移植；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/lib/selection.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/lib/session-identities.mjs`|2|部分实现（身份编辑、来源与聊天绑定已验证）；其余缺口见第2项|app/src/mvvm/services/plugin_identity.py:10；app/src/mvvm/services/plugin_settings.py:120；app/src/qml_shell.py:710；runtime-target-final.log：真实磁盘变更→模型请求 prompt 断言；QML persona 保存；权限测试|
|`plugins/deva-agent/lib/shared-deva-model.mjs`|7|本地已实现并验证；Studio认证作用域无应用内接口；其余缺口见第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534；runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|`plugins/deva-agent/lib/skills.mjs`|6|部分实现（本地命令和迁移已验证）；现有本地扩展页保留，Studio共享skills registry/更新事件未接入；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/lib/storage-contracts.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；本地checkpoint结构已验证，Studio状态schema迁移器未接入；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/lib/studio-mcp.mjs`|9|无应用内宿主接口（功能未实现）；需要对应Studio ctx、state或工具/模型/Agent RPC适配，不能用本地假数据代替|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/lib/studio-model.mjs`|7|无应用内宿主接口（功能未实现）；需要对应Studio ctx、state或工具/模型/Agent RPC适配，不能用本地假数据代替|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534；runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|`plugins/deva-agent/lib/subagents.mjs`|9|无应用内宿主接口（功能未实现）；需要对应Studio ctx、state或工具/模型/Agent RPC适配，不能用本地假数据代替|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/lib/tools.mjs`|5|本地已实现并验证；Studio RPC 无应用内宿主接口；其余缺口见第5项|app/src/mvvm/services/plugin_interactions.py:15；app/src/mvvm/services/tool_runtime.py:460；app/src/qml/InteractionPrompt.qml:1；runtime-target-final.log：审批3种结果、问题关闭/超时/重启、QTest真实点击四条路径全部通过|
|`plugins/deva-agent/package.json`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/plugin.json`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/sdk/NOTICE`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/sdk/docs/FIELD_REFERENCE.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/sdk/docs/STUDIO_CTX.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/sdk/docs/STUDIO_RETURNS.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/sdk/src/agents.ts`|9|无应用内宿主接口（功能未实现）；需要对应Studio ctx、state或工具/模型/Agent RPC适配，不能用本地假数据代替|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/sdk/src/contexts.ts`|9|无应用内宿主接口（功能未实现）；需要对应Studio ctx、state或工具/模型/Agent RPC适配，不能用本地假数据代替|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/sdk/src/core.ts`|9|无应用内宿主接口（功能未实现）；需要对应Studio ctx、state或工具/模型/Agent RPC适配，不能用本地假数据代替|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/server.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/tests/agent-studio-mcp.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/agent.test.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/tests/cancellation.test.mjs`|3|部分实现（本地恢复已验证）；其余缺口见第3项|app/src/mvvm/services/tool_checkpoint.py:31；app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:443；runtime-target-final.log：未知执行不重放、完成结果恢复、真实中断审批恢复、图片结果往返；features.log：压缩与取消相关测试|
|`plugins/deva-agent/tests/client.test.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/tests/completion-attachments.test.mjs`|4|部分实现；Studio交付无应用内宿主接口；其余缺口见第4项|app/src/mvvm/services/deliverables.py:1；app/tests/test_qml_chat_files.py:1；features.log：附件/交付用例通过；contracts-final.log：Studio 附件未验证声明|
|`plugins/deva-agent/tests/completion-recovery.test.mjs`|3|部分实现（本地恢复已验证）；其余缺口见第3项|app/src/mvvm/services/tool_checkpoint.py:31；app/src/mvvm/services/checkpoint_recovery.py:6；app/src/mvvm/view_models/chat_vm.py:443；runtime-target-final.log：未知执行不重放、完成结果恢复、真实中断审批恢复、图片结果往返；features.log：压缩与取消相关测试|
|`plugins/deva-agent/tests/completion-sdk.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/completion-secrets.test.mjs`|7|本地已实现并验证；Studio认证作用域无应用内接口；其余缺口见第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534；runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|`plugins/deva-agent/tests/completion-storage.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/contracts.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/desktop-models.test.mjs`|8|部分实现；其余缺口见第8项|app/src/mvvm/services/settings_service.py:85；app/src/mvvm/services/plugin_identity.py:15；runtime-target-final.log：外部改配置后保存失败且旧key保留；可写权限与symlink拒绝；Windows ACL 未验证|
|`plugins/deva-agent/tests/deva-home.test.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/tests/ekko-protocol.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/fixtures/README.md`|9|部分实现；Studio SDK/安装器无应用内宿主接口；文档/元数据以docs/PLUGIN-PORT.md说明差异，不复制Node工程和SDK发行物；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/fixtures/memory-v1.json`|9|部分实现；Studio SDK/安装器无应用内宿主接口；无应用内宿主接口：需要state.user.namespace与agents.run，未用本地假数据代替；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/fixtures/subagents-v1.json`|9|部分实现；Studio SDK/安装器无应用内宿主接口；无应用内宿主接口：需要state.user.namespace与agents.run，未用本地假数据代替；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/identity.test.mjs`|2|部分实现（身份编辑、来源与聊天绑定已验证）；其余缺口见第2项|app/src/mvvm/services/plugin_identity.py:10；app/src/mvvm/services/plugin_settings.py:120；app/src/qml_shell.py:710；runtime-target-final.log：真实磁盘变更→模型请求 prompt 断言；QML persona 保存；权限测试|
|`plugins/deva-agent/tests/mcp.test.mjs`|1|部分实现（本地管理与运行链路已验证）；其余缺口见第1项|app/src/mvvm/services/mcp_runtime.py:193；app/src/mvvm/services/plugin_settings.py:71；app/src/qml/PluginSettingsPane.qml:1；runtime-target-final.log：stdio 1、HTTP JSON/SSE 2、取消 1 个真实传输测试通过；QML 保存测试通过|
|`plugins/deva-agent/tests/memory.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；无应用内宿主接口：需要state.user.namespace与agents.run，未用本地假数据代替；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/model.test.mjs`|7|本地已实现并验证；Studio认证作用域无应用内接口；其余缺口见第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534；runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|`plugins/deva-agent/tests/persona-avatar.test.mjs`|2|部分实现（身份编辑、来源与聊天绑定已验证）；其余缺口见第2项|app/src/mvvm/services/plugin_identity.py:10；app/src/mvvm/services/plugin_settings.py:120；app/src/qml_shell.py:710；runtime-target-final.log：真实磁盘变更→模型请求 prompt 断言；QML persona 保存；权限测试|
|`plugins/deva-agent/tests/persona-editor.test.mjs`|2|部分实现（身份编辑、来源与聊天绑定已验证）；其余缺口见第2项|app/src/mvvm/services/plugin_identity.py:10；app/src/mvvm/services/plugin_settings.py:120；app/src/qml_shell.py:710；runtime-target-final.log：真实磁盘变更→模型请求 prompt 断言；QML persona 保存；权限测试|
|`plugins/deva-agent/tests/skills.test.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`plugins/deva-agent/tests/studio-compatibility.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/studio-mcp.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/studio-model.test.mjs`|7|本地已实现并验证；Studio认证作用域无应用内接口；其余缺口见第7项|app/src/mvvm/services/plugin_settings.py:13；app/src/mvvm/services/provider_setup.py:65；app/src/qml/SettingsModal.qml:534；runtime-target-final.log：真实HTTP success/503共2次且无fallback；地址切换与作用域；QML从Models入口填写保存/清空密码框|
|`plugins/deva-agent/tests/subagents.test.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；无应用内宿主接口：需要state.user.namespace与agents.run，未用本地假数据代替；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|
|`plugins/deva-agent/tests/support/deva-home.mjs`|6|部分实现（本地命令和迁移已验证）；其余缺口见第6项|app/src/mvvm/services/plugin_identity.py:44；app/src/mvvm/services/plugin_layout.py:10；app/src/mvvm/webui/assembly.py:45；runtime-target-final.log：命令不调用模型、会话隔离、迁移备份/不覆盖/幂等；现有 ChatHost 回归|
|`scripts/install-deva-agent.mjs`|9|部分实现；Studio SDK/安装器无应用内宿主接口；其余缺口见第9项|docs/PLUGIN-PORT.md:1；app/src/mvvm/webui/assembly.py:45；app/tests/test_plugin_host_requirements.py:1；contracts-final.log：4 skipped是未验证声明；完整pytest中的现有打包测试只验证Python桌面包|

## 尚未完成的本地兼容项（不归咎于宿主）

旧版独立SSE endpoint/OAuth、MCP非文本结果专用渲染、头像上传编辑控件、完整上游prompt能力模板、迁移后共享mcp.json自动导入、Windows ACL提示与可信网络审批未完成。已完成的本地路径并不覆盖这些子项；相关行保持部分实现。

## 视觉验收方法

`runtime-*.png`是实际offscreen渲染，均1280×820，不冒充真实WM。对历史截图直接比较的`runtime-pixels.log`包含身份来源变更导致的Assistant名称和相对时间变化，因此不能据此声称几何回退。

另用真实基线commit c82d564c598dc680750346bf512bcf4efdf1156a的完整app/src解包到.tmp/plugin-baseline，在同一隔离夹具下分别运行基线与改后代码；fixture的旧/共享persona文件内容一致，时间固定。`pair-before-*.png`与`pair-after-*.png`为这组受控比较，未修改生产身份文件。具体像素数见pair-pixels.log；新增设置导航和模型入口是预期差异。

## 最终验收数字

|验证|真实结果|rc|原始日志|
|---|---|---|---|
|本轮运行链路针对性|24 passed / 0 skipped|0|runtime-target-final.log|
|全量pytest（app/tests是仓库全部测试目录）|1390 passed / 9 skipped|0|final-all.log|
|全部QML用例|207 passed / 0 skipped|0|final-qml.log|
|已有压缩/取消/附件/交付/策略针对性|115 passed / 0 skipped|0|features.log|
|应用未接入的Studio契约|0 passed / 4 skipped|0|contracts-final.log|
|85行清单核对|85/85，同顺序，终态齐全|0|report-evidence-check.log|

全量9个skip包含4个明确未验证的Studio契约声明，其余为已有用例跳过；不把skip计入通过。

受控比较（基线→改后）：chat 0→0变化像素（0%）；General 0→1266（0.120617378%）；Models 0→3506（0.334032012%）。旧区域变化为0，差异仅新增设置导航与Models自定义网络入口。所有页面1280×820。截图：pair-before/after-chat.png、pair-before/after-settings-general.png、pair-before/after-settings-models.png；新页runtime-settings-custom-model.png、runtime-settings-mcp.png、runtime-settings-identities.png；审批窗runtime-interaction.png。图片全部为offscreen，不是WM/macOS证据。现有环境CJK缺字未修复。

结束时deva工作区观察到5个已跟踪文件有改动：apps/web/README.md、build.mjs、package.json、server.mjs，以及暂存删除src/web/favicon.svg。先前记录只有其中3个；期间出现额外修改。本任务只读参考该仓库，没有写入、提交或回滚这些文件。原始状态见deva-status-final.log。

最终push核对见runtime-publish.log与runtime-push.rc。后者在提交之后生成，因此属于工作区交付证据，不能要求当前提交包含自己的hash。
