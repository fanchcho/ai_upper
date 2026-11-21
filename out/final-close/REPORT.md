# ai_upper 收尾：7 项缺口逐项排查修复报告

仓库：`/home/agent/shared_workspace/ai_upper`（分支 `develop`）
参考原版：`/home/agent/shared_workspace/deva`（只读，未做任何写操作）
环境：所有应用/测试进程 `AI_UPPER_HOME` 均指向 `/tmp/...`，未触碰真实 `~/.ai_upper`。

> 本文件按 1–7 逐项落盘，每完成一项先追加片段，再继续下一项。

---

## 缺口 1：`deva_pages_all.sh` 参数 bug —— 已修复并重拍 18 页基线

### 1.1 根因

`scripts/parity/deva_pages_all.sh` 里页面筛选写的是 `ONLY="$*"`，而 `$1` 是输出目录：

```bash
OUT="${1:-out/qml-shell/pages/deva}"
...
ONLY="$*"          # ← 把 $1（输出目录）也算进页名
want() { ... }     # 逐页比对 $page 是否在 ONLY 里
```

于是「只给输出目录」（最常见的用法）时 `ONLY` 里永远只有那个目录名，`want` 对任何页名都不命中 → **一张图都不拍，脚本却返回 0**。用户看到的就是「脚本跑完了、没报错、但输出目录是空的」。

### 1.2 修复

`scripts/parity/deva_pages_all.sh`：

```diff
+FAILED=()
+PRODUCED=0
...
+# 注意 $1 是输出目录，页名从 $2 开始；早先写成 "$*" 会把输出目录也算进页名，
+# 于是所有 want 判定都不命中、静默产出 0 张图还返回 0。
+ONLY="${*:2}"
...
+if [ "$PRODUCED" -eq 0 ]; then
+  echo "FAIL: 0 页产出（输出目录 $OUT，筛选条件 ONLY='${ONLY}'）" >&2
+  exit 1
+fi
+if [ "${#FAILED[@]}" -gt 0 ]; then
+  echo "FAIL: ${#FAILED[@]} 页失败: ${FAILED[*]}" >&2
+  exit 1
+fi
+echo "done: $PRODUCED 页 -> $OUT"
```

同时把「单页非空但像素全黑/全白」也当成失败重试（每页最多 2 次），避免灰度存根图混进证据。

diffstat（本文件）：

```
 scripts/parity/deva_pages_all.sh | 21 ++++++++++++++++++---
```

### 1.3 复现与反证（真实命令 + 输出）

日志：`out/final-close/logs/01-repro-old-silent-zero.log`

```
== A: HEAD 版脚本 + 只给输出目录（复现静默 0 图）
RC=0
PNG 数: 0

== B: 修复版脚本 + 只给输出目录（应真的出图）
ok   empty 1280x820 40733B
ok   first-run 1280x820 40733B
done: 2 页 -> /tmp/repro-fixed
RC=0
40733 /tmp/repro-fixed/empty-deva.png
40733 /tmp/repro-fixed/first-run-deva.png
```

A 用 `git show HEAD:scripts/parity/deva_pages_all.sh` 取 HEAD 版本执行，B 用工作区修复版。同一调用方式，A 静默 0 图、B 正常出图，差异完全由本次修复造成。

守卫的「另一方向」也有实证：批量跑时 `settings-general` 连出两次 435B 灰度存根，新守卫直接 `FAIL: 1 页失败: settings-general` / `EXIT=1`，不再假成功（`out/final-close/logs/03-deva-rerun.log`）。

### 1.4 重拍结果：18 页原版对照基线

> 注：页面清单是 **18 页**，不是 19 页。`deva_pages_all.sh` 与 `qml_pages_all.sh` 各 18 条 `run_if`/`shot`，`qml_shell.py` 的 `PAGE_NAMES` 也是 18 个。原报告里的「19 页」是笔误，已把脚本注释里的过期措辞一并改掉（`deva_pages_all.sh:56`、`parity_run.sh:5`、`rebuild_parity.sh:22,31`）。

