# 表格渲染路径：一次插满行 + 边框并入同一次写入

承接 `e711a5f`（分块渲染，400 轮长会话同步段 5744.6 → 2256.0 ms）。本轮只做两件事：

1. 把 `_table` 的「`insertTable(1, n)` + 逐行 `appendRows(1)`」改成一次 `insertTable(行数, 列数)`；
2. 把 `_apply_cell_borders` 的第二遍整表遍历并进 `_table_row` 的同一次 `setFormat`。

以及一项**调查**：attach 段那约 900–960 ms 里到底是不是语法高亮，能不能靠「高亮前置、随片段迁移」省掉。
结论是**不能**，而且原先的归因是错的。调查过程与反证数据全部在 §4。

- 仓库：`/home/agent/shared_workspace/ai_upper`，分支 `develop`
- 基线：`fb5cca8`（工作区无改动时开跑）
- 输出：`out/render-opt2/`

---

## 1. 结论

| 指标（400 轮正文，20800 块，2000 个表格） | 改动前 | 改动后 | 变化 |
| --- | --- | --- | --- |
| 渲染器整篇（交替 A/B，7 次中位数） | 5101.1 ms | 2773.2 ms | **−45.6%** |
| 渲染器整篇（同机独立进程，各 3 进程取最小） | 5140.4 ms | 2778.1 ms | −46.0% |
| 同步段 `kind_table`（`profile_sync_breakdown.py`，两趟各 2 轮均值） | 559.8 / 582.4 | 530.9 / 545.5 | −29 / −37 ms |
| 同步段 `body_render` | 1319.8 / 1359.8 | 1291.5 / 1316.9 | −28 / −43 ms |
| 同步段 `attach`（未改） | 934.3 / 901.4 | 899.9 / 917.9 | 噪声内 |
| 长会话 `openSession` 同步段（点击探针两趟各 4 次中位数） | 2270.6 / 2177.5 | 2159.6 / 2188.8 | 第一趟 −111 ms、第二趟 +11 ms（BEFORE 自身两趟差 93 ms，属漂移范围） |
| 长会话首帧 | 761.6 / 729.6 | 738.6 / 748.9 | 噪声内 |
| 短会话同步段 | 69.9 / 71.4 | 71.4 / 68.9 | 无变化 |
| 短会话首帧 | 89.7 / 92.9 | 92.6 / 91.4 | 无变化 |

逐块保真：**12 组（3 个轮数 × 4 个分组）全部 0 差异**，`toHtml()` 逐字节相等，单元格格式
（四条边的宽度/画刷/样式、四向内边距、底色）逐格相等。见 §3。

**长会话同步段的收益没有渲染器层面那么大**，因为同步段里 `attach` 的约 900–960 ms 完全没动
（见 §4，那里也说明为什么动不了），而 `body_render` 只剩 1240 ms 左右，表格本来
只占其中约 500 ms。

### 1.1 分段计时明细（交替两趟，同机同口径）

`AI_UPPER_PROBE_OLD_TABLE=HEAD` 在进程内把 `_table`/`_table_row` 换回 `HEAD` 的实现，
源码不动；BEFORE/AFTER 交替跑两趟，每趟 2 轮长会话取均值。原始 JSON：
`sync_breakdown_{before,after}_{1,2}.json`。

| 段 | BEFORE #1 | AFTER #1 | BEFORE #2 | AFTER #2 |
| --- | --- | --- | --- | --- |
| `kind_table` | 559.8 | **530.9** | 582.4 | **545.5** |
| `kind_code` | 215.0 | 217.8 | 223.7 | 222.8 |
| `kind_hairline` | 64.7 | 65.5 | 64.7 | 66.2 |
| `body_render` 合计 | 1319.8 | 1291.5 | 1359.8 | 1316.9 |
| `attach`（未改） | 934.3 | 899.9 | 901.4 | 917.9 |
| `_render_total` | 2255.7 | 2192.8 | 2262.8 | 2236.2 |
| 短会话同步段 | 68.9 / 61.7 | 66.8 / 69.8 | 67.9 / 62.2 | 70.3 / 63.8 |

