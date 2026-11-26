# 最终交付口径（淘汰释放修复后）

以下是最终产品源码三组数据，优先于后面保留的阶段结果。基线仍为 468f5b7 的 accepted-before 三组。同一24落盘会话、每组冷24+热24、每侧 N=72/路径。

|路径|指标|基线 ms|最终 ms|目标 ms|结果|
|---|---|---:|---:|---:|---|
|热|完整帧中位|140.993|21.603|≤60|达标|
|热|完整帧P95|147.720|23.547|≤80|达标|
|热|最长GUI事件|69.685|14.601|≤16.7|达标|
|冷|完整帧中位|136.105|127.561|如实报告|仍有首次打开成本|
|冷|完整帧P95|146.805|138.209|如实报告|仍有首次打开成本|
|冷|最长GUI事件|65.891|60.050|如实报告|未消除连续阻塞|

冷路径三项相对基线均改善；若沿用热阈值，差距分别 +67.561 / +58.209 / +43.350 ms。热点击派发中位20.624 ms（基线11.190），冷派发11.420 ms（基线11.232）；派发额外耗时已披露，不用它掩盖完整帧结果。

最终缓存：冷0/72命中、热72/72命中，合计50%；三组 RSS 峰值284348 / 284428 / 282580 KiB，最大277.762 MiB。每组24项，74,526,720 bytes估算计费。96项淘汰压力稳定在32项，最终峰值312.805 MiB，具体序列和先前失败数据保留在下文。

`python .tmp/hot-cache/final-summary.py` exit 0，final-summary.log：三组最终冷/热PNG与已提交基线逐像素RGB一致，144次完整文本哈希、标题、活动ID、末轮文本断言全过。release-after-*.log/json/png 为最终原始数据。运行退出码由 final-release-exits.json 明确保存，非零轮次不算通过。

|版本|组|路径|N|中位 ms|P95 ms|最长GUI ms|
|---|---:|---|---:|---:|---:|---:|
|accepted-before|1|cold|24|138.024|145.923|65.891|
|accepted-before|1|hot|24|144.327|149.795|67.236|
|accepted-before|2|cold|24|135.734|142.962|65.054|
|accepted-before|2|hot|24|140.981|145.889|69.685|
|accepted-before|3|cold|24|134.807|151.171|64.270|
|accepted-before|3|hot|24|139.290|144.333|67.485|
|release-after|1|cold|24|122.518|131.127|54.674|
|release-after|1|hot|24|21.345|22.044|13.591|
|release-after|2|cold|24|128.681|138.209|60.050|
|release-after|2|hot|24|21.646|23.547|14.601|
|release-after|3|cold|24|128.458|134.217|58.050|
|release-after|3|hot|24|22.163|22.472|14.215|


---

以下为保留的探索与初版验证记录，不能替代上面的最终交付数据。

# 验收结果

|版本|路径|N|完整帧中位 ms|P95 ms|最长 GUI 事件 ms|点击派发中位 ms|
|---|---|---:|---:|---:|---:|---:|
|accepted-before-cold|冷|72|136.105|146.805|65.891|11.232|
|accepted-before-hot|热|72|140.993|147.720|69.685|11.190|
|accepted-after-cold|冷|72|125.706|134.716|55.406|11.398|
|accepted-after-hot|热|72|21.732|23.300|14.293|20.820|

热路径三指标满足 60/80/16.7 ms；冷路径相对基线三指标均降低，但仍超出这些数值，未消除首次打开卡顿。点击派发包含完整同步缓存切换，热路径派发中位从 11.190 升至 20.820 ms（含 QTest 默认鼠标事件开销）；它不是 GUI 单事件，不隐瞒该回归，用户本轮三项验收为完整帧/P95/单 GUI 事件。

## 各组原始口径

