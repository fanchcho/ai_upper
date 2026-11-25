# B：普通点击切换对话的性能修复

本轮唯一目标是普通点击左侧不同对话，切换正文。未使用 A 勾选或 C 归档数据。

## 验收与范围
- [x] 在 develop 上从当前源码重新定位同步调用链。
- [x] 真实 QML 窗口、24 条真实落盘会话、真实鼠标点击复现。
- [x] 最小局部修复、同口径三组前后测量。
- [x] 三组最终截图与各自基线逐像素一致。
- [x] 每次测量断言 activeId、activeTitle 和正文末轮消息正确。
- [x] 新增真实窗口测试覆盖切换、列表信号、正文、选中、滚动和重命名刷新。
- [ ] 用户实际桌面/实际会话库的卡顿是否消失：未验证；本环境只证明所述夹具局部改善。

没有访问 deva、真实 ~/.ai_upper，没有改依赖 pin、新建分支或 push。运行应用/测试 AI_UPPER_HOME 均为 /tmp/ai-upper-switch-*；测试夹具再在该隔离目录建立 home。测量/探索文件留在仓库 .tmp/session-switch，最终证据在本目录。起点 4bb8799，磁盘对账见上一轮 .tmp/multi-selection-audit/REPORT.md；本轮开始 git status --short 无输出。

## 同步路径和根因

- Main.qml:665 MouseArea 普通左键 → Main.qml:1712 activate → qml_shell.py:611 openSession。这是 GUI 线程同进程 QObject slot，调用返回前全部完成；无 await、网络 bridge 往返或工作线程调度。选择状态由 ShellBridge 承担呈现层职责，并非另有 selection ViewModel。
- openSession 设置 _active、清理当前 TurnState，调用一次 _render、一次 _publish。
- qml_shell.py:1356 _markdown_base → store.load_session → transcript_markdown。chat_session_store.py:165 load_session 首先查缓存，未命中才同步读 JSON、校验模型与恢复拆分记录。不能说每次点击必然全量读盘：本次列表初始化后缓存已热；72 次样本中 load_session 所有嵌套调用合计中位数约 0.044 ms。
- qml_shell.py:1367 _render → BodyDocument.set_markdown → render_markdown(document.py:314) 清空并重新解析/构建完整 QTextDocument。未使用增量正文。body.py:170 attach 清掉旧 overlay，整篇 insertFragment 到 QML 文档，endEditBlock 触发布局及目标高亮器。高亮器在目标文档上按变更重跑；render 仅在高亮器挂到源文档时显式 rehighlight，本次切换不额外对旧正文显式全量高亮。最后 _scroll_to_bottom 保持原来的贴底语义。
- document.py:791 _table_column_widths 对每个单元格调用 _measure_cell_width，后者每次创建临时 QTextDocument 并 idealWidth 布局。相同表头/纯文本值在同一正文中反复出现，仍反复执行昂贵的 Qt 测量。这是本次可安全消除的主要重复成本。
- qml_shell.py:1435 _publish → :1414 _rows → session_rows(:151) → load_sessions，重投影所有可见会话，归档列表另投影一次。load_sessions 每次扫描拆分文件目录，缓存命中后不重新解析全部会话 JSON。修复前无条件 setProperty 整份 sessions / archivedSessions，但固定时间标签后，基线真实窗口测试证实同值赋值没有触发 sessionsChanged / archivedSessionsChanged，因此不能认定每次点击都整表 reset。没有 Python QAbstractItemModel 显式 modelReset。
- 计数器每次记录 _render=1、_publish=1、_rows=1、set_markdown=1、attach=1，load_session=31。未发现 B 点击重复发布。没有单独统计全部 Qt 底层信号，不能断言全局不存在信号风暴。
- cProfile 辅助定位见 profile.txt（单独诊断运行，不混入计时样本）：表格单元格测宽 3000 次、累计约 325 ms；attach_table_grids 约 756 ms；highlightBlock 约 166 ms。这些为整个诊断运行累计数，包含启动；当时仅有源文档禁用 undo 的试验，与最终实现不同，不用于最终提升比例。

## 最终修复

1. document.py:484、:818：沿用 _Renderer 现有局部格式缓存方式，缓存同一 renderer 内纯文本单元格的宽度，以字体和文本为键。每次新渲染自动新建缓存，主题/字号/正文变化不会复用上次结果；富文本、图片单元格保留原测量路径。
桥接层和 QML 最终未修改。基线对照证明同值列表赋值已抑制变化通知，故撤回显式相等判断。新增真实窗口测试用于守住标题、选中、正文和贴底语义；另新增重复表格测量测试，保证 40 格只创建 4 个测量文档且列宽不变。

未保留探索改动：逐表边框批处理会改变网格位置；暂停布局没有稳定收益；禁用 undo 也未纳入最终补丁。正文仍完整同步构建，本修复不承诺消除所有长正文卡顿。

