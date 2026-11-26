# 设置页黑白主题分离修复

## 验收清单

- [x] develop/origin 与全部 ahead 提交核对：初始 HEAD 315e407，远端 b011b65，仅 6e59c78、315e407 两条，范围为 app/ 和 out/workspace-mount/。见 git-audit.log。
- [x] 七个侧栏页面及 Models 详情/高级页审计：见 AUDIT.md（完整 file:line）。
- [x] deva 仅只读；原版 tokens.css 与控件规则已取证。
- [x] light/dark 即时绑定；system getter 与系统信号处理；General 当前选项通知修复。
- [x] Linux offscreen 1420×1076 before/after 及像素表。
- [x] 不改 QTextDocument 正文渲染、不改依赖 pin、不重构其它页面。
- 回归结果见下方真实日志；推送结果见 push-receipt.log（推送后生成的本地收据，明确不纳入同一个自引用提交）。

## 根因与改动

1. `PluginSettingsPane.before.qml:34-88` 的 ComboBox、TextField、TextArea、CheckBox、Button 和 ScrollView 全依赖平台 palette，Theme 仅用于少数 Text。macOS 原生控件与手绘 QML 面板混搭导致用户图中的白字白底和黑色圆角残片；Linux 默认样式虽形状不同，深色下仍可直接复现浅色控件残留。现在使用设置专用 QtQuick.Controls.Basic 及完整 Theme 背景/contentItem/indicator/popup/scrollbar。
2. `SettingsModal.before.qml:532` 自定义模型入口同样漏绑；多处小字使用 fgSubtle（如 566、629、957、1105、1148、1185、1251、1298、1381、1511），改用原版 fgMuted。警告/结果小字改为可读正文色，旁边图标保留语义色。
3. `app/src/qml_shell.py:570-584`（修复后行号）原 `_resolve_dark` 把 colorScheme 方法与枚举比较，system 永远解析不到 Dark；现在调用 getter 并监听 colorSchemeChanged，显式 light/dark 不受系统信号影响。具体当前行号见 changes.diff。
4. `SettingsModal.before.qml:321-327` 的 General 原 themeIndex() 是无通知方法，已打开弹窗的选中项不刷新；增加 themeChoice 通知属性。回归在同一窗口检查 System/Light/Dark 三种选项及输入内容保持。
5. 新增 SettingsField/SettingsButton/SettingsCheck/SettingsScrollBar，仅设置页使用；增加 accentHover 原版 token；开关圆点按原版 app.css:4070 / redesign.css:3431 的白色常量集中到 switchThumb（原版两套主题均为白色，并非遗留错色）。危险按钮以 danger 边框承载语义、fg 承载文字，避免原版白字红底不达 4.5 的问题；未创造新色值。禁用按钮使用 bgInset/fgMuted，保留可读性。

## deva 原版配色对照

来源：`/home/agent/shared_workspace/deva/apps/desktop/src/renderer/src/styles/tokens.css:41-88,109-155`；控件规则 `styles/app.css:2530-2578,4079-4095`。快照 deva-tokens.css / deva-controls.css。

|语义|Light|Dark|设置使用|
|---|---|---|---|
|bg|#ffffff|#1e1e20|基础背景|
|bg-panel|#f7f7f8|#252528|弹窗|
|bg-elevated|#ffffff|#2a2a2e|输入/次按钮/弹层|
|bg-inset|#f0f0f2|#191919|侧栏/禁用按钮|
|fg|#1f1f24|#e4e4e7|主文字|
|fg-muted|#5c5c66|#a1a1aa|提示/占位符|
|fg-subtle|#8a8a94|#71717a|仅次要图标|
|border|#e6e6ea|#2f2f33|分隔线|
|border-strong|#d5d5db|#3d3d42|输入边框|
|accent|#5b5bd6|#7c7cf0|主按钮/勾选|
|accent-hover|#4c4cc4|#9090f5|主按钮悬停/按下|
|accent-fg|#ffffff|#14141a|主按钮文字/选区|
|danger|#e5484d|#ff6b6b|危险边框|
|bg-hover|rgba(0,0,0,.045)|rgba(255,255,255,.06)|悬停|
|bg-active|rgba(0,0,0,.08)|rgba(255,255,255,.10)|按下|
|scrollbar|rgba(0,0,0,.18)|rgba(255,255,255,.16)|滚动条|

## 每页截图与对比度

完整逐文本实际像素值及比值见 CONTRAST.md / contrast.json；方法及复现命令见 README-reproduce.md。字体测试环境加载 Noto CJK，未修改系统字体。所有采样统一要求 ≥4.5（比大字 ≥3 更严格）。

