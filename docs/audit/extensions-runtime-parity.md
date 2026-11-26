# 扩展页运行态与同数据验收（2026-11-26）

结论：本轮已经补齐真实 MCP stdio / HTTP / SSE 连接、失败、重试、工具发现，角色头像堆叠与多选下拉，目录自动刷新、非 ASCII 排序、长内容滚动和技能回收站端到端。**尚不声称整体逐项精确对齐**：同状态截图仍能看到详情字段间距、正文段落/滚动条和头像生成策略的差异。第 3 项精确版式仍未完全收口；不是网络或图形上下文不足造成，属于实现差异。

旧报告 `docs/audit/extensions-parity.md` 是上一提交的历史结论；本报告及 `out/extensions-complete/` 为本轮证据。

## 原版依据（只读）

以下路径以 `/home/agent/shared_workspace/deva/` 为根：

|行为|路径:行号|
|---|---|
|技能、MCP聚合和列表|apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:183|
|角色列表头像与多选下拉|同文件:300、326|
|技能顶栏、正文、删除确认|同文件:417|
|MCP标题右侧状态、重试、参数、工具|同文件:493|
|参数草稿、键值锁图标、600ms保存反馈|同文件:689、718|
|顶栏/分隔线|apps/desktop/src/renderer/src/styles/app.css:4586、4602、4624|
|技能正文、字号|同文件:5105、5337、5344|
|字段标签、输入框、参数域、状态色|同文件:5406、5430、5460、5490|
|技能 localeCompare 排序|apps/desktop/src/main/services/skills.ts:354|
|技能目录监听/变更广播|同文件:659、681|
|MCP状态IPC/手动重试|apps/desktop/src/main/services/mcp.ts:628、654|
|secretRef解析|apps/desktop/src/main/services/mcp-config.ts:302|

页面只列技能和 MCP；内置三条锁定置顶，随后自装技能、MCP各自按名称排序。没有独立插件tab、打开目录或刷新按钮。

## 本轮根因与实现

- 上版仅投影配置，状态固定“未连接”，无实际MCP生命周期。新增 `app/src/mvvm/services/extension_runtime.py` 常驻工作线程；复用 `mcp_runtime.py` 的 stdio/Streamable HTTP，并补旧式 SSE 的 GET endpoint + POST + message 路径。状态通过 Qt signal 回到列表/详情，失败显示真实异常，可重试。禁用/配置变化/窗口销毁关闭连接。
- 上版 roles 是复选框。现在列表用20px头像堆叠、详情32px多选下拉，含“所有角色”、分组标题、逐项勾选；支持已有头像图片，缺资源时首字母 fallback。**fallback 不等同原版运行时 Humation 按 seed/spec 生成的人物**，未用硬编码人物伪装一致。
- 上版详情 MCP 状态在标题上方、字段为默认控件尺寸。改为标题右侧状态，32px等宽输入、72px参数域、上下文字工具清单、锁图标、独立正文滚动区。600ms自动保存密钥、失焦提交、遮罩草稿保留、“已保存”均有实测。
- 上版仅进入页面读盘。新增500ms目录/文件指纹监听与配置对账；这不是 OS 原生 QFileSystemWatcher，但外部新增/修改/删除会自动刷新。MCP状态线程直接广播，无须重开页面。
- 技能 casefold 改为 `QCollator(QLocale('en_US'))`。不声称任意语言环境和任意ICU版本完全等价。
- 列表和详情大幅滚轮会越过底部，现设 StopAtBounds；技能正文改为独立 Flickable。
- QFile实例moveToTrash可返回实际回收站路径，供真实内容验证；失败带Qt错误文本。正常删除仍只走用户确认，无永久删除替代。
- secretRef写盘从上一版完整键改为原版字段名；读取兼容上一版完整键。

## 逐项验收