`kind_table` 两趟都是 AFTER 更低（−29 / −37 ms），方向一致；`body_render` 与总量的差值
小于 `attach` 自己的抖动（±35 ms），单次点击测不出来是正常的。短会话两版都在
62–70 ms，说明 ≤50 块的原始路径没有被触碰。

渲染器层面（§1 第一行）才是这次改动的真实收益口径：表格渲染在整篇路径上省掉 2.3 s，
但在 `openSession` 里表格只跑一次分块路径，且和 `attach` 的 900 ms 串行叠加。

---

## 2. 改动

### 2.1 `_table`：一次插满所有行

`app/src/markdown/document.py`

```python
# 前
table = cursor.insertTable(1, len(header), table_fmt)
self._table_row(table, 0, header, align, header_row=True)
for row_index, row in enumerate(rows, start=1):
    table.appendRows(1)
    self._table_row(table, row_index, row, align, header_row=False)
self._apply_cell_borders(table)

# 后
table = cursor.insertTable(1 + len(rows), len(header), table_fmt)
self._table_row(table, 0, header, align, header_row=True)
for row_index, row in enumerate(rows, start=1):
    self._table_row(table, row_index, row, align, header_row=False)
```

形状不变的前提是 `parser.py:205-207` 已经把每行补齐到表头列数
（`cells += [""] * (len(header) - len(cells))`，再 `cells[:len(header)]`），所以
`insertTable(1 + len(rows), len(header))` 与「先插一行再 appendRows」得到同样的行列数。
保真矩阵（§3）里 `blocks`/`chars`/`tables_eq`/逐格内容逐项相等，是这条前提的实测检查。

### 2.2 边框并入同一次 `setFormat`

原先 `_apply_cell_borders` 在整表填完后**再遍历一遍**，逐格 `QTextTableCellFormat(cell.format())`
读出、改边框、写回。现在边框写在 `_table_row` 里本来就要做的那次 `setFormat` 中，第二遍不再存在
（`_apply_cell_borders` 整个删除，仓库里没有其它调用点）：

```python
cell_fmt = QTextTableCellFormat(cell.format())
... setLeftPadding / setRightPadding / setTopPadding / setBottomPadding
... setBackground（表头 bg_panel、偶数行 bg_hover）
cell_fmt.setBorder(0.0)
四条边 setXxxBorder(1.0)
四条边 setXxxBorderBrush(border)
四条边 setXxxBorderStyle(Solid)
cell.setFormat(cell_fmt)
```

顺序上唯一要守的是：**先读 `cell.format()`、再写边框、最后一次性 `setFormat`**。原先
`_table_row` 已经写过一次 `setFormat`（内边距/底色），第二遍再读回来就是为了叠加边框；
合并成一趟后只写一次，语义等价。

为什么不能只写表格级 1px：`QTextTableFormat.setBorder(1)` 在 `BorderCollapse=True` 下不产生
逐格边框属性，`toHtml()` 里 `<td style>` 不会出现 `border-*`，QML 侧就退回无线框表格。
实测数据见 §3 的「只写表格级边框」对照（`html_eq_inherit: false`、`cells_eq_inherit: false`）。

---

## 3. 保真

### 3.1 改动前 vs 改动后（同进程，旧渲染器从 git 取出）

`probe_table_before_after.py HEAD` → `fidelity_table.json`。
旧渲染器 = `git show HEAD:app/src/markdown/document.py`，独立模块加载；两版用同一份
`BodyStyle`、同一 `content_width=676`、同一图片解析器渲染同一份 Markdown（含 RICH：引用、
嵌套引用、任务列表、图片、表格、代码块）。逐块比：块文本、块格式（四边距/行高/类型/对齐/
缩进/制表位/块属性）、每个字符片（字体族/字号/字重/斜体/前景色/背景色/图片名）；另比表格
形状、逐格单元格格式、文档尺寸、`toHtml()`。