|页面/状态|主题|before|after|采样数|最小对比度|
|---|---|---|---|---|---|
|general|light|[before](before/general-light.png)|[after](after/general-light.png)|21|5.806:1|
|models|light|[before](before/models-light.png)|[after](after/models-light.png)|12|5.806:1|
|models-provider|light|[before](before/models-provider-light.png)|[after](after/models-provider-light.png)|13|5.806:1|
|models-advanced|light|[before](before/models-advanced-light.png)|[after](after/models-advanced-light.png)|13|5.806:1|
|extensions|light|[before](before/extensions-light.png)|[after](after/extensions-light.png)|18|5.379:1|
|about|light|[before](before/about-light.png)|[after](after/about-light.png)|12|5.806:1|
|custom-model|light|[before](before/custom-model-light.png)|[after](after/custom-model-light.png)|19|5.368:1|
|mcp|light|[before](before/mcp-light.png)|[after](after/mcp-light.png)|27|4.833:1|
|identities|light|[before](before/identities-light.png)|[after](after/identities-light.png)|16|4.833:1|
|mcp-filled|light|[before](before/mcp-filled-light.png)|[after](after/mcp-filled-light.png)|26|4.833:1|
|mcp-hover|light|[before](before/mcp-hover-light.png)|[after](after/mcp-hover-light.png)|26|4.833:1|
|mcp-pressed|light|[before](before/mcp-pressed-light.png)|[after](after/mcp-pressed-light.png)|26|4.833:1|
|mcp-disabled|light|[before](before/mcp-disabled-light.png)|[after](after/mcp-disabled-light.png)|26|4.833:1|
|general|dark|[before](before/general-dark.png)|[after](after/general-dark.png)|21|6.860:1|
|models|dark|[before](before/models-dark.png)|[after](after/models-dark.png)|12|5.964:1|
|models-provider|dark|[before](before/models-provider-dark.png)|[after](after/models-provider-dark.png)|13|5.964:1|
|models-advanced|dark|[before](before/models-advanced-dark.png)|[after](after/models-advanced-dark.png)|13|5.964:1|
|extensions|dark|[before](before/extensions-dark.png)|[after](after/extensions-dark.png)|18|5.893:1|
|about|dark|[before](before/about-dark.png)|[after](after/about-dark.png)|12|5.964:1|
|custom-model|dark|[before](before/custom-model-dark.png)|[after](after/custom-model-dark.png)|19|5.240:1|
|mcp|dark|[before](before/mcp-dark.png)|[after](after/mcp-dark.png)|27|4.624:1|
|identities|dark|[before](before/identities-dark.png)|[after](after/identities-dark.png)|16|4.624:1|
|mcp-filled|dark|[before](before/mcp-filled-dark.png)|[after](after/mcp-filled-dark.png)|26|4.624:1|
|mcp-hover|dark|[before](before/mcp-hover-dark.png)|[after](after/mcp-hover-dark.png)|26|4.624:1|
|mcp-pressed|dark|[before](before/mcp-pressed-dark.png)|[after](after/mcp-pressed-dark.png)|26|4.624:1|
|mcp-disabled|dark|[before](before/mcp-disabled-dark.png)|[after](after/mcp-disabled-dark.png)|26|4.624:1|

总计 510 个文本区域采样，低于 4.5:1：0。

## 回归输出

命令：`.venv/bin/python out/theme-settings/run_tests.py`。脚本内明确 pytest 参数与隔离环境。

```text
................................................s....................... [ 45%]
........................................................................ [ 51%]
....ssss................................................................ [ 56%]
........................................................................ [ 61%]
........................................................................ [ 66%]
........................................................................ [ 71%]
........................................................................ [ 76%]
........................................................................ [ 81%]
........................................................................ [ 86%]
........................................................................ [ 91%]
........................................................................ [ 96%]
...........................................                              [100%]
=========================== short test summary info ============================
SKIPPED [1] app/tests/test_build_tool_compat.py:1704: the auto-link pragma belongs to the Windows pyconfig.h
SKIPPED [1] app/tests/test_build_tool_compat.py:1758: handle inheritance for GUI-subsystem children belongs to Windows
SKIPPED [1] app/tests/test_e2e_local.py:447: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] app/tests/test_e2e_local.py:488: set AI_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] app/tests/test_native_deployment.py:177: requires cc, patchelf and readelf
SKIPPED [1] app/tests/test_plugin_host_requirements.py:11: 无应用内宿主接口，需要 Studio user/profile: authenticated identity and profile namespace injection into the desktop runtime
SKIPPED [1] app/tests/test_plugin_host_requirements.py:11: 无应用内宿主接口，需要 Studio approval/interaction RPC envelopes and cross-runtime resume callbacks (local QML controller is implemented and tested separately)
SKIPPED [1] app/tests/test_plugin_host_requirements.py:11: 无应用内宿主接口，需要 Attachments: assetId resolver, authorizedRoots, expiresAt, and delivery acknowledgment API
SKIPPED [1] app/tests/test_plugin_host_requirements.py:11: 无应用内宿主接口，需要 SDK/installer: Studio plugin registration, RPC context, plugin lifecycle and signed release distribution
1402 passed, 9 skipped in 323.98s (0:05:23)

exit_code=0
```