命令：`bash scripts/parity/deva_pages_all.sh out/final-close/deva-rerun`（Xvfb :97 1400×900 + Electron + `import`/`convert` 裁到 1280×820）

产物目录：`out/final-close/deva-rerun/`

> 本节数字由脚本从落盘文件重新生成（`stat -c %s` + `md5sum`），不再手抄：
> 早先手抄的字节数/md5 有若干行与文件不符（dark-chat、settings-*）。以下为当前磁盘实况。

| 页 | 文件 | 字节 | md5 |
|---|---|---:|---|
| chat | chat-deva.png | 155397 | `06a81f02a1ef8b789329f2808268dbb6` |
| ctx-menu | ctx-menu-deva.png | 155525 | `872dc19994a37d9a5cefe2e5aa56bf36` |
| dark-chat | dark-chat-deva.png | 156605 | `dd174cfe874cca285df5cfd2b6ef3038` |
| delete-confirm | delete-confirm-deva.png | 161499 | `115b84c3c896b33ce07e59f8a2d2b751` |
| empty | empty-deva.png | 40733 | `e07548ba4a6511b62e5e45ab07c27121` |
| first-run | first-run-deva.png | 40733 | `26a05a5435320d03600e00b40fc06d0a` |
| focus-composer | focus-composer-deva.png | 155698 | `a5273989e6eb741908af9273352ad1af` |
| hover-thread | hover-thread-deva.png | 155046 | `358efb1a6e05413687487207ae7a3541` |
| long-bottom | long-bottom-deva.png | 154577 | `8f6fded19b63b3f90a9213c7ec55c960` |
| long-mid | long-mid-deva.png | 140254 | `6e1673c62c6b0a59feb449f065ec20fb` |
| model-picker | model-picker-deva.png | 161178 | `b3857b3344c4c8e42c8d4cfe3ebb9c0f` |
| search-none | search-none-deva.png | 64532 | `72036a2dabc6e64dc4626e38be891a33` |
| search-open | search-open-deva.png | 155630 | `9c8a62e33f55f2be59b65ee96870c839` |
| search-results | search-results-deva.png | 128199 | `0523e1a443a3a1fb91b23b84c0a769b9` |
| settings-about | settings-about-deva.png | 134899 | `50b2ee8135ee7c4cc4f5568d36cac0ab` |
| settings-extensions | settings-extensions-deva.png | 138577 | `59ce447e9abfe50f32d9b39e65701b5b` |
| settings-general | settings-general-deva.png | 141705 | `98dd6a130c4f340f8393a6272f299990` |
| settings-models | settings-models-deva.png | 131480 | `6ecf7e64c87db41f8204cb2166da9338` |

合计 **18/18**，尺寸均为 1280×820（`identify` 实检）。

`delete-confirm` 为缺口 3 修正坐标后重拍的值；旧值（140176 B / `1a0f5cde…`）是在
Archive 项上截到的错误画面，已废弃。

### 1.5 缺页与重试

- 首轮批量（`logs/03-deva-rerun.log`）：`settings-general` 连出两次 435B 灰度存根（Electron 首帧未画完就截），被新守卫判 `FAIL`，整批 `EXIT=1`。
- 单页重拍（`logs/04-settings-general-retry.log`）：`ok settings-general 1280x820 141705B` / `done: 1 页` / `EXIT=0`。
- 最终 18 页齐全，无缺页。

### 1.6 结论

缺口 1 **已修复并验证**。脚本在「只给输出目录」和「指定页名」两种用法下都行为正确；失败不再伪装成成功。18 页原版基线 `out/final-close/deva-rerun/` 已建立，作为缺口 7 的像素对照基准。

---

## 缺口 2：`test_renderer_font_and_line_height_are_stable_across_calls` 红项 —— 断言缺陷，已修正

