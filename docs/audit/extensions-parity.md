# Settings 扩展页整体对账（2026-11-26）

**当前仍未整体对齐。** 本轮补齐可进入的技能/MCP详情、配置编辑、密钥单独加密、角色配置、确认删除及可见读取错误；原版常驻MCP连接/状态广播/重试/工具发现、角色头像多选器、详情精确版式和技能实时目录监听尚未移植完成。不得以列表合并或全量测试通过替代上述验收。

## 原版真实实现与通道（只读）

根目录 `/home/agent/shared_workspace/deva`，以下均为该根目录下文件：

|职责|路径与行号|
|---|---|
|设置扩展列表、进入时刷新、钻取导航|apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:183|
|技能/MCP两类聚合、徽标、状态注记、内置锁定|同文件:220|
|列表行结构、独立开关、角色头像、右箭头|同文件:249|
|角色头像与角色多选器|同文件:300、326|
|技能只读详情、回收站删除确认|同文件:417|
|MCP编辑器、状态、失败重试、密钥、工具|同文件:493|
|字段草稿、参数失焦提交、密钥键值编辑器|同文件:689、718|
|记录转换|apps/desktop/src/renderer/src/store/extensions.tsx:103、155、174、194、208|
|数据Provider、订阅、refresh、保存队列|同文件:223、244、265、323、509|
|前端IPC|apps/desktop/src/preload/index.ts:689、759|
|技能IPC与扫描|apps/desktop/src/main/services/skills.ts:753、328|
|MCP IPC与运行态合并|apps/desktop/src/main/services/mcp.ts:633、164、182|
|MCP文件读写与启用位|apps/desktop/src/main/services/mcp-config.ts:173、208、220|
|行布局CSS|apps/desktop/src/renderer/src/redesign/redesign.css:3308–3388|

调用链：SettingsPane → useExtensions Provider → window.deva.skills/mcp → preload ipcRenderer.invoke → skills:list/set-enabled/set-roles/remove 或 mcp:list/upsert/set-enabled/set-roles/remove/retry/set-secret/has-secret →服务扫描/配置/运行时。不是从mock目录取展示数据；mock/extensions.ts在此链路提供类型。

## 原版数据、分类、状态、排序

- 页面只列**技能和MCP**，无分类tab、无独立plugins类别。personas用于角色范围选择，不是该列表中的扩展条目；内置子智能体也不列入。
- 技能：`<DEVA_HOME或~/.deva>/skills/<id>/SKILL.md`，id为目录名；frontmatter包含name/description/trigger/allowed-tools/license/compatibility/metadata，正文为instructions；列表并不显示描述和所有frontmatter。
- 内置create-skill/create-agent/create-mcp由服务常量合成，不落盘、恒启用、置顶。同名磁盘技能不得覆盖内置；目录id为唯一身份。
- 自装技能按name.localeCompare排序，接在三项内置之后。启用位config.json.skills.enabled[id]不为false即启用；roles缺省null为所有角色。
- MCP：`mcp.json.mcpServers[id]`，配置字段name/description/transport/command/args/env/url/headers；transport为stdio/sse/http。env/headers支持字符串或secretRef对象；密钥另存加密库，不回显。
- MCP按显示名localeCompare排序，整体接在技能后。启用位config.json.mcp.enabled[id]严格为true才启用，roles在config.json.mcp.roles。
- **没有把桌面pluginScopes和mcp.json合并覆盖的原版规则。** 上轮引入的合并属于移植扩展。本轮扩展页改回原版mcp.json来源，桌面自有MCP设置页/运行时不改；两者仍是未统一的配置入口，需后续处理。
- 技能与MCP使用kind:id复合身份，同id跨类别不互相覆盖。
- 原版MCP状态来自常驻运行时：connecting/connected/error/needs_config/needs_secret/disconnected，不能从enabled推断已连接。已启用显示状态注记；error/needs_config/needs_secret使用warning色；未启用不显示列表状态注记。

## 版式、交互、错误与空态

列表无描述副标题：名称13px/600、类型徽标10.5px、内置/状态注记11px；行padding 11px 14px、gap12px、卡片1px边框+12px圆角；右侧38×22开关，内置透明度0.55且不可操作。自装行名称区是详情按钮，角色头像与15px箭头在名称区右侧，开关是独立兄弟元素。

技能详情：顶栏返回、删除图标、启用开关；标题有Puzzle图标和等宽名称；角色多选下拉含头像；正文只读Markdown占剩余高度、框内滚动。删除须确认，文件夹进入系统回收站，失败保留条目并显示错误。

