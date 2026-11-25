# 完整帧成本分解与最终策略裁决

起点 80bc3b5，git status --short 无输出；slices/ 已有 45 个受控文件，用户提到未跟踪的情况与磁盘现状不符。本轮保留这些已提交证据，不删除或重复归档。

## A：保持现状；阈值边界未完全通过

按决定不再追 30 万行，产品 A 源码没有修改。沿用真实窗口压力脚本，仅测 1000/100000 两档，三轮全选、单项切换、取消、已选后滚动；正文仍是 200 段代码与小图片。第一次完整流程最大 12.263 / 19.051 ms。因为点击到抓帧并不等于 GUI 单次阻塞，补加 QGuiApplication.notify 事件计时，结果两档最长点击 GUI 事件分别 3.235 / 17.030 ms；第二次流程最大 14.327 / 20.179 ms。原始 a*.json/log 保留全部样本。

1000 行可以按标准收口。100000 行出现 17.030 > 16.7 ms，超出 0.330 ms，不能宣称阈值全部通过；遵守“不再追极端规模”的意图，本轮不引入新的数组兼容折衷。A 的整体收口标为“保持现状、100000 行边界超限待观察”，不是两档硬门槛已达成。notify 本身有插桩成本且主机负载有波动，未用这一点删除超限证据。滚动仍仅有到抓帧计时，滚动单事件最长值未单独插桩，未验证。

## B 成本分解

profile.py 使用同一 24 条真实落盘会话/30 轮正文夹具，在 GUI/worker 函数和 attach 两个阶段加计时。数据为 24 样本阶段中位，profile 总帧中位 138.014 ms。下表有嵌套项，不能相加；百分比为各自中位 / 总中位，仅用于判断热点。

|阶段|中位 ms|占总中位|位置/含义|
|---|---:|---:|---|
|会话列表及状态发布|5.474|4.0%|qml_shell.py _publish；其中 _rows 2.888|
|Markdown 解析|2.087|1.5%|markdown/document.py:314 → parse_markdown|
|表格列宽测量|3.978|2.9%|document.py:792；包含已有纯文本测宽缓存|
|块与格式/表格文档构建|35.107|25.4%|document.py:541 render_blocks，包含测宽|
|后台整份文档构建|37.521|27.2%|prepare.py → render_markdown，包含解析和块构建|
|显示文档替换/高亮/布局与图片资源|29.809|21.6%|body.py:170 attach；原 attach_steps 阶段 0|
|表格网格/逐表格式调整|28.026|20.3%|viewport.py:139 attach_table_grids|
|代码局部视口|2.072|1.5%|viewport.py attach_code_viewports|
|全部 overlay 阶段|30.207|21.9%|原 attach_steps 阶段 1，含上两项|
|最终 grabWindow|0.673|0.5%|完成所有阶段后的抓帧，非全部内部绘制|

纯 JSON 读取调用合计约 0.039 ms，缓存已热。没有单独测出 Qt C++ 的纯布局与纯首次光栅化时间：它们交错在 endEditBlock/表格 setFormat/事件处理中，当前插桩测的是上述综合阶段。此项细分“未验证”：需要 Qt 原生 profiler/调用栈级采样，不能把 grabWindow 当成所有绘制。阶段中位约 34.8 ms 未由非重叠函数计时覆盖，包含 worker 排队/线程与事件调度、复制和中间绘制；未凭空分配给某一函数。

最大综合成本是后台构建 + GUI 整篇替换 + 逐表网格，不是 Markdown 解析。仅把 parser 放缓存无法满足 60/80/16.7 目标。

## 热点试验和回退

1. 针对 viewport.py:188 每个 table.setFormat 的同步通知，用 QSignalBlocker 包住格式变更。完整帧中位 131.311、P95 138.696 ms，但 RGB 差异 bbox=(484,27,1278,644)，最终布局改变，撤回。
2. 将表格倒序处理以减少前面格式变化引发后续布局，中位 135.283、P95 141.372 ms，但 RGB bbox=(486,28,611,621)，撤回。
3. 关闭显示文档 undo history，中位 134.679、P95 148.730 ms，RGB 一致，但无稳定收益，未保留。
4. 没有新增文档/LRU 缓存，因此没有以命中数据遮盖未命中退化；本轮正式数据仍为 24 个不同会话首次切换。
5. 未重新引入此前已被退出崩溃证据否决的跨线程 QObject 移交。合法可重入不等于当前 PySide/对象生命周期实现已验证安全；继续保留 worker 返回 fragment/image 值对象。

