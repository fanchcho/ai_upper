# A 规模压力与 B 正文后台准备（续查）

## 交付边界与未完成项

- [x] 起点 git status --short 无输出；git log --oneline -8 确认 HEAD 5884c70、11c63f2 在盘上。
- [x] A 五档规模、已选集合切换、全选/取消、全选后滚动、长正文及图片资源夹具。
- [x] A 复现规模瓶颈、局部修复、同脚本前后数据、五档选中滚动截图 RGB 一致。
- [x] B 独立文档后台构建、文档片段值交接、取消与过期结果防护、关闭清理。
- [x] B 三组相同真实落盘会话、相同 notify 插桩计时和最终帧 RGB 比较。
- [ ] 真实用户桌面症状全部消失：未验证，没有实际用户库/桌面。
- [ ] 全部读盘与共享 store 投影后台化：未完成，仍在 GUI；共享 store 缓存及 host 会修改数据，不能直接跨线程并发操作。
- [ ] 主线程挂接分段且保持中间与最终布局语义：未实现，最终依然约 69 ms 最长 GUI 事件；不能称为消除卡顿。
- [ ] A 数十万真实落盘文件：未验证，压力列表是元数据注入，不冒充数十万文件读取。

本轮仍遵守 develop 本地提交、不 push、不新分支、不改依赖 pin、不操作 deva 和真实 ~/.ai_upper。环境沿用父目录 environment.txt。

## A：旧夹具遗漏了什么

入口 Main.qml:665 MouseArea 的选择态分支 → toggleSelect(:1871) / toggleSelectAll(:1884)。没有 Python slot、IPC、读盘、Markdown 渲染或 modelReset；修改的是 QML selectedSessions。列表是虚拟化 ListView，只有可见 delegate 加缓存区实例化。

旧夹具只有 120 条真实会话、每条一条短消息、初始选择集合小，未测全选后的列表尾部滚动。当前夹具保留真实 Main.qml、bridge 和 ticker、120 条实际文件，但把列表元数据依次扩大到 120/1000/10000/100000/300000；同时正文放置 200 段含代码、粗体与内联 PNG 的内容。超大列表不读文件，所以仅隔离 QML 选择瓶颈；真实文件数量、冷盘、用户 GPU 和系统合成器与现场差异仍未知。

每档三轮：全选→取消一行→恢复该行→取消全选→再全选→滚动到尾部抓帧→回顶部→取消全选；断言选中数，抓取选中状态及最终截图。每次点击从 QTest.mouseClick 到 processEvents+grabWindow；滚动另标 scroll。以 16.7 ms 为单帧预算、50 ms 为本报告“明显卡”的操作阈值，非通用 UX 定律。

| 会话元数据行数 | 前全选最大 ms | 后全选最大 ms | 前单项最大 ms | 后单项最大 ms | 前已选滚动最大 ms | 后已选滚动最大 ms |
|---|---:|---:|---:|---:|---:|---:|
|120|5.05|4.97|5.23|5.15|10.89|11.09|
|1000|4.97|4.98|5.18|4.96|11.77|11.70|
|10000|9.03|7.61|4.83|4.33|15.60|12.21|
|100000|28.76|14.53|23.90|18.97|63.76|12.70|
|300000|89.13|50.13|102.15|52.01|256.64|13.29|

拐点：已选后滚动在 10 万行超过 50 ms，勾选/全选在 30 万行超过 50 ms。修复后 30 万行勾选/全选仍约 50 ms，不能说已消除。120～1 万行的原始“只勾选就卡”仍未复现；当前覆盖下全流程最大约 15.60 ms（基线），不包括初始化和正文首次生成。

根因与最终修复：Main.qml 原 toggleSelect slice 复制整个大数组；delegate 的 selected 绑定逐行 indexOf 扫描整个选择集合，滚动到尾部最差；toggleSelectAll 点击时遍历完整 QVariantList。最终原地更新数组并显式发送 changed，保留选择顺序与归档接口；列表变化时提取 ID 数组，点击全选复制 ID；明确全选状态下 delegate 直接返回 true，选择集/列表变化清除此快路径。没有改变部分选择的语义。

