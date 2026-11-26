# 详情残差校准（本轮不宣告整体对齐）

基线 68bb695；所有坐标为 1280×820、DPR=1 下的实际截图/DOM/QML 可视树。
证据目录：`/home/agent/shared_workspace/ai_upper/out/extensions-calibration/`。
最新用户指令要求三个额外入口保持原样：SettingsModal.qml 已恢复到 HEAD，入口、路由、底层服务均无最终改动。中途 navigation 截图属于已撤回状态，不能作为交付证据；compare-* 最终截图包含三个保留入口。

## 已归零

原版依据：deva/apps/desktop/src/renderer/src/styles/app.css:5406 的 ext-field、:5410 的 label、:5189 的 kv-row、:5223 的 mcp-tools；redesign/SettingsPane.tsx:578–658 为实际字段/工具组件，:803–855 为密钥组件。只读参考。

McpField 分别计算 label 16.5px + label margin 6px + control height + field margin 16px。Arguments 另计原版 inline textarea 基线下方 5.5px，不再通过统一 Column.spacing 推算。环境项内部独立 gap=8px；工具列表无额外 Column gap，行内 padding=8px、固定18px行高，非末行border=1px。

|测量项|原版|此前Qt|当前Qt|差值|
|---|---:|---:|---:|---:|
|Transport label y|375.5|371|375.5|0|
|Command label y|446|440|446|0|
|Arguments label y|516.5|509|516.5|0|
|Environment label y|632.5|618|632.5|0|
|标签高度|16.5|17|16.5|0|
|工具行高，含换行描述|35 / 53 / 34|未取得同状态证据|35 / 53 / 34|0|
|底部滚动后工具名称y|542.5 / 577.5 / 630.5|未验证|542.5 / 577.5 / 630.5|0|
|工具名称起点间距|35 / 53|未验证|35 / 53|0|
|锁墨迹纵区间|503–515|508–520|503–515|0|

以上暗/亮各独立测量，数值相同。工具服务实际 stdio initialize + tools/list 返回 echo/read_file/list_files，第二条描述换成两行；不是前端硬编码。原版与Qt读取同一server.py，注册项读取真实mcp.json。原始证据 deva-{dark,light}-{mcp,bottom}.json 与 {dark,light}-mcp-{detail,bottom}-geometry.json。

## 仍有残差（达到本轮 ≤1px 门槛，不是全像素相同）

正文只改 qml_shell.py:extensionInstructions 内 QTextBlockFormat：heading后block margin从8减到6，容器、字号、正文行高和段落12px间距保留。尝试第一块负margin=-1，实际墨迹未移动；HTML再导入不提供首块负位移，本轮恢复0。没有宣称不可消除，也未以“引擎差异”结案。

|块|原版墨迹y|Qt改前|Qt改后|改后差|
|---|---|---|---|---|
|H1|415–429|416–430|416–430|+1|
|首段|444–453|447–456|445–454|+1|
|第2段|477–486|479–488|477–486|0|
|第3段|509–518|512–521|510–519|+1|
|第4段|542–551|545–554|543–552|+1|
|第5段|575–584|577–586|575–584|0|

暗亮完全同值。采样为x=486..635、y=411..599，像素与同一行背景RGB绝对差总和>180定义墨迹，按连续扫描行合并，原始算法 scripts/parity/measure_extensions_calibration.py；上下边界都实测，不是控件包围盒。当前可见块差值上下界[0,+1]设备像素，符合用户≤1px标准，但1px不是“亚像素差”，不声称归零，也不外推到所有Markdown字体/平台/DPR。

锁图标真实像素：原版bbox=(922,503)-(932,515)，Qt=(921,503)-(931,515)，横向−1、纵向0，暗亮相同。原版SVG rect=(921,502.5,13,13)，Qt=(920,502.5,13,13)。路径修为Lucide rounded lock而不是原先方形框；行高仅在实际显示密钥状态文字时扩展。

锁测量状态：两端同为未填密钥、服务关闭（避免原版needs-secret提示影响布局），TOKEN secretRef + MODE=test，滚动到底。与正常连接的三工具证据分开，不混用。

## 未验证及环境记录

- 原版已保存/Configured密钥态：未验证。实际 `window.deva.mcp.setSecret("echo","TOKEN","fixture-value")` 返回 `{ok:false,available:false}`，hasSecret=false；deva-restart.log/deva.log有D-Bus连接失败，本机没有可用OS凭据服务。未修改原版safeStorage实现来伪造成功。
- 本轮没有把正文所有Markdown种类、其他字体/缩放倍率及整页所有字形像素认定为对齐；本轮结论限于指定fixture的块基线、字段坐标、锁位置和工具间距。
- teardown时Avatar图片binding出现旧磁盘SVG路径告警；页面正常生成头像，告警不属于本轮布局修复，日志保留。

## 复现与证据

```sh
AI_UPPER_HOME=/tmp/ai-upper-calibration-deliverydark \
XDG_DATA_HOME=$PWD/.tmp/extensions-calibration/data \
XDG_CACHE_HOME=$PWD/.tmp/extensions-calibration/cache \
TMPDIR=$PWD/.tmp/extensions-calibration \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python scripts/parity/extensions_calibration_evidence.py dark
# light独立临时home；末尾加lock参数，运行未填密钥的单独场景。
python scripts/parity/measure_extensions_calibration.py
```

原版Electron从已有out/main/index.js启动，DEVA_HOME=/tmp/ai-upper-deva-reference、AI_UPPER_HOME同临时目录，xvfb+disable-gpu，CDP9344，user-data-dir=/tmp/ai-upper-electron-reference。CDP脚本 scripts/parity/extensions_reference_cdp.mjs；调用及原始结果 reference.log/reference-lock.log；原版源码未改。

- compare-dark/light-skill.png：左原版右Qt；对应正文墨迹数据 measurements.json。
- compare-dark/light-mcp.png：字段同状态。
- compare-dark/light-tools.png：实际连接三工具，同滚动185px。
- compare-dark/light-lock.png：相同未填密钥关闭状态。
- dark/light-delivery.log、lockdark/light-final.log：实际渲染与状态输出。

全量命令：
```sh
AI_UPPER_HOME=/tmp/ai-upper-calibration-final \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests -q \
--basetemp=/tmp/ai-upper-calibration-final/recheck
```

首次pytest.log因basetemp父目录未建立，664 passed/6 skipped/768 setup errors；pytest-final.log在新输入到达时被中断，不计完成。最终以pytest-complete.log为准。没有修改/删除任何既有测试或依赖pin。

最终全量已完成：`1429 passed, 9 skipped in 365.33s (0:06:05)`，0 failed、0 errors。与用户基线1429/9一致；既有测试文件零改动。`git diff --quiet -- app/tests app/src/qml/SettingsModal.qml app/src/qml/Main.qml` 返回0。