|版本|组|路径|N|中位 ms|P95 ms|最长 GUI ms|
|---|---:|---|---:|---:|---:|---:|
|accepted-before|1|cold|24|138.024|145.923|65.891|
|accepted-before|1|hot|24|144.327|149.795|67.236|
|accepted-before|2|cold|24|135.734|142.962|65.054|
|accepted-before|2|hot|24|140.981|145.889|69.685|
|accepted-before|3|cold|24|134.807|151.171|64.270|
|accepted-before|3|hot|24|139.290|144.333|67.485|
|accepted-after|1|cold|24|127.087|133.689|55.406|
|accepted-after|1|hot|24|21.504|23.240|13.929|
|accepted-after|2|cold|24|124.455|134.716|55.204|
|accepted-after|2|hot|24|22.352|23.300|14.293|
|accepted-after|3|cold|24|124.863|129.546|53.879|
|accepted-after|3|hot|24|21.700|22.418|13.689|


## 帧与文本

`python .tmp/hot-cache/summarize.py` exit 0，输出 summary.log：12 张冷/热最终帧与已提交 costs/sync-1.png RGB 每像素一致，144 次完整文本 SHA-256 一致；每次活动 ID、标题、末条正文断言通过。三组候选与基线各冷 24 + 热 24，runner `subprocess.run(check=True)` 全部 exit 0；非零退出的早期探针（漏导入 NameError，exit 1）未纳入。

## 剩余成本（独立 profile，不作为正式性能样本）

|阶段中位 ms|冷|热|
|---|---:|---:|
|_publish|5.554|5.398|
|_rows|2.914|2.875|
|parse_markdown|2.113|0.000|
|_table_column_widths|3.856|0.000|
|render_blocks|34.785|0.000|
|render_markdown|37.420|0.000|
|attach|48.452|0.000|
|attach_code_viewports|1.951|0.000|
|attach_table_grids|25.861|0.000|
|activate|0.349|0.199|

这些阶段有嵌套，不能相加：render_markdown 含 parse/render_blocks；attach 含 grids/code overlays。热命中解析、构建、挂接调用均为零；冷路径最大成本仍是约 37 ms worker 构建与约 48 ms GUI attach，其中约 26 ms 表格网格。Qt C++ 纯布局与光栅绘制无法由这些 Python 探针独立拆出，未验证；不将总残差臆测为某个阶段。

## 内存

正式三组热命中 72/72=100%，冷命中 0/72，总体 72/144=50%；每组缓存 24 项、计费 74,526,720 bytes。进程峰值 RSS 分别 284636/282548/284660 KiB（最大 278.0 MiB）；基线最大 205716 KiB（200.9 MiB），约增加 77.1 MiB。缓存预算 128 MiB 是估算存储而非进程硬 RSS 限制。

初次 96 会话压力（stress.json）只调用 processEvents、不主动排空 DeferredDelete；32 项、99,368,960 bytes 固定，但峰值 RSS 从第32项 321716 KiB 增至第96项398060 KiB。不能凭条数上限宣称无内存增长，后续补测 Qt 延迟删除并记录结果。

## 实际命令

`python .tmp/hot-cache/accepted-runs.py > .tmp/hot-cache/accepted-runs.log 2>&1` exit 0。runner 为六次进程分别设置 `AI_UPPER_HOME=/tmp/ai-upper-finaldisplay-accepted-{before,after}-{1,2,3}`，`LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu`，`PYTHONDONTWRITEBYTECODE=1`，运行 `.venv/bin/python .tmp/hot-cache/measure.py .tmp/hot-cache/accepted-{before,after}-{1,2,3}`。代码前后从 .tmp 快照切换并 finally 恢复，正式基线是 468f5b7，未改分支/历史。JSON 为真正逐样本结果，log 中跨冷/热的总中位不作验收结论。

`python .tmp/hot-cache/remaining.py` 顺序运行 profile/stress，状态 remaining-exits.json 均为 0。geometry 的像素失败证据保留，但不纳入验收。脚本启动后都设 QT_QPA_PLATFORM=offscreen、QT_QUICK_BACKEND=software。


