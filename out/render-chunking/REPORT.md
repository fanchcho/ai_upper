# 正文分块渲染：把 O(块数²) 的结构性插入摊平成线性

日期：2026-11-18　分支：`develop`　提交：`e711a5f`

## 0. 结论

点开 400 轮大会话的 `openSession` 同步段：**5744.6 ms → 2256.0 ms**（同机同口径，
长会话 4 次取中位），其中渲染段 **4724.7 → 1341.4 ms**；短会话 84.1 → 69.2 ms，
无回归；首帧 746.1 → 747.3 ms（无变化）。分块路径与整篇路径在 4 种轮数 × 4 种分组
（16 组）上**逐块签名差异为 0**，`toHtml()` 完全相同。

## 1. 根因（实测）

结构性插入（`insertTable` / `appendRows` / `insertFrame`）的单价**只跟插入那一刻
文档已有规模有关**，与插入位置无关：

| 文档已有块数 | 在末尾插一张 4×3 表 | 在开头插同一张表 |
|---|---|---|
| 1 000 | 0.32 ms | 0.31 ms |
| 4 000 | 0.55 ms | 0.55 ms |
| 13 000 | 1.15 ms | 1.13 ms |

（数据来自上一轮 `probe_pos_and_fix.py`，本轮未重测。）

正文每 50 个顶层块里就有多张表（代码块 = 单列表格、引用 = 双列表格、h2 下划线 =
1px frame），所以整篇渲染的累计成本随块数平方增长。400 轮 13200 块这一档，
`profile_sync_breakdown.py`（改动前，`AI_UPPER_PROBE_WHOLE=1` 强制整篇路径）实测：

```
_render_total 5608.1 ms
  body_render  4724.7 ms   ← parse 44.2 + render_blocks 4678.5
    kind_table          2550.2   (document.py:508 _table)
    kind_hairline       1124.3   (document.py:356 _hairline)
    kind_code            708.9   (document.py:583 _code)
    kind_heading        1186.0   (上述三个分支的合计已含在 heading 内)
    kind_apply_cell_borders 94.4 (document.py:561)
    kind_inline          126.1 / kind_list 111.5 / kind_paragraph 116.7
  attach        881.8 ms   ← 目标文档高亮重跑 ~720 ms + insertFragment 59.3 + 图片搬运 41.7
```

## 2. 改动

`app/src/markdown/document.py`

- `_CHUNK_BLOCKS = 50`（:203）：阈值常量。顶层块数 ≤ 50 走原路径，逐字节不变。
- `render_markdown()`（:206-230）：解析一次，按顶层块数分派。
- `_render_chunked()`（:234-298）：每 50 个顶层块渲染进一份全新 `QTextDocument`
  （单价恒定），再按顺序 `insertFragment` 拼进目标。
- `_copy_resources()`（:301-317）：图片是文档级资源，不随片段走，每块渲染完按名字
  从 scratch 搬到目标。

两处继承链搬运（这是接缝 0 差异的关键）：

1. **末块格式**：`_table`/`_quote` 前的锚点空块靠 `insertBlock()` 不带格式、继承光标
   当前格式。新分块的光标是新的 → 把上一分块末块格式 `setBlockFormat` 到 scratch
   的初始块上（:250-252）。
2. **首块格式**：`insertFragment` 让片段首块继承目标当前块格式 → 拼完把源首块格式
   回填（:269-271）。

`app/src/markdown/body.py`：只更新两处过时注释里的数字（`document.py` 模块文档补第
7 条）。`attach()` 的行为与契约未变。

### 2.1 上一轮半成品为什么是红的

上一轮把锚点空块的判据写成 `if cursor.position() > 0`。但首块格式回填会把光标停回
**该分块首块的位置**（`setPosition(start)`），第二块起位置判据就不再成立 → 锚点空块
被跳过 → 片段首块与上一分块末块合并 → **每分块静默少一块**。400 轮少 15 块、逐块
签名差 2777 处、文档矮 289.6 px。改成 `if not first:`（按第几块，不看光标）后归零。

## 3. 前后测量（同机同口径）

### 3.1 真实壳 `openSession`：长/短会话分开

`out/conversation-picker-lag/probe_click_split.py 120 400 4`（新增；原
`probe_click_visible.py` 按奇偶轮交替开长/短会话后合并取中位，那个数字是混合物，
已按用户要求拆开）。BEFORE 用 `AI_UPPER_PROBE_WHOLE=1` 在进程内把阈值提到无穷大，
强制整篇路径，其余完全一致。