| 轮数 | 块数 | 字符数 | 逐块差异 | `tables_eq` | `cells_eq` | 表格数 | 单元格数 | `height_eq` | `html_eq` | `html_len` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 260 | 1885 | 0 | ✔ | ✔ | 25 | 110 | ✔ | ✔ | 119811 |
| 12 | 624 | 4528 | 0 | ✔ | ✔ | 60 | 264 | ✔ | ✔ | 286898 |
| 30 | 1560 | 11350 | 0 | ✔ | ✔ | 150 | 660 | ✔ | ✔ | 716576 |
| 60 | 3120 | 22720 | 0 | ✔ | ✔ | 300 | 1320 | ✔ | ✔ | 1432706 |
| 120 | 6240 | 45500 | 0 | ✔ | ✔ | 600 | 2640 | ✔ | ✔ | 2865006 |
| 400 | 20800 | 152180 | 0 | ✔ | ✔ | 2000 | 8800 | ✔ | ✔ | 9549446 |

（块数/字符数/单元格数/`html_len` 每行都是 `[旧, 新]` 两值相等的形式，这里只列一个值；
原始 JSON 里是成对数组。400 轮文档高度两版同为 `372390.25`。）
`cells_eq` 的逐格快照字段：`(row, col, left/right/top/bottomBorder, 四种样式, 左/上边画刷色,
四向内边距, 底色)`。

### 3.2 改动后 × 分块分组（含 RICH 图片资源）

`probe_table_matrix.py HEAD` → `fidelity_matrix.json`。旧/新渲染器各自的 `_CHUNK_BLOCKS`
都设成同一分组，两版都走分块路径：

| 轮数 \ 分组 | 5 | 25 | 50 | 100 |
| --- | --- | --- | --- | --- |
| 12 | 0 差异 | 0 | 0 | 0 |
| 60 | 0 | 0 | 0 | 0 |
| 120 | 0 | 0 | 0 | 0 |

12 组组合：`n_diffs=0`、`tables_eq`/`cells_eq`/`height_eq`/`html_eq` 全 `true`，
图片资源引用数（`my://pic`）逐组相等（12/60/120）。

### 3.3 四方对照：一次插满行 / 只写表格级边框 / 落地版

`probe_table_fast.py`，基线是 git `HEAD` 的改动前实现，三个变体都在同一份 Markdown、
同一 `BodyStyle`、同宽度下渲染：

| 轮数 | 实现 | 耗时 ms | 逐块差异 | `cells_eq` | `html_eq` |
| --- | --- | --- | --- | --- | --- |
| 12 | 改动前（基线） | 43.2 | — | — | — |
| 12 | 只改一次插满行（边框仍第二遍） | 29.2 | 0 | ✔ | ✔ |
| 12 | 边框只写表格级 | 26.3 | 0 | **✘** | **✘** |
| 12 | **落地版** | 32.6 | 0 | ✔ | ✔ |
| 60 | 改动前（基线） | 251.7 | — | — | — |
| 60 | 只改一次插满行（边框仍第二遍） | 190.4 | 0 | ✔ | ✔ |
| 60 | 边框只写表格级 | 169.0 | 0 | **✘** | **✘** |
| 60 | **落地版** | 189.0 | 0 | ✔ | ✔ |

「边框只写表格级」那两行是本轮的**反证**：逐块格式（含字符片）看着完全一样，
但单元格格式缺失、`toHtml()` 不等——QML 侧会退回无网格表格。所以「省掉逐格 setFormat、
让单元格继承整表边框」这条路不走。

「只改一次插满行」与「落地版」的差别（边框是否并入同一次 `setFormat`）在 400 轮规模上
另做交替 A/B（`probe_ab_merge.py`，七次中位数）：

| 实现 | 中位数 | 最小 | 最大 |
| --- | --- | --- | --- |
| 只改一次插满行（边框走第二遍） | 2821.9 ms | 2798.5 | 2860.4 |
| **落地版**（边框并入同一次 setFormat） | 2783.6 ms | 2771.6 | 2800.1 |