源码证据：`qml_shell.py:1391` 缓存查找/键、`:1434` GUI 独立显示实例、`:1458` 直接 fragment 挂接、`:1467` 同步更新失效；`markdown/cache.py:36` 数量/预算、`:58` 复用与旧实例释放、`:74` LRU；`markdown/body.py:215` 一次 insertFragment；`markdown/viewport.py:139` 未改变的逐表网格热点。`test_display_cache.py` 覆盖 key 失效、LRU、真实 QML 编辑失效/复用、水平代码滚动重置和图片绕过。

## 全仓库回归

最终产品源码（含水平代码滚动重置）执行全量 pytest，未筛文件：`1399 passed, 9 skipped in 275.36s (0:04:35)`，**0 failed，退出码 0**。日志 pytest-full.log。新增 3 个测试包括真实 QML 文档 identity 复用、编辑/字号/图片失效与淘汰、横向代码滚动重置；原有 openSession/stale generation/正文/桥接测试全过。9 个条件 skip 未执行，不当作通过，完整打包 E2E 未开启。


## LRU 实际释放修复

仅补齐 DeferredDelete（stress-flush.json，exit 0）仍从第32次322328 KiB增长到第96次393984 KiB，否决“只是脚本未清空事件”的解释。移出 Python 容器不能保证 QML/信号持有的 C++ 文档及时释放；最终 `Display.release` 对目标和 staging 文档显式 deleteLater，并解除高亮器关联/清理 overlay。真实 QML 测试追加 shiboken6.isValid 断言确认淘汰后 C++ 实例已销毁。

同一96会话压力、同一每轮清空 DeferredDelete：release-stress.json/log，exit 0。32项、99,368,960 bytes；峰值 RSS 第24/32/48/64/80/96次 = 282068 / 316300 / 320296 / 320312 / 320312 / 320312 KiB，末32次平台稳定，最终312.805 MiB。这是此夹具下内存有界的实测，不是任意正文大小的物理内存硬保证。旧增长数据保留，不计为最终通过。

修复发生在首轮全量测试后，因此首轮1399通过不能代替最终验证；最终三组见本报告开头，最终全量回归在文末记录。


最终退出与推送收据将在 `.tmp/hot-cache/PUSH-RECEIPT.md` 保存。此文件是本地最终 hash 的运行收据，不将其自身提交造成 hash 递归；受控报告与性能/测试原始数据全部正常提交。全部 .tmp 工作文件均在 gitignore 内，交付目录不留未跟踪文件。


## 回归期间一次失败及处理

释放修复后的第一次全量结果：`1 failed, 1398 passed, 9 skipped in 271.64s`，pytest exit 1（final-release-exits.json），不计通过。失败 `test_actual_qml_approval_and_answer_buttons`：后台 pending 请求存在，但固定 pump(1s) 后 QML prompt.visible 为 False；原始 traceback 在 pytest-release-full.log。同文件独立执行 `3 passed in 20.20s`，exit 0（pytest-isolated.log）。

该用例的 worker 入队与30 ms桥接tick属于两个异步阶段，固定时长不是完成条件。只修改测试同步：用现有 `_pump(predicate, timeout=5)` 等待请求和弹窗都就绪；仍用真实鼠标事件执行批准/拒绝/回答/取消，仍检查 outcome/answer，未跳过或删断言，产品审批逻辑未改。没有足够证据断言底层只因主机调度；保留完整失败证据。最终全量必须在此测试修改后重新 exit 0 才允许推送。

本地代码提交：`b11ed32`（显示文档LRU、直接fragment挂接、失效与释放、相关测试）；`b2de19d`（审批QML用例按完成条件等待，未改产品逻辑）。报告与数据为后续独立提交。最终普通推送前原远端 `468f5b7c5db151bcb7ddfb139c6767ddbb348d35`。


## 最终全量结果（允许推送的门槛）

真实输出：`1399 passed, 9 skipped in 276.83s (0:04:36)`，0 failed，进程退出码 **0**；FINAL-EXITS.json 与 pytest-final.log 保存最终状态/完整输出。9个条件跳过未执行，不算执行通过。全仓库、未筛文件；本轮最后一次产品代码变更已被此完整回归覆盖。`git diff --check` 无输出、exit 0。