| 指标 | BEFORE（整篇） | AFTER（分块） |
|---|---|---|
| 长会话同步段 中位 | 5744.6 ms | **2256.0 ms** |
| 长会话同步段 最小 / 最大 | 5605.3 / 5828.9 | 2235.9 / 2277.0 |
| 长会话首帧 中位 | 746.1 ms | 747.3 ms |
| 短会话同步段 中位 | 84.1 ms | **69.2 ms** |
| 短会话同步段 最小 / 最大 | 80.7 / 85.7 | 63.9 / 73.3 |
| 短会话首帧 中位 | 91.9 ms | 91.5 ms |

### 3.2 分段拆解

`profile_sync_breakdown.py 120 400 3`（短会话 3 轮同一脚本内）：

| 阶段 | BEFORE | AFTER |
|---|---|---|
| `_render_total` | 5608.1 | 2225.1 |
| `body_render` | 4724.7 | **1341.4** |
| `parse_markdown` | 44.2 | 44.3 |
| `kind_table` | 2550.2 | 570.4 |
| `kind_hairline` | 1124.3 | 65.4 |
| `kind_code` | 708.9 | 216.7 |
| `kind_heading` | 1186.0 | 126.2 |
| `kind_apply_cell_borders` | 94.4 | 90.0 |
| `attach` | 881.8 | 882.3 |
| `insertFragment` | 59.3 | 120.1 |
| `_copy_images` | 41.7 | 41.3 |
| 长会话三段总计 | 5522.0 / 5636.5 / 5717.5 | 2222.3 / 2241.4 / 2263.1 |
| 短会话三段总计 | 78.0 / 82.9 / 83.2 | 67.8 / 70.6 / 64.2 |

`profile_attach.py 60 400`：

| 项 | BEFORE | AFTER |
|---|---|---|
| `set_markdown`（自有文档渲染） | 1357.0 / 1355.4 | 同左（该脚本同样可走 `AI_UPPER_PROBE_WHOLE`，此处为分块后） |

注：`profile_attach.py` 本轮只在分块路径下跑过一次（`set_markdown` 1357.0/1355.4、
`attach` 912.9/910.5、短会话 50.7/49.5），BEFORE 列沿用 `profile_sync_breakdown` 的
同源拆解；`attach` 的 912.9 ms 与拆解里的 882.3 ms 属同一量级，差在脚本自身口径。

### 3.3 分块矩阵（渲染器层）

`out/render-chunking/probe_chunk_matrix.py`，取 `render_markdown` 整函数耗时：

| 轮数 | 整篇 ms | 分组 25 | 加速 |
|---|---|---|---|
| 12 | 64.4 | 52.6 | 1.22× |
| 30 | 164.4 | 131.4 | 1.25× |
| 120 | 1258.8 | 538.0 | 2.34× |
| 400 | 10084.5 | 1825.3（分组 5/25/50/100 = 1951/1825/1879/1973） | 5.52× |

> 本表用的合成文档每轮 52 个顶层块、含 6 张表，比 `probe_heavy` 的 400 轮样本
> 更重（20800 块 vs 13200 块），所以整篇耗时比 §3.2 的 `body_render` 大。

## 4. 保真证据

`out/render-chunking/probe_fidelity_chunked.py`：同一进程内把 `_CHUNK_BLOCKS` 临时
提到 10⁹ 得到整篇基准，再按目标分组渲染，逐项对比。

比较项：块数、字符数、`toPlainText()`、逐块块格式（四边距/行高/行高类型/对齐/
缩进/制表位/自定义属性）、每字符片（字体族/字号/字重/斜体/前景色/背景色/图片名）、
表格形状（行数/列数/宽度/边距/边框/单元格间距）、`documentLayout()` 后的文档尺寸、
`toHtml()`。

| 轮数 | 块数 | 字符数 | 逐块差异 | 表格 | 文档高 | `toHtml()` |
|---|---|---|---|---|---|---|
| 5 | 260 / 260 | 1885 / 1885 | 0 | 一致 | 一致 | 相等 |
| 12 | 624 / 624 | 4528 / 4528 | 0 | 一致 | 一致 | 相等 |
| 30 | 1560 / 1560 | 11350 / 11350 | 0 | 一致 | 一致 | 相等 |
| 60 | 3120 / 3120 | 22720 / 22720 | 0 | 一致 | 一致 | 相等 |
| 120 | 6240 / 6240 | 45500 / 45500 | 0 | 一致 | 一致 | 相等 |

`probe_chunk_matrix.py` 另在 12/30/120/400 轮 × 分组 5/25/50/100 共 16 组上复核：
`n_diffs` 全为 0、`tables_eq` / `height_eq` / `html_eq` 全为 true。

**短文档逐字节不变**：顶层块数 ≤ 50 时 `render_markdown` 走与改动前完全相同的代码
路径（同一个 `_Renderer`、同一个 `QTextCursor(document)`），输出不可能变。

## 5. 回归用例

新增 `app/tests/test_markdown_chunked.py`（10 个用例）：

- 分块 vs 整篇逐块签名、表格形状、文档高度、`toHtml()` 全等（12/30 轮 × 分组
  5/25/50 共 6 组参数化）；
