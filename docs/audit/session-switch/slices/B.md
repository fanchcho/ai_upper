# B：GUI 挂接分阶段；完整帧目标未达成

代码提交 0037a65。起点 a0eedd3；没有推翻已验证的后台准备和值对象交付，没有跨线程操作目标文档。最终 A 候选已回退，正式 B 三组均使用保留的原 A QML。

## 最终改动

- app/src/markdown/body.py:201 attach_steps 将一次挂接拆为两个 GUI 阶段：清理旧 overlay、替换正文、目标高亮及图片资源注册完成后 yield；下一阶段创建代码视口和表格网格。原同步 attach 包装器仍遍历全部步骤，用于首屏/同步渲染与原测试。
- app/src/qml_shell.py:1427 接收 worker 成果后创建步骤迭代器；:1431 _advance_attach 每次只推进一步，QTimer.singleShot(0) 把后续步骤交还事件循环。每步检查 generation，切换会话/重新渲染/关闭后不允许旧步骤继续覆盖新状态。全部步骤结束才增加 rendered 并滚到底部。
- app/tests/test_qml_shell.py 的 _tick_until 同时处理 Qt 事件，以覆盖真正的分阶段完成，不把 worker 已完成当作目标文档已完成。

分段边界是真实 GUI 事件边界；不是将同一事件内部计时拆成几个数字。当前仍有两个较大的阶段，未做到每个阶段小于 16.7 ms。中间帧可能已显示正文而表格 overlay 尚未创建；最终排版和滚动与原版一致。

## 同口径与测量结果

沿用 followup/switch.py 的 QGuiApplication.notify 插桩、24 条真实落盘会话 × 30 轮代码/表格内容、顺序 1..23,0、offscreen/software 后端。修正完成判据为 rendered 增加后再抓帧，避免分段后只看到目标文本就提前计时结束；修复前后都用这个判据。仍断言 activeId、activeTitle 和末轮文本。每侧三组新进程共 N=72，AI_UPPER_HOME 每次独立 /tmp 路径，不与 pytest 并发执行。后台宿主负载不可锁定，所有样本公开。

|组|前完整帧中位/P95 ms|后完整帧中位/P95 ms|前最长 GUI 事件 ms|后最长 GUI 事件 ms|
|---|---|---|---:|---:|
|1|133.602 / 137.062|144.529 / 163.476|64.528|40.185|
|2|137.746 / 141.132|139.737 / 153.695|67.396|33.889|
|3|143.127 / 147.334|133.787 / 142.928|68.031|33.248|
|合并 72 次|138.685 / 147.065|140.045 / 159.897|68.031|40.185|

点击派发中位数 11.326→11.356 ms。最长 GUI 事件下降约 40.9%，但完整帧中位增加约 1%，P95 增加约 8.7%。上一轮保留值为完整帧 137.946/148.193、最长事件 68.652、派发 11.225；原同步参照为 119.303/124.912。本次仍明显慢于原同步参照，**该项目标未达成**。

原因：两阶段没有减少文档构建/复制、目标布局、高亮和逐表 overlay 工作总量；让出事件循环允许 Qt 渲染中间状态，额外事件调度和中间绘制增加完整帧尾延迟。无法从单一 offscreen 主机精确分离系统调度与中间绘制各自占比，该归因是根据代码结构与数据的解释，未宣称已做 OS 级采样。

三组最终 RGB 截图差异 bbox 均 None；文本/标题/活动 ID 断言全部通过。原始 b-before/after-{1,2,3}.json 保存每次 notify 最长事件、dispatch、frame 和阶段数据，截图同名 .png。初次分段探索测得最大约 34 ms，但不作为最终交付数字；最终使用正式三组最大 40.185 ms，不挑选较好轮次。

## 真实命令及退出码

```bash
python .tmp/selection-slices/b-retained-runs.py
# 每个子进程的结构：
AI_UPPER_HOME=/tmp/ai-upper-slices-retained-b-after-1 \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python .tmp/selection-slices/switch.py .tmp/selection-slices/b-retained-after-1
```

三组前后全部退出码 0；聚合调用日志 b-retained-runs.log。runner 临时替换两个候选文件测试基线，并在 finally 恢复最终文件；基线文件是起点 a0eedd3 的 body.py、qml_shell.py。后续可从本目录 switch.py 直接重测当前版本（输出必须写 .tmp，home 用新的 /tmp 后缀）。

```bash
AI_UPPER_HOME=/tmp/ai-upper-slices-retained-tests QT_QPA_PLATFORM=offscreen \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m pytest app/tests/test_qml_context_menu.py \
app/tests/test_qml_session_switch.py app/tests/test_qml_shell.py \
app/tests/test_chat_sessions_vm.py app/tests/test_markdown_body.py \
app/tests/test_markdown_document.py app/tests/test_markdown_highlight.py \
app/tests/test_markdown_chunked.py app/tests/test_qml_packaging.py \
--basetemp=/tmp/ai-upper-slices-retained-pytest -q
```

输出 `199 passed in 74.61s`，进程退出码 0。此前候选集成也为 199 passed / exit 0；A 的独立 Proxy 查询测试另为 1 passed / exit 0，仅作为被拒绝候选的证据，不计入最终产品测试数。git diff --check 无输出。

## 未解决

- A 的 O(1) 成员查询候选因全选退化撤回，见 A.md；产品仍是上一轮有效实现。
- B 完整帧中位/P95 未回到原同步水平，最长 GUI 事件仍约 40 ms；仅单次阻塞改善。
- 真实桌面合成器/GPU、图片密集大图、冷盘与用户真实库未验证，原因是本轮仅有相同本地 offscreen 夹具。
- 未把“阶段拆开”说成“总工作量减少”，也未将两个目标标为完成。

硬约束保持：develop 本地提交，无 push/新分支/依赖 pin 修改，未操作 deva 或真实 ~/.ai_upper。临时探针仅在 .tmp/selection-slices；A 被拒绝源码差异以报告证据保存，不在产品导入路径。
