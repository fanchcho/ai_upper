# A/B/C 增补交付报告

本轮 ai_upper 基线：74384d0613722633b1be69d8e733f19381d09ba7。上一轮无边框已实现并验证。

## A — 已完成代码实现与分支测试；macOS 未真机验证

依据只读 deva apps/desktop/src/main/index.ts:85-98：overlayOptions 仅为 Windows/Linux 返回值，macOS 返回 undefined；112 使用 titleBarStyle:hidden，118 指定 trafficLightPosition={x:9,y:13}。不是 hiddenInset。

Main.qml:20 起，Qt.platform.os === "osx" 分支不使用 FramelessWindowHint；使用 WindowTitleHint/SystemMenuHint/MinMaxButtonsHint/CloseButtonHint 保留系统按钮，并用 Qt 6.9+ ExpandedClientAreaHint / NoTitleBarBackgroundHint 扩展内容和透明标题背景。QML 右上按钮 visible=false。macOS 图标栏为72px，头像/导航下移40px，顶端40px不参与拖动，自绘边缘缩放禁用。Linux/Windows 的56px栏和右上96×40位置不变。

官方API依据：https://doc.qt.io/qt-6/qt.html#WindowType-enum 。Qt/macOS 决定原生按钮的实际位置；未通过 Cocoa 单独重定位到 Electron 的精确 (9,13)，该几何未验证。没有把 Linux 模拟分支当作 macOS 截图。

a-tests.log：5 passed，0 skipped，rc=0；含 Linux/macChrome 两种初始属性分支断言，macOS 不绘制 QML 三按钮且保留原生 flags。现有 Linux 三按钮/命中用例继续通过。macOS 真机显示、拖动及原生按钮行为未验证：当前主机是 Linux。

## B — 部分完成：真实 WM 排查完成，重影未复现，未修复

使用 Xvfb :102 + Openbox + xcb，应用读取隔离 AI_UPPER_HOME。b-wm-capture.log 记录四页几何均为 (160,140,1280,820)。每页都有整桌面 `<page>-wm.png` 与相同客户坐标 (0,0,356,220) 的2倍 `<page>-icons-2x.png`。

实测页：chat、settings-general、settings-models、empty。查看导航和会话头像裁剪，未发现双份图标/拖尾；设置页底层变暗是 modal 遮罩，不能当作残影。源码 ThreadRow.qml:64 的单个 Avatar → Avatar.qml:24 的单个 Image；Icon.qml:29 的单个 Shape，子路径分槽来自 IconData，不是第二份完整图标。这些只能说明所查区域和页面没有复现，不能证明所有图标无问题，也不能排除 GPU/平台缓存问题。未修改图标渲染，未生成虚假的修复前后对比。剩余需要用户指出具体图标位置或出现条件，才能锁定同坐标重影。

## C — 部分完成：全文件对账 + 配置冲突保护合入；不是全量插件移植

当前只读 deva HEAD：bfbfee7aa6a549ce0ead101f2eed8ec093a12d45；最近15条提交见 baseline.log。
根 package.json 没有 version；apps/desktop/package.json:3 为0.1.16；plugins/deva-agent/package.json:3 实际为0.8.20（提交标题0.8.18不作为版本依据）。
初次迁移基线109937f不是最近对齐点。out/latest-parity/REPORT.md:728-729 明确记录最近对齐 HEAD=065657976c611a462d9844eed3ebab9575233af9；本轮按它对账。current-changed-files.tsv / current-numstat.tsv 保存完整提交差异。desktop.diff 长度为0：新增提交没有更改 Electron 桌面/QML 对应 renderer 的几何、配色和文案，不能捏造新的桌面UI变更。

参考仓库还有3个原有 tracked 工作区修改（deva-status.log）：apps/web/build.mjs、package.json、server.mjs；deva-working.diff 保存完整diff。它们将web静态资源复制到dist/web、服务端改读dist/web、web版本变0.1.17；QML没有Node静态资源服务器，无需移植，未改动参考仓库。

实际合入：新版 desktop-models.mjs:127-130 / deva-fs.mjs:119-145 的 expectedRaw 语义——写配置前检查磁盘内容是否仍是读取的快照。ai_upper SettingsService 增加冲突检查；QML模型/思考等级选择先写配置成功再更新会话，冲突返回False，保留外部数据与会话状态。是已有QML设置链路的行为修复，不新增UI、不搬React/Electron代码。此检查不是跨进程锁，读检查与原子替换之间仍有竞态窗口，不能声称强事务隔离。

