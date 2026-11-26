# 本轮裁决与证据范围

从 468f5b7 继续，develop 原工作树干净；不改 A 路径、不改依赖、不改 deva，不新建分支。运行实例和测试的 AI_UPPER_HOME 均为 /tmp 下独立目录；脚本与临时结果位于仓库 .tmp/hot-cache。

## 采纳候选

每会话缓存 GUI 线程拥有的已完成显示文档，同时保留其高亮器和网格/代码视口对象。命中只切换 QQuickTextDocument 指向和 overlay 可见性，不重新解析、构建、插入或计算网格。Qt 6.7 起支持 setTextDocument；当前依赖 Qt 6.11.2 不改 pin。文档从未跨线程传递，worker 仍只返回 fragment/image 值对象。官方依据：https://doc.qt.io/qt-6/qquicktextdocument.html#setTextDocument （调用者保留文档所有权）。

键包含会话 ID、正文 SHA-256、纯文本模式、BodyStyle（主题、字号缩放、字体族）、渲染宽度、实际 TextEdit 宽度、设备 DPR。正文/设置变化不命中；同步渲染先使当前缓存失效。图片正文绕过缓存，包括图片暂不存在的 Markdown 图片语法，避免资源变更不改正文时返回过期内容。

LRU 最多 32 个缓存项，估算存储预算 128 MiB。计费 = characterCount×512 + blockCount×2048 + allFormats 数×1024。Qt 不提供实例内存分配量，所以这不是物理内存的硬上限。当前显示实例必须保活；超预算正文不进入缓存，可能额外保留 1 个活动实例。淘汰会移除 overlay、解除高亮器关联，并对目标及 staging 文档显式 deleteLater；没有后台线程与 GUI 并发使用同一 QTextDocument。RSS 另行实测，不能把估算预算冒充 RSS。

冷路径直接使用 worker 的 fragment 挂接目标文档，省去“还原到源文档→再次创建 fragment→目标文档”一次中间复制。BodyDocument 自有文档此时只是后续同步渲染的 staging，源字符串仍保存，流式/主题变化可正常重建。

## 否决/不再引入

- 32 MiB worker fragment 缓存：24 个会话循环只有 15 项能留下，0/48 命中，增加 toHtml 序列化成本。没有保留该类实现。
- 仅显示缓存、仍做中间复制的初版：热帧达标，但正式 cold P95 140.879→143.000 ms，按门槛不交付该版，继续消除中间复制再验收。
- Worker 预计算表格几何并批量提供 overlay：geometry.py 独立进程试验，冷中位 143.053 ms、P95 151.428 ms；RGB 差异 bbox=(486,28,611,610)。还出现 worker 无 Qt event dispatcher 的 QBasicTimer 警告。虽然 exit 0，视觉验收失败，未进入产品源码。
- GUI 分片：既有分片已在 965c385 撤回，保持撤回。热命中直接复用已有显示文档，根本不执行挂接/高亮，因此无需为热命中增加时间片；本轮未重新实施冷路径分片，不能宣称冷路径单事件达标。
- 列表：对实际 QML sessionsChanged 计数，48 次切换为 0，等值 setProperty 不触发整表更新。仍存在 _rows 构造与 Python/QML 属性转换成本，没有把它说成零成本；本轮不追加可能冗余的比较缓存。

## 测量定义

measure.py 使用真实 Main.qml + QTest.mouseClick，24 条实际落盘会话，每条 30 轮，正文包含代码与表格。禁用启动自动选首会话，使冷样本全为第一次打开；第一遍 24 次冷，第二遍同序 24 次热。每侧各三独立进程，offscreen/software、同一夹具、同一窗口尺寸，不与 pytest 并发。时钟从鼠标事件到 rendered 递增、processEvents、grabWindow 完成。GUI 最长事件由 QApplication.notify 计时；该值不是 processEvents 聚合阻塞。系统其它任务负载未锁定。

每组末帧的冷/热 PNG 均与已提交 costs/sync-1.png 做 RGB 逐像素比较。每次采集正文完整 SHA-256，与基线同 ID 的文本逐项比对；每次检查活动 ID、标题和末轮文本。原始 JSON 保留每个样本，P95 使用 nearest-rank，不删除高尾。

冷路径不是磁盘冷缓存：会话由夹具落盘、元数据/store 已初始化；此处“冷”是会话首次打开、文档缓存未命中。真实慢盘、桌面合成器/GPU、超大图片以及跨显示器 DPR 切换未验证。9 个条件 skip 不代表执行通过。


内存测量方法核验：Qt 官方说明，在局部循环中持续 processEvents 而不运行事件循环时，DeferredDelete 不会被处理，可用 sendPostedEvents 补齐。https://doc.qt.io/qt-6/qcoreapplication.html#processEvents 。因此保留初始压力结果，同时增加仅补齐 DeferredDelete 的对照；不通过更换夹具隐藏初始增长。


本轮没有追 A 的30万行；也没有修改选择态数组或兼容映射。已提交 slices/ 证据继续保留。全部候选迭代只在本地 develop 工作树中进行，未使用新分支或历史改写。
