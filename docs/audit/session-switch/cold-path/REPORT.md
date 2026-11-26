# 冷路径试验：全部回退，无性能修复交付

起点 e1fbf809fbb939390a9fb07910bba6905ce68718，develop，`git status --short` 无输出。本轮沿用真实QML、24个真实落盘会话、三组每路径N=72；不与pytest并发。没有预取/预热，冷0%命中、热100%命中。冷为显示文档首次打开，非OS磁盘冷缓存。

## 根因与试验

`qml_shell.py:1434` 在GUI创建目标实例，`:1443` 将其接入QML，再由`:1458`挂接后台返回片段。`markdown/body.py:214-221` 编辑事务提交同步触发布局和高亮；`:236`继续生成表格网格。`markdown/viewport.py:161`查询单元格布局，`:185`对每张表setFormat(border=0)，然后下一表又查询布局。查询与格式修改交错，完整帧必须等待最终布局和所有overlay完成。

候选deferred：目标文档先继承当前宽度/字体/textOption，在尚未接入TextEdit时完成片段、高亮、网格，再setTextDocument整体接入。三组RGB均一致，但冷中位148.001/P95 181.170/最大GUI165.164 ms，比基线更差，回退。热三项也未满足21.60/23.55/14.60硬门槛。未用交互早返回掩盖完整帧。推断：提前做的布局未避免接入QQuickTextEdit后的成本；Qt C++内部各次重排的独立时间未验证，缺少原生profiler，不将推断当成已定位的C++根因。

候选batch：把逐表setFormat放进一个QTextCursor编辑事务、最后统一endEditBlock。冷中位126.205/P95 142.783 ms，比基线123.665/139.505 ms更差；三组RGB网格差异bbox=(486,28,611,621)，回退。几何查询依赖事务中可见的布局状态，批处理改变最终overlay坐标。正文完整文本不变不等于视觉一致，未保留。

两候选patch只作为审计证据保存在本目录，未留在运行时代码。`git diff --exit-code -- app/src` exit0无输出。热分支、文档缓存、LRU、贴底及代码水平滚动逻辑没有改动。没有引入QtWebEngine、改pin、新分支、deva改动或真实用户目录访问。

## 方法与命令

`python .tmp/cold-path/run.py > .tmp/cold-path/run.log 2>&1`，exit0；内含baseline/deferred/batch各三次独立进程，各48次点击，全部子进程退出0，见exits.json。runner每次恢复对应源码，finally恢复起点。脚本/候选patch与原始JSON/PNG全部归档。

子进程命令：`AI_UPPER_HOME=/tmp/ai-upper-cold-path-{baseline,deferred,batch}-{1,2,3} LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .tmp/cold-path/measure.py .tmp/cold-path/{mode}-{group}`。脚本设置offscreen/software，禁用自动首次打开；每次等rendered并processEvents后grabWindow。notify测最长GUI事件。正文完整SHA-256、标题、活动ID、末轮正文均断言。每组冷/热末帧对已提交cache/release-after-1.png做RGB逐像素差分。

`python .tmp/cold-path/verify.py` 在候选全撤回后另外三组retained，再串行全仓库pytest；没有将基线数据冒充最终重测。最终状态见verify-exits.json。

测量主机不是独占，未锁频/锁外部负载。本轮未变更的基线热路径也出现高尾，但不删样本，不归咎于未测量的具体系统原因；不能保证任意重复测量都不超过历史21.60/23.55/14.60。

复现：从根目录将本目录脚本复制到.tmp/cold-path，使用全新/tmp应用目录后执行。run.py从当前产品源码生成候选并finally恢复，因此只能在无并发编辑/无pytest情况下使用；measure.py本身不改产品源码。所有临时文件均位于.tmp，应用数据位于/tmp。

## 未完成

冷路径60/80/16.7阈值未实现；本轮没有可保留的运行时优化。Qt内部纯布局/光栅阶段单独采样、真实GPU/桌面合成器、慢盘、图片密集正文未验证。没有重新实施预取或跨线程QObject移交，也没有用已否决分片方案凑指标。

## 最终全量验证

命令：`AI_UPPER_HOME=/tmp/ai-upper-cold-full QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --basetemp=/tmp/ai-upper-cold-full-base -q`。

实际输出：`1399 passed, 9 skipped in 274.58s (0:04:34)`，0 failed，退出码0。9个条件skip未执行，不算通过。完整日志pytest.log，所有独立测量退出码exits.json/verify-exits.json。

`git diff --check`无输出exit0，`git diff --exit-code -- app/src app/tests`无输出exit0。本轮仅提交审计证据，不宣称性能修复。最终推送输出和远端hash收据保存于仓库`.tmp/cold-path/PUSH-RECEIPT.md`，避免将含自身hash的收据递归提交。