|项|真实验证|结论/剩余差异|
|---|---|---|
|1 MCP运行态|实际子进程stdio + 本地ThreadingHTTPServer的HTTP、SSE，initialize/tools/list/ping；错误命令修正后重试；UI错误详情点击Retry成功|已验证三种传输，均tools=1；未验证远程TLS、OAuth服务器，不影响本地三种传输结论|
|2 角色头像|暗/亮列表堆叠、四个真实persona的多选下拉；鼠标切换writer并读配置；缺SVG触发fallback|布局/选择/持久化已验证；运行时Humation自定义seed/spec未移植，保留差异|
|3 精确详情|同数据原版/移植版正常、连接成功详情，暗亮均截图；保存修前图|结构已补齐，精确版式未完成：段落基线、字段间距、滚动条宽度、MCP外层滚动时顶栏行为仍不同|
|4 刷新监听|页面不退出，创建external-added/SKILL.md，signal=2，UI可见文本断言|已验证；用500ms轮询目录指纹，非原版fs.watch|
|5 非ASCII排序|Chromium实际localeCompare与QCollator结果逐项相同，新增回归|已验证本机默认en-US；跨locale未验证|
|6 长列表/详情|39项列表、71段正文、MCP字段区，用真实QWheelEvent拉到底部|已验证contentY边界，不裁切尾项；截图见*-bottom.png|
|7 回收站|实际鼠标点击删除→确认OK，原目录消失，读取trash/SKILL.md，rename恢复并读取|已验证；平台Qt本次把文件放到挂载点回收站，路径记录在日志|
|8 并排|同alpha/beta、Echo/Failure/Off和相同MCP脚本，1280×820、DPR1、暗亮、列表/技能/MCP详情|已生成8组（含角色popup）；没有使用旧三内置基线|
|9 全量|见下方最终输出|不删除旧测试、不放宽旧断言，窗口计数用例保持原样|
|10 提交|本地develop，无push/new branch/pin变更|SHA另见交付消息及git-final.log|

## 原版与移植差异表（不掩盖）

|位置|修前|当前|原版|
|---|---|---|---|
|运行态|固定未连接|真实三种连接+错误+重试+工具|真实常驻连接|
|标题状态|标题上方单独一行|标题右侧、绿连接/红错误|标题右侧|
|角色|复选框|头像堆叠+多选下拉，缺资源首字母|头像堆叠+多选下拉，Humation生成|
|字段|默认控件、参数单行高度|32px输入、72px参数、锁按钮和保存反馈|32px/72px、CSS行高与间距|
|正文|默认Markdown大标题、滚动未证实|16px标题、独立滚动、底部验证|16.25px标题，段落基线略不同|
|列表监听|仅进入时|500ms盘状态检测与Qt广播|fs.watch与IPC|
|导航外壳|额外Custom model/MCP/Personas入口|保留既有入口|只有General/Models/Extensions/About|

保留的额外导航是既有移植功能，不在本轮偷偷删除；因此整张设置弹窗也不是像素相同。原版“所有角色”圆形底图、下拉阴影、正文细节同样可从并排图看到残差。不能把测试全部通过表述成视觉完全一致。

## 环境和复现命令

仓库实体：`/home/agent/shared_workspace/ai_upper`，分支develop。所有Python应用/测试都显式设置AI_UPPER_HOME到/tmp。Electron使用临时DEVA_HOME和user-data-dir，源码、原版out产物只读引用。

真实原版启动（先前GTK缺库失败日志也保留）：

```sh
PATH=$PWD/.tmp/icon-dpi/runtime/usr/bin:$PWD/.tmp/wm/usr/bin:$PATH \
LD_LIBRARY_PATH=$PWD/.tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu:$PWD/.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu:$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
AI_UPPER_HOME=/tmp/ai-upper-deva-reference DEVA_HOME=/tmp/ai-upper-deva-reference \
TMPDIR=$PWD/.tmp/extensions-complete XDG_CACHE_HOME=$PWD/.tmp/extensions-complete/cache \
.tmp/wm/usr/bin/xvfb-run -a \
.tmp/extensions-complete/browser/node_modules/electron/dist/electron \
--no-sandbox --disable-gpu --remote-debugging-port=9344 \
--user-data-dir=/tmp/ai-upper-electron-reference \
/home/agent/shared_workspace/deva/apps/desktop/out/main/index.js
```

Electron33.4.11与原版一致，隔离安装于.tmp，未改仓库依赖。GTK/epoxy/cloudproviders离线包解压到.tmp，不是更改deva。启动日志：`out/extensions-complete/deva-launch.log`（libgtk缺失），`deva-launch2.log`（DBus缺失警告，仍成功显示窗口）。本轮不存在“拿不到图形上下文所以无法对照”的阻塞。

Qt证据脚本（dark/light使用不同新home，脚本会拒绝复用已有技能目录）：