差 **38.3 ms**（1.4%），两版逐格单元格格式与 `toHtml()` 全等。这条差额很小，
但它顺带消除了「整表再遍历一遍、逐格读-改-写」这条与 `_table_row` 重复的路径
（DRY），所以保留。

---

## 4. attach 段：调查结论是「未改」

### 4.1 先纠正归因

`e711a5f`/`fb5cca8` 的报告写的是「attach 882 ms 里高亮约 720 ms + `insertFragment` 120 ms」（本轮同机重测 attach 为 900–963 ms，方向一致）。
**这个归因是错的。** 用构造前安装的 `highlightBlock` 探针（PySide 的虚函数派发在对象构造时
绑定，构造后再改类属性拦不到已存在的实例——我先踩了这个坑，第一版探针报 0 次调用）：

`probe_highlight_phase2.py 12 400`（`highlight_phase2.log`，两次打开长会话）：

```
heavy-000  openSession 2159.3 ms
  body_render 1203.0 ms   highlightBlock 调用 0 次
  attach       947.6 ms   highlightBlock 调用 13200 次, 本体合计 106.5 ms
heavy-000  openSession 2182.1 ms
  body_render 1264.5 ms   highlightBlock 调用 0 次
  attach       908.7 ms   highlightBlock 调用 13200 次, 本体合计 105.5 ms
```

高亮器**确实**在 attach 里被 `contentsChange` 逐块驱动（13200 次 = 每个块一次），但它自己的
`highlightBlock` 只花约 105–112 ms（`highlight_phase2.log` 105.5/106.5，
`attach_decisive.log` 112.1）。attach 里真正的大头是 `endEditBlock`。

`probe_attach_lines.py 12 400`（逐行复刻 `attach`，片段构造单独计时，3 次均值；
`attach_lines.log`）：

| 语句 | ms |
| --- | --- |
| `target.setDocumentMargin(...)` | 0.0 |
| 高亮器 `setDocument(target)` | 0.0 |
| `QTextCursor(target)` | 0.0 |
| `beginEditBlock` | 0.0 |
| `select(Document)` | 0.0 |
| `removeSelectedText` | 31.7 |
| `QTextDocumentFragment(...)` 构造 | 69.8 |
| `insertFragment` | 63.5 |
| **`endEditBlock`** | **751.6** |
| `_copy_images` | 41.4 |
| 合计 | 958.0（三次总时长 963.1 / 960.2 / 951.1） |

`endEditBlock` 这 750 ms 是 `QQuickTextEdit` 在编辑块提交时对整篇文档做排版。
`probe_attach_decisive.py 12 400`（`attach_decisive.log`）把四个情形放在同一进程里对比，
各取 3 次最小值：

| 情形 | `insertFragment` | `endEditBlock` 提交 | 合计 | `highlightBlock` |
| --- | --- | --- | --- | --- |
| 线上：高亮器挂目标文档 | 162.9 | **778.8** | 941.8 | 13201 次 / 112.1 ms |
| 高亮器留在源文档（目标无高亮器） | 161.7 | **463.4** | 625.1 | 0 |
| 同一片段搬进普通 `QTextDocument` | 109.7 | **2.7** | 112.4 | 0 |
| 空编辑块（只有 begin/end） | — | 0.08 | 0.09 | 0 |

三条结论：

1. **慢在 QML 文档，不在渲染器**：同样的片段搬进普通 `QTextDocument`，提交只要 2.7 ms
   （`probe_attach_target.log`：QML 文档 `endEditBlock` 800.4 ms vs 普通 2.9 ms）。
   这是 `QQuickTextEdit` 提交后对整篇文档重排的成本。
2. **高亮器不干活也在场**：把高亮器挪走，它 0 次调用，提交仍要 463 ms；挂着它时提交
   778.8 ms。多出来的约 315 ms 不是 `highlightBlock` 本体（112 ms），而是它作为目标文档
   高亮器参与提交、并在 `contentsChange` 上被逐块驱动所带来的重排穿插。