### 2.1 根因判定：**不是实现回归，是断言锁错了量纲**

失败断言（`app/tests/test_markdown_document.py:523`）：

```python
assert renderer.line_height(28.0, 1.65) != renderer.line_height(14.0, 1.65)
```

`_Renderer.line_height()` 返回的是 **`ProportionalHeight` 百分比**，不是像素。定义（见
`app/src/markdown/document.py:480` 的 docstring 与返回值）：

```python
spacing = _line_spacing(tuple(self.style.sans), max(1, int(round(px))))
return (px * factor) / spacing * 100.0      # 百分比，相对「字体行距」
```

即 `spacing * pct / 100 == px * factor`。字体行距 `QFontMetricsF.lineSpacing()` 与字号成正比
（Noto Sans CJK SC：14px→20.265625，28px→40.53125，正好 2 倍），所以 **14px 与 28px 的百分比
本来就该相同**：

```
px=14  line_height(14,1.65) = 113.98612181958366
px=28  line_height(28,1.65) = 113.98612181958366   ← diff = 0.0
```

断言把「百分比」当成了「像素」，因此要求一个**正确实现**给出两个不同的值——这在字体行距严格
线性（度量按 1/64px 网格取整后恰好等比）的任何机器上都必然失败。测试作者的原意是「不同缓存键
不能撞到同一个值」，但拿百分比当探针选错了对象。

同一断言在**缓存优化之前**（6d8e1ed^ 的旧实现 `QFontMetricsF(self.font(px)).lineSpacing()`）
上也得到相同数值，直接证明与 6d8e1ed 的性能改动无关：

```
px= 12 old=114.05940594059405 new=114.05940594059405 equal=True
px= 14 old=113.98612181958366 new=113.98612181958366 equal=True
px= 28 old=113.98612181958366 new=113.98612181958366 equal=True
px= 56 old=113.96415494314896 new=113.96415494314896 equal=True
px= 96 old=113.95683453237409 new=113.95683453237409 equal=True
```

完整探针：`out/final-close/logs/19-line-height-rootcause.log`。

补充：百分比并非对字号完全无关——1/64px 取整让 12px/56px/96px 的比值偏离整倍，百分比在
113.956～114.086 之间浮动。但这属于度量量化噪声（<0.12%），不能当「键是否分开」的判据。

### 2.2 修法：改断言（实现不动）

缓存键是否齐全，已经有专门用例用 `cache_info()` 精确锁住：

```python
def test_font_and_line_height_caches_are_keyed_on_their_inputs(qapp):
    ...
    assert info.hits == 1 and info.misses == 2   # 14 / 28 必须是两个键
```

那条用例断言的是「28px 真的产生了新的 miss」，与返回值的数值是否相等无关，是正确的锁。
所以本用例改为锁住 `line_height` 的**真实契约**：

```python
    # 百分比必须满足 spacing * pct / 100 == px * factor，且随字号等比放大
    pixels = {}
    for px in (14.0, 28.0, 56.0):
        pct = renderer.line_height(px, 1.65)
        font = QtGui.QFont()
        font.setFamilies(list(BodyStyle().sans))
        font.setPixelSize(int(px))
        spacing = QtGui.QFontMetricsF(font).lineSpacing()
        assert spacing > 0
        got = spacing * pct / 100.0
        assert got == pytest.approx(px * 1.65, rel=1e-9), (px, got)
        pixels[px] = got
    assert pixels[28.0] == pytest.approx(2 * pixels[14.0], rel=1e-9)
    assert pixels[56.0] == pytest.approx(4 * pixels[14.0], rel=1e-9)
    # 倍率是公式里的真实因子：不同倍率不能给出同一个百分比
    assert renderer.line_height(14.0, 1.65) != renderer.line_height(14.0, 2.0)
```

为什么这样改仍能锁住行为：它断言的是「把百分比按定义换算回像素后，必须等于 CSS 期望的
`px * factor`」——这正是渲染器输出格式与浏览器对齐的地方。实现如果把行距算错、把 `factor`
漏掉、或把 `px` 丢掉，都会立刻红。

