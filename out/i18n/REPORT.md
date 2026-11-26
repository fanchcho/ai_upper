# ai_upper 多语言修复与验收记录

## 结论与验收边界

“界面只有英文”的直接原因已经修复：QML 的静态文案未接翻译、语言切换缺少属性通知、未设置 locale 时实际固定返回英文。现已接入 deva 的双语资源，设置和主界面能够即时切换并持久化；原有主题 token 未回退。

**不能把本报告理解为“全仓库所有 Python / tools 文案均已翻译完毕”。** 本次完成了 QML 界面及已连接的 Python 设置、会话、附件、工作区提示等路径；底层工具运行时、旧 QWidget 界面和构建 CLI 中仍有未迁移的字面量，详见剩余项。本轮按要求提交已验证修复与证据，但全量目标仍需继续。

## 要求清单

- [x] 修复前 HEAD / 远端 / 工作树对账，保留主题提交。
- [x] 只读核实 deva 的语言集合、加载机制、设置顺序、资源键数。
- [x] 迁移全部 deva 语言资源，保留上游已有键值；修复上游一个英文缺键。
- [x] QML 静态文案与设置/导航/发送按钮/会话列表即时切换。
- [x] 首次按系统语言选择，已保存值优先，写入 config.json 的 locale。
- [x] 模型/用户正文不翻译；应用角色标题、附件标签按语言生成。
- [x] 中英 × 明暗 × 设置/主界面，共 8 张实际 QML 截图。
- [x] 当前资源表缺键为零、引用缺键为零；空 tagline 为原版设计。
- [ ] 所有 Python / tools 用户可见错误与旧界面全部迁移并逐项验收。
- [ ] 工具卡片各种成功/失败/审批状态逐语言截图验收。
- [x] 全量 pytest：1406 passed、9 skipped、0 failed，退出码 0。
- [x] 代码与证据分单元提交；远端核对记录见 push.txt（交付时生成）。

## 第 0 步：基线证据与根因

`initial-git.txt` 保存修改前第一条工具命令的实际输出：

```text
$ git log --oneline -8
ccca79e fix(settings): bind all controls to deva light and dark themes
315e407 docs(audit): record workspace mount screenshots and full verification
6e59c78 fix(qml): contain file icons and persist picked workspaces
b011b65 docs(audit): record three rejected cold rendering candidates
055db71 docs(audit): close rejected idle prefetch investigation
cf960b8 docs(audit): reject cold attachment regressions with measured evidence
e1fbf80 docs(audit): verify cold and cached session frames and bounded memory
b2de19d test(qml): await interaction prompt readiness
$ git status --porcelain
<空>
$ git rev-parse HEAD
ccca79e4523c29ac6f2a527ecc95faf1b9d698ff
$ git ls-remote origin refs/heads/develop
ccca79e4523c29ac6f2a527ecc95faf1b9d698ff refs/heads/develop
```

基线和远端一致。没有重置历史；本次代码提交为 `f4317ef`，其祖先包含主题修复。

根因证据以基线文件为准，可运行 `git show ccca79e:app/src/qml/SettingsModal.qml` 和 `git show ccca79e:app/src/qml_shell.py`；原始输出在 `audit.txt`：

| 基线文件:行 | 观察 |
| --- | --- |
| app/src/qml/SettingsModal.qml:69、128、297、311、319 | Settings、General、Language、Theme 等直接写死英文 |
| app/src/qml/SettingsModal.qml:312–314 | 实际已有语言项，顺序是简体中文、English；调用 setLanguage |
| app/src/qml_shell.py:446–460 | language() 读 locale、兼容 language，但最后直接 return "en"；注释称跟随系统却未实现 |
| app/src/qml_shell.py:541–547 | setLanguage 写 locale，然后只 _publish；没有语言属性通知 |
| app/src/qml_shell.py:92 | SETTINGS_LABELS 已有中英字典；不是“完全从未移植中文” |
| app/src/mvvm/services/settings_models.py:21 | 模型设置已有 MODELS_TEXT 中英投影 |
| app/src/mvvm/services/settings_service.py:79、94 | 从 AI_UPPER_HOME/config.json 读写；配置服务本身不是翻译引擎 |