以上探索实际命令统一为 AI_UPPER_HOME=/tmp/ai-upper-cost-{profile,block,reverse,undo}、LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu、PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .tmp/frame-cost/{profile,switch}.py .tmp/frame-cost/{profile,block,reverse,undo}；均 exit 0，日志随报告提交。非零退出轮次未计入。

## 最终裁决：撤回分段，恢复单次 GUI 挂接

遵照明确规则：分段未证明三项同时改善，删除 body.attach_steps / bridge._advance_attach，worker 结果恢复一次 _body.attach、rendered++、scrollBottom。后台准备与值对象传输保持原样。产品只改 body.py、qml_shell.py；A 与依赖不变。

本轮三组前后各 24 次（每侧 N=72），所有阶段完成后抓帧，notify 测 GUI 事件，前后同一 switch.py、同一最终 QML 与夹具，无 pytest/profile 并发。后台宿主负载不可控。基线是分段，sync 是最终单次挂接。

|组|分段中位/P95 ms|单次挂接中位/P95 ms|
|---|---|---|
|1|138.063 / 142.250|133.866 / 137.929|
|2|138.732 / 149.639|134.662 / 141.751|
|3|137.299 / 140.699|142.084 / 253.654|
|合并|137.940 / 144.993|136.596 / 160.645|

最长 GUI 事件：分段 36.060 ms，单次 129.696 ms；第三组有高尾样本，不能以较快两组代替。三组最终帧 RGB bbox 全 None；目标末轮文本、标题、活动 ID 断言全部通过。

这一结果只说明按用户策略撤回分段，不代表新性能改善。最终中位 136.596 >60、P95 160.645 >80、最长 GUI 129.696 >16.7：三项目标全部未达成。较好两组单次挂接中位约 134 ms，仍远未达 60 ms；剩余大成本是整篇文档重建、目标布局、高亮和逐表 overlay。

命令：`python .tmp/frame-cost/sync-runs.py`，完整输出 sync-runs.log；各子进程 AI_UPPER_HOME=/tmp/ai-upper-cost-{before,sync}-{1,2,3}，输出 JSON 保存逐次 frame/dispatch/max_gui 与阶段计数，三组均 exit 0。runner finally 恢复源码，随后人工应用最终单次挂接并删除未再使用的分段入口。

## 限制

没有实现可使三项同时达标的核心渲染优化；没有把“回退策略”说成“性能目标完成”。实际桌面/GPU、大图、冷盘未验证；这次仅同一机器 offscreen/software 后端。全量测试结果与最终 SHA 在收尾部分补记。所有新临时文件在 .tmp/frame-cost；应用/测试 AI_UPPER_HOME 指 /tmp。未 push/新分支/改 pin/操作 deva/真实 ~/.ai_upper。

点击派发中位数（同一三组）：分段 11.268 ms；最终单次挂接 11.232 ms。


## 全量验证和收尾

最终代码提交 965c385（恢复单次挂接，删除分段入口）。最终工作树运行全仓库 pytest，没有按文件筛选：

```bash
AI_UPPER_HOME=/tmp/ai-upper-cost-full-tests QT_QPA_PLATFORM=offscreen \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m pytest --basetemp=/tmp/ai-upper-cost-full-pytest -q
```

真实输出：`1396 passed, 9 skipped in 271.50s (0:04:31)`，进程退出码 0。完整 stdout 在 pytest-full.log。9 个 skip 沿用项目条件，不当成已执行通过；没有显式开启 AI_UPPER_E2E 的完整构建 E2E。未运行 CI。

全量测试期间产品源码未再变更。git diff --check 无输出，报告及数据提交后 git status --short 无输出；slices/ 原有证据继续受控。本轮全部结论使用真实命令及输出，未删除高尾样本，未宣称 A 两档全部过线或 B 性能目标达成。
