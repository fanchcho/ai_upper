# Git 面板与缺密钥警告显示修复

基线：`dd3f91ebf411c74aa3957f46866a486a2bd28cdf`，develop；开始时工作树为空。本轮仅修这两个显示问题。deva 全程只读；未改 Theme token、依赖 pin、既有测试或历史提交。所有应用数据在 `/tmp/ai-upper-git-display-*/home`。最终提交和远端回读见本轮回执。

## 截图与源码定位

用户 A：`/home/agent/.hermes-web-ui/upload/default/dcf8eecef6de5557.png`；B：`/home/agent/.hermes-web-ui/upload/default/84978b1ef406aa95.png`。截图布局和错误字符串与移植版源码及基线渲染吻合。原图 A 实际1134×140，B实际1022×1596（user-images.json含SHA256）；本轮按用户明确指定的1025×1746输出目标交付，未把原图尺寸写成该目标值。定位命令：

```sh
rg -n '丢弃全部|AI 提交信息|已启用但未配置密钥' app/src/qml app/src/locales
```

修复后 `GitPanel.qml:103/116` 分别对应丢弃与 AI 按钮；`SettingsModal.qml:895/918` 是警告组件及文案绑定，文字在 `app/src/locales/zh-CN.json:816`。基线 Git 的未定制 `TextField` 在 105/106/123/133/134 行；对象数组 `.join()` 在 129 行。现在字段使用 `SettingsField`，提交读取 `short` 和 `subject`。

B 在 Linux 默认样式下表现为白色输入框，尺寸为 24 或 26px；用户 macOS 图是原生样式的残缺背景。**本轮没有 macOS 宿主，不声称复现了 macOS 的实际绘制**。修复去除了这几个输入框对平台默认样式的依赖。

## 原版依据（/home/agent/shared_workspace/deva/apps/desktop/src/renderer/src 下）

| 对象 | 原版依据 | 本轮处理 |
|---|---|---|
| 缺密钥条件 | `features/settings/ModelSettings.tsx:477-483`，enabled && !hasKey | 真实启用 provider p1，删除真实隔离 vault 的密钥；重新创建 SettingsService/SecretsVault 验证 enabled=true、hasKey=false |
| 警告颜色 | `styles/app.css:4929-4941` | 8% warning 背景不改；边框由错误的透明 warning 改成 warning 40% + border 60% 的不透明 sRGB 混色 |
| warning token | `styles/tokens.css:65/133` | 浅 #d9860b、暗 #fcc419，未改 token |
| 警告正文 | 同上 `.provider-warn {color:var(--warning)}` | 暗色恢复 warning；浅色正文用现有 fg=#1f1f24，详见可读性取舍 |
| 面板/分隔线/正文三级 | `styles/tokens.css:41-54/109-122` | Git bgElevated、状态区 bgPanel、边线 border/borderStrong、正文 fg、次级 fgMuted，未重新调色 |
| 输入框 | `styles/app.css:4079-4094`，项目现有 `SettingsField.qml:1-23` | 使用现有 Basic 控件：完整背景、1px 描边、8px 内边距、fgMuted 占位符、主题色选区及可见文本光标。宽度改由 RowLayout 分配；高度与邻按钮统一34px（tokens.css:33 的 control-h），不照搬原版独立 input 的32px及 button的30px |
| 按钮三种变体 | `styles/app.css:2550-2579` | primary 是 accent 底/边和 accent-fg；danger 是 danger 实色底/边和白字；ghost 无底无边；disabled opacity=.45 |
| 身份保存 | `redesign/GitIdentityForm.tsx:61` | primary |
| AI 生成/停止 | `redesign/GitWidget.tsx:768-783` | ghost；Fetch/Pull/Push 保留次级操作，未随意设为主按钮 |
| 其他 Git 操作 | `redesign/GitWidget.tsx:240` 分支 prompt；`:433-435` fetch/pull/push 菜单；删除分支 `:322-334` danger confirm | 原版不是此整块面板。当前内联创建/添加复用其确认按钮的 primary，删除/丢弃用 danger。未声称原版有同名同布局面板 |
| 提交字段 | 移植版 `mvvm/services/git_service.py:175-187`；桥 `qml_shell.py:2134` | 原始 Git 返回对象 short/subject，不能直接 join 对象。现在每条展示短 hash · subject，空库明确“暂无提交” |