基线 `git ls-tree -r --name-only ccca79e app/src tools` 输出保存在 `baseline-inventory.txt`：没有独立的 i18n/locale 资源目录，已有翻译散落在 Python 字典中。启动读取语言配置，但无法翻译写死的 QML 文案。

`qml-inventory.json` 列出基线可见文本/回退文本的 104 次出现，分布 5 个 QML 文件，去重为 86 个字符串；保留文件、行号和原文，已排除 SVG path 和字体名。动态模型文本、用户名、文件名不在这个计数中。

Python 侧 AST 清单 `baseline-python-candidates.json` 和 `python-literal-candidates.json` 均带文件:行号。**这是候选字面量统计，不是已人工确认的 UI 文案总数**；包含日志、模型提示词、开发工具报错和测试协议片段。基线为 1357 条候选、85 个文件，数量见 `baseline-counts.txt`，最终为 1338 条候选、86 个文件，见 `coverage-summary.txt`。完整“全部用户可见字符串”人工分类尚未完成，不拿候选数冒充。

## deva 的真实能力

只读参考提交：`6c83301c182db8bb6d9b4c5cb99f5869046fa595`。`audit.txt` 保存源码带行号快照及参考仓库状态；本轮未写入 deva。

根目录 `/home/agent/shared_workspace/deva/apps/desktop/src/renderer/src/`：

| locale | 语言自称 / 顺序 | 原版键数 | 资源路径 |
| --- | --- | ---: | --- |
| zh-CN | 简体中文 / 第 1 项 | 1383 | i18n/messages.ts:12 的 zhCN |
| en | English / 第 2 项 | 1382 | i18n/messages.ts:1579 的 en |

确切支持列表是 `i18n/i18n.tsx:18` 的 `['zh-CN', 'en']`，没有第三种。选项自称在 `redesign/SettingsPane.tsx:133–134`；设置位置在 General 的第一行。

加载使用静态 import `messages`，React I18nProvider 创建 locale state，useMemo 构造 t，组件通过 useI18n 读取。首次选择优先级是 `~/.deva/config.json.locale` → localStorage `deva.locale` → navigator.language；系统字符串转小写后以 zh 开头映射 zh-CN，其余映射 en。显式切换 await config.set，更新 React state 和 localStorage，因此即时生效。

**缺键不回退英文**：`i18n/i18n.tsx:46–54` 的 resolve 直接返回 key 字符串。本次 Python translate 保留这一规则。无 ICU/plural 引擎；`{name}`、`{count}` 等由调用点 replace 插值。两个资源有意使用不同参数：`extensions.rolesSummary`、`chat.deliver.collapsedMany` 中文用总数 n，英文用剩余数 rest；调用方必须提供对应参数，不能机械认定翻译错误。日期部分由各组件使用 Intl/toLocaleString，例如 `redesign/shell-common.tsx:117、124`；不是 t 的统一功能。

`deva-coverage.txt` 为真实提取统计：英文原版缺 `chat.setup.change`，本次补为 Change；两种语言所有原版已有键值均保持不变（changed upstream values: []）。

## 实现与验证方法

