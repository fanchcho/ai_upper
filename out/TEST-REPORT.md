# 剩余五项专项执行报告（2026-11-23）

本轮完成 long-mid 悬停修复、设置内部缺失标题/阴影及基线偏移修复，并给出 E1/E3、E5 的逐带定位。**E4 图标和 E3 布局残差未闭环，不能报告五项全部修复。** 裸 alt 修复已在本轮起点 ab66967 中，由另一执行提交，本轮未重复修改。

最终完整回归：**1352 passed, 5 skipped in 190.08s (0:03:10)，rc=0**；0 failed。原始日志 [final-full.log](residual-20261123/modal/final-full.log)，退出码 [final-full.rc](residual-20261123/modal/final-full.rc)。

## 起点和边界

开工只读原始输出，三个命令 rc 均0：

```text
git rev-parse HEAD
ab66967621de70b683ef5afd807d4117f6b1852a
git ls-remote origin refs/heads/develop
ab66967621de70b683ef5afd807d4117f6b1852a	refs/heads/develop
git status --porcelain --untracked-files=no
```

最后一条无输出，document.py 对 HEAD 也无差异。这个起点在上一轮12个提交之后已有 ab66967，不能将 c660bf8 继续写成本轮起点。`document.py` 本轮始终未改；未改全局配置、未重做用户列出的提交、未 reset/rebase/force-push/amend，所有提交均在 develop，没有新建分支。deva 目录只读取源码。

运行应用和测试均显式设置 `/tmp/ai-upper-residual-*` 下的 AI_UPPER_HOME；临时脚本/工作日志在 `.tmp/residual-20261123/`，正式证据在 `out/residual-20261123/`。原来的未跟踪产物未删除或批量纳入提交。

## 五项结论、前后数字与提交

| 项 | 本轮结果 | 改前 → 改后 | 独立提交 |
|---|---|---|---|
| [1 E4](residual-20261123/E4.md) | 起点已有裸alt修复验收；断图图标仍缺 | 本轮 chat **112725→112725 px，10.739806%→10.739806%**；起点前旧包装113088px，减少363px属于ab66967 | `ae5eed6` |
| [2 E1/E3](residual-20261123/E1-E3.md) | 逐带映射排除分段丢行；定位行推进/表格/列表/引用布局，未修复布局 | 原始 **18→18 带**（deva19）；首带 `[40,43]` 对 `[43,45]`；非均匀偏移仍为−28..−1px；chat百分比不变 | `1a8ac73` |
| [3 E5](residual-20261123/E5.md) | 复现下部15/16带并定位额外断图图标；无搜索专属丢行 | **15→15 对16**（y200..699）；全正文18对19；search-none **84812→84812 px，8.080412%→8.080412%** | `8fa0fe5` + `8065d86` |
| [4 long-mid](residual-20261123/LONG-MID.md) | 悬停缺口已修复，绑定随contentY更新 | **0→54行，(668,721)**；**142100→130345 px，13.538491%→12.418540%** | `c1fdbf1` |
| [5 设置/删除确认](residual-20261123/MODALS.md) | 修复About标题、General选中阴影、3页标题2px leading；其他残差逐项分类 | 详见下表；遮罩未改 | `8c880e6` |

E5 初始文档对旧区域说明不准确，另用独立追加提交补齐 y[200,700) 坐标表，没有 amend 已推送历史。该区域末两带来自输入框提示，不全是正文；缺少的额外带位于 deva y602（断图图标），alt文字为y606–619。逐带坐标详见链接文档和 [E1/E3 坐标表](residual-20261123/e13/bands.md)。

## 弹窗内部实测

| 页 | 全页差异 px 前→后 | 百分比前→后 | 内部 >8 px 前→后 | 判定 |
|---|---:|---:|---:|---|
| settings-general | 315274→311758 | 30.037538%→29.702553% | 5732→3122 | 缺选中阴影和标题基线2px，已修；余下字形/圆角差仍在 |
| settings-extensions | 305797→305414 | 29.134623%→29.098133% | 4777→4250 | 标题2px已修；行/徽标字体尺寸量化与字形仍有差 |
| settings-about | 302389→302188 | 28.809928%→28.790777% | 2114→1773 | 缺失About标题已补；品牌SVG等光栅残差仍在 |
| settings-models | 300497→300497 | 28.629668%→28.629668% | 1596→1596 | 未见缺控件；名称/count文字度量及边缘差，未强行调色 |
| delete-confirm | 382289→382289 | 36.422351%→36.422351% | 6645→6645 | 未见缺按钮/文案；文字光栅及1–2px定位差，不能算遮罩取整 |

四页设置 outside_diff 均保持 **297039**、outside_le2 均保持 **248842**。总差异减少来自内部修改，没有修改 rgba(0,0,0,0.42)。delete-confirm 本轮起点全页382289与用户引用旧382652相差363px，来自此前ab66967裸alt修复，不归到本轮设置修改。

归因使用每个>8像素的双向1/2px邻域匹配、局部平坦性、40px网格定位与文字bbox。邻域匹配不从原始差异中扣除，也不能独自证明纯光栅舍入。原始数值在 [modal/summary.log](residual-20261123/modal/summary.log)、[最终前后数值](residual-20261123/modal/final-summary.log) 和每页JSON；三页标题最终bbox逐坐标一致，见 [title-final-bbox.log](residual-20261123/modal/title-final-bbox.log)。

## 修改文件

产品源码仅两份：
- `app/src/qml/Main.qml`：long-mid 强制悬停从固定11改为随contentY计算当前可见行；不改滚动距离。
- `app/src/qml/SettingsModal.qml`：About标题、选中项复用SoftShadow、三页标题leading。

测试仅新增：
- `app/tests/test_qml_sidebar.py`：30行，真实滚动后检查悬停及回到chat。
- `app/tests/test_qml_settings_overlay.py`：17行，断言右侧About标题实际存在。

相对起点测试删除行数0。源码/测试 `git diff --check` rc0。保留的原始 `modal/change.patch` 内有diff上下文空白行，针对整个证据目录运行 `git diff --check` 会提示4处尾随空格；这是原始补丁内容，不是产品源码空白错误，未修改原始证据来掩盖。

## 测试原始结果

| 验证 | 原始结果 | 进程rc |
|---|---|---:|
| 正文Body/Document | 82 passed in 0.45s；0 skipped | 0 |
| 新long-mid测试修复前 | 1 failed in 5.20s | 1 |
| sidebar模块修复后 | 2 passed in 9.96s；0 skipped | 0 |
| shell模块 | 49 passed in 15.28s；0 skipped | 0 |
| long-mid后的完整套件 | 1351 passed, 5 skipped in 174.06s | 0 |
| About标题新测试修复前 | 1 failed in 5.15s | 1 |
| 设置/服务商/右键组合（含阴影） | 56 passed in 68.96s；0 skipped | 0 |
| 最终标题overlay模块 | 3 passed in 14.37s；0 skipped | 0 |
| **最终完整套件** | **1352 passed, 5 skipped in 190.08s** | **0** |

**非零退出也保留**：sidebar+scrollbar+shell组合两次分别53 passed后rc139；scrollbar单跑2 passed后rc139。将未修改的改前Main.qml复制到临时资源目录、运行同一未改scrollbar测试，也2 passed后rc139。因此特定退出路径的Qt生命周期问题在hover修复前可复现，但底层原因未修。不能把这些运行写成rc0。最终完整套件正常退出。所有原始日志和rc均保留在 long-mid/。

最终测试命令在之前已有的隔离检出执行，临时检出未提交、未新建分支。主工作树 `.tmp/` 已含旧名兼容夹具，会污染递归改名测试，因此把当前7份变化的产品/测试文件逐字同步到已有隔离检出；[SHA-256清单](residual-20261123/modal/final-regression-manifest.log) 与最终工作树一致。

```bash
# cwd: /home/agent/shared_workspace/ai_upper/.tmp/retest-20261123/baseline-checkout
AI_UPPER_HOME=/tmp/ai-upper-residual-final-full /home/agent/shared_workspace/ai_upper/.venv/bin/python -m pytest app/tests -q -ra > /home/agent/shared_workspace/ai_upper/out/residual-20261123/modal/final-full.log 2>&1
retest_rc=$?
echo rc=$retest_rc
# rc=0
# 1352 passed, 5 skipped in 190.08s (0:03:10)
```

5个skip：Windows专属2项、需AI_UPPER_E2E=1的构建2项、需cc/patchelf/readelf的native1项。没有删除、过滤、放宽测试。

## 未闭环及具体限制