### 2.3 变异验证（证明确实没放松）

日志：`out/final-close/logs/21-assertion-mutation-check.log`

| 变异 | 结果 |
|---|---|
| 基线（未变异） | `58 passed in 0.32s` |
| `return (px*factor)/spacing*100.0` → `return factor*100.0` | `1 failed, 57 passed`（`33.43828125 != 23.099999999999998`） |
| `_line_spacing` 内 `setPixelSize(pixel_size)` → `setPixelSize(14)` | `1 failed, 57 passed`（`92.4 != 46.199999999999996`） |
| 恢复后 | `git diff --stat app/src/markdown/document.py` 空输出；`58 passed` |

### 2.4 全量 pytest（真实数字）

```bash
cd app && env -u AI_UPPER_HOME -u PYTHONPATH HOME=/tmp/final-pytest-home \
  QT_QPA_PLATFORM=offscreen ../.venv/bin/python -m pytest tests -q
```

```
1260 passed, 5 skipped in 29.07s
```

日志：`out/final-close/logs/20-pytest-full-after.log`

对照修正前（`out/final-close/logs/14-pytest-after.log`，此前记录的最近一次全量）：

```
1 failed, 1259 passed, 5 skipped in 29.24s
```

passed 恰好 +1、failed 归零，与「只修一条断言」的改动范围一致。

> 直接跑时曾出现另一组 3 红（`test_qt_prune` 的 `PYTHONPATH` 断言 + `settings_service` /
> `secrets_vault` 的 `DEVA_HOME` 断言）。原因是外面的 `AI_UPPER_HOME` / `PYTHONPATH` 覆盖了
> 用例自己要验证的变量——`AI_UPPER_HOME` 优先级高于 `DEVA_HOME`，用例设的 `DEVA_HOME` 被压住；
> `PYTHONPATH` 被用例断言为「探测子进程必须原样继承」。按 CI 的方式（在 `app/` 下跑、不预设这两个
> 变量、`HOME` 指到 `/tmp`）即全绿。这是跑法口径问题，不是代码缺陷，也不是被隐藏的失败。

### 2.5 结论

缺口 2 **已修复**：根因是断言把「百分比」当「像素」，属测试缺陷；实现 `document.py` 一字未改
（`git diff` 为空）。全量 pytest 为 `1260 passed, 5 skipped`。

---

## 缺口 3：delete-confirm 基线点错菜单项 —— 已修正并重拍

### 3.1 旧基线错在哪

`scripts/parity/deva_page_shot.sh` 的 `delete-confirm` 用固定坐标点右键菜单：

```bash
rclick 160 90
click 225 205 1.4     # ← 旧值
```

注释当时按「4 项菜单 × 每项 ~31px」估算 Delete 在 y≈205。但**实际是 5 项**
（New chat / Rename / Select / Archive / Delete），Delete 根本不在 205。

旧的 `out/final-close/deva/delete-confirm-deva.png`（140125 B）拍到的就是这一错：
右侧正文被 Archive 动作替换、右上角挂着 `Archived "对比用会話：一条完整回合"  Undo`
的 toast，**完全没有删除确认框**。以此当基线，QML 侧无论怎么画都会得到 ~93% 的
「差异」，属于假差异。

### 3.2 菜单几何：改由渲染进程实测，不再估算

新增只读探针 `scripts/parity/verify_menu_geometry.mjs`：起原版 Deva（带
`--remote-debugging-port`），用 CDP `Input.dispatchMouseEvent` 发真实右键，再用
`Runtime.evaluate` 读 `[role="menu"]` / `[role="menuitem"]` 的 `getBoundingClientRect()`。

```bash
node scripts/parity/verify_menu_geometry.mjs out/final-close/logs/22-menu-geometry.json
```

实测（`out/final-close/logs/22-menu-geometry.json`，视口 1280×820、dpr 1）：