- `app/src/locales/{zh-CN,en}.json`：原版完整扁平键表，加 native.* 本地功能文案。
- `app/src/native_i18n.py`：加载资源、缺键返回 key、占位符替换、已知应用错误的本地化；外部诊断原文保留。
- `app/src/qml/I18n.qml` 和 qmldir：通过 shellBridge.locale 通知建立翻译依赖。
- `app/src/qml_shell.py`：localeChanged 信号与 Property，系统 QLocale 默认映射，保存成功后通知并刷新界面；工作区提示、文件选择器、插件设置错误和状态文案翻译。
- `Main.qml`、`SettingsModal.qml`、`PluginSettingsPane.qml`、`InteractionPrompt.qml`、`ContextRing.qml`：导航、按钮、空态、右键菜单、确认框、设置等翻译绑定；模型详情切换语言时刷新投影。
- `app/src/qml_shell_sessions.py`：未命名会话、应用角色标题和附件说明；模型/用户正文不经过翻译函数。
- `app/tests/test_native_i18n.py`：键覆盖、缺键规则、插值、系统 locale 模拟、真实 QML 窗口切换、保存值重新读取、正文原样保留。
- `tools/audit_i18n.py`：生成键覆盖与文件行号清单，可复现执行。

首次选择中文系统（包含 zh_TW）→ zh-CN，其他系统 → en。已有 locale 优先；继续兼容移植版旧 language 键。Qt 壳没有浏览器 localStorage，使用原有 config.json。选项顺序与语言自称保持原版。Theme.qml 未改，主题测试使用同一窗口验证。

最终资源统计：每语言 **1453 键**，缺键 0，QML 引用缺键 0；98 个翻译调用点分布 5 个 QML 文件。`app.tagline` 两边均为空，原版设计，不属于漏翻译。原样保留的 Deva、MCP、URL、模型 ID、用户输入、角色/文件名称不算漏翻译。**此统计只证明资源覆盖，不证明 Python 候选清单的每一条都已迁移。**

命令与结果在 `coverage-summary.txt`：

```sh
.venv/bin/python tools/audit_i18n.py
```

截图命令使用 `I18N_TEST_FONT=$PWD/.tmp/theme-settings/NotoSansCJKsc-Regular.otf` 和 `I18N_EVIDENCE=$PWD/out/i18n` 运行 test_native_i18n。字体从已有工作区文件加载，仅为无中文系统字体的容器提供可见字形；没有伪造截图或替换文本。

## 截图绝对路径

- [contact-sheet.png](/home/agent/shared_workspace/ai_upper/out/i18n/contact-sheet.png)
- [en-dark-chat.png](/home/agent/shared_workspace/ai_upper/out/i18n/en-dark-chat.png)
- [en-dark-settings-general.png](/home/agent/shared_workspace/ai_upper/out/i18n/en-dark-settings-general.png)
- [en-light-chat.png](/home/agent/shared_workspace/ai_upper/out/i18n/en-light-chat.png)
- [en-light-settings-general.png](/home/agent/shared_workspace/ai_upper/out/i18n/en-light-settings-general.png)
- [zh-CN-dark-chat.png](/home/agent/shared_workspace/ai_upper/out/i18n/zh-CN-dark-chat.png)
- [zh-CN-dark-settings-general.png](/home/agent/shared_workspace/ai_upper/out/i18n/zh-CN-dark-settings-general.png)
- [zh-CN-light-chat.png](/home/agent/shared_workspace/ai_upper/out/i18n/zh-CN-light-chat.png)
- [zh-CN-light-settings-general.png](/home/agent/shared_workspace/ai_upper/out/i18n/zh-CN-light-settings-general.png)

逐张检查 1280×820 设置与主界面：设置标题、导航、语言和主题分段无重叠；英文会话长标题使用原有 ellipsis，未覆盖右侧时间。截图使用空内容会话，因此不证明复杂工具卡片或长错误提示的布局。macOS、真实系统 locale 改变、Windows 原生文件选择器、发布打包后的字体和资源加载均未验证。

## 测试原始记录

- `initial-test.txt`：补入仓库已有 libEGL 路径后的主题回归，1 passed。
- `native-test.txt`：早期双语真实窗口验证，2 passed；后续新增正文保留测试纳入 focused。
- `focused.txt` / `focused.exit`：44 passed in 68.46s，退出码 0。
- `pytest.txt` / `pytest.exit`：完整测试日志与真实退出码，结束后追加摘要。
- `verify.sh`：全量可复现命令。AI_UPPER_HOME 始终显式设为 /tmp/ai-upper-i18n-test；最终测试夹具 home 位于 /tmp 的 basetemp。最早主题探测使用工作区 .tmp/i18n/pytest，夹具覆盖后的 home 因而在该目录；发现后后续验收统一改到 /tmp。没有启动默认真实用户数据目录。