3. **不是撤销栈、也不是可提前触发的排版**：`probe_attach_undo.log`
   `setUndoRedoEnabled(False)` 前后 758.4 / 760.1 ms；提交前先读一次
   `documentLayout().documentSize()`（0.3 ms）也不能把排版提前。
   `probe_attach_layout.log`：400 轮拆成 66 个编辑块（每 200 块一个）提交合计 1009.1 ms、
   17 组（每 800 块）823.8 ms，都比一次提交（880.1 ms）更慢——它不是可按段摊销的成本。

### 4.2 「高亮前置 + 随片段迁移」为什么不可行

用户给的方案是：把语法高亮放到各个分块 scratch 文档里跑，让字符格式随 `insertFragment` 迁移，
抑制目标文档里的重跑。三条实测全部否定：

1. **`QSyntaxHighlighter` 的产物不是字符格式，不随片段迁移。** 它写的是
   `QTextLayout.FormatRange`（布局格式）。`probe_reorder_highlight.log` 的 `B_no_rh`
   组（搬完只 `setDocument(target)`、不显式重跑）：总耗时 1092.3 ms、`hl_calls 0`，
   但目标文档着色块数 `no_rh_colored_blocks` 为 **0**，而线上路径是 2000 个着色代码块、
   10800 个布局格式区间；`no_rh_equals_A: false`。也就是说「不重跑」等于「代码没颜色」。
2. **重跑比现状慢一个数量级。** 同一探针的 `B_after` 组（搬完再 `setDocument` + 显式
   `rehighlight()`）：`rehighlight_and_rebind` 8949.5 ms，总耗时 10037.7 ms；现状
   `A_current` 945.4 ms。原因同上：在 QML 文档上一次性重高亮会把每个块都推过
   `QQuickTextEdit` 的重排路径，而现状是被 `contentsChange` 顺带驱动的。
3. **强行把布局格式搬过去会塌高度。** 这是历史反例（见 `markdown/body.py` 模块文档）：
   把源文档的 `FormatRange` 或其副本 `setFormats` 进目标 `QTextLayout` 后，那些块高度变 0，
   代码整段不可见。本轮没有再试这条，因为它已经被验证为错误方向。

等价性方面，`B_after` 与 `A_current` 的产物**确实**相等（`layout_diffs=0`、
`block_fmt_diffs=0`、`html_eq=true`、尺寸同为 `239177.75`）——方案不是「结果不对」，
是「更慢且要靠显式重跑」，而显式重跑就是 8949.5 ms。所以无论从正确性还是收益看都不该落地。

**结论：attach 段保持现状，未改。** 提交时的约 750 ms 排版是 `QQuickTextEdit` 的成本，
不在渲染器/高亮器的可改范围内；本轮的收益只来自 `body_render`（表格路径）。

> 附带的更正：旧报告把 attach 拆成「高亮 720 + 搬运 120」。实际是「提交排版 751.6 +
> 片段构造 69.8 + `insertFragment` 63.5 + 图片 41.4 + 删除 31.7」。高亮器本体约 105–112 ms，
> 且它这 112 ms 是在提交过程中被 `contentsChange` 驱动的，不能单独抽出来省。

### 4.3 着色现状基线（切换会话后仍然有颜色）

改 attach 的前提是「现在是有颜色的」。`probe_tint_switch.py` 在真实壳里连续切换
`heavy-000 → heavy-001 → heavy-000 → heavy-002 → heavy-000`，每次在同步段结束和首帧之后
各数一遍目标文档的 `QTextLayout.FormatRange` 覆盖（`tint_switch.log`）：

| 会话 | 同步段 ms | 首帧 ms | 同步后 [着色块, 着色字符, 代码块] | 首帧后 |
| --- | --- | --- | --- | --- |
| `heavy-000`（120 轮） | 612.4 | 178.3 | 600 / 14280 / 600 | 600 / 14280 / 600 |
| `heavy-001`（1 轮） | 26.5 | 29.9 | 5 / 119 / 5 | 5 / 119 / 5 |
| `heavy-000`（回切） | 612.8 | 158.0 | 600 / 14280 / 600 | 600 / 14280 / 600 |
| `heavy-002`（1 轮） | 25.2 | 26.2 | 5 / 119 / 5 | 5 / 119 / 5 |
| `heavy-000`（再回切） | 610.2 | 157.8 | 600 / 14280 / 600 | 600 / 14280 / 600 |

