# 冷路径架构边界候选审计

起点055db71c1a5c0a4f901c4f34a7ee989e14a38808，本地/远端一致、工作树干净，app/src与app/tests相对cf960b8无差异。按最新授权顺序评估最多3个候选，没有并行展开；每个撤回后才执行下一个，没有预热、跨会话命中替代冷数据。热命中分支未编辑。

## 固定基线

沿用cache/measure.py，24个真实落盘会话每条30轮含表格与代码；第一遍冷打开、第二遍热切换，三组每路径N=72。启动自动打开被禁用，冷0%命中、热100%命中。开始试验前完成三组，后续不更换基线。冷中位126.315、P95 137.837、最长GUI79.444 ms，第二组高尾保留。offscreen/software、全阶段完成后grabWindow、notify事件时长，完整正文哈希/标题/活动ID断言，不与pytest并发。

## 顺序裁决

1. grid：逐表QQuickPaintedItem合并为单一DocumentGridOverlay，保留每张表原有几何查询/格式设置顺序与取整，降低scene节点数。冷128.967/138.696/50.777 ms，中位和P95退化，撤回；RGB/完整文本三组一致，但RSS峰值约1222208 KiB，整篇高度的绘制层放大了纹理/绘制内存，不能保留。
2. layout：worker独立QTextDocument构建期间关闭布局、完成后恢复。冷123.422/138.687/61.826 ms；中位改善但P95高于固定基线，整份撤回，RGB/完整文本三组一致。不是表格模板缓存，也不是预取；之前提出的表格片段复用没有实施，不报成果。
3. commit：目标显示文档片段写入期间关闭布局，endEditBlock后立即恢复，再用原网格挂接；独立测试，不含前两项改动。最终裁决见数据与收尾。

Qt布局开关官方依据：https://doc.qt.io/qt-6/qtextdocument.html#layoutEnabled-prop 。Qt6.4起提供，本机Qt6.11.2，未改pin。使用官方API不等于性能或视觉验收通过。

## 根因边界

viewport.py:154逐表遍历，:161布局查询，:185 setFormat(border=0)，:189创建overlay；grid只重做绘制层聚合，仍保留逐表布局副作用。prepare.py的render_markdown构建整个结构，关闭中间布局不能省去结构/格式插入。body.py:214-221片段提交与高亮/目标布局同步，之后:236继续网格挂接。不能把一次Qt C++调用用QTimer抢占。

先前约35.1ms是render_blocks全体块构建（含测宽），并非已经独立证实的纯表格构建时间；不沿用“35.1ms全是表格”的误称。纯Qt C++布局/光栅独立时间未验证，当前工具计的是Python入口综合时长。

若三项失败，真正待重做的边界是“整篇QTextDocument必须一次提交布局”和“表格去边框改变布局后再叠加网格”的耦合。仅减少绘制层数量或推迟布局不足以解决；块级布局/可见区虚拟化及一体化表格网格布局需要新的兼容性工程，本轮未实施，不声称已验证可行。

## 命令

`python .tmp/architecture/run.py baseline`先固定基线，再分别执行grid/layout/commit，全部日志、逐样本JSON及退出码独立保存。各子进程AI_UPPER_HOME=/tmp/ai-upper-architecture-{mode}-{group}、LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu、PYTHONDONTWRITEBYTECODE=1；`.venv/bin/python .tmp/architecture/measure.py .tmp/architecture/{mode}-{group}`。`python .tmp/architecture/summary.py MODE`生成与固定基线的冷/热、RGB、文本对照。候选patch是证据，不在运行时加载。无新分支、不碰deva/真实用户目录/依赖pin。


## 第三项性能门槛通过，但功能回归失败，最终撤回

commit三组每路径N=72，cold=123.101/131.896/55.242 ms，hot=21.160/22.555/13.700 ms。所有候选子进程exit0；第三项三组冷/热末帧RGB差异均None、完整文本哈希一致、标题/活动ID断言通过。冷缓存命中0%，热100%；无预热或缓存凑冷数值。

通过四项保留门槛：冷中位较固定基线126.315更低、P95较137.837更低、最长GUI较79.444更低、像素文本一致。因此当时停止探索并进入回归，但后续功能回归失败，撤回。注意基线最长值含高尾，三组较平稳的基线最长55.910/56.048 ms与候选接近，不能据聚合最大值夸称连续阻塞彻底消除。

第三项只改body.py目标文档片段写入前setLayoutEnabled(False)、endEditBlock后setLayoutEnabled(True)，最终也已撤回；worker和viewport均原样恢复。布局仍在GUI线程同步执行，只是合并中间布局，没有引入点击槽中的额外计算或后台QObject跨线程操作。不是整套正文架构重写，也不能宣称完成架构级根治。

**冷路径绝对目标未达**：中位超60目标63.101ms，P95超80目标51.896ms，最长GUI超16.7目标38.542ms。仍需重做整篇目标布局与表格几何/边框耦合边界；本轮没有实施可抢占Qt布局，也没有证明可见区虚拟化的视觉等价性。实际桌面GPU、慢盘、超大图片等未验证。

相关子集与全量测试顺序执行，绝不与性能测量并发；最终完整输出见pytest-related.log、pytest-full.log，退出码test-exits.json。命令：AI_UPPER_HOME=/tmp/ai-upper-arch-{related,full} QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest [相关文件或无筛选] -q --basetemp=/tmp/ai-upper-arch-{related,full}-base。


## 最终裁决：三个候选全部撤回

第三项相关测试真实输出`1 failed, 157 passed in 16.34s`，exit1。失败为test_qml_shell.py::test_qml_scrollbars_match_deva_and_scroll，转调test_qml_scrollbars.py:235，正文滚动条hover颜色仍#000000，期望#8a8a94。原始日志pytest-candidate-failed.log和candidate-test-exits.json。没有删断言、没有宣称性能截图覆盖全部交互；按保守门槛整份撤回第三项。此失败是否完全由候选而非时序引起尚未独立证明，不虚构因果；未过功能回归就不交付。

**架构改动未能达标**。最终app/src和app/tests与055db71零差异，没有保留任何候选代码。最终产品性能仍为本轮固定基线126.315/137.837/79.444 ms，对60/80/16.7分别差66.315/57.837/62.744 ms；此为恢复同一源码后的基线引用，不冒充一次新的性能测量。三组baseline PNG保留，所有候选与基线RGB/正文一致，但第三项额外交互失败说明末帧一致不等于完整功能正确。


## 最终回退工作树验证

相关子集：`158 passed in 22.21s`，exit0。全仓库（无文件筛选）：`1399 passed, 9 skipped in 275.08s (0:04:35)`，0 failed，exit0。9个条件skip未执行，不算通过。两次均在全部候选撤回后执行；最终应用/测试目录与055db71零差异，diff --check无输出。

实际测试AI_UPPER_HOME=/tmp/ai-upper-arch-retained-{related,full}、basetemp=/tmp/ai-upper-arch-retained-{related,full}-base，完整命令见tests.py。最终仅审计提交；普通push后收据保留于.tmp/architecture/PUSH-RECEIPT.md，记录真实输出、前后hash和退出码，不递归提交含自身hash的收据。