c-before.log 记录改前复现：外部模型变更被覆盖，pytest 1 failed。c-tests.log 验证冲突拒写、重载后成功、含冒号模型引用保留、QML模型和思考等级冲突不修改会话。其余测试终态见 regression.log 和后续 verification 日志。

剩余功能：Studio MCP管理页/凭据桥接、插件身份与persona编辑器、插件压缩/检查点/取消恢复、附件交付、子代理/记忆存储合约、SDK/安装器完整集成；未实现插件等价界面/宿主API，也未验证Studio联网行为。完整逐文件表如下；“未实现”指新版插件合约，不能据此断言 ai_upper 完全没有同类本地功能。

| 新版变更文件 | ai_upper 当前证据/实现状态 | 是否需要继续改 |
|---|---|---|
| M `plugins/deva-agent/.gitignore` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/AGENTS.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| A `plugins/deva-agent/INSTALL-WINDOWS.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| A `plugins/deva-agent/INSTALL.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| A `plugins/deva-agent/LICENSE` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/README.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/client.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/contracts/plugin.json` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/docs/CONTRACTS.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/docs/FIELD_REFERENCE.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| A `plugins/deva-agent/docs/OPERATIONS.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/docs/SDK-NOTICE` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/docs/STUDIO_CTX.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/docs/STUDIO_RETURNS.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/lib/agent.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/approval.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/attachments.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/checkpoint.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/lib/commands.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/compression.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/custom-model-network.mjs` | 本地模型菜单已有 app/src/qml_shell.py:867；新版Studio凭据/共享模型合约未实现 | 需要后续集成；不得让QML直接读取Studio密钥 |
| A `plugins/deva-agent/lib/desktop-models.mjs` | 部分合入：app/src/mvvm/services/settings_service.py:85；app/src/qml_shell.py:970；其余插件路由/权限未实现 | 冲突保护已改；插件模型桥接仍待实现 |
| A `plugins/deva-agent/lib/deva-fs.mjs` | 部分合入：app/src/mvvm/services/settings_service.py:85；app/src/qml_shell.py:970；其余插件路由/权限未实现 | 冲突保护已改；插件模型桥接仍待实现 |
| A `plugins/deva-agent/lib/deva-home.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/deva-layout.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/lib/interact.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/lib/loop.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/mcp-secrets.mjs` | 未实现：QML尚无新版Studio MCP管理页/凭据桥接 | 需要后续界面与宿主接口集成 |
| A `plugins/deva-agent/lib/mcp-store.mjs` | 未实现：QML尚无新版Studio MCP管理页/凭据桥接 | 需要后续界面与宿主接口集成 |
| M `plugins/deva-agent/lib/mcp.mjs` | 未实现：QML尚无新版Studio MCP管理页/凭据桥接 | 需要后续界面与宿主接口集成 |
| M `plugins/deva-agent/lib/memory.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/model-selection.mjs` | 本地模型菜单已有 app/src/qml_shell.py:867；新版Studio凭据/共享模型合约未实现 | 需要后续集成；不得让QML直接读取Studio密钥 |
| M `plugins/deva-agent/lib/model.mjs` | 本地模型菜单已有 app/src/qml_shell.py:867；新版Studio凭据/共享模型合约未实现 | 需要后续集成；不得让QML直接读取Studio密钥 |
| A `plugins/deva-agent/lib/persona-avatar.mjs` | 本地persona已有 app/src/mvvm/services/persona_store.py:1；新版Studio身份编辑/共享合约未实现 | 需要后续集成 |
| A `plugins/deva-agent/lib/persona-file.mjs` | 本地persona已有 app/src/mvvm/services/persona_store.py:1；新版Studio身份编辑/共享合约未实现 | 需要后续集成 |
| A `plugins/deva-agent/lib/persona-store.mjs` | 本地persona已有 app/src/mvvm/services/persona_store.py:1；新版Studio身份编辑/共享合约未实现 | 需要后续集成 |
| M `plugins/deva-agent/lib/prompt.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/lib/selection.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| A `plugins/deva-agent/lib/session-identities.mjs` | 本地persona已有 app/src/mvvm/services/persona_store.py:1；新版Studio身份编辑/共享合约未实现 | 需要后续集成 |
| A `plugins/deva-agent/lib/shared-deva-model.mjs` | 本地模型菜单已有 app/src/qml_shell.py:867；新版Studio凭据/共享模型合约未实现 | 需要后续集成；不得让QML直接读取Studio密钥 |
| M `plugins/deva-agent/lib/skills.mjs` | 本地扩展已有 app/src/qml_shell.py:1010；新版插件共享技能合约未实现 | 需要后续集成 |
| A `plugins/deva-agent/lib/storage-contracts.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/lib/studio-mcp.mjs` | 未实现：QML尚无新版Studio MCP管理页/凭据桥接 | 需要后续界面与宿主接口集成 |
| A `plugins/deva-agent/lib/studio-model.mjs` | 本地模型菜单已有 app/src/qml_shell.py:867；新版Studio凭据/共享模型合约未实现 | 需要后续集成；不得让QML直接读取Studio密钥 |
| M `plugins/deva-agent/lib/subagents.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/lib/tools.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/package.json` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/plugin.json` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/sdk/NOTICE` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/sdk/docs/FIELD_REFERENCE.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/sdk/docs/STUDIO_CTX.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/sdk/docs/STUDIO_RETURNS.md` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/sdk/src/agents.ts` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/sdk/src/contexts.ts` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/sdk/src/core.ts` | 未移植：插件文档、契约或构建元数据；本轮行为见 out/chrome-upgrade/REPORT.md | 插件整体移植时评估；不是QML几何变更 |
| M `plugins/deva-agent/server.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |
| M `plugins/deva-agent/tests/agent-studio-mcp.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/agent.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/cancellation.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/client.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/completion-attachments.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/completion-recovery.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/completion-sdk.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/completion-secrets.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/completion-storage.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/contracts.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/desktop-models.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/deva-home.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/ekko-protocol.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/fixtures/README.md` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/fixtures/memory-v1.json` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/fixtures/subagents-v1.json` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/identity.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/mcp.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/memory.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/model.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/persona-avatar.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/persona-editor.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/skills.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/studio-compatibility.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/studio-mcp.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/studio-model.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| M `plugins/deva-agent/tests/subagents.test.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `plugins/deva-agent/tests/support/deva-home.mjs` | 未移植：上游插件测试/夹具；本仓库 app/tests/test_settings_external_edit.py:1 仅覆盖本轮冲突保护 | 随对应插件功能补等价测试，不直接复制JS测试 |
| A `scripts/install-deva-agent.mjs` | 未实现：该新版Studio插件/安装器合约没有对应QML实现 | 需要后续逐功能移植与验证 |

提交范围共 85 个差异文件；另有3个参考仓库原有工作区修改。所有原始输出保存在本目录。最终提交/推送核对见 publish.log（提交后生成）。

## 最终验证与交付边界

- 平台与窗口专项：a-tests.log，5 passed，0 skipped，rc=0。
- QML 全量及配置冲突单测：regression.log，204 passed，0 skipped，rc=0。
- 调整模型/思考等级的写入顺序后，重跑外部配置+QML桥接+模型选择：c-tests.log，7 passed，0 skipped，rc=0。此项是上述全量运行之后的针对性复验，不把两组数字相加冒充独立覆盖。
- SettingsService / 设置写入 / VM 回归：settings-tests.log，64 passed，0 skipped，rc=0。
- Linux 真实 WM：linux-wm-actions.log，rc=0；Normal→Iconic→Normal，位置(160,140)→(230,190)，1280×820→1370×880，最大化1600×1100后还原，关闭后应用rc=0。
- git diff --check（代码）：rc=0。

所有测试 AI_UPPER_HOME=/tmp/ai-upper-chrome-upgrade；真实窗口截图使用上一轮专用隔离夹具 /tmp/ai-upper-frameless-20261125。临时工具及捕获脚本位于本仓库 .tmp；未访问真实 ~/.ai_upper。deva 工作区原有3个修改仅取证未写入。

A 代码层交付；macOS 真机与(9,13)原生按钮像素位置未验证。B 未修复，因具体重影未复现；缺少用户具体图标坐标/触发步骤。C 仅配置冲突保护完成并验证，其余插件差异保留在表中，不宣称全量合入完成。