MCP详情：名称只读，配置即时落盘；命令/URL/参数失焦提交；env/headers可增删行、切换明文/密钥，密钥约600ms防抖保存并有保存中/已保存/已配置反馈。支持错误后重试、工具名和描述清单。删除确认后删除注册及相关配置/密钥。

无列表新增、打开目录、导入、手动刷新按钮。新增来自对话工具/上传或直接写盘。进入页面refresh，技能目录监听持续推送，MCP订阅状态广播。不能根据其他旧扩展面板的能力给这个设置页加按钮。

原版全部items为空时显示`cf.extEmpty`（暂无扩展）；正常空磁盘仍有内置三条，所以不会进入全空态。原版读取失败部分路径静默保持空列表；本次用户明确要求可见错误，因此保留了比原版更明确的错误文本。上轮“暂无自装扩展”是我方新增，不属于原版；为满足本轮空目录可见文案要求暂保留，不能称严格像素一致。

主题token（tokens.css，浅色:40起，深色:108起）：背景面板light #f7f7f8 / dark #252528；正文#1f1f24/#e4e4e7；muted #5c5c66/#a1a1aa；subtle #8a8a94/#71717a；border #e6e6ea/#2f2f33；accent #5b5bd6/#7c7cf0；warning #d9860b/#fcc419。移植继续引用Theme，不另造配色。

## 修前/修后逐项差异

|原版行为|修前移植|本轮修后与未完成项|
|---|---|---|
|技能+MCP，内置技能先|已合并，但混入pluginScopes|扩展页MCP改为mcp.json真实注册；自有MCP页仍保留|
|MCP按localeCompare排序|casefold|QCollator(en_US)排序；跨平台ICU与浏览器非ASCII完全一致未验证|
|自装技能localeCompare|casefold|仍casefold，非ASCII排序未对齐|
|类型徽标，无tab|技能/MCP徽标|保持|
|内置锁定、不进详情|锁定|保持，服务层也拒绝编辑/删除|
|自装项详情、箭头|无入口|新增详情按钮与箭头|
|技能Markdown正文|无|新增只读Markdown文本；正文框独立滚动/标题细节尚未精确对齐|
|角色头像堆叠+多选下拉|无|角色配置可保存、共享角色可读；目前复选框布局，未实现原版头像和下拉|
|MCP命令/URL/参数编辑|无|新增，真实写mcp.json，保留其他字段|
|env/headers密钥行|无|新增字段编辑与单独加密保存、不回显；600ms保存反馈未对齐|
|启停落盘重启读回|列表支持|列表与详情写盘；写失败可见；实际鼠标及重新装配读取已验证|
|常驻连接、状态广播、重试、工具|固定未连接|仍未实现，工具空态不能视为发现结果；禁止声称运行态对齐|
|确认删除|无|MCP删注册/密钥/配置；技能QFile.moveToTrash；MCP服务测试通过，技能回收站端到端未验证|
|进入刷新+目录监听|仅进入读取|仍缺目录监听/状态订阅|
|卡片与详情精确版式|仅列表近似|列表延续旧几何，详情控件及角色部分尚非像素等价；长列表滚动未补齐|
|错误反馈|注册解析失败静默空表|新增config/mcp/技能读取错误面板；坏注册不被保存覆盖|
|空目录正常内置3条|内置3条+自装空态|保留，差异已说明|

## 新增实现与验证

- app/src/mvvm/services/extension_settings.py:10：严格读取、错误清单、详情、安全字段投影、配置更新、密钥、删除。
- app/src/qml_shell.py:1045：extensionAction结构化调用，失败返回ok=false/error；:1062列表投影。extensionsSummary仅存在于历史注释，不是有效调用链。
- app/src/qml/ExtensionDetail.qml:1：详情、返回、启停、确认删除、正文、角色、MCP字段。
- app/src/qml/SettingsModal.qml:1276：列表进入刷新、错误文本、详情钻取及开关错误反馈。
- app/src/mvvm/services/skill_store.py：坏UTF-8文件跳过，配合上层错误清单显示文件读取失败。
- app/tests/test_extension_settings.py：新建3个测试，覆盖详情与重启持久化、密钥不回显/不写明文/MCP删除、坏文件可见且不可被覆盖。

## 隔离渲染与真实操作证据

fixture采用标准skills/<id>/SKILL.md，创建alpha-review、beta-report两个测试技能，明确是结构复刻的验证数据、不是用户真实技能。三条MCP从只读~/.deva/mcp.json复制hindsight、ekko-studio-plugins、ekko-studio-use，分别设置true/false/true；未执行这些服务器命令。技能beta-report停用，alpha-review初始未设置（按原版默认启用）。注册条目不硬编码进应用。

