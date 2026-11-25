# A：O(1) 成员查询候选因性能门槛回退

起点 a0eedd3，git status --short 无输出；保留前轮 67edda7 全选快路径与数组更新优化。本轮 A 产品源码最终完全回到起点，未声称完成 O(1) 改造。

## 方案和验证

试验使用单独 JavaScript 闭包内的 Object.create(null) 查询表，delegate 读取 selectionRevision 后 contains(id)，确保 QML 绑定收到变更通知。全选采用 all + excluded 补集，部分选择采用 chosen；避免每次选中重建整个 QML 属性映射。查成员是哈希查询（平均 O(1)，非严格最坏情况常数保证）。Proxy 测试记录源数组读取次数：初始化后 10000 次 contains 调用没有再读原数组，结果 1 passed / exit 0，见 lookup-test.log。

单项插入前用 contains 判断是否已存在，避免对未选成员运行 array.indexOf；为了保持有序 selectedSessions 和既有归档接口，删除仍保留数组 indexOf/splice，整个变更不是 O(1)。因此不能把“成员查询 O(1)”冒充“完整点击 O(1)”。

初版额外维护全部 listed ID 的映射，全选最大出现 65.06 ms，撤回该映射；只保留补集与部分选择闭包后，最大仍有波动。最后还调整全选时查询状态更新次序，未通过门槛，整套 A 候选回退，原 QML 未改变。候选源码隔离在 .tmp/selection-slices/Main-rejected.qml、Selection-rejected.js，测试源在 lookup-test-source.py，不留产品目录探针。

## 同口径数据

沿用 followup/selection.py：真实 Main.qml 窗口、五档注入列表元数据、200 段代码/小图片正文、每档三轮选择/取消/全选后滚动；不是数十万真实会话文件。每次点击→processEvents+grabWindow，滚动单独计时。数据为最大样本，单位 ms。

|行数|本轮基线全选|候选最后全选|本轮基线单项|候选最后单项|本轮基线滚动|候选最后滚动|
|---|---:|---:|---:|---:|---:|---:|
|1000|4.73|7.25|5.11|5.51|10.85|12.15|
|100000|14.09|14.10|19.27|5.25|12.53|12.63|
|300000|48.07|59.36|51.39|10.52|13.04|13.01|

上一轮保留基线（followup/REPORT.md）：1000 行为 4.98/4.96/11.70；100000 行 14.53/18.97/12.70；300000 行 50.13/52.01/13.29。候选 300000 行单项改善明显，但全选 59.36 高于 50.13；1000 行的三项也未守住基线。遵守“任何一项退化就回退”的硬要求，不以噪声假设豁免。不同轮次的全部数据均保留 a-after/final/repeat/delivery/last.json，不挑最好一轮交付。

五个规模 120/1000/10000/100000/300000 全选滚动截图前后 RGB bbox 都为 None，最终呈现无差异。产品最终回退，故最终产品 A 三项数字仍对应原已验证实现；表中 after 是被拒绝候选，不是已交付性能。

## 命令与输出

```bash
python .tmp/selection-slices/a-runs.py
AI_UPPER_HOME=/tmp/ai-upper-slices-a-last \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python .tmp/selection-slices/selection.py .tmp/selection-slices/a-last
```

两轮退出码均为 0，原始输出 a-runs.log / a-last.log。Proxy 查询测试命令为 pytest app/tests/test_qml_context_menu.py::test_selection_lookup_does_not_rescan_ids_for_membership（候选期间），退出码 0。测试随候选回退，不污染最终产品回归。

结论：A 目标未达成。已证实成员查询可绕开 QML 大对象属性访问采用原生 JS 闭包，但没有找到同时保持全选最大延迟不退化的可交付实现；完整选择数组的复制/删除和 GC 成本仍在。实际用户桌面/GPU/冷盘未验证，本轮不对其做结论。