- 接缝处块格式（列表末块 → 下一分块标题）与整篇一致；
- 阈值边界：恰好 50 块**不**走分块（用 spy 断言），51 块走一次且输出全等；
- 图片资源在分块后仍能按名字解析。

两条变异验证用例确有防护力：

| 变异 | 失败用例数 |
|---|---|
| 去掉「末块格式传递」 | 6 failed, 4 passed |
| 锚点判据改回 `cursor.position() > 0` | 8 failed, 2 passed |

全量 pytest：**1243 passed, 5 skipped**（基线 1233 passed, 5 skipped，+10 为新用例）。

```
$ LD_LIBRARY_PATH=/tmp/qtlibs QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
1243 passed, 5 skipped in 28.61s
```

## 6. 真实壳截图

`out/conversation-picker-lag/probe_shot_long.py out/render-chunking`（真实 Main.qml +
ShellBridge，400 轮，`bodyView` 文档 **13200 块 / 136580 字符**，可见高 618 px、
内容总高 239221.75 px）：

- `long-session-top.png`：h2 下划线、代码块着色（`def` / `return` / 字符串 / `lambda`
  都有色）、有序列表 1./2.、表格（表头底色 + 斑马纹 + 1px 网格）；
- `long-session-mid.png`：内容中段（第 180 轮附近），同样的元素；
- `long-session-bottom.png`：滚到 91.7% 处（`contentY = 219515.45`），仍是正常正文。

中文显示为方框是 offscreen 环境只有 DejaVu Sans、没有 CJK 字体所致（`QFontDatabase.
families()` 只有 6 个族：DejaVu Sans/Mono/Serif），上一轮 `after-session-1.png` 同样
如此——与本改动无关，代码着色/表格/列表结构本身清晰可辨。

## 7. 残留项与余量

1. **`attach` 的 882 ms 没动**。它的大头是目标文档上的高亮器在 `insertFragment` 引起的
   `contentsChange` 里逐块重跑（≈720 ms），`insertFragment` 本身 59.3 → 120.1 ms
   （分块后片段更多，多花 61 ms）。这段在 GUI 线程上、且必须在首帧前完成，本轮未碰。
2. **渲染器单价仍有二次项**。分块后 `kind_table` 570 ms、`kind_code` 217 ms、
   `kind_apply_cell_borders` 90 ms。`_apply_cell_borders` 逐单元格 `setFormat`，是纯
   线性但常数大；`_table` 用 `insertTable(1,n)` + 反复 `appendRows(1)`，一次插满行
   可再省一截（上一轮微基准：4191 → 2875 ms）。本轮没做，避免把改动面铺开。
3. **分块大小是常量 50**，没按内容自适应。表密集的文档更小吃分块更划算，纯段落文档
   几乎没有二次成本、分块反而多花拼接开销（12 轮 1.22× 已接近临界）。
4. **高亮器在分块拼装期间没有挂在目标文档上**——`_render_chunked` 在自有文档里跑，
   高亮仍由 `attach()` 之后的目标文档高亮器完成，所以接缝不影响着色；但如果以后有人
   把高亮提前到渲染阶段，分块会产生 N 次重排。
5. 上表 §3.3 的合成文档比线上 400 轮样本更重（20800 vs 13200 块），两个数字不要混用。

## 8. 复现命令

```bash
cd /home/agent/shared_workspace/ai_upper
# 分块矩阵（渲染器层耗时 + 逐块保真）
LD_LIBRARY_PATH=/tmp/qtlibs QT_QPA_PLATFORM=offscreen \
  .venv/bin/python out/render-chunking/probe_chunk_matrix.py
# 逐块几何保真（5 种轮数）
LD_LIBRARY_PATH=/tmp/qtlibs QT_QPA_PLATFORM=offscreen \
  .venv/bin/python out/render-chunking/probe_fidelity_chunked.py
# 真实壳长/短会话分开计时（AFTER；加 AI_UPPER_PROBE_WHOLE=1 得 BEFORE）
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/probe_click_split.py 120 400 4 AFTER
# 分段拆解（同样支持 AI_UPPER_PROBE_WHOLE=1）
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/profile_sync_breakdown.py 120 400 3
# attach 细分
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/profile_attach.py 60 400
# 截图
LD_LIBRARY_PATH=/tmp/qtlibs .venv/bin/python out/conversation-picker-lag/probe_shot_long.py out/render-chunking
# 全量测试
LD_LIBRARY_PATH=/tmp/qtlibs QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

全部走 `AI_UPPER_HOME=/tmp/ai-upper-*` 临时 home（脚本内 `tempfile.mkdtemp`），不碰
真实 `~/.ai_upper`；`/home/agent/shared_workspace/deva` 未读取、未修改。
