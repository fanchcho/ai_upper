# 扩展页剩余实差验收

## 结论

1. 精确详情版式**未完全闭环**。完成了正文尺寸token、正文左内边距、滚动条可见宽度、MCP顶栏随滚动、工具清单双列和密钥行比例的修正。实际截图仍有字形基线和字段几何差值，以下列明确数据，不以测试通过代替。
2. 动态头像**同fixture闭环**：Qt直接运行随包分发的原版Humation核心与素材；seed、spec、shape、颜色、compact/pop构图均为运行时生成，不按角色名预生成。reviewer/writer及自定义spec与原版库对账通过。没有不可移植的技术障碍。
3. 导航来源与影响分析**完成**；处置待用户决定，三条入口完整保留。

## 详情依据及差值

只读原版依据：`/home/agent/shared_workspace/deva/apps/desktop/src/renderer/src/styles/app.css:765`（正文），`:5337`（技能正文尺寸），`:5406`（字段），`:5189`（密钥行），`:5223`（工具清单），`:46`（滚动条）。DOM实测见out/extensions-exact/deva-skill-geometry.json、deva-mcp-geometry.json；Qt可视树数据见dark/light-*-geometry.json。

|项目|原版|修前|修后|剩余差值/边界|
|---|---|---|---|---|
|正文font-family|CSS系统字体栈，本机DejaVu Sans|Sans Serif|DejaVu Sans|族对齐；不是跨OS字体保证|
|正文字号|12.5px|13px|12.5px（9.375pt）|token差0|
|H1字号|16.25px|16px|16.25px（12.1875pt）|token差0|
|正文行高|20.625px|21px|20.625px固定行高|token差0；实际字形基线见下|
|H1行高|21.125px|21px|21.125px|token差0|
|H1后间距/段间距|8px / 12px|12px / 12px|8px / 12px|token差0|
|正文容器左缘|469px|469px|469px|0px|
|正文内容左缘|486px|485px|486px|0px；1px边框+16px padding|
|正文内容顶缘|411px|415px|411px|容器坐标差0|
|H1字形墨迹纵区间|415–429px|未重采旧版本字形|416–430px|Qt字形下移1px|
|首段字形墨迹纵区间|444–453px|未重采旧版本字形|447–456px|下移3px|
|后续段落字形|477–486 / 509–518 / 542–551|未重采|479–488 / 512–521 / 545–554|下移2/3/3px|
|普通输入/参数域高度|32 / 72px|32 / 72px|32 / 72px|0px|
|Transport标签包围盒y|375.5px|371px|371px|−4.5px；Qt标签含4px topPadding，不能当字形偏移|
|Command标签y|446px|440px|440px|−6px|
|Arguments标签y|516.5px|509px|509px|−7.5px|
|Environment标签y|632.5px|618px|618px|−14.5px|
|密钥行键宽/列间距|34% / 8px|30% / 6px|34% / 8px|比例token差0；锁图标原版同状态像素位置本轮未验证|
|工具清单|34%机器名+12px gap+描述，padding 8px|上下两行|左右两列、名称accent/描述subtle、padding8px、分隔线|结构/颜色token修正；多工具行间距仍未验证，Qt描述lineHeight按字体metrics计算可能偏大|
|MCP顶栏滚动|随外层内容滚动|固定|Back y207→135，滚动72px|相对位移72px，与contentY一致；技能顶栏仍固定|
|滚动条|轨道8px、两边内缩2px，可见4px|可见8px|轨道8px、可见4px|宽度token差0|
|滚动条配色|light黑18% / dark白16%，hover fgSubtle|同token|同token|颜色token差0|

正文剩余差值位于 `qml_shell.py:extensionInstructions` 生成QTextDocument并序列化成HTML，再由QQuickTextEdit布局的路径；字体的ascent/descent、HTML二次导入行框与Chromium不同。不是Qt不能修，也不是已对齐，当前未做逐块基线校准。字段差值位于 `ExtensionDetail.qml` 的Column.spacing、FieldLabel.topPadding及Qt控件implicitHeight组合；尚未完全映射原版每个ext-field的margin-bottom。密钥锁的像素坐标、多工具间距缺原版同状态重测，明确标为未验证。

## 头像

实现：`app/src/mvvm/services/humation.py`、`app/assets/humation/runtime.js`、`qml_shell.py:personaAvatar`、`Avatar.qml`。

原版库版本均1.0.3；MIT原文许可证随资源分发。构建脚本 `scripts/parity/build_humation.mjs` 只读deva安装包、shape路径/规格解析源码，构建出约760KB的IIFE。应用使用QJSEngine执行，不调用Node，不依赖deva路径。Qt旧JS环境缺globalThis/flatMap，补局部兼容层；已有应用依赖pin未改。