```sh
AI_UPPER_HOME=/tmp/ai-upper-ext-dark4 \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
.venv/bin/python .tmp/extensions-parity/render.py dark fixture
```

浅色替换home和theme；空目录末尾使用empty；坏注册使用error。脚本内部设置QT_QPA_PLATFORM=offscreen、QT_QUICK_BACKEND=software，装配真实QML和ShellBridge。输出截图、日志在out/extensions-parity。

实际点击alpha-review开关输出：
`CLICK {'enabled': {'beta-report': False}} -> {'enabled': {'beta-report': False, 'alpha-review': False}}`

配置位于/tmp/ai-upper-ext-dark4/home/config.json。导出非敏感配置摘录dark-fixture-config.json:5的alpha-review=false；:10–12为MCP true/false/true。SettingsService新实例读回false，断言通过。没有修改真实用户配置。

截图：dark-fixture.png、light-fixture.png、dark-fixture-skill-detail.png、dark-fixture-mcp-detail.png、dark-empty.png、dark-error-visible.png。

并排图comparison.png复用已有原版baseline `out/final-parity/deva/settings-extensions-deva.png`，三列分别为原版浅色三内置、修前暗色fixture、修后浅色fixture。**原版截图没有相同的自装fixture，也没有暗色详情基线；该图只可对照布局，不证明同数据/同主题像素一致。** 未启动或修改原版。原版全状态同fixture并排渲染未验证，原因是本轮只复用了已有基线，没有原版可运行环境与详情基线。

## 未收口的核心项

本次仍不满足“扩展页整体对齐”：MCP运行态生命周期/重试/工具发现、原版角色头像下拉、详情顶栏/表单精确版式、目录监听、长列表滚动、技能Unicode排序和技能删除端到端尚未完成。它们是实质实现与验证缺口，不是测试通过就可以豁免的项目。任务保持open；本次提交应视为可审查的增量，不是最终验收提交。

真实临时config.json的行号证据：`/tmp/ai-upper-ext-dark4/home/config.json:22`为alpha-review=false，:27为hindsight=true，:28为ekko-studio-plugins=false，:29为ekko-studio-use=true；带行号输出保存在out/extensions-parity/config-lines.txt。

中间回归：早期全量轮次1424 passed、9 skipped、1 failed；失败为test_mount_picker_mouse_persist_cancel_and_reject检测到2个可见窗口（期望1），完整full-tests.log保留。该文件独立复跑2 passed in 13.02s，不能用独立复跑替代最终全量结论。

窗口生命周期回归：第二轮全量同样1424 passed/9 skipped/1 failed，不能归为偶发后忽略。详情原先随列表提前实例化Dialog，已改为Loader只在选择条目时加载，返回销毁。新增test_qml_extension_details.py实际点击启停/钻取/返回/关闭并断言无可见窗口残留；与工作区选择器共同运行3 passed in 19.67s。最终截图在此修正后重渲染，home为/tmp/ai-upper-ext-dark-final/home和/tmp/ai-upper-ext-light-final/home。

截图fixture角色reviewer/writer没有随包头像资源，现有Avatar组件报找不到reviewer-pop.svg/writer-pop.svg；该角色头像缺口尚未修复，不以这些截图证明角色头像对齐。命令日志完整保留。

后续回归说明：详情改为按需加载后全量仍出现同一窗口数量失败，因此该调整不是已证实的窗口泄漏根因。相邻window_controls+workspace_mount组合7 passed，故继续核对全量资源生命周期。三个既有测试文件（test_qml_window_controls.py、test_qml_plugin_settings.py、test_qml_external_settings.py）用del engine清理，但bridge._engine仍有引用；改为engine.deleteLater()，由conftest既有DeferredDelete钩子销毁。没有删用例或放宽原有断言。最终结果以clean-final-tests.log为准。

## 最终回归与本地增量提交

```sh
AI_UPPER_HOME=/tmp/ai-upper-ext-clean-final \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
XDG_CACHE_HOME=$PWD/.tmp/extensions-parity/cache \
.venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-ext-clean-final/tests
```

输出：**1426 passed, 9 skipped in 356.96s**，0 failed。相对基线1422 passed新增4项用例，未删测试。完整日志out/extensions-parity/clean-final-tests.log。git diff --check无输出。

提交为本地develop上的增量，未push、未新建分支、未改依赖pin；提交后sha与git status --porcelain保存在out/extensions-parity/git-final.txt。尽管回归通过，整体对齐目标仍未完成，以上未完成清单保持有效。