失败方案：Set 集合在 1 万项出现约 873 ms；字符串映射在 30 万项全流程最大约 515 ms；均撤回。最终只保留数组与全选快路径。五档全选滚动截图 RGB diff bbox=None，最终空选择截图同样一致。此前只测取消后滚动会遗漏主瓶颈，已纠正测试序列。

## B：线程可行性与实现

Qt 官方说明 QTextDocument/QTextCursor 是 reentrant，并非只能在 GUI 使用；各线程只能操作独立实例，不能并发操作正在显示的同一文档。参考 https://doc.qt.io/qt-6.10/threads-modules.html 与 https://doc.qt.io/qt-6.11/threads-qobject.html 。用户要求的安全边界被保留：QML 活动文档与 overlay 始终只在 GUI。

后台部分：markdown/prepare.py:prepare_document 在单 worker 内建立私有 QTextDocument，执行 Markdown 解析、表格宽度/字体度量、独立文档结构构建、_load_image 的 QImage 图片解码与读取；后台文档不跨线程；返回 QTextDocumentFragment 和图片资源值，后台文档在后台销毁。GUI 将片段写入原有源文档后再 attach。没有创建 QPixmap 或 QQuickItem。解析与测宽已整体移出 GUI，不仅是解析树搬运。

GUI 部分：qml_shell.py:616 openSession 先更新 active 与 _publish，再 :1373 _prepare_render 取得当前正文字符串并提交 worker；完成信号以 QueuedConnection 回到 :1400 _finish_prepared_render。generation 排除旧会话/主题/同步重新渲染后的结果，排队任务取消，正在工作的结果到达后丢弃；退出时 shutdown 等待 worker 完成并清队列。高亮器与 GUI 自有文档的生命周期保持原样，不交接 QObject。_body.attach、目标文档高亮、overlay 与贴底留在 GUI。

读盘范围限制：_markdown 和 _publish 仍使用共享 store 热缓存并在 GUI 执行，未把主会话 JSON 读取或全量列表投影后台化。读取图片在 worker，主会话缓存一致性尚未改造。也没有将现有流式发送重渲染改成异步，本项针对普通切换。

挂接方案评估：独立源文档后台构建有效降低单事件阻塞；已有 attach 是单次 edit block 的整篇 fragment 搬运。拆分目标文档会引发多次 QQuickTextEdit 布局，并暴露半篇正文和滚动跳动；本轮未实现分段候选，不能声称实测证明其无效。新正文等待阶段仍显示旧正文，同时选中态/标题先更新；没有新增视觉控件。最终帧与基线一致，但中间态与旧版阻塞式切换不同，必须明确此行为。

失败与修正：初版移交源文档未调整 highlighter parent 导致 Internal C++ object already deleted；调整 parent 后仍在 pytest 退出时崩溃，整个 QObject 移交方案已撤回，换成值对象传输；先提交 worker 再发布列表发生 GIL 竞争，单次 mouseClick 达 125 ms，改为先发布；仅靠 ticker 收结果总延迟约 140 ms，改 queued signal 即时交付。上述失败日志只留 .tmp/selection-thread，不纳入最终数据。

## B 同口径最终测量

switch.py 基于原 measure.py，同样 24 条真实落盘会话 × 30 轮代码/表格消息，顺序 1..23,0；每组新进程新 /tmp home。前后都等待目标末轮消息真正出现在 QML 文档，然后抓最终帧。QGuiApplication.notify 对 GUI 线程每个事件计时，max_gui_ms 为最长一次事件处理，包括其嵌套调用；这是事件边界测得的阻塞指标，不是 OS 级全线程采样。额外保留 dispatch 和总帧时长。三组 RGB bbox 都为 None。

|组|前最终帧中位/P95 ms|后最终帧中位/P95 ms|前最长 GUI 事件 ms|后最长 GUI 事件 ms|
|---|---|---|---:|---:|
|1|122.857 / 126.613|134.176 / 137.447|103.601|61.705|
|2|119.884 / 122.081|137.258 / 140.543|98.983|63.580|
|3|118.745 / 121.384|145.424 / 149.288|99.724|68.652|