三点：代码块数与着色块数相等（600/600、5/5），说明着色没有漏块；同步段结束时颜色就已经在，
不需要等首帧；同一会话反复切回，数字完全一致，没有累积或丢失。这既是 §4.2「不重跑就没颜色」
的反面基线，也是以后任何 attach 改动必须保持的不变量。

---

## 5. 分块大小复核

表格路径变便宜后，`_CHUNK_BLOCKS = 50` 是否仍最优？`probe_chunk_sweep.py`（400 轮，3 次最小值；
`chunk_sweep.log`）：

| 分组 | 10 | 25 | 50 | 100 | 200 |
| --- | --- | --- | --- | --- | --- |
| ms | 1855.4 | **1828.9** | 1870.8 | 1951.7 | 2099.7 |

25 比 50 快 41.9 ms（2.2%），仍在噪声边缘；两者都落在同一平台区，而 100/200 明显变差。
改动分组会重新影响分块路径的保真矩阵覆盖面，收益不足以支撑，本轮不改，如实记录。

---

## 6. 回归测试与变异验证

新增两条（`app/tests/test_markdown_document.py`）：

- `test_a_table_with_many_rows_fills_every_row_and_column`：9 行 × 2 列表格，逐格校验文本。
  锁「一次插满行」没有少行。
- `test_every_cell_gets_its_own_border_brush_and_style`：逐格校验四条边的宽度/画刷/样式、
  四向内边距、表头底色、斑马纹底色与「奇数行无底色」。锁「边框并入同一次写入」没有漏掉
  任何一格，也锁住「不能退化成只写表格级边框」。

变异测试（改源码 → 跑测试 → 还原，逐条确认保护力）：

| 变异 | 失败用例 | 结论 |
| --- | --- | --- |
| 删掉逐格边框整段 | `test_every_cell_draws_its_own_one_pixel_border`、`test_every_cell_gets_its_own_border_brush_and_style` | 2 failed / 51 passed |
| 表头底色写到所有行（`if True:`） | `test_even_rows_carry_the_hover_background`、`test_every_cell_gets_its_own_border_brush_and_style` | 2 failed / 51 passed |
| 跳过最后一行内容 | `test_table_cells_have_10_by_6_padding`、`test_alignment_marker_is_applied_per_cell`、新增的两条 | 4 failed / 49 passed |
| 行数改回 `insertTable(1, n)` + `appendRows` | 0 failed | **见下** |

最后一条值得说明：**行数写法本身没有独立断言**。改回 `insertTable(1,n)+appendRows(1)` 后
13 条表格相关用例全绿——因为两种写法产出的文档结构完全相同，这正是 §3 保真矩阵 0 差异的
另一面。它是纯性能改动，功能等价，没有可断言的差异；用一条「必须调用 insertTable 一次」
的 spy 测试只会把实现细节焊死（`_code` 也走 `insertTable`，且将来换实现就会红）。
性能本身的回归由 `out/render-opt2/probe_ab_alternating.py`（交替 A/B）负责观测，不放进
pytest 的断言里。

完整 pytest（隔离 `HOME`，不设 `AI_UPPER_HOME`，避免 `test_default_home_uses_deva_home_env`
这类用例被环境污染）：

```
1243 passed, 5 skipped          # 改动前基线
1245 passed, 5 skipped          # 改动后（+2 新增）
```

> 注意：如果带着 `AI_UPPER_HOME=...` 跑全量 pytest，`test_secrets_vault.py::
> test_default_home_uses_deva_home_env` 与 `test_settings_service.py` 同名用例会失败——
> 那条用例断言 `DEVA_HOME` 生效，而 `AI_UPPER_HOME` 优先级更高。这是测试环境用法问题，
> 与本次改动无关（改动前同样会红）。

---

## 7. 真实外壳截图