同fixture实测（不是硬编码人物列表）：

- reviewer / writer纯seed：两端生成SVG逐字节相同。
- reviewer指定head=hm1-p-000005、hair=ff0000：逐字节相同。
- writer探出构图：逐字节相同。
- 后续加入原版shape表、auto与clover兼容、invalid selections过滤；cloud/auto用例通过测试。所有形状逐像素截图尚未穷举，不声称动画busy morph已移植。

哈希与对账：out/extensions-exact/avatar-check.log、avatar-reference.json。最终含shape的6组Node/Qt逐字节对账见avatar-final-check.log、avatar-bundled-reference.json；字形像素纵区间实测见ink-measurements.json。生成器来源：原版components/humation.tsx:243、308、339、390；shared/avatar-shape.ts。

图片头像优先；无图片直接运行seed/spec生成。首字母仅在Image真正Error时兜底并伴随QML错误日志，不再以“角色SVG没打包”为正常降级路径。日志末尾少量缺SVG来自窗口销毁时shellBridge已清空、binding切回磁盘路径；正常页面截图已为生成的人物，不是首字母。

## 三条导航：只报告，未删除

位置：`app/src/qml/SettingsModal.qml:132-134`（Custom model / MCP / Personas），`:187`路由到`:197`的PluginSettingsPane。Main.qml保留settings-custom-model/settings-mcp/settings-identities直达路由。

真正引入提交（git log -S验证）：

`8de00f088c43d6cb10167ef693ea1859b6962ca4`

作者记录：Claude Code；时间2026-11-25 19:33:15 +0800；标题 `feat(qml): add plugin settings, direct model routing and interrupted-tool recovery`。

f4317ef5及819bcf06只是后续翻译文案修改，不是原始添加者。原始patch保存在out/extensions-exact/navigation-origin.patch。

- Custom model：PluginSettingsPane的baseUrl/model/secret，服务为pluginSettings桥+PluginSettings，连接桌面自有模型配置；General页还有转入该面板的按钮。
- MCP：桌面自有server注册/启停、密钥、approval配置；与扩展页mcp.json配置不完全同源，直接删整个服务会影响既有运行链。
- Personas：共享persona文本读取/保存；删入口会失去当前设置里的编辑路径，但不会删除文件或角色本身。

1:1建议：先只移除设置导航中的三条可见入口，保留底层服务、现有数据和直达路由；再单独决定是否把模型/角色编辑迁到原版对应入口。不能把“去掉导航”扩大成删除PluginSettingsPane、pluginSettings服务或用户配置。影响验证至少覆盖test_qml_plugin_settings.py、test_qml_settings_theme.py及General中的跳转按钮。**等用户定，不擅自实施。**

## 证据和命令

目录：`/home/agent/shared_workspace/ai_upper/out/extensions-exact/`。

- compare-{dark,light}-{skill,mcp}.png：左原版，右本轮真实Qt渲染，同fixture。
- dark/light-skill-detail.png、mcp-detail.png、mcp-bottom.png、roles-popup.png：未裁剪截图。
- dark5.log/light5.log：鼠标、键盘、滚动、角色写盘、重试、回收站完整实测。
- scripts/parity/extensions_exact_evidence.py：本轮可视树几何和截图脚本，临时数据只在显式/tmp home。
- final-regression.log：最终全量结果（delivery-pytest.log保留首次Qt导入约束失败）；git-final.log：本地提交。

```sh
AI_UPPER_HOME=/tmp/ai-upper-exact-delivery \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests -q \
--basetemp=/tmp/ai-upper-exact-delivery/tests
```

临时home通过/tmp别名指向仓库.tmp隔离目录；未写真实~/.ai_upper，未修改deva源码。原版使用隔离DEVA_HOME及Electron user-data-dir，启动命令沿用上一报告；本轮真实启动日志deva.log。

首次全量：1 failed, 1428 passed, 9 skipped，失败为test_only_the_shim_imports_a_qt_binding；已把直接PySide6导入改为utils.qt_compat.QtQml，旧测试断言未改。最终数字见final-regression.log。

补充：Qt兼容层及动态头像定向回归命令为上述环境下 `pytest app/tests/test_qt_compat.py app/tests/test_humation_runtime.py -q`，实际15 passed。暗/亮字段差值机器记录见field-deltas.json。

最终全量：`1429 passed, 9 skipped in 364.39s (0:06:04)`，0 failed。相对1428基线新增1项头像测试；既有断言未删改。最终命令basetemp为`/tmp/ai-upper-exact-delivery/recheck`，完整输出final-regression.log。