原版 CSS 实际用 Electron 33.4.11 / Chromium 130.0.6723.191 渲染控件样本，输出 `original-css-{dark,light}.png/.json`。这是**原版 CSS 的隔离控件样本，不是原版完整客户端状态**；没有改动 deva。其输入/按钮样本尺寸和字体环境不同，仅用于核实颜色与变体，不声称像素闭环。渲染 exit=0；DBus/GTK 缺会话和 schema 的非致命日志见 `original-css-render.log`。

## 真实渲染与交互

完整 Main.qml + ShellBridge + ChatHost 装配，Qt offscreen/software，DPR=2，窗口1280×1060逻辑像素。应用最小宽度940，不伪称它在512px窗口完成布局；保存完整2560×2120图，并裁切**1025×1746原像素区域，不缩放**，符合用户指定的输出目标尺寸；不是对原图1022×1596进行缩放。基线与修复后相同数据、同字体、同窗口/裁切坐标。警告裁切左上(936,200)，Git裁切左上(836,200)，全部全图保留用于复核。另提供 `before/after-{dark,light}-warning-strip.png` 作为警告条局部原像素裁切。

| 主题 | 修改前 | 修改后 | 真实输入及 Fetch 回显 |
|---|---|---|---|
| 暗 | `before-dark-git.png` / `before-dark-warning.png` | `after-dark-git.png` / `after-dark-warning.png` | `after-dark-git-interacted.png` / `after-dark-git-focused.png` |
| 亮 | `before-light-git.png` / `before-light-warning.png` | `after-light-git.png` / `after-light-warning.png` | `after-light-git-interacted.png` / `after-light-git-focused.png` |

`after-{dark,light}.json/.log`：真实鼠标选中字段，逐键输入、点击按钮，调用真实 Git 服务。没有替换 Git 回调；本地裸仓库 remote 是**本地 fixture，不是公网服务成功态**。未执行模型回合，构建装配的测试 transport 未消费。

- 五个字段：输入 Verified User、verified@example.invalid、display-check、mirror、真实临时裸仓库路径。
- 重新启动 Git 子进程读 `.git/config`：身份一致；`git branch --list` 存在并选中 display-check；`git remote -v` 包含 mirror 与 origin。
- 点击 Fetch：真实 `git fetch`，新生成 `.git/FETCH_HEAD`；内含 `14debe2baa41a9b8076e864aa34aff0e4c35ce92`，UI 回显 `Fetch 完成`。记录原文见 JSON。只验证 Fetch，未冒领 Pull/Push 的本轮交互验证。
- 所有四份基线/修复数据使用固定 author/committer 时间，真实提交 `14debe2 · Display fixture initial commit`。修改前对象字符串、修改后字段字符串都来自同一真实 commit。
- 切到新建的真实空仓库并点击刷新：`最近提交：暂无提交`，`after-*-git-empty.png`。
- 原来身份名/邮箱/分支/remote名/URL高度24/24/26/26/24；现在全是34，邻接按钮也是34。480px面板时宽149/223/218/106/192；扩到560px后为181/271/298/135/243，证明不是固定窄块。
- 聚焦截图能看到实际文本光标及 accent 边框。输入文字从磁盘独立读回，不仅断言 QML property。

## 固定坐标采样与对比度

原始值和**全部逐点坐标**见 `pixels.json`；坐标均为完整 PNG 的物理像素。固定点在前后相同；对移动了的控件边缘另记录实际几何采样点，未把背景误叫成边框。

| 采样项（全图 x,y） | 暗：前 → 后 | 亮：前 → 后 |
|---|---|---|
| Git 面板底 (870,600) | #2a2a2e → #2a2a2e | #ffffff → #ffffff |
| 状态列表底 (900,460) | #252528 → #252528 | #f7f7f8 → #f7f7f8 |
| 状态列表边/分隔 (880,500) | #2f2f33 → #2f2f33 | #e6e6ea → #e6e6ea |
| 警告标题下分隔 (1200,806) | #2f2f33 → #2f2f33 | #e6e6ea → #e6e6ea |
| 输入底 (1100,910) | #ffffff → #2a2a2e | #ffffff → #ffffff |
| 输入左边 (880,900) | #ababab → #3d3d42 | #ababab → #d5d5db |
| 次级按钮边 (1200,830) | #3d3d42 → #3d3d42 | #d5d5db → #d5d5db |
| 警告底 (1100,844) | #363227 → #363227 | #f5efe6 → #f5efe6 |
| 警告边 (1100,832) | #7b6422 → #816b29 | #ebca99 → #e1c091 |
| 占位符实际笔画（JSON给精确点） | #808080 → #a1a1aa | #808080 → #5c5c66 |
| 警告正文实际笔画（JSON给精确点） | #a1a1aa → #fcc419 | #5c5c66 → #1f1f24 |