总计每侧 72 次，最终聚合数值：

```text
before: N=72, final frame median=119.303 ms, P95=124.912 ms, max GUI event=103.601 ms, dispatch median=118.483 ms
after: N=72, final frame median=137.946 ms, P95=148.193 ms, max GUI event=68.652 ms, dispatch median=11.225 ms
```

最长事件 103.601→68.652 ms（下降 33.7%），点击派发约 120→11 ms；最终完整帧变慢，值对象交付需要一次源文档片段复原，Python 线程/GIL 与调度也增加墙钟时间。不能把响应更早写成总吞吐提高。


最终 B 三组前后均使用最终 A QML；只切换 bridge 为基线或最终版本，普通点击不进入选择态。当前主机无测试/profile 并发执行正式测量，但无法保证宿主其他负载绝对一致。

## 实际命令与产物

所有命令从仓库根执行。原始脚本与 JSON/日志随本报告提交；探索临时文件只在 .tmp/selection-thread。每次 home 使用新的后缀避免夹具目录冲突。

```bash
python .tmp/selection-thread/a-final-runs.py
python .tmp/selection-thread/values-runs.py
# 每个子进程实际使用：
AI_UPPER_HOME=/tmp/ai-upper-thread-before-values-1 \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python .tmp/selection-thread/switch.py .tmp/selection-thread/b-before-values-1
```

可独立用本目录 selection.py / switch.py 代替临时脚本重测当前版本；旧版本基线为 5884c70 的 Main.qml 和 qml_shell.py，脚本 finally 恢复最终文件。正式 B 输出逐组见 values-runs.log，A 输出见 a-final-runs.log。


## 退出清理验证记录

第一次集成回归打印 193 passed，但解释器退出发生 segmentation fault，退出码 139，因此该轮不算通过。随后为单元测试中没有 QQmlEngine / aboutToQuit 事件的 bridge 加入夹具清理，模拟真实应用关停顺序，在 Qt 仍存活时 join worker。最终退出码必须为 0 才计入交付。日志分别保留 pytest-first-exit139.log 和最终 pytest.log。


跨线程 QObject 移交失败重复验证：193 passed / exit 139 两次；显式释放高亮器仍为 50 passed / exit 139。最终改为片段与图片值交接，先验证 bridge 子集 50 passed / exit 0；完整回归结果另列。失败源码仅存 .tmp/selection-thread/bridge-transfer-failed.py 与 prepare-transfer-failed.py，不在产品导入路径。


## 最终验证与本地提交

A：67edda7；B：bbd3e3f。最终源代码已核对，git diff --check 无输出。

```bash
AI_UPPER_HOME=/tmp/ai-upper-thread-values-full QT_QPA_PLATFORM=offscreen \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m pytest app/tests/test_qml_context_menu.py \
app/tests/test_qml_session_switch.py app/tests/test_qml_shell.py \
app/tests/test_chat_sessions_vm.py app/tests/test_markdown_body.py \
app/tests/test_markdown_document.py app/tests/test_markdown_highlight.py \
app/tests/test_markdown_chunked.py --basetemp=/tmp/ai-upper-thread-values-full-pytest -q
```

真实输出：193 passed in 74.27s，退出码 0。包括异步切换正文与高亮、过期结果排除、worker 确实不在 GUI、选中数组与全选状态、原归档和 ViewModel、正文几何与分块测试。失败方案不能算通过；最终方案没有保留跨线程 QObject 或 highlighter parent 改动。

五档 A 已选滚动截图以及三组 B 最终帧 RGB 差异均为空 bbox；A 辅助元数据列表、200 个 1px 图片的压力条件不等于真实图片密集会话的大图解码/GPU 上传。真实桌面合成器/GPU/冷盘上界未验证，不能把本机上界推广到实际用户库。A 30 万行部分勾选依然线性；B GUI 挂接和 store 读取仍未全部移出。这两项保留为明确未完成范围，没有宣布彻底解决。

退出失败留下的 core 文件（139730944 字节）已移到 .tmp/selection-thread/exit-core；所有探索产物留在 .tmp/selection-thread，不在运行时 QML 目录，不提交 core。