```sh
AI_UPPER_HOME=/tmp/ai-upper-complete-dark24 \
XDG_DATA_HOME=$PWD/.tmp/extensions-complete/trash-dark24 \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python scripts/parity/extensions_runtime_evidence.py dark
```

浅色替换为light和对应home。脚本真实构建QML/ShellBridge，聊天网络mock不参与扩展注册、配置文件、MCP子进程或本地HTTP服务。

MCP服务与排序定向测试：

```sh
AI_UPPER_HOME=/tmp/ai-upper-complete-sse \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests/test_extension_runtime.py \
app/tests/test_qml_extension_details.py app/tests/test_extension_settings.py \
-q -s --basetemp=/tmp/ai-upper-complete-sse/tests
```

真实输出（focused-final.log / polish-tests.log）：`6 passed`。传输输出：

```text
stdio connected tools=1; HTTP connected tools=1; SSE connected tools=1;
missing executable error; retry connected tools=1; broadcasts=7
```

排序两边均为：`ä, alpha, Álpha, éclair, Zulu, 中文, 日本語`。原始数据：deva-sort.json、qt-sort.json。

失败尝试没有删日志：runtime-final.log此前错误路径/基目录问题已修；ui-dark11.log及dark-delete-result旧图记录QFile Bad file descriptor，原因是未创建XDG_DATA_HOME；创建后实际移入回收站成功。ui-dark9.log记录长列表滚动过头，现有边界断言验证修复；旧版fixture漏inputSchema被原版拒绝，已修正并通过真实SDK握手。

## 证据索引

所有下列相对路径都位于 `/home/agent/shared_workspace/ai_upper/out/extensions-complete/`：

- `compare-{dark,light}-{list,skill,mcp,roles-popup}.png`：左原版、右移植；只裁剪设置弹窗区域，不缩放。
- `deva-{dark,light}-{list,skill,mcp}.png`：原版完整截屏；`{dark,light}-{list,skill-detail,mcp-detail}.png`：移植完整截屏。
- `before-{dark,light}-{skill,mcp}-detail.png`：本轮进一步调整前的真实渲染（当时两个技能、两个MCP，详情同alpha/Echo）。
- `{dark,light}-mcp-error.png`、`*-mcp-retry.png`、`*-mcp-bottom.png`：错误、点击重试后的连接和工具清单。
- `*-roles-popup.png`、`*-secret-saved.png`：实际下拉和键盘密钥保存。
- `*-external-added.png`、`*-list-bottom.png`、`*-skill-bottom.png`：自动发现与滚到底。
- `*-delete-confirm.png`、`*-delete-result.png`和`ui-dark24.log`/`ui-light24.log`：确认、列表移除、实际trash路径和恢复。
- `dark-fixture.json`/`light-fixture.json`和`deva-fixture.json`：同数据原始配置/投影；不含密钥明文。
- `deva-geometry.json`：原版DOM几何实测，不靠估计。
- `delivery-pytest.log`：最终全量回归；`git-final.log`：最终提交/状态。

最终全量命令：

```sh
AI_UPPER_HOME=/tmp/ai-upper-complete-delivery \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
XDG_CACHE_HOME=$PWD/.tmp/extensions-complete/cache \
.venv/bin/python -m pytest app/tests -q \
--basetemp=/tmp/ai-upper-complete-delivery/tests \
> out/extensions-complete/delivery-pytest.log 2>&1
```

实际输出：`1428 passed, 9 skipped in 356.12s (0:05:56)`，0 failed。对照用户基线1422，累计+6；对照本轮开始1426，新增2项。`git diff -- app/tests`不包含任何既有测试变更；新增运行态与非ASCII排序测试，窗口计数断言保持原样。

同数据机器对账：`fixture-match.log`验证两端8条记录的id/name/enabled/roles完全相同。三列修前/修后/原版图：`before-after-deva-{dark,light}-{skill,mcp}.png`。

本地提交SHA以`out/extensions-complete/git-final.log`和交付消息为准，避免在提交正文中自引用SHA。

Studio任务卡首次更新成功；收尾更新返回 `Unauthorized. Web UI token was not accepted.`，携带default profile重试仍失败。目标应保持open，不将本轮测试通过记作整体完成；失败记录见`out/extensions-complete/studio-update-failure.json`。