- **E4图标未实现**：裸alt已验收；直接QTextImage插入会产生U+FFFC，实际最小实验 `existing_bare_alt_contract=False`，见 [image-object-contract.log](residual-20261123/e4/image-object-contract.log)。现有测试要求裸纯文本，保持此契约还需独立绘制标记；本轮未完成，不能用已修文案代替图标验收。
- **E3布局未修复**：行推进及表格/列表容器段后距路径已具体定位，仍需逐块实现和验证；没有通过全局contentY补偿掩盖非均匀差。
- **E5共享残差**：没有额外搜索丢行；图标和间距仍随E4/E3开放。
- **long-mid其他状态差**：本项0/54悬停缺口关闭；活动会话与参考不同、首完整行身份026/027不同仍未改，整页不算像素闭环。
- **模态其余残差**：Models/delete-confirm内部未得到每个像素的唯一归因；没有发现缺控件但仍有文字/小几何残差。General/Extensions/About修复后也未清零。
- **测试退出问题**：部分QML模块组合退出139在改前资源也可复现，未修；最终全量rc0不代表消除此问题。

本轮无权限/网络推送阻塞。上述未完成项属于实现尚未闭环，已与完成的定位和修复分开，任务不能标记“全部修复”。

## 每项push与远端原始行

每个commit完成后立即单独 `git push origin HEAD:develop`；全部push rc0。每次紧接 `git ls-remote origin refs/heads/develop`，原始行如下（不是将最终HEAD重复填给每项）：

```text
ae5eed62ed7e99c7b9321b2e8ee0ad353393ad59	refs/heads/develop
1a8ac73936a2446168fd1a886a7657461f1b4214	refs/heads/develop
8fa0fe509aa4730a40a9e360822f2e9e69322a15	refs/heads/develop
8065d86420f276d056a02bd74cff24089af7499a	refs/heads/develop
c1fdbf1c3e407c5fc42ce3871ecbb50140129f1a	refs/heads/develop
8c880e61f3cfae2638b45ed742101d6ec0a35130	refs/heads/develop
```

顺序依次为E4、E1/E3、E5、E5坐标补充、long-mid、模态。原始push/ls-remote日志在 [receipts](residual-20261123/commits.json) 对应映射目录。总报告随后独立提交推送；最终HEAD和远端原始行由本地交付文件 `out/residual-20261123/publish-final.txt` 记录，不把该回执纳入它自身证明的commit，避免自引用hash。

## 追加项：Models 面板结构收口（2026-11-23）

**Models 面板：改前 31.25% → 改后 28.629668%。** 31.25%是历史值；本轮同环境重拍前后均为28.629668445%，没有新增视觉降幅。

五项结构在当前HEAD已经实现，本轮新增三种provider状态与真实点击下钻/Wrench回归验证，保留全部既有产品实现与44个投影测试。指定测试：Shell 49 passed/rc0，Models 47 passed/rc0，均0 skipped/failed/error；未再跑全量。