初次主题测试报缺少 libEGL.so.1，随后设置 LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu。首轮键表检测发现上游英文缺键和两处总数/剩余数占位差异，均按前述方式处理；未把失败运行报告成通过。

## 未完成项与未验证项

1. `app/src/mvvm/views/transcript_render.py:19–28` 的旧工具卡角色和成功/失败标签、旧 QWidget 设置界面，以及 tools 下构建/验证 CLI 文案仍未整体接入新翻译服务。QML 路线 B 不调用所有旧界面路径，但本轮用户要求覆盖 app/src/** 与 tools/**，因此明确保留未完成项。
2. Python 候选清单尚未逐条按“真实用户界面 / 模型提示词 / 外部诊断 / 开发工具”完成审查，不能声称全部用户可见文案漏翻译为零。
3. 工具卡、长错误、复杂对话框的逐语言视觉验收未完成；八张必需页面截图不能替代这些状态。
4. 测试模拟 QLocale.system 返回值，不等于真实操作系统切换语言。macOS、Windows 原生渲染与发布包未验证。
5. 原生 CJK 字体依赖实际平台字体；本容器截图加载指定字体。没有声称所有部署环境都有中文字体。


## 后续验证修正

- 第一轮完整测试实际为 **1 failed, 1403 passed, 9 skipped in 359.63s**，原始输出在 `pytest-first.txt`。测试运行管理器结束父 shell 的退出状态为 143，因此该次没有独立 pytest.exit；不能把父 shell 状态冒充 pytest 退出码。
- 失败是旧工作区测试在英文界面下硬性期待中文。已显式选择 zh-CN 保持该用例的中文语义；`mount-retest.txt` 为 **2 passed，退出码 0**。
- 后续发现文件选择器用例同样固定期待中文筛选器，已显式选择 zh-CN；`files-retest.txt` 为 **29 passed，退出码 0**。中间一次全量运行已主动终止，保留 `pytest-interrupted.txt` 和退出码 **143**，不计作通过。
- `3a1e626` 补充 memory egg loader 的 read_data 资源读取通路，避免 Windows 内存包缺少 ResourceReader 时无法加载 JSON。`resources-test.txt` 为 **3 passed, 1 deselected，退出码 0**。这是加载协议单测，不是 Windows 发布包实测。
- 最终完整测试针对 `3a1e626` 开始，期间不再编辑应用实现。

## 同一设置面板即时更新证据

`live_settings_check.py` 保持 settingsModal 对象不销毁、不切页，在同一窗口连续 zh-CN → en → zh-CN。每次断言导航标题、发送按钮、未命名会话标题已更新，设置对象身份不变。`live-settings.txt` 实际输出：

```text
zh-CN same settings object; navigation, send and session title updated: PASS
en same settings object; navigation, send and session title updated: PASS
zh-CN same settings object; navigation, send and session title updated: PASS
```

`live-settings.exit` 为 0。运行使用与 verify.sh 相同的环境变量，命令为 `.venv/bin/python out/i18n/live_settings_check.py`。

## 最终完整测试

```text
$ bash out/i18n/verify.sh
1406 passed, 9 skipped in 349.46s (0:05:49)
$ cat out/i18n/pytest.exit
0
```

应用代码状态为 `3a1e626`，原始全量输出保存于 `pytest.txt`。本次完整运行无失败。9 skipped 按测试环境条件跳过，不表示对应平台实测通过。

本报告、原始输出、逐条候选清单和 PNG 随证据提交一并保存。`push.txt` 在推送后生成，记录远端 develop 与本地最终 HEAD 一致及工作树干净；它自身是本地交付核验文件，不再递归提交。