按 WCAG sRGB 相对亮度公式计算，取实测纯色笔画与背景，不把抗锯齿边缘当正文色：

- 占位符：暗3.949→5.577:1，亮3.949→6.608:1。
- 警告正文：暗4.989→7.945:1，亮5.781→14.356:1。
- **明确取舍**：原版浅色 warning 字 #d9860b 对实测底 #f5efe6 只有2.494:1，达不到普通文字4.5:1。本轮按用户可读性要求，用现有 fg 正文，仍保留 warning 图标/底/边；不称浅色警告文字与原版逐色相同。
- 原版的暗橄榄底本身并非移植错误，8% warning 叠在 bgPanel 的真实结果如此；本轮保留，不随手改色。

## 共用组件与影响面

`SettingsField.qml` 已有正确的 Basic 实现，本轮直接复用而不更改它，所以原先使用它的页面无代码变化。`GitPanel.qml` 的 Popup/TextArea 也明确用 Basic，避开 macOS native control 的背景约束。仅 Git 页调整行布局、34px高度、提交映射、成功回显。

`SettingsButton.qml` 统一修正 primary 边、danger实色、disabled透明度，增加ghost。普通启用的次级按钮底/边/文字及几何不变。现有调用页面包括 BotDetail、PluginSettingsPane、ScheduledTasks、TurnListPopup、PlanCards、RewindPanel、Main、DecisionProviders、PhonePane、RemoteBots、PersonaRoster、ProfilePanel、SessionFilter、SettingsModal、TerminalPanel、ExtensionDetail、ComposerCapsules、AgentCards。受视觉影响的是选用 primary/destructive 的控件及禁用态，非所有页面整体变色。除 Git 外现有 destructive 调用仅 PluginSettingsPane 的 MCP 删除。没有改已验收页面的 token 或布局。

`after-{dark,light}-bots-shared-buttons-full.png` 另外保留共用控件真实页面渲染；全量回归覆盖已有页面的行为断言。**没有逐页重拍所有已验收页面，也不声称验证了 macOS 成功态**。采集窗口退出时偶有原有 `Main.qml:69 ... saveError of null` 日志，未造成采集失败，原文保留。

## 复跑入口

从新仓库目录执行，全部用隔离目录：

```sh
AI_UPPER_HOME=/tmp/ai-upper-git-display-bootstrap QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software QT_SCALE_FACTOR=2 LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" .venv/bin/python scripts/parity/git_display/interaction.py after dark
# 同上，将dark改为light
AI_UPPER_HOME=/tmp/ai-upper-pixels LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" .venv/bin/python scripts/parity/git_display/pixels.py
python3 scripts/parity/git_display/reference.py
```

`before-*` 是修改应用代码之前捕获的基线，不应在新代码上用 before 标签覆盖。渲染工具依赖本机已存在的 `.tmp` Qt/Electron/字体环境，未更改仓库依赖 pin。证据源脚本与输出均提交；仅临时运行数据留在隔离目录。

## 全量回归与提交

```sh
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-git-display-tests-XXXXXX) QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONFAULTHANDLER=1 .venv/bin/python -m pytest app/tests -q
```

原始 `pytest-full.log` 末行：`1486 passed, 9 skipped in 557.93s (0:09:17)`；failed=0，日志中没有段错误。**最终工具会话返回143，不能据通过摘要声称进程正常退出0；本轮保留为“全量断言通过、退出过程未归因”。** 未用重跑覆盖首次回执。既有测试文件未修改，未预载Qt绕过问题。当前应用三文件SHA256记录在 `verification.json`，可与提交对象复核测试所对应代码。

新增证据进入索引后，补跑索引路径约束 `app/tests/test_app_home.py -q`：18 passed in 0.34s，退出0。没有修改断言。

推送原文与远端回读另保留在 `.tmp/git-display/push.log` / `remote-after.txt`，最终回执附 SHA。

## 未完成／未验证

- macOS 原生宿主的修复后真实渲染未验证；本轮验证的是Linux Qt 6.11.2、Basic控件、DPR2。没有将Linux成功冒充macOS成功。
- 原版完整客户端与此Git整块面板同状态截图未完成：原版不存在这套同名同布局面板，本轮用其Git身份表单/菜单/提交弹窗及真实CSS样本取规则。
- 浅色警告文字不是原版黄色逐色复制，因其2.494:1不满足可读性要求而使用既有fg；这是明示取舍，不声称该文字像素完全一致。
- 其他历史环境、像素与崩溃边界本轮没有重试或升级状态；本轮全量通过不构成历史崩溃根因已解决。

