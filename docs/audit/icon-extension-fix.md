# 左侧图标与扩展发现复核（2026-11-26）

结论：扩展列表遗漏 MCP 注册项已修复；图标悬停色已对齐原版。用户截图中的黑色、错位图标未在当前 develop 软件渲染复现，不能宣称该问题已修复。

## 验收清单

- [x] 打开两张用户截图。
- [x] 隔离 home、真实 QML 渲染修前/修后截图与像素对比。
- [ ] A1 用户截图异常复现与精确底层根因：未验证。软件后端图标正常；OpenGL 无法建立 QRhi context。
- [x] A2 原版 CSS、SVG currentColor 与移植 QML token 对照；补齐 hover 前景色。
- [ ] A2/A3 原版 Electron 实际渲染取色：未验证。参考仓库预期 node_modules/electron/dist/electron 不存在；未修改或安装依赖到只读原版目录。
- [x] A3 移植版 dark/light、选中/悬停/常态像素采样，指示条代码保持不变。
- [x] B4 真实目录只读清单、函数定位。
- [x] B5 原版技能+MCP 分类与移植版遗漏根因。
- [x] B6 复制真实 mcp.json 结构到隔离 home，5 项自装注册项和3项内置共同显示；两套主题截图。
- [x] B6 实际鼠标点击开关、持久化读取验证；空目录截图显示自装扩展空态。
- [x] B7 列表来自磁盘/现有作用域注册，未硬编码自装条目。
- [ ] MCP 服务连接/工具调用与原版详情编辑器：本次未验证；本次只接入发现及启停配置，不把磁盘 MCP 自动加入原有运行时。启用不等于已连接。
- [ ] C8 最终全量回归结果见后续记录。
- [ ] C9 提交与状态见后续记录。

## 根因及实现

`app/src/qml_shell.py:1045 extensionRows()` 原先只遍历 `SkillStore.list_skills()`。
`app/src/mvvm/services/skill_store.py:185` 的 SkillStore 扫描 `<home>/skills/*/SKILL.md`；文件夹为 id，frontmatter 为名称，config.json 的 skills.enabled 决定启停；内置 BUILTIN_SKILLS 三项在代码合成，磁盘无目录仍返回它们。
原版 `apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:220` 则按技能列表、MCP列表合并，技能标签与内置注记分开，内置开关锁定。该页没有额外的通用 plugins 文件夹发现规则；本机 ekko-studio-plugins 实际是 MCP 注册 id。

新增 `PluginSettings.registered_servers()` 读取当前 SettingsService.home 的 mcp.json/mcpServers，保持 AI_UPPER_HOME 隔离。显式 `servers(include_registered=True)` 合并作用域注册项，同 id 作用域优先，按显示名排序。磁盘项启用态沿用原版 config.json/mcp/enabled（默认关），作用域项使用原有 enabled 字段。敏感 env/headers 不进入列表投影。列表只构造名字、类型、启用状态和未连接注记，不探测真实服务。
`toggleExtension(kind,id)` 区分技能/MCP，同名 id 不会切错类型。磁盘 MCP 开关只更新配置的 enabled 映射，保留 roles 和 mcp.json 原文；作用域 MCP 使用既有存储，并停止对应活动连接。

图标 `Main.qml:364` 原先 active 为 Theme.accent，其他状态恒为 Theme.fgSubtle；原版 redesign.css:166 hover 为 --fg。仅补齐该分支，没有随意提高 token、改 opacity 或动指示条。Icon.qml 用 ShapePath.strokeColor 绑定 Icon.color，size=20，未禁用、opacity=1。软件渲染已验证该绑定正常。未证实用户异常由 source/color、材质或 disabled 的哪一层导致。

## 真实来源（只读）

`/home/agent/.ai_upper` 不存在。
`/home/agent/.deva` 存在，子目录只有 personas，无 skills/extensions/plugins 目录。
`/home/agent/.deva/mcp.json` 有以下5项，transport 均为 stdio；原配置 mcp.enabled 均为 true：

- hindsight
- ekko-studio-plugins
- ekko-studio-use
- ekko-studio-browser
- ekko-studio-api