最后修改后的设置与上一轮 workspace-mount 专项输出：
```text
app/tests/test_qml_settings_models.py::test_update_provider_patches_without_touching_the_input PASSED [ 57%]
app/tests/test_qml_settings_models.py::test_update_provider_none_drops_the_key PASSED [ 59%]
app/tests/test_qml_settings_models.py::test_update_provider_unknown_id_returns_none PASSED [ 61%]
app/tests/test_qml_settings_models.py::test_remove_provider_and_active_model_cleanup PASSED [ 62%]
app/tests/test_qml_settings_models.py::test_remove_provider_keeps_unrelated_active_model PASSED [ 64%]
app/tests/test_qml_settings_models.py::test_remove_provider_unknown_returns_none PASSED [ 66%]
app/tests/test_qml_settings_models.py::test_add_provider_appends_and_deep_copies PASSED [ 67%]
app/tests/test_qml_settings_models.py::test_add_provider_replaces_same_id_in_place PASSED [ 69%]
app/tests/test_qml_settings_models.py::test_new_provider_shape_matches_upstream_custom_defaults PASSED [ 71%]
app/tests/test_qml_settings_models.py::test_set_headers_sanitizes_and_writes_lowercase_table PASSED [ 72%]
app/tests/test_qml_settings_models.py::test_set_headers_drops_the_key_when_nothing_valid_remains PASSED [ 74%]
app/tests/test_qml_settings_models.py::test_set_headers_caps_rows_at_the_upstream_limit PASSED [ 76%]
app/tests/test_qml_settings_models.py::test_set_headers_unknown_provider_returns_none PASSED [ 77%]
app/tests/test_qml_settings_models.py::test_set_headers_last_wins_on_duplicate_names PASSED [ 79%]
app/tests/test_qml_settings_models.py::test_set_model_enabled_flips_only_the_target_model PASSED [ 81%]
app/tests/test_qml_settings_models.py::test_add_model_dedupes_and_requires_non_empty_id PASSED [ 83%]
app/tests/test_qml_settings_models.py::test_add_model_creates_the_list_when_missing PASSED [ 84%]
app/tests/test_qml_settings_models.py::test_remove_model_and_active_model_cleanup PASSED [ 86%]
app/tests/test_qml_settings_models.py::test_provider_headers_applies_custom_headers_last_and_overrides_user_agent PASSED [ 88%]
app/tests/test_qml_settings_models.py::test_provider_headers_without_custom_rows_keeps_the_default_user_agent PASSED [ 89%]
app/tests/test_qml_settings_models.py::test_written_headers_are_exactly_what_gets_sent PASSED [ 91%]
app/tests/test_qml_settings_provider.py::test_provider_delete_confirm_flow PASSED [ 93%]
app/tests/test_qml_settings_provider.py::test_provider_delete_cancel_keeps_provider PASSED [ 94%]
app/tests/test_qml_settings_provider.py::test_add_provider_button_creates_and_opens_custom PASSED [ 96%]
app/tests/test_qml_workspace_mount.py::test_mount_picker_mouse_persist_cancel_and_reject PASSED [ 98%]
app/tests/test_qml_workspace_mount.py::test_scrolled_delivery_icons_do_not_paint_over_composer PASSED [100%]

======================== 59 passed in 111.51s (0:01:51) ========================

exit_code=0
```

## 推送收据

真实 `git push origin develop`、本地 HEAD、`git ls-remote origin refs/heads/develop` 与工作树输出保存在 [push-receipt.log](push-receipt.log)。该文件是提交后产生的本地证据，不纳入本次提交，以免 hash 自引用；其余 out/theme-settings 证据随提交交付。

## 未验证与边界

- macOS 原生窗口/Retina 渲染未验证：本机为 Linux offscreen，不能冒充 macOS 重现。用户上传原图保存在 user.png。
- 系统桌面真实昼夜切换未验证：offscreen 不提供桌面主题服务；已用真实 QStyleHints 信号和可控 getter 验证应用响应、显式主题覆盖，以及运行时不重启更新。
- 截图覆盖列出的可见页面和按钮状态；未穷举外部服务器任意返回错误文案、任意长度列表的所有滚动位置。
- before 保留平台默认样式；不声称 Linux 的黑色圆角表现与用户平台一致。