`probe_shot_long.py out/render-opt2/shots`，离屏驱动真实 `Main.qml` + `ShellBridge`，
`openSession("heavy-000")` 后读回正文文档：13200 块、136580 字符、内容高 239221.75 px。

- `shots/long-session-top.png`、`shots/long-session-mid.png`、`shots/long-session-bottom.png`

中段截图可见：表格 1px 网格、表头 `#f7f7f8` 底色、偶数行斑马底、代码块语言标签、关键字蓝色、
字符串红色、注释斜体绿色（本张里被中文替换掉）。

**中文显示为方框是环境问题**：离屏容器里 `QFontDatabase.families()` 只有 6 个 DejaVu 族，
`/usr/share/fonts/truetype` 只有 `dejavu`，没有 CJK 字体。与 `out/render-chunking/` 下
截图是同一现象，不是本轮改动引入的回归；表格网格、代码着色、块结构与边距都不依赖 CJK 字体，
在截图里可正常核对。

---

## 8. 复现

```bash
cd /home/agent/shared_workspace/ai_upper
VENV=.venv/bin/python
ENV="LD_LIBRARY_PATH=/tmp/qtlibs QT_QPA_PLATFORM=offscreen"

# 1) 改动前 vs 改动后逐块保真（旧渲染器从 git 取出）
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/render-opt2/probe_table_before_after.py HEAD

# 2) 轮数 × 分组交叉矩阵（含 RICH 图片资源）
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/render-opt2/probe_table_matrix.py HEAD

# 3) 交替 A/B 性能（同进程，抵消热漂移）
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/render-opt2/probe_ab_alternating.py

# 3b) 独立进程整篇计时（旧/新各 3 个进程取最小）
for m in old new; do for i in 1 2 3; do
  AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV \
    $VENV out/render-opt2/probe_indep_render.py $m
done; done

# 3c) 分段计时：BEFORE 用 AI_UPPER_PROBE_OLD_TABLE=HEAD 换回旧实现，交替两趟
for pass in 1 2; do
  AI_UPPER_PROBE_OLD_TABLE=HEAD AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV \
    $VENV out/conversation-picker-lag/profile_sync_breakdown.py 120 400 2 > /tmp/sb_before_$pass.json
  AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV \
    $VENV out/conversation-picker-lag/profile_sync_breakdown.py 120 400 2 > /tmp/sb_after_$pass.json
done

# 4) attach 归因（逐行复刻 attach，片段构造单独计时）
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/render-opt2/probe_attach_lines.py

# 4b) attach 的决定性对照（有/无高亮器、普通文档、空编辑块）
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/render-opt2/probe_attach_decisive.py 12 400

# 4c) 高亮调用次数与归属（body_render 0 次 / attach 13200 次）
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/render-opt2/probe_highlight_phase2.py 12 400

# 4d) 撤销栈、排版提前、分块提交三组排除
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV out/render-opt2/probe_attach_undo.py 12 400
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV out/render-opt2/probe_attach_target.py 12 400
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV out/render-opt2/probe_attach_layout.py

# 4e) 只改行数 vs 边框并入的交替 A/B（400 轮）
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV out/render-opt2/probe_ab_merge.py

# 4f) 切会话后着色是否仍在（真实壳，120 轮长会话 + 两个 1 轮短会话）
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV out/render-opt2/probe_tint_switch.py 12 120

# 5) 高亮前置方案的三组反证
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/render-opt2/probe_reorder_highlight.py 12 400

# 6) 分块大小复核
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/render-opt2/probe_chunk_sweep.py

# 7) 全量 pytest（隔离 HOME，别带 AI_UPPER_HOME）
env -u AI_UPPER_HOME HOME=$(mktemp -d /tmp/ai-upper-home-XXXX) env $ENV \
  $VENV -m pytest app/tests -q

# 8) 真实外壳截图
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-XXXX) env $ENV $VENV \
  out/conversation-picker-lag/probe_shot_long.py out/render-opt2/shots
```

A/B 环境变量（只影响当前进程，不改源码）：