证据 `out/icon-extension-fix/inventory.json`，未包含命令参数、密钥或认证配置。
复刻位置 `/tmp/ai-upper-font-ext-dark/home/mcp.json`、`/tmp/ai-upper-font-ext-light/home/mcp.json`。只复制该注册文件及配置中 mcp 段；没有执行其中命令。渲染采用仓库 `_build_window` 装配真实 ShellBridge/SettingsService/QML，mock transport 仅用于禁止会话联网，扩展注册来自真实文件。

## 像素对照

下表原版列为 CSS 声明及其 alpha 合成预期，**不是原版浏览器实测**。移植列为截图图标区域实际非抗锯齿像素；WCAG sRGB 相对亮度公式 `(L亮+0.05)/(L暗+0.05)`。

|主题/状态|原版前景 token|移植实际图标/背景|实测对比度|
|---|---|---|---|
|dark 常态|fg-subtle #71717a|#71717a / #191919|3.638|
|dark 选中|accent #7c7cf0|#7c7cf0 / #303030|3.770|
|dark hover|fg #e4e4e7|#e4e4e7 / #272727|11.773|
|light 常态|fg-subtle #8a8a94|#8a8a94 / #f0f0f2|3.003|
|light 选中|accent #5b5bd6|#5b5bd6 / #dddddf|3.957|
|light hover|fg #1f1f24|#1f1f24 / #e6e6e8|13.166|

修前 dark 常态3.638、选中3.770，与修后相同，因此不能用这组数据证明已解决用户截图中的暗色异常。
截图 before.png、after-dark.png、after-light.png、*-hover.png、extensions-*.png、*-toggle.png、*-empty.png 与 pixels.json 均在 out/icon-extension-fix。

## 可复现命令

```sh
AI_UPPER_HOME=/tmp/ai-upper-font-ext-dark \
 LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
 .venv/bin/python .tmp/icon-ext/render.py dark extensions-dark.png extensions
```

输出：`saved ... size 1280 820`，8条真实来源行；`UI click enabled true -> false; persisted config verified`。
浅色同命令替换 home、theme 与截图名。无末尾 extensions 参数时抓会话、hover、空目录扩展页。
脚本使用 `.tmp/theme-settings/NotoSansCJKsc-Regular.otf` 解决验证环境中文字体缺失，无产品字体改动。

OpenGL 尝试：同环境增加 `QT_QUICK_BACKEND=rhi QSG_RHI_BACKEND=opengl`，exit 134，日志：
`QRhiGles2: Failed to create context / Failed to initialize graphics backend for OpenGL.`

针对性最终测试：
```sh
AI_UPPER_HOME=/tmp/ai-upper-focused-final \
 LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
 .venv/bin/python -m pytest app/tests/test_plugin_port.py app/tests/test_settings_write.py \
 -q --basetemp=/tmp/ai-upper-focused-final/tests
```
输出 `37 passed in 0.88s`。新增测试验证磁盘发现、启用状态、排序、同名覆盖、敏感字段过滤、配置持久化、不改注册原文、空/坏注册文件。

中间验证记录：第一次针对性运行35 passed；新增两项后一次测试因 basetemp 父目录不存在产生37 setup errors，创建隔离目录后37 passed（最终0.86s）。旧全量轮次在新增测试的排序假设上出现1 failed；改为按 id 检查覆盖记录，旧轮次主动停止时986 passed、9 skipped、1 failed。该轮不作为最终回归结论。

## 最终回归

```sh
AI_UPPER_HOME=/tmp/ai-upper-final-regression \
 LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
 .venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-final-regression/tests
```

**1416 passed, 9 skipped in 349.86s**。失败0。日志：`out/icon-extension-fix/final-tests.log`。
补充最终针对性测试 **37 passed in 0.86s**。`git diff --check` 无输出。
C8 完成。C9 本地 develop 提交；sha 与提交后状态由 `out/icon-extension-fix/git-final.txt` 记录（提交后生成）。没有 push、没有新建分支或更改依赖 pin。

仍未完成的核心验收：A1 异常复现与底层根因，A2/A3 原版实际渲染取色及用户运行环境复测。整个任务保持未完成状态。