```
menu role=menu  rect = (160, 90, 148, 157)
count = 5
New chat  rect (166, 96, 136, 29)  center (234, 111)
Rename    rect (166, 125, 136, 29) center (234, 140)
Select    rect (166, 154, 136, 29) center (234, 169)
Archive   rect (166, 183, 136, 29) center (234, 198)   ← 旧坐标 y=205 落在这里
Delete    rect (166, 212, 136, 29) center (234, 227)   ← color rgb(229,72,77)
```

y=205 落在 Archive 的 183..212 区间内，与旧图里出现的 Archive toast 完全吻合——
这既解释了旧基线，也证明坐标就是根因。

### 3.3 修复

`scripts/parity/deva_page_shot.sh`：

```diff
   delete-confirm)
     rclick 160 90
-    click 225 205 1.4
+    # 实测：5 个 menuitem，高 29px、从 y=96 起，Delete 中心 (234, 227)
+    click 234 227 1.4
     shot
```

同时修掉 `scripts/parity/deva_dom.mjs:140` 里同一个过期坐标（该文件用与截图脚本
一一对应的点击序列取 DOM 几何，坐标不同步会让 DOM 侧也取到 Archive 状态）。

### 3.4 重拍

```bash
bash scripts/parity/deva_pages_all.sh out/final-close/deva-rerun delete-confirm
# ok   delete-confirm 1280x820 161499B
# done: 1 页 -> out/final-close/deva-rerun
# EXIT=0
```

日志：`out/final-close/logs/23-deva-delete-confirm-fixed.log`

| | 旧基线 `out/final-close/deva/` | 新基线 `out/final-close/deva-rerun/` |
|---|---|---|
| 字节 | 140125 | **161499** |
| md5 | 6642766e98f55915fb938e2736c8a447 | **115b84c3c896b33ce07e59f8a2d2b751** |
| 尺寸 | 1280×820 | 1280×820 |
| 内容 | Archive toast，无确认框 | 删除确认框 |

### 3.5 新图为何可信（点到了什么 / 图里应出现什么）

- **点到了什么**：CDP 实测的 Delete 项中心 (234, 227)，该项 `color: rgb(229,72,77)`
  （danger 色）且 `text: "Delete"`，五个 menuitem 里唯一位于 y 212..241 的一项。
- **图里应出现什么**：居中模态框，标题 `Delete conversation "对比用会话：一条完整回合"?`，
  正文 `This conversation and all its messages will be permanently removed. This
  cannot be undone.`，右下 `Cancel`（次按钮）+ `Delete`（红底危险按钮），背景被压暗。

数值核验（`out/final-close/logs/24-delete-confirm-visual-check.log`）：

```
区域 400x160+440+330 的 mean / stddev
  新图: mean=0.941702 stddev=0.184556   ← 有内容
  旧图: mean=1        stddev=0         ← 纯白

对话框区域命中 danger 色 #E5484D（fuzz 12%）的绿色占比
  新图: 0.924408   ← 红色 Delete 按钮存在
  旧图: 1          ← 一个像素都不命中

新图 Delete 按钮中心像素 (795,468) = #EB7377
compare -metric AE 新旧两图 = 976916 / 1049600 = 93.07% 不同
```

再配合上面直接看过的新图渲染结果（禁用/正常两态一致：标题、正文、Cancel、红色 Delete
四要素齐全），可以确认新基线是真正的删除确认框，而不是又一次点偏。

### 3.6 结论

缺口 3 **已修复并验证**。坐标来自 CDP 实测而非估算，探针脚本保留在
`scripts/parity/verify_menu_geometry.mjs`，以后菜单项再变可以直接复跑核对。
`out/final-close/deva-rerun/delete-confirm-deva.png` 已更新为 161499 B /
`115b84c3c896b33ce07e59f8a2d2b751`，缺口 1 表格中的字节数与 md5 已同步更正。