## 测量方法

机器：Linux aarch64，内核 5.10.0-16-arm64；现有 .venv 与 Qt 依赖不变。QT_QPA_PLATFORM=offscreen、QT_QUICK_BACKEND=software。使用 test_qml_context_menu._build_window 加载真实 Main.qml/bridge/host/store，保持原 30 ms ticker。

每个进程新建 24 条落盘会话，每条含 30 轮助手消息，每轮有段落、粗体、链接、Python 代码和两列表格。updatedAt 固定，条目内容固定。先让窗口初始化，再按 1..23,0 顺序连续切换 24 个不同会话。先滚动列表使目标可见（不计入点击），QTest.mouseClick(delay=0) 后 processEvents + grabWindow，抓帧非空且目标正文/标题/ID 断言成功才记样本。该指标为 offscreen 帧抓取完成延迟，包含 QTest/Qt 事件处理成本，不等于显示器输入到光子延迟。

前后同一个 measure.py、同样夹具、同一主机和后端；均在无 pytest/profile 并发时测量。三组独立进程，before 三组先完成，最终 after 三组在撤回冗余列表判断后重新独立测量，先前试验 after 不纳入数据。无法保证宿主系统后台负载完全恒定，因此同时给逐组原始数据。每进程 N=24，合计每侧 N=72；P95 使用 nearest-rank。

| 组 | 前中位 ms | 后中位 ms | 前 P95 ms | 后 P95 ms |
|---|---:|---:|---:|---:|
| 1 | 127.010 | 107.109 | 128.862 | 108.897 |
| 2 | 120.199 | 111.245 | 126.622 | 113.218 |
| 3 | 121.209 | 106.760 | 124.514 | 109.562 |
| 合并 72 次 | 121.940 | 107.531 | 128.738 | 112.228 |

中位降低 11.8%，P95 降低 12.8%。收益来自重复单元格测宽；列表全量行投影和整篇正文构建仍在执行。阶段为嵌套计时，不能直接相加，完整分段见 JSON。

复现（每次用不存在的 /tmp AI_UPPER_HOME；在仓库根执行）：

```bash
AI_UPPER_HOME=/tmp/ai-upper-switch-reproduce-UNIQUE \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
docs/audit/session-switch/measure.py .tmp/session-switch/reproduce
```

基线为 4bb8799 的 document.py 和 qml_shell.py；其余产品源码相同。基线重复测量命令与切换/恢复脚本保存在 .tmp/session-switch/repeat.py，最终 after 实际执行 .tmp/session-switch/final-repeat.py；该脚本 finally 恢复最终文件。正式数据为 before-{1,2,3}.json / final-{1,2,3}.json，日志同名 .log。before.png/final.png 为第一组最终帧，三组 RGB 差异 bbox 均 None。

## 限制

本数据的单元格有重复内容，所以缓存收益可见；全为不同单元格或无表格的会话不会得到同等收益。尚余约 108 ms 的同步切换、约 54 ms 挂接开销。未验证实际用户桌面 GPU、慢盘冷缓存、图片密集正文和并发流式输出组合；不能宣布用户现场卡顿已彻底解决。没有改变原有字体环境，截图中的中文缺字是现有环境限制。


## 测试与提交

最终代码提交：11c63f2（fix(markdown): reuse plain table cell measurements during session rendering）。仅 document.py 有运行时改动，桥接与 QML 保持基线；另加两个测试覆盖测量复用和切换语义。

实际执行：

```bash
AI_UPPER_HOME=/tmp/ai-upper-switch-tests-delivered QT_QPA_PLATFORM=offscreen \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m pytest \
app/tests/test_qml_session_switch.py app/tests/test_qml_shell.py \
app/tests/test_qml_sidebar.py app/tests/test_chat_sessions_vm.py \
app/tests/test_markdown_body.py app/tests/test_markdown_document.py \
app/tests/test_markdown_highlight.py app/tests/test_markdown_chunked.py \
--basetemp=/tmp/ai-upper-switch-pytest-delivered -q
```

输出：`185 passed in 35.26s`，退出码 0。完整日志 pytest.log。git diff --check 无输出。

测试开发过程：首次运行 1 failed / 183 passed，原因是夹具每秒一个相对时间标签，跨分钟会合法触发列表更新；固定测试时间后通过。随后用基线 bridge 跑同一个测试也通过（baseline-list-test.log），证明原先同值列表赋值不会产生所怀疑的列表通知，最终撤回 bridge 试验改动。未把这次失败当作产品缺陷。

最终三组阶段中位数（ms）：set_markdown 41.018→28.908，attach 55.146→53.363，_render 96.177→82.362，_rows 2.946→2.946，_publish 5.565→5.532。读取方法累计约 0.044→0.043；本夹具热缓存下的主要瓶颈是正文构建与挂接，而非 JSON 读盘或 bridge 往返。