只重拍settings-models，数据仍来自settings_models.py投影。详情与完整源码/命令/像素及测试证据见 [latest-parity报告 §4.4.5](latest-parity/REPORT.md#445-models-开发收口以当前实现和运行态重新验收2026-11-23)。其他原五项未闭环状态不因此关闭。

## 并入项复核（2026-11-23，起点 7be5e480bc7d0d3037d5182ab9f40c8576c27cbe）

起点 develop 与远端一致，tracked 干净；本轮只修实测缺口，已验证项不重做。Models 沿用
`7be5e48`：历史31.25%→当前28.629668445%，上一轮前后同值；Shell49/Models47 passed，均rc0。
默认QML入口和打包启动沿用 `out/qwebengine-remove/logs/final-packaged-launch2.log`：
HEAD=4bea1ba，命令 `AI_UPPER_HEADLESS=1 AI_UPPER_HOME=/tmp/qwe-final-pkg-home AI_UPPER_QML_SHOT=/tmp/qwe-final-pkg2.png dist/ai_upper/ai_upper`，
原文 `QML OK ...`、`EXIT=0`；这是历史产物证据，本轮不声称重新构建或启动过。

### 并入1：模型弹层、effort、ContextRing — 已具备，旧缺陷已不存在

命令：`AI_UPPER_HOME=/tmp/ai-upper-merged-picker .venv/bin/python -m pytest app/tests/test_qml_model_picker.py app/tests/test_qml_context_ring.py -q -s -ra > out/merged-review/picker-tests.log 2>&1; echo rc=$?`。
结果 **8 passed in 44.47s，0 skipped/failed/error，rc=0**；真实点击模型、effort、High档位、ContextRing，验证互斥和状态写回。
额外命令：`AI_UPPER_HOME=/tmp/ai-upper-merged-picker-probe .venv/bin/python out/merged-review/picker_probe.py > out/merged-review/picker-probe.log 2>&1; echo rc=$?`，rc0。

| 核对点 | 实测 | 结论 |
|---|---|---|
| 分组/模型/选中 | Anthropic / deepseek-v4.1-flash；activeRef=anthropic:deepseek-v4.1-flash，已有accent勾选渲染 | 一致，数据投影驱动 |
| effort接线 | 模型菜单与thinking菜单分别打开；选择High后activeEffort=high，菜单关闭 | 旧误接线不存在 |
| 输入卡片四边 | top/bottom/left/right全为#5b5bd6，即(91,91,214) | 一致 |
| 面板位置/大小 | x847/y688/w248/h65，row h27；相对chip定位+2px | 与参考图一致 |
| 阴影 | deva CSS 0 6px 24px；QML offsetY6/blur20 | 原先为补偿Qt与Chrome模糊核不同的已验证实现；参数不相等，不重做既有像素校准 |
| ContextRing | 几何、tooltip/card切换、无读数隐藏、与菜单互斥均经真实点击通过 | 已具备 |

只重拍model-picker：`AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh model-picker out/merged-review/model-picker.png /tmp/ai-upper-residual-20261123 config.json > out/merged-review/picker-shot.log 2>&1; echo rc=$?`，rc0。
像素命令：`python3 out/residual-20261123/measure_page.py out/merged-review/model-picker.png model-picker > out/merged-review/picker-metrics.json 2>&1; echo rc=$?`，rc0。
当前117074px / **11.154153963%**。本项未改产品代码，本轮画面无新增修复收益；旧图差异及MD5记录在
[图片数值](merged-review/picker-image-summary.log)，不能把历史裸alt修复的降幅算成本项收益。
源码摘录：[picker-source.log](merged-review/picker-source.log)；操作输出：[picker-probe.log](merged-review/picker-probe.log)。

### 并入2：右键 Rename / Select / Archive — 已具备，渲染空接线缺陷已不存在

命令：`AI_UPPER_HOME=/tmp/ai-upper-merged-menu .venv/bin/python -m pytest app/tests/test_qml_context_menu.py -q -s -ra > out/merged-review/menu-tests.log 2>&1; echo rc=$?`。
**6 passed in 38.95s，0 skipped/failed/error，rc=0**。探针对非活动会话真实右键、点击菜单、键入并确认；非直接调用动作方法。

```text
BEFORE sessions=120 active='parity-000'
AFTER_RENAME sessions=120 title='renamed non active' active='parity-000' file_exists=True
AFTER_SELECT selectMode=True selected=['parity-001'] active='parity-000'
AFTER_ARCHIVE sessions=119 archived=True active='parity-000' file_exists=True
```

会话文件、当前活动会话、归档入口列表同时断言，删除确认/取消原用例也通过。本项产品代码与视觉不变，不重拍、不虚构百分比收益。
证据：[menu-tests.log](merged-review/menu-tests.log)。

### 并入3：窗口按钮、侧栏范围、设置遮罩导航 — 已具备，旧缺陷已不存在

命令：`AI_UPPER_HOME=/tmp/ai-upper-merged-controls .venv/bin/python -m pytest app/tests/test_qml_window_controls.py app/tests/test_qml_sidebar.py app/tests/test_qml_settings_overlay.py -q -s -ra > out/merged-review/controls-tests.log 2>&1; echo rc=$?`。
**7 passed in 36.23s，0 skipped/failed/error，rc=0**。

- 窗口控件整块96×40，三个32×40连续热区，x1184/1216/1248；常态白底、hover(237,237,237)，图标bbox分别10×2/10×10/10×10，像素数20/64/48。真实点击：Windowed→Minimized→Windowed；Windowed→Maximized→Windowed；Close后visible=False。
- 侧栏首行x64/y56/w275/h54，第二行y110；hover与selected底色均止于x338，x339保持背景。long-mid既有修复的54行hover回归通过，未重复实现。
- 设置720×560浮层保持正文及输入卡片可见；四导航Cog/Brain/Puzzle/Info路径和About内容标题均通过。遮罩源码仍为rgba(0,0,0,.42)，未调整。四页outside_diff=297039及内部残差沿用前述专项，未重拍。
- 输入卡片dark-chat既有修复未改；本轮正文主题桥接将在下一节单独实测。403文案、模型贴片和滚动条没有新增实现，不因并入重复调整。

证据：[controls-tests.log](merged-review/controls-tests.log)、[deva窗口取值](merged-review/controls-source.log)、[输入框和遮罩源码](merged-review/input-source.log)。
本项产品代码不变，尺寸前→后相同，不声称新的全页百分比收益。

### 并入4：正文真实操作与 E1/E3/E5 合并复核 — 部分已具备，缺口仍在

新探针加载实际 `Main.qml` 的 `bodyView/bodyScroll` 和同一个 BodyDocument，复用真实壳装配；
不使用旧 `scripts/qml_body_probe.py` 中直接设置剪贴板、仅比较超宽即认定可滚动的判据。

```bash
AI_UPPER_HOME=/tmp/ai-upper-merged-body QT_SCALE_FACTOR=1 .venv/bin/python out/merged-review/body_probe.py out/merged-review/body-1x > out/merged-review/body-1x.log 2>&1; echo rc=$?
AI_UPPER_HOME=/tmp/ai-upper-merged-body-2x QT_SCALE_FACTOR=2 .venv/bin/python out/merged-review/body_probe.py out/merged-review/body-2x > out/merged-review/body-2x.log 2>&1; echo rc=$?
```

两个进程均rc0，**表示采集完成，不表示全部功能通过**；JSON明确保留 `horizontal_code.ok=false`。

| 项目 | 结论 | 真实操作与数字 |
|---|---|---|
| 跨块连续选择/复制 | 已具备 | 鼠标从(485,58)拖到(558,196)，跨段落/代码/表格到尾段；Ctrl+C复制96字符，所有目标内容存在；Qt内部U+FDD0/FDD1/U+2029变换为换行、NBSP变为空格后与选区逐字相等。未直接写入剪贴板 |
| 双击选词 | 已具备 | 真实mouseDClick后selectedText=`sorted`，1x/2x都通过 |
| 代码块横向滚动 | **仍缺** | 长行idealWidth=7321，textWidth/view宽=696，尾部x7282.78125；横向滚轮后contentX仍0→0。bodyScroll contentWidth固定924，无单代码块横向滚动视图；不能把文档超宽当作成功 |
| 表格边框/间距 | 已具备基础表格，像素等价未闭环 | format border=1/#e6e6ea，spacing=0；cell padding为0，由3个NBSP和固定34.45px行盒实现CSS 10/6留白。实际描边采样y148有150个边框像素，底部y182/183各150；存在2行底边/绘制机制残差，不能称所有边线均单像素一致 |
| 本地图片 | 已具备 | 48×32图片进入QML资源；1x指定区域936个accent像素，2x3744，恰为4倍面积 |
| broken-image | **仍缺图标** | data URI按deva默认urlTransform保留裸alt，正文为U+FFFC本地图加“示意图”；断图本身没有图标。沿用E4未闭环结论，不重复算收益 |
| 浅深主题与字体 | 已具备 | 调用实际设置桥接setTheme(light/dark)，shellDark同步false/true，文档前景#1f1f24→#e4e4e7，字体族列表不变、14px不变 |
| 中文/emoji | **部分具备** | “中/文”glyph9544/20036（Noto Sans CJK SC）；😀glyph5857（DejaVu Sans）；🚀/✅均glyph0，本机缺可用回退字形，未安装或替换系统字体 |
| 1x/2x缩放 | 已具备物理缩放 | 相同逻辑1280×820，DPR1/2分别抓取1280×820、2560×1640；两种缩放下选择/复制/双击和本地图均实测。与deva的2x像素等价**未验证**，现有参考只有1x |

正文测试命令：`AI_UPPER_HOME=/tmp/ai-upper-merged-body-tests .venv/bin/python -m pytest app/tests/test_markdown_document.py app/tests/test_markdown_body.py app/tests/test_markdown_chunked.py -q -ra > out/merged-review/body-tests.log 2>&1; echo rc=$?`。
**102 passed in 3.60s，0 skipped/failed/error，rc=0**。

**E3最小修复实验被验收否决，未提交到产品**：从deva `.md ul/ol` 12px段后距出发，新增候选回归测试先实测失败
`2.0 != 12.0`（1 failed，rc1），候选补margin后103 passed/rc0；但只重拍chat后差异112725/10.739805640%
→126094/12.013528963%，可见带数18→17。底部锚定把上方内容进一步裁掉，单独加列表间距并不解决
表格/引用/滚动的组合问题。因此撤销的仅是本轮未提交候选及配套新测试，所有原测试和已推送产品保持逐字不变。
完整候选保留于 [list-experiment.patch](merged-review/list-experiment.patch)，失败/通过日志及候选截图均保留。
当前正式代码的chat仍为10.739805640%，search-none仍为8.080411585%，E1/E3/E5逐带坐标沿用同报告前节，未重复计算。

证据：[1x原始结果](merged-review/body-1x/results.json)、[2x原始结果](merged-review/body-2x/results.json)、
[真实操作探针](merged-review/body_probe.py)、[代码横向CSS原文](merged-review/code-source.log)、[列表CSS](merged-review/list-source.log)。
代码横向滚动、E4图标、E3组合布局尚未实现；这属于明确的实现缺口，没有用“已核对”替代修复完成。

### 并入5：长消息/连续消息性能与 CI — 本地测量完成，CI尚未最终收敛

性能使用上节同一真实QML壳探针：`perf_counter`计时覆盖set_markdown、attach、processEvents和首张grabWindow；
不把固定sleep算进加载耗时。随后60次不同contentY位置，每次processEvents+同步grabWindow。
120条使用实际Message对象（user/assistant交替）和生产transcript_markdown拼接，非仅复制标题冒充会话。

| 负载 | 字符数 | 加载/排版/首帧抓取 ms | 文档高度 px | 60次滚动抓取 ms | 每步中位/最大 ms |
|---|---:|---:|---:|---:|---:|
| 单条400段超长消息 | 72688 | 132.801 | 23925.5 | 229.677 | 3.775 / 4.435 |
| 120条连续消息 | 25748 | 64.581 | 19448.375 | 157.961 | 2.638 / 3.028 |

这是本机offscreen软件渲染的一次测量，**不是显示器FPS或用户输入延迟**；未声称跨平台性能结论。
1x/2x均为独立进程，无截图进入对话上下文。原始值在body-1x/results.json，产品代码未变，无“优化前后”数字可报。

额外既有修复回归：
`AI_UPPER_HOME=/tmp/ai-upper-merged-existing .venv/bin/python -m pytest app/tests/test_provider_headers.py app/tests/test_qml_shell.py -q -ra > out/merged-review/existing-fixes-tests.log 2>&1; echo rc=$?`。
**60 passed in 16.82s，0 skipped/failed/error，rc=0**，覆盖403服务商原因文案、壳入口、滚动条真实wheel/drag等现有判据；不重复开发。

CI通过GitHub公开REST API查询 `repos/fanchcho/ai_upper/actions/runs?branch=develop&per_page=15`，
再读各run jobs_url的job和step状态，命令/查询结果在[ci-query.log](merged-review/ci-query.log)、
[ci-jobs.log](merged-review/ci-jobs.log)、[失败步骤](merged-review/ci-failed-steps.log)。
本轮前三个提交的Python3.8–3.13 Build Tool jobs全部success，native jobs仍in_progress/queued，**不能宣称最终全绿**。
此前7be5e48与其父1d1afb8都已出现Windows x86/x64/py38/arm64的Unit tests失败，
相同步骤在本轮起点之前存在；只证明不是首次出现，不证明每条失败的根因相同。
非arm64原始job日志下载返回HTTP403（[原始错误](merged-review/ci-log-fetch.log)），因此确切失败测试名/堆栈**未验证**；
没有把所有Windows失败统归为已知arm64缺轮子，也没有重复排查该平台阻塞。
本轮`app/src`、`app/tests`、`.github/workflows`相对起点无最终修改，尚未观察到可归因本轮的新失败，但结论以CI未结束为限。

### 并入项提交与剩余清单

本轮最终没有保留产品代码改动；真实操作已具备的项没有重写。唯一列表间距候选因视觉回退被否决，实验文件留证，正式代码和所有原测试均与起点一致。

| 项 | 独立commit | push |
|---|---|---|
| picker | `796910bbb7ed1d8e06c24f5e760c801776ba7f4d` | rc=0 |
| menu | `a70b71d6a12667927062dabc0bf2bd02fbfdbb33` | rc=0 |
| controls | `309fa2e448979745fa0619f7ad894b91ae43c070` | rc=0 |
| body | `8bd63109c4bbe796da418f7ec0137e6ac7e6a198` | rc=0 |
| perf | `16357df2bc0bc5375f145743cdc4bc7b376f6989` | rc=0 |

每次push后即时取得的ls-remote原始行：

```text
796910bbb7ed1d8e06c24f5e760c801776ba7f4d	refs/heads/develop
a70b71d6a12667927062dabc0bf2bd02fbfdbb33	refs/heads/develop
309fa2e448979745fa0619f7ad894b91ae43c070	refs/heads/develop
8bd63109c4bbe796da418f7ec0137e6ac7e6a198	refs/heads/develop
16357df2bc0bc5375f145743cdc4bc7b376f6989	refs/heads/develop
```

未完成：代码块缺独立横向滚动承载；E4缺图图标仍缺；E3单独补列表间距会增加裁切，组合布局修复未完成；表格底边与像素级间距仍有残差；🚀/✅本机缺字形；deva 2x参考缺失，未验证2x像素等价；CI仍运行且job日志403，最终归因未完成。原设置内部残差和long-mid非悬停状态差不因本轮复核而关闭。

本轮没有再跑完整app/tests。已跑的五组分别8/6/7/102/60 passed，均0 skipped/failed/error且rc0；不将有重叠覆盖的组相加冒充完整套件。Models沿用上轮49/47 passed，历史全量1352 passed/5 skipped/rc0明确属于先前快照。最终报告随后单独提交，最终远端回执在本地out/merged-review/publish-final.txt。

### 第3步追加完成度判断：旧结构缺口 A1–A4 / D1–D3 / G5（今日 HEAD 复核）

核验起点 **8455309568c1756e9381201b84ede831fb8d01c3**，本地develop与远端相同，tracked工作区为空，
三个只读命令rc均0；原始行见 [start-head.log](structure-review/start-head.log)、
[start-remote.log](structure-review/start-remote.log)、[start-status.log](structure-review/start-status.log)。
本轮只追加同一报告及实测证据，不重写或回退既有实现。产品和测试相对已验收的7be5e48逐字相同。

| 旧编号 | 今天结论 | 现有实现与真实操作证据 |
|---|---|---|
| A1 | **已不存在** | Main.qml:2350起windowControls和Minimize/Maximize/Close三个32×40热区，整块96×40；原版Linux参考在右上角x1184..1279，不是左上角。真实点击状态Minimized、Maximized/Windowed、visible=False均通过。deva main/index.ts:79–97定义原生标题栏叠加层；不将已验证控件挪到左上 |
| A2 | **已不存在** | Main.qml:585将DevaScrollBar挂到sessionList，objectName=sidebar-scrollbar；常态可见滑块宽4px，已有真实wheel/drag测试当前重跑通过 |
| A3 | **已不存在** | Main.qml:994将同一组件挂到bodyScroll，objectName=body-scrollbar；真实wheel/drag改变正文contentY，当前测试通过 |
| A4 | **已不存在** | Main.qml:215是内联`component DevaScrollBar: ScrollBar`，含AsNeeded策略、8px宽、2px内缩；不需要再加ScrollView包装。最初搜索独立DevaScrollBar.qml返回不存在，已从内联组件找到实现 |
| D1 | **已不存在** | ModelPicker.qml有独立modelList/thinkingList；Main.qml模型贴片openPicker("model")，模型深链默认mode=model。Anthropic/deepseek-v4.1-flash内容与当前勾选状态已实测；本轮真实点击用例继续通过 |
| D2 | **已不存在** | Main.qml:1351菜单打开分支使用Theme.accent；本轮测试真实采样四边都为(91,91,214)，不是只看绑定代码 |
| G5 | **已不存在** | Main.qml:1516 effort调用openPicker("thinking")，与模型贴片分开；点High写回activeEffort=high并关闭菜单，互斥测试通过 |
| D3 | **旧16.8k结构缺口已不存在；小范围像素残差仍在** | 见下方新拍分区结果；没有发现缺面板、缺模型项或缺勾选，不通过调色/改阴影压低差异率 |

对应既有交付证据：窗口和设置/侧栏复核309fa2e，模型/effort/ContextRing复核796910b；更早实现详见本报告引用的最新parity报告§4.9/§4.10/§5.6。
源码定位：[implementation-evidence.log](structure-review/implementation-evidence.log)；只读参考：[标题栏](structure-review/deva-titlebar.log)、[滚动条CSS](structure-review/deva-scrollbar.log)。

**本轮针对性回归**（没有删除或放宽测试；50 deselected不算skipped）：

```bash
AI_UPPER_HOME=/tmp/ai-upper-structure-check .venv/bin/python -m pytest app/tests/test_qml_model_picker.py app/tests/test_qml_window_controls.py app/tests/test_qml_shell.py -k 'model_chip_opens_model_menu or effort_chip_opens_thinking_menu_and_picks or model_and_effort_chips_keep_their_own_menus or window_controls or qml_scrollbars_match_deva_and_scroll' -q -ra > out/structure-review/targeted-tests.log 2>&1; echo rc=$?
# rc=0
# 6 passed, 50 deselected in 39.96s
```

0 skipped、0 failed、0 error。日志：[targeted-tests.log](structure-review/targeted-tests.log)。

**D3重新归因：纯白净计数与通道差分分开**

沿用旧的inclusive bbox x600..1119、y470..799；以同夹具的chat作为菜单关闭控制页。
只重拍model-picker和其chat控制页，不重拍18页。原版沿用out/latest-parity/deva既有图。

```bash
AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh model-picker out/structure-review/qml/model-picker.png /tmp/ai-upper-residual-20261123 config.json > out/structure-review/shot-picker.log 2>&1; echo rc=$?
# rc=0
AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh chat out/structure-review/qml/chat.png /tmp/ai-upper-residual-20261123 config.json > out/structure-review/shot-chat.log 2>&1; echo rc=$?
# rc=0
python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/structure-review/qml > out/structure-review/page-diff.log 2>&1; echo rc=$?
# rc=0
python3 out/structure-review/d3_attribution.py > out/structure-review/d3-attribution.log 2>&1; echo rc=$?
# rc=0
python3 out/structure-review/d3_panel_detail.py > out/structure-review/d3-panel-detail.log 2>&1; echo rc=$?
# rc=0
```

page_diff18原始行（其余页未放入该次输入目录，不当作新一轮18页验收）：

```text
chat                   ac72cd597ae44377b608777cbd5e2e81 e0a127e4773b01daf6cfddae6b1ad3eb  158583  164669  112725  10.74% max=248 same=False
model-picker           946b07def583e696822df943b6935f04 4ca5e740ba78cca45a0723843a9b6e1e  164258  170480  117074  11.15% max=248 same=False
```

两张当前截图与上一轮同代码产物字节完全相同：model-picker 170480B、md5=4ca5e740ba78cca45a0723843a9b6e1e；chat 164669B、md5=e0a127e4773b01daf6cfddae6b1ad3eb。
**本轮改前→改后：model-picker 117074→117074px，11.154153963%→11.154153963%；chat 112725→112725px，10.739805640%→10.739805640%。**
没有新产品改动，不把旧收益重复算成本轮修复。只打印像素数、百分比、字节、md5，没有读取PNG进上下文。

| y范围（两端含） | deva纯白 | QML纯白 | 差deva−QML | chat同区域差 | 菜单专属净计数差 |
|---|---:|---:|---:|---:|---:|
| 470–619 | 77367 | 76777 | 590 | 590 | 0 |
| 620–650 | 11440 | 9360 | 2080 | 2080 | 0 |
| 651–687 | 11066 | 11024 | 42 | 0 | 42 |
| 688–752 | 29245 | 29223 | 22 | 0 | 22 |
| 753–799 | 15673 | 15652 | 21 | -11 | 32 |
| 合计 | 144791 | 142036 | 2755 | 2659 | 96 |

旧归档161546 vs deva144791，即多16755（约16.8k），不在当前图复现。今天QML142036，比deva少2755；
其中2659是chat原有的正文/输入区背景差，菜单自身纯白**净计数差96**＝阴影带42＋面板本体22＋贴片行32。
历史报告的“菜单专属316”同样不是今天值；本轮按当前图重算，没有直接套用旧结论。
净白像素数的相减可能抵消不同位置的差异，**96不是全部坏像素数**；因此同时用设置遮罩归因的max通道差分桶：

| 区域 | 任意通道差非零 | 差1–2 | 差3–8 | 差>8 |
|---|---:|---:|---:|---:|
| 面板内部 x847..1094/y688..752 | 1308 | 167 | 196 | 945 |
| 面板外 | 115766 | 33958 | 13785 | 68023 |

内部945个>8像素中：标题带278，模型/勾选文字带615，顶/底边各26；893/945集中在文字带。
内区没有“双方都是相邻同色平面但差>8”的像素（0），未见大块背景缺失。
标题墨迹QML bbox(861,700,917,712)，deva(862,700,915,712)；模型文字QML左边861、deva862，右边及纵向相同；
✓ 两侧均20个accent像素，bbox都为(1069,729,1078,736)。这些是文字度量/定位、圆角及阴影的细小绘制残差；
**不能将>8残差全称为1灰阶取整，也没有证据支持重新实现菜单结构**。

这页没有设置弹窗的整屏rgba(0,0,0,.42)遮罩：源码是绝对定位白色面板＋box-shadow，
(60,120)/(1100,100)/(1200,100)在菜单开关两页均保持原RGB，左右页面没有统一变暗。
因此D3不属于A5“整屏遮罩合成取整”；沿用相同分桶判据，并不意味着归因为相同根因。
逐像素与子区域原始值：[d3-attribution.json](structure-review/d3-attribution.json)、[d3-panel-detail.json](structure-review/d3-panel-detail.json)。

**第3步完成度**：本次追加的A1、A2、A3、A4、D1、D2、G5旧结构/接线缺陷均已不存在，D3约16.8k旧结构差已不复现；
无需新增产品修复，未重做既有提交。D3字体/边缘/阴影像素残差仍存在，未宣称像素全等。
整体任务仍未完成：代码块横向滚动、E4断图图标、E3组合布局、表格像素残差、🚀/✅缺字形、deva 2x像素等价、CI最终归因，
以及此前设置内部残差和long-mid非悬停状态差，均沿用上一节的开放状态，本次不重复算作新缺口。

本项审计证据独立commit并push；最终原始远端行由out/structure-review/publish-final.txt留存，并在文字交付中贴出。

### A：代码块独立横向滚动（7f304e9之后，本轮实现）

已修复。原来长代码文档宽7321px，但没有代码块视口，横向滚轮读不到尾部；现在仅对超宽代码单元建立局部绘制视口，复用同一QTextDocument，语言头固定、正文列裁切，普通纵向滚轮仍交给原Flickable。没有修改正文纵向滚动尺寸、偏移或滚动条。

真实事件命令：`AI_UPPER_HOME=/tmp/ai-upper-code-tests CODE_SCROLL_EVIDENCE="$PWD/out/ab-closeout/a" .venv/bin/python -m pytest app/tests/test_qml_code_scroll.py -q -s -ra > out/ab-closeout/a-tests.log 2>&1; rc=$?`。
结果rc0，1 passed in 6.14s，0 skipped/failed/error。原始操作输出：

```text
CODE width=7321.0 viewport=682.5 contentX=0->120->6638.5 tail_local_x=630.78125 second_contentX=0.0 bodyY=0.0->0.0
VERTICAL bodyY=0.0->70.51579335804627 code_contentX=6638.5
```

横向wheel后第一块0→120→6638.5，第二块保持0，正文contentY保持0；普通纵向wheel后正文滚到70.516px，第一块横向位置不变。END字符从视口外进入local x630.78125，处于682.5px视口以内。
截图：[长行首](ab-closeout/a/code-start.png)、[长行尾](ab-closeout/a/code-end.png)；两个代码块同时展示，第二块保持首部，证明不是移动整个正文列。

回归命令：`AI_UPPER_HOME=/tmp/ai-upper-code-regression .venv/bin/python -m pytest app/tests/test_markdown_body.py app/tests/test_markdown_document.py app/tests/test_markdown_chunked.py app/tests/test_qml_code_scroll.py -q -ra > out/ab-closeout/a-regression.log 2>&1; rc=$?`。
**103 passed in 9.59s，0 skipped/failed/error，rc=0**。跨块复制/双击仍由共享正文文档提供，旧操作探针也复测通过；旧探针检查父级contentX的字段不适用于新增子级视口，A以专用真实事件测试为验收。
只读deva依据：[.md-code__body overflow-x:auto及white-space:pre](ab-closeout/deva-code-css.log)。本项立即独立提交推送，B另行实现。


### B · E4 原生断图图标（本段独立修复）

A 已提交并推送：`88b2de28620e2d4a32b39f0d764e4efae291a513`，push rc=0；原始远端行：

```text
88b2de28620e2d4a32b39f0d764e4efae291a513	refs/heads/develop
```

B 起点即上述 A 提交，修改前 `git diff HEAD -- app/src/markdown/document.py` 输出 0 字节，tracked 工作区干净。
结论：**断图结构已修复**，从只有裸 alt 改成原生图标 + 裸 alt；整页像素一致性并未宣称完成。
未修改 deva 文件；只读其 `features/chat/Markdown.tsx:120`、`styles/app.css:848` 和 Electron 原生资源。
ReactMarkdown 没有自定义 img renderer；data URL 经默认转换后为 `src=""`。实时 CDP 输出在 `out/ab-closeout/deva-image-live.json`。

| 对照项 | 原版源码 / 实时测量 | 本轮 QML 实测 / 实现 |
|---|---|---|
| 结构 | Chromium 原生断图 + `示意图` | 内联 QTextImage + `示意图`；无括号、无「图片：」前缀 |
| 图标原图 | `chrome_100_percent.pak` resource 48871，14×16 PNG，448 字节，md5 `6e211e3f7fce75eec8847e5ba76431a5` | 同一 PNG 字节内嵌于 `markdown/broken_image.py`，没有重画或另选图标 |
| 图标槽 | 占位总宽 58 − alt 41.99981689453125 ≈ 16px；原生图高 16px | 16×16px，QML 游标坐标实测首字符至 alt 为 16px |
| 文案 | 裸 alt，字号 14px，颜色 rgb(31,31,36)，行高 23.1px | 同一 BodyStyle / 前景色；alt 宽 41.953125px，总宽 57.953125px；Qt 字宽量化差 0.046875px |
| 容器 | margin/padding/border 均 0；CSS radius 6px | 无额外间距与边框；图标按包含 alt 的原版占位盒裁剪 6px 圆角，而非四角全裁的 16px 小方块 |
| 圆角实际生效 | CDP 仅将 radius 6→0，区域 (488,602,546,626) 变化 17px | 采用同一 radius 和占位盒尺寸；不把圆角当作无效 CSS 跳过 |
| 实拍图标证据 | 目标区域绿色像素 43，bbox (489,612,502,616) | 绿色像素 **0→42**，bbox (485,611,498,615)；仍有正文全局坐标和栅格化差，未借此调整本轮排除的 E3 布局 |

QML 实拍首轮发现相对图片资源名被当作文件名，出现 `Cannot open .../md-broken-image`；已经改成内嵌 data URL，最终截图日志没有此错误。
测试没有删除或放宽旧的文字包装约束：旧断言改为严格检查对象占位符 + 原样 alt，新增图标尺寸、资源搬运、透明圆角和真实 QML 绿色像素断言。

实际命令与结果：

```sh
AI_UPPER_HOME=/tmp/ai-upper-b-deva DEVA_HOME=/tmp/ai-upper-b-deva DEVA_CONFIG=/tmp/ai-upper-residual-20261123/config.json DEVA_SEED=/tmp/ai-upper-residual-20261123/data/chats CDP_PORT=9334 node .tmp/ab-closeout/deva_icon_probe.mjs chat out/ab-closeout/deva-image-live.json > out/ab-closeout/deva-image-live.log 2>&1; rc=$?
# rc=0；DOM 数字见 deva-image-live.json；窗口管理器激活不支持的 stderr 原样保留。
AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh chat out/ab-closeout/b-before/chat.png /tmp/ai-upper-residual-20261123 config.json > out/ab-closeout/b-before-shot.log 2>&1; rc=$?
# 改前 rc=0
AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh chat out/ab-closeout/b-after/chat.png /tmp/ai-upper-residual-20261123 config.json > out/ab-closeout/b-after-shot.log 2>&1; rc=$?
# 改后 rc=0
python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/ab-closeout/b-before > out/ab-closeout/b-before-diff.log 2>&1; rc=$?
python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/ab-closeout/b-after > out/ab-closeout/b-after-diff.log 2>&1; rc=$?
# 两次 rc=0；chat：112725 / 10.74% → 112844 / 10.75%，增加 119 个严格差异像素。
python3 out/ab-closeout/measure_b.py > out/ab-closeout/b-image-metrics.log 2>&1; rc=$?
# rc=0；前后图实际变化 769px，范围 (484,599,541,617)。
AI_UPPER_HOME=/tmp/ai-upper-b-targeted BROKEN_IMAGE_EVIDENCE=out/ab-closeout/b-probe .venv/bin/python -m pytest app/tests/test_qml_broken_image.py app/tests/test_markdown_document.py app/tests/test_markdown_body.py app/tests/test_markdown_chunked.py app/tests/test_qml_code_scroll.py -q -s -ra > out/ab-closeout/b-tests.log 2>&1; rc=$?
# rc=0；104 passed in 14.27s；0 skipped、0 failed。
# BROKEN_IMAGE slot=16.0x16 alt_width=41.953125 total_width=57.953125 green_pixels=42 icon_position=(484.0,67.0)
```

截图：`out/ab-closeout/b-before/chat.png`（164669 字节，md5 e0a127e4773b01daf6cfddae6b1ad3eb）→ `out/ab-closeout/b-after/chat.png`（165232 字节，md5 783154083938b2b1e76921e486f210e2）。
原版实时截图 `out/ab-closeout/deva-image-live.png`；细节图 `deva-image-detail.png`、`before-image-detail.png`、`after-image-detail.png` 均在同一证据目录。
代码改动限于 `markdown/document.py`、新增 `markdown/broken_image.py`；测试涉及 `test_markdown_document.py`、`test_markdown_body.py`、新增 `test_qml_broken_image.py`。


### C · 本段最终产品代码全量回归与交付边界

B 已提交并推送：`c141d0d837bf1dd6f3ca3ed921f5aa976c48035e`，push rc=0；原始远端行：

```text
c141d0d837bf1dd6f3ca3ed921f5aa976c48035e	refs/heads/develop
```

**本段产品代码全量：1357 passed、5 skipped、0 failed，rc=0，213.46s。**
测试源码为 A/B 完成后的 `c141d0d837bf1dd6f3ca3ed921f5aa976c48035e`；C 提交只补报告和证据，不改产品或测试。
本轮不采用历史 `1352 passed, 5 skipped` 作为结论。

| 运行环境 / 实测命令 | 真实结果 | 判定 |
|---|---|---|
| 原工作区：`AI_UPPER_HOME=/tmp/ai-upper-ab-full .venv/bin/python -m pytest app/tests -q -ra > out/ab-closeout/full-root.log 2>&1; rc=$?` | **1 failed, 1356 passed, 5 skipped in 214.45s (0:03:34)**；rc=1 | 原工作区原地全绿 **未达标**；唯一失败为 `test_repository_keeps_no_stale_old_name`，会扫描历史 `.tmp/` 内容 |
| 当前提交源码快照：工作目录 `.tmp/ab-closeout/final-source`；`AI_UPPER_HOME=/tmp/ai-upper-ab-clean /home/agent/shared_workspace/ai_upper/.venv/bin/python -m pytest app/tests -q -ra > /home/agent/shared_workspace/ai_upper/out/ab-closeout/full-clean.log 2>&1; rc=$?` | **1357 passed, 5 skipped in 213.46s (0:03:33)**；rc=0 | 当前产品和测试全量通过，无 A/B 引入的测试失败 |
| 同一未修改的名称扫描单测，在源码快照运行 | **1 passed in 0.07s**；rc=0 | 原地失败来自历史临时文件，不是新产品命名残留 |

环境归因证据：

- `app/tests/test_app_home.py` 与原始基线 `7f304e9` 完全一致，sha256 `822bf527c2196aa4404363adf17b09cea7379816b0e4ac06088c15ce11fe20e8`。
- 使用基线和当前同一个函数对现工作区各扫描一次，都是 **21 个 offenders、全部在 .tmp/、两个列表完全相同**；详见 `out/ab-closeout/name-baseline-proof.log` 和 `name-offenders.json`。
- 通过 `git archive c141d0d` 导出仓库源码，不包含本来就被测试排除的 `out/`；没有新分支、没有修改测试。
  `app/`、`tools/`、`launcher/` 的 **231 个 tracked 文件逐字节相同**。
  仓库现有且被 gitignore 的 `app/pyproject.toml` 原样复制，sha256 `fc979936f0cfba16d08e208aebd81bafb926528d4e59e4b22c97a729e5b7892c`。
- 临时目录仍保留；不通过删除历史数据、修改忽略列表或放宽断言把原地结果伪装成绿色。

5 个 skip 原文类别：2 个 Windows 专属构建行为；2 个需要 `AI_UPPER_E2E=1` 的完整本机构建 E2E；1 个要求 cc/patchelf/readelf 的原生部署测试。它们不是本轮新增跳过。

报告提交后的 **最终 HEAD** 复验命令（全量，不是只测 A/B）：

```sh
AI_UPPER_HOME=/tmp/ai-upper-ab-final-head python3 out/ab-closeout/run_final_head.py > out/ab-closeout/final-head-run.log 2>&1; rc=$?
```

该入口从运行时 `git rev-parse HEAD` 再次导出源码，逐字节比对 231 个 tracked 文件，再运行同一条 `python -m pytest app/tests -q -ra`。
最终 HEAD、命令、配置摘要、全部源文件哈希写入 `out/ab-closeout/final-head-verification.json`；真实 pytest 输出与退出码写入 `final-head.log` / `final-head.rc`。
这次复验在报告提交后执行，结果文件留在工作区作为交付证据；最终回复给出实际 HEAD 和真实数字。

本段完成度：A 独立横向滚动已修复，B 原生断图结构已修复；C 当前产品代码全量通过，但**原工作区历史临时目录导致的单个名称扫描红项仍在**，不能写成原地零失败。

本轮按用户范围未做：D3 文字/边缘/阴影残差、E3 组合布局、表格底边与间距、🚀/✅ 缺字形、deva 2x 对照、CI 最终归因、旧设置内部残差、long-mid 非悬停差。
原因均为用户明确延期，未另行尝试或改变已验证结果。A1、A2–A4、D1、D2、G5 没有重做；已消失的 D3 旧「约 16.8k 白像素差」没有按旧结论修改。


## 25883ce 之后：真实工作区回归、证据入口与 E3/表格收口

### 第 0 步：只读起点

命令 `git rev-parse HEAD > out/layout-closeout/start-head.log 2>&1; rc=$?`，rc=0。原始 stdout：

```text
25883cead40d791c006b38f83c5a45ffc13c1df6
```

命令 `git log --oneline -3 > out/layout-closeout/start-log.log 2>&1; rc=$?`，rc=0。原始 stdout：

```text
25883ce test: 记录最终代码全量回归及环境归因 / record final regression evidence
c141d0d fix(markdown): 复用原生断图图标 / render native broken-image placeholder
88b2de2 fix(markdown): 代码块独立横向滚动 / scroll overflowing code independently
```

命令 `git status --porcelain --untracked-files=no > out/layout-closeout/start-status.log 2>&1; rc=$?`，rc=0。原始 stdout：

```text
```

命令 `git ls-remote origin refs/heads/develop > out/layout-closeout/start-remote.log 2>&1; rc=$?`，rc=0。原始 stdout：

```text
25883cead40d791c006b38f83c5a45ffc13c1df6	refs/heads/develop
```

status 的代码块为空，表示 tracked 工作区干净。原 A/B/C 三个提交未重做、未回退。

### 第 1 项：真实工作区名称扫描已修复

修改 `app/tests/test_app_home.py`，使用 `git ls-files -z` 枚举 Git index 路径，再读取工作区真实内容；保留显式兼容白名单和旧名断言，排除 `.tmp/`、`out/` 等运行期目录。未清理 `.tmp/`，未导出源码快照来替代真实工作区验收。

- 正常扫描命令：`AI_UPPER_HOME=/tmp/ai-upper-layout-clean .venv/bin/python -m pytest app/tests/test_app_home.py::test_repository_keeps_no_stale_old_name -q > out/layout-closeout/scan-clean.log 2>&1; rc=$?`；**1 passed in 0.09s，rc=0**。
- 变异：新建 `app/src/brand_mutation_probe.py`，内容 `# py_upper deliberate mutation, removed after verification`，`git add` 后用同一测试（AI_UPPER_HOME=/tmp/ai-upper-layout-mutant）运行；**1 failed in 0.31s，rc=1**，原文 `AssertionError: ['app/src/brand_mutation_probe.py: py_upper']`。随后 `git rm -f` 移除该临时受控文件，未提交变异。
- 真实工作区全量命令：`AI_UPPER_HOME=/tmp/ai-upper-layout-full .venv/bin/python -m pytest app/tests -q > out/layout-closeout/full-step1.log 2>&1; rc=$?`；**1357 passed, 5 skipped in 211.83s (0:03:31)，0 failed，rc=0**。
- 改前真实工作区 **1 failed / 1356 passed / 5 skipped / rc=1** → 改后 **0 failed / 1357 passed / 5 skipped / rc=0**。变异证明受控文件中的旧名仍被拒绝。

### 第 2 项：A/B/C 证据入口已补齐

新增 `out/ab-closeout/REPORT.md`，按落盘日志逐项列出 A/B/C 命令、rc、真实滚轮值、断图像素和历史最终 HEAD 全量结果；另列本轮真实工作区全量及未闭环项。未重新实现 A/B。第1项提交 `71ff27b`，push rc=0；原始行见 `out/layout-closeout/remote1.log`。

### 第 3 项：E3 组合布局已改善；表格底边/精确间距仍未闭环

**不宣称全部修完**：列表行推进、列表容器段后距和引用边界已按原版修正；表格底边仍两行、行盒及精确 padding 残差仍存在。
修改前 `git diff HEAD -- app/src/markdown/document.py` 输出 0 字节。只改 `app/src/markdown/document.py` 和两条新增几何回归测试；未修改旧测试断言、未重做 A/B。最终产品代码未保留失败的候选表格绘制器。

实际来源：deva 只读 `apps/desktop/src/renderer/src/styles/app.css:765–875`；完整本段 CSS 抽取 `out/layout-closeout/deva-body.css`。
CDP 实时原始几何 `deva-layout.json`：正文 line-height=23.1px，列表行高23.09375px、li margin=2px、ol/ul bottom=12px；blockquote 左边框3px、内边距左12px/上下2px、外边距左右0；table margin-bottom=12px、th/td padding=6px 10px、border=1px。
CDP 命令：`AI_UPPER_HOME=/tmp/ai-upper-layout-deva DEVA_HOME=/tmp/ai-upper-layout-deva DEVA_CONFIG=/tmp/ai-upper-residual-20261123/config.json DEVA_SEED=/tmp/ai-upper-residual-20261123/data/chats CDP_PORT=9335 node .tmp/layout-closeout/deva_layout.mjs chat out/layout-closeout/deva-layout.json > out/layout-closeout/deva-layout.log 2>&1; rc=$?`；rc=0。仅运行时测量，无 deva 文件写入。

| 子项 | 改前 → 改后实测 | deva 实测 / 判定 |
|---|---|---|
| CJK 列表行推进 | 25.921875 → **25.09375px** | deva25.09375；已修复字体 fallback 造成的比例行高漂移，使用 CSS 固定行高 |
| 两组列表边界推进 | 25.921875 → **35.09375px** | deva35.09375；已修复容器12px段后距缺失 |
| 嵌套引用横向缩进 | 27 → **15px**（3+12） | 原版每层15；去除6px全向补偿 margin、额外空块，新增测试锁定 |
| 一级到二级引用纵向推进 | 43.921875 → **37.09375px** | deva37.09375；容器边界已修复 |
| 表后间距 | 最后 cell 内容盒底到后段起点 **2.5→14.5px**；表格 margin-bottom **0→12px** | 原版表外边框底到后段起点12px；QText 的盒模型另含2.5px偏差，**精确像素仍缺** |
| 表格底边 | 改前 y214/215 两行 → 改后 y217/218 两行 | 原版 y224 单行；**仍存在，未修复**。行坐标移动不等于双边已解决 |
| 表格行推进与内边距 | 行推进 **35→35px**，3个NBSP的近似水平padding保留 | deva34.4375px、真实10×6 padding；**仍有差异**，不把结构格式的1px边框断言当成实拍单行 |
| 分块渲染 | 候选曾多出接缝空块，修正边界状态传递后既有 **20项全部通过** | 未放宽分块/整篇 blockCount、size、内容及格式等价断言 |

逐带坐标（暗像素 max<200、每行>3像素，x=[530,1184)、y=[40,640)，同阈值比较）：

| 内容 | 改前 QML | 改后 QML | deva |
|---|---|---|---|
| 表头 | 92–105 | 94–107 | 96–109 |
| README | 127–140 | 129–142 | 132–144 |
| src | 163–175 | 165–177 | 166–178 |
| package | 197–210 | 199–212 | 201–214 |
| 有序1 | 259–269 | 275–285 | 277–287 |
| 有序2 | 283–297 | 298–312 | 301–314 |
| 有序3 | 309–323 | 323–337 | 327–340 |
| 无序1 | 336–348 | 359–371 | 363–375 |
| 无序2 | 362–374 | 384–396 | 388–400 |
| 已完成 | 388–401 | 409–422 | 413–425 |
| 未完成 | 413–426 | 434–447 | 437–450 |
| 一级引用 | 447–460 | 471–484 | 475–487 |
| 二级引用 | 490–504 | 507–521 | 511–524 |

源码文档布局命令：`AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 .venv/bin/python out/residual-20261123/body_layout_probe.py > out/layout-closeout/after-layout.json 2> out/layout-closeout/after-layout.err; rc=$?`，rc=0；改前同命令使用 before-layout.json。
像素带与底边命令：`python3 out/layout-closeout/measure_layout.py out/latest-parity/deva/chat-deva.png out/layout-closeout/before/chat.png out/layout-closeout/after/chat.png > out/layout-closeout/final-bands.log 2>&1; rc=$?`，rc=0；底边仍两行的原始输出保留。

只重拍 chat/search-none：

```sh
AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh chat out/layout-closeout/after/chat.png /tmp/ai-upper-residual-20261123 config.json > out/layout-closeout/after-chat.log 2>&1; rc=$?
AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh search-none out/layout-closeout/after/search-none.png /tmp/ai-upper-residual-20261123 config.json > out/layout-closeout/after-search.log 2>&1; rc=$?
python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/layout-closeout/before > out/layout-closeout/before-diff.log 2>&1; rc=$?
python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/layout-closeout/after > out/layout-closeout/after-diff.log 2>&1; rc=$?
```

以上 rc 均0；改前截图同命令把 after 换为 before，rc也为0。原版图复用既有基线。严格像素差：

| 页面 | 改前 px / % | 改后 px / % | 减少 |
|---|---:|---:|---:|
| chat | 112844 / 10.75% | **108149 / 10.30%** | 4695px |
| search-none | 84931 / 8.09% | **80236 / 7.64%** | 4695px |

候选否决依据：只补列表/固定行高候选 chat126479px；原生 cell padding + 全表重画候选131636px，并曾引入分块差异；最终没有保留这些候选。给表格 border 显式 Solid 也未改变双行像素，已撤销无效改动。卡点是 QQuickTextEdit 的表格行盒/边界绘制，不能靠当前 QTextTableFormat 的1px格式直接得到单像素边缘；复现命令 `measure_layout.py` 输出 after 底边 `[(217,209),(218,209)]`，原版底边 `[(224,302)]`。

受影响测试命令：`AI_UPPER_HOME=/tmp/ai-upper-layout-target .venv/bin/python -m pytest app/tests/test_markdown_document.py app/tests/test_markdown_body.py app/tests/test_markdown_chunked.py app/tests/test_qml_code_scroll.py app/tests/test_qml_broken_image.py -q -ra > out/layout-closeout/target-tests.log 2>&1; rc=$?`；**106 passed in 14.20s，0 skipped，rc=0**。


第3项最终产品代码的真实工作区全量（保留 `.tmp/`）：
`AI_UPPER_HOME=/tmp/ai-upper-layout-final .venv/bin/python -m pytest app/tests -q > out/layout-closeout/full-final.log 2>&1; rc=$?`。
原文：**1359 passed, 5 skipped in 213.07s (0:03:33)，0 failed，rc=0**；增加的2项是本轮几何回归测试。
第3项提交包含的产品/测试文件与此次运行一致；commit 前未再改源码。前后截图字节数和md5见 `out/layout-closeout/image-manifest.log`。

第2项已推送，原始远端行：
```text
0617c04ee37315dac11932f74eaa4ba9b1fbd61a	refs/heads/develop
```

本轮未闭环：E3整体像素仍有偏移、表格底边仍两行、表格行高35px对34.4375px及近似padding残差。第3项为部分修复，不能标全完成。
本轮明确未做：emoji缺字形、deva 2x、CI终态归因、settings遮罩内部残差、long-mid非悬停差异、18页全量重拍，原因是用户指定延期。


## b752b0e 之后：B/C/A/D 最终收尾

起点实测 HEAD/远端均 `b752b0e17e5b9e92e17dae8016c0b0168365e063`，tracked status 空；原始输出 out/final-parity/start-*.log。A要求最终产品代码，因此先B/C，再A，最后D。

### B：emoji 缺字形已修复

原版 tokens.css:9 字体栈 `-apple-system, BlinkMacSystemFont, Segoe UI, Microsoft YaHei, Roboto, Helvetica, Arial, sans-serif`，没有明确 emoji 家族，走系统 fallback。
`fc-list :charset=1f680 file family` 与 `fc-list :charset=2705 file family` 均 rc=0、输出0字节；Qt 的实际fallback为Noto Sans CJK SC，🚀/✅ glyph index都是0。因此是**缺字形方块**，不是没有渲染。

使用上游 Noto Color Emoji v2.047，git tag commit `22e564626297b4df0a40570ad81d6c05cc7c38bd`；从只读克隆 `git show v2.047:fonts/NotoColorEmoji.ttf` 提取到 app/assets/fonts，10643852字节，OFL许可一并打包。main分支的旧fonts下载地址404，原始错误保留在 .tmp/final-parity/font-download*.log；没有假称首次下载成功。
实现：BodyDocument创建时注册该字体，设置Qt emoji fallback；正文主字体不变。命令及文件sha见 out/final-parity/b-font-file.log。

真实 QML 像素探针：`AI_UPPER_HOME=/tmp/ai-upper-emoji-pixel-before .venv/bin/python out/final-parity/emoji_probe.py before > out/final-parity/emoji-pixel-before.log 2>&1; rc=$?`，after同理换后缀，两次rc=0。before只在独立探针进程禁用本次新加的注册函数，不修改产品或原提交。

| 字符 | 改前位置/像素/glyph | 改后位置/像素/glyph |
|---|---|---|
| 🚀 | (484,69)，暗像素114、彩色0、glyph0 | (484,69)，暗像素93、彩色76、Noto Color Emoji glyph963 |
| ✅ | (501,69)，暗像素114、彩色0、glyph0 | (502,69)，暗像素146、彩色143、Noto Color Emoji glyph143 |

截图 out/final-parity/emoji-before/glyphs.png → emoji-after/glyphs.png。18页固定夹具不含这两个字符（源搜索rc1），所以chat复拍严格差异 **108149px/10.30%→108149px/10.30%**、md5相同；不为制造改善数字篡改标准夹具。实际命中的专用emoji正文截图如上，功能有真实改善。
chat命令：`AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh chat out/final-parity/b-after/chat.png /tmp/ai-upper-residual-20261123 config.json > out/final-parity/b-after/chat.log 2>&1; rc=$?`，rc0；page_diff18.py对b-before/b-after两次rc0，原始输出b-before-diff.log/b-after-diff.log。
测试：`AI_UPPER_HOME=/tmp/ai-upper-emoji-tests .venv/bin/python -m pytest app/tests/test_emoji_font.py app/tests/test_markdown_body.py app/tests/test_qml_shell.py -q > out/final-parity/b-tests.log 2>&1; rc=$?`，**74 passed in 17.12s，0 skipped，rc0**。

### C：long-mid 行内结构已修；设置内部仍不能证明纯取整

B已提交推送 `223274c5b24daac594e2eaf815e0e3a40561168c`，push rc0，回执 out/final-parity/b-remote.log。

**long-mid：结构性缺口已修。** 不是54px行高累积：两端每行推进54px，悬停色带都为y668–721共54行；(668,721)这个单点在主正文区域，两端都是(255,255,255)，不能将它误作侧栏色带坐标。
行内标题盒错误为17px，原版实时DOM为19px；角色名 y27 原版应y29。修正 ThreadRow.qml 的这两个值，行高、contentY=1386、悬停注入未改。
原版源码 `.cf-thread__title font-size:13px/600`、`.cf-thread__sub margin-top:2px`，CDP实测第一个完整行rect y98/h54、title y106/h19、owner y127/h13（相对行8/29）。该次DOM自动滚动落点不同，使用的是行内相对几何，不将绝对y冒充截图滚动位置。源与输出 deva-thread-css.log / deva-thread.json。
命令 `AI_UPPER_HOME=/tmp/ai-upper-thread-dom DEVA_HOME=/tmp/ai-upper-thread-dom DEVA_CONFIG=/tmp/ai-upper-residual-20261123/config.json DEVA_SEED=/tmp/ai-upper-residual-20261123/data/chats CDP_PORT=9336 node out/final-parity/deva_thread_probe.mjs long-mid out/final-parity/deva-thread.json > out/final-parity/deva-thread.log 2>&1; rc=$?`，rc0。
重拍命令 `AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh long-mid out/final-parity/c-after/long-mid.png /tmp/ai-upper-residual-20261123 config.json > out/final-parity/c-after-long.log 2>&1; rc=$?`，rc0。page_diff18.py 的 long-mid **130093px/12.39%→124617px/11.87%**（本轮新deva基线）；并非整个页面像素全部一致。

**设置内部：未达成用户要求的两种闭环结论。** 无证据允许把所有残差称为“纯取整”，也没有声称所有结构性差异已修。仍需后续处理，不编造二选一。
逐页分区 `python3 out/final-parity/regions.py > out/final-parity/regions.log 2>&1; rc=$?`，rc0；区域(280,130)-(1000,690)：

| 页 | inside_diff | inside_gt8 | outside_diff |
|---|---:|---:|---:|
| general |14719|3122|295806|
| models |3458|1596|295806|
| extensions |8375|4250|295806|
| about |5149|1773|295806|

原始像素例：内部边缘(280,130) QML(84,84,90)对deva(109,109,113)，差25；这是边缘采样，不能称1级遮罩取整。主要外部色对(143,143,144)对(144,144,144)，才符合1级合成差。
`python3 out/final-parity/modal_probe.py settings-models settings-extensions settings-about settings-general > out/final-parity/modal-analysis.json 2> out/final-parity/modal-analysis.err; rc=$?`，rc0。
大差像素在两侧都为平坦色块的计数各为0；但2px邻域双向匹配仅825/1596、2257/4250、835/1773、1907/3122，余项不能自动归为取整。
具体文字bbox：Models provider_name QML[506,257,576,269] vs deva[506,258,576,274]；extensions row2 QML[483,302,667,313] vs deva[484,301,669,313]，见 modal-regions-summary.log。卡点为字体行盒/字重栅格与控件边缘的剩余差异，仍保留，没有只拿outside_diff下结论或改遮罩颜色。
测试命令 `AI_UPPER_HOME=/tmp/ai-upper-c-tests .venv/bin/python -m pytest app/tests/test_qml_sidebar.py app/tests/test_qml_settings_overlay.py app/tests/test_qml_settings_models.py -q > out/final-parity/c-tests.log 2>&1; rc=$?`；具体原文见该日志及.rc。

### D：CI 可读但本轮尚无终态；1x/2x 实测已完成

`gh run list --branch develop --limit 6 --json databaseId,headSha,status,conclusion,url > out/final-parity/ci-runs.json 2> out/final-parity/ci-runs.err; rc=$?`，rc127，原文 `/bin/bash: line 1: gh: command not found`。
后备命令 `curl -fL --max-time 30 -H 'Accept: application/vnd.github+json' 'https://api.github.com/repos/fanchcho/ai_upper/actions/runs?branch=develop&per_page=4' > out/final-parity/ci-latest.json 2> out/final-parity/ci-latest.err; rc=$?`，rc0。不是“读不到远端CI”，实际阻塞是本轮run尚queued、conclusion=null，不能报告通过或失败：

```text
0ebe4f06e67e5e4c97a4ceafb182d68a135e9b77 queued None https://github.com/fanchcho/ai_upper/actions/runs/45216326257
223274c5b24daac594e2eaf815e0e3a40561168c queued None https://github.com/fanchcho/ai_upper/actions/runs/45214752528
b752b0e17e5b9e92e17dae8016c0b0168365e063 queued None https://github.com/fanchcho/ai_upper/actions/runs/45213129634
0617c04ee37315dac11932f74eaa4ba9b1fbd61a completed failure https://github.com/fanchcho/ai_upper/actions/runs/45210222140
```

旧提交0617c04的failure不代表本轮结果，未据此推测本轮归因。最终报告提交后再查询最终HEAD，回执留out/final-parity/ci-final-*。

2x：deva通过CDP Emulation.setDeviceMetricsOverride(deviceScaleFactor=1/2)，逻辑视口1280×820；每个scale/page均新起Electron进程，QML通过QT_SCALE_FACTOR=1/2各新起进程。没有缩放PNG伪造2x。
命令循环 `AI_UPPER_HOME=/tmp/ai-upper-scale-deva DEVA_HOME=/tmp/ai-upper-scale-deva DEVA_CONFIG=/tmp/ai-upper-residual-20261123/config.json DEVA_SEED=/tmp/ai-upper-residual-20261123/data/chats PROBE_SCALE=<1或2> CDP_PORT=9338 node out/final-parity/deva_scale_probe.mjs <chat或empty> out/final-parity/scale/deva-<page>-<scale>.json > 对应.log 2>&1; rc=$?`，4次rc0，DOM返回dpr1/2。
QML命令 `AI_UPPER_HOME=/tmp/ai-upper-qml-scale QT_SCALE_FACTOR=2 bash scripts/parity/qml_page_shot.sh chat out/final-parity/scale/qml-chat-2.png /tmp/ai-upper-residual-20261123 config.json > out/final-parity/scale/qml-chat-2.log 2>&1; rc=$?`；empty用独立无会话home `/tmp/qml-page-empty-empty`，两次rc0。1x沿用本轮全页的独立进程图。
`python3 out/final-parity/scale_compare.py > out/final-parity/scale-compare.log 2>&1; rc=$?`，rc0，实际输出：

```text
chat 1 size (1280, 820) AE 102556 pct 9.77096 qml_md5 069142b30b193cd575b485f9ad1ea86f deva_md5 fa884a918c9f9f8267d689c59a1147d1
empty 1 size (1280, 820) AE 13333 pct 1.27029 qml_md5 e56462d7a538be35dae1b166403f4784 deva_md5 bf92513a0cbecec215621d4b3368bd16
chat 2 size (2560, 1640) AE 341660 pct 8.13786 qml_md5 e1bfa9009cf2c7fe93d799db7cb7e3ca deva_md5 266fa30e74116fa631210cb367a96292
empty 2 size (2560, 1640) AE 45299 pct 1.07896 qml_md5 a984d121858334d1aa8fdffc1c2525df deva_md5 054b55b4d8a6d2a87a3e34c6f861d224
```

两端尺寸同为1x1280×820、2x2560×1640。此为1x/2x已验证有差异，不宣称像素等价；CDP基线与常规X11截图路径不同，不能混用两套百分比。