- `AI_UPPER_PROBE_OLD_TABLE=<git rev>`：把 `_Renderer._table`/`_table_row` 换回该 rev 的实现
  （`probe_old_table.py`）。
- `AI_UPPER_PROBE_WHOLE=1`：把 `_CHUNK_BLOCKS` 提到 `10**9`，强制整篇渲染路径。

### 8.1 本目录文件

| 文件 | 用途 |
| --- | --- |
| `probe_old_table.py` | 从 git 取出任意 rev 的表格实现，进程内替换（所有 BEFORE 测量的基础） |
| `probe_indep_render.py` | 独立进程整篇渲染计时（old/new） |
| `probe_ab_alternating.py` | 整体改动（行数 + 边框合并）的交替 A/B |
| `probe_ab_merge.py` | 只改行数 vs 行数+边框合并的交替 A/B |
| `probe_table_scale.py` | old/new 整篇渲染，各 5 次取最小 |
| `probe_table_fast.py` | 四方对照：基线 / 一次插满行 / 只写表格级边框 / 落地版 |
| `probe_cell_borders.py` | 逐格「读-改-写」与「只读」的微基准 |
| `probe_table_before_after.py` | 逐块 + 逐格 + `toHtml()` 保真（6 个轮数） |
| `probe_table_matrix.py` | 轮数 × 分块分组的 12 组保真矩阵（含 RICH） |
| `probe_attach_lines.py` | 逐行复刻 `attach`，片段构造单独计时 |
| `probe_attach_decisive.py` | 有/无高亮器、普通文档、空编辑块四方对照 |
| `probe_highlight_phase2.py` | `highlightBlock` 调用次数归属（构造前安装） |
| `probe_attach_target.py` / `probe_attach_undo.py` / `probe_attach_layout.py` | QML vs 普通文档 / 撤销栈 / 分块提交 三组排除 |
| `probe_reorder_highlight.py` | 高亮前置方案的三组反证与等价性检查 |
| `probe_tint_switch.py` | 真实壳里反复切换会话，数着色块/字符是否仍然存在（§4.3） |
| `probe_chunk_sweep.py` | 分块大小复核 |
| `*.log` / `*.json` | 上表各探针的原始输出 |

早期还有五个逐调用包装的探针（`probe_attach_steps.py`、`probe_attach_inner.py`、
`probe_attach_highlight.py`、`probe_highlight_phase.py`、`probe_highlight_when.py`）：
它们漏计了 `QTextDocumentFragment` 构造，也数不清高亮器在提交过程中的那部分，
数字与本报告口径不一致，已连同 `attach_steps.log`、`attach_inner.log` 一并删除，
避免目录里留着两套互相打架的数。正文一律以 `attach_lines.log` 与
`attach_decisive.log` 为准。

---

## 9. 未做 / 已放弃

| 项 | 状态 | 原因 |
| --- | --- | --- |
| attach 高亮前置 | **未改** | §4.2：布局格式不随片段迁移（不重跑时着色块 0 个）；显式重跑 8949.5 ms；强搬会塌高度 |
| `_CHUNK_BLOCKS` 调到 25 | 未改 | 41.9 ms / 2.2%，噪声边缘，收益不足以重跑全部矩阵 |
| 表格级边框替代逐格边框 | 放弃 | §3.3：`html_eq`/`cells_eq` 均为 false，QML 会退化成无网格 |
| 「行数写法」的 pytest spy | 放弃 | 功能等价、无可断言差异；spy 会焊死实现细节，性能由 A/B 探针观测 |

---

## 10. 提交

本轮提交见 `git log --oneline develop`（报告末尾同步更新 sha 列表）：

| sha | 内容 |
| --- | --- |
| `4aaa631` | `perf(markdown)`: 表格一次插满行 + 边框并入同一次 setFormat（含 `attach()` 归因更正） |
| `c5b25df` | `test(markdown)`: 表格行列与逐格边框回归用例 |
| 报告自身所在提交 | `docs(render-opt2)`: 本报告、探针与数据。sha 随本表所在提交变动，以 `git log --oneline -1 -- out/render-opt2` 为准 |
