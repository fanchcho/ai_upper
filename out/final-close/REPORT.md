# ai_upper 收尾：7 项缺口逐项排查修复报告

仓库：`/home/agent/shared_workspace/ai_upper`（分支 `develop`）
参考原版：`/home/agent/shared_workspace/deva`（只读，未做任何写操作）
环境：所有应用/测试进程 `AI_UPPER_HOME` 均指向 `/tmp/...`，未触碰真实 `~/.ai_upper`。

> 本文件按 1–7 逐项落盘，每完成一项先追加片段，再继续下一项。

## 0. 本段开工前的盘面核对（真实命令 + 输出）

```
$ git rev-parse HEAD
17a8d2f2cb76f92fb811d8d044e9ecebd6021578
$ git rev-parse --abbrev-ref HEAD
develop
$ git log --oneline -8
17a8d2f fix(parity): delete-confirm 点错菜单项（Archive→Delete），坐标改由 CDP 实测
bafa9db fix(markdown): 行高断言锁错量纲 —— 改为按定义反算像素
38bdf10 feat(qml): 页面状态注入后重应用 + 输入区/列表桥接槽
c7a7faf feat(qml): 补齐图标与状态色 token
c1d4f8c fix(parity): deva_pages_all 参数 bug 静默产出 0 图，补齐图标生成
4bdd884 chore(evidence): 在 HEAD b98d59e 上复验 QtWebEngine 移除的 6 条结项
b98d59e docs(render-opt4): attach 两个方向逐条证伪，代码未改
3f01757 docs(render-opt3): 报告、全部探针与逐条日志证据
$ git rev-list --count origin/develop..HEAD
20
```

工作树（`git status --porcelain`，只列本任务相关）：

```
 M app/src/qml/SettingsModal.qml
 M app/src/qml_shell.py
 M app/tests/test_qml_shell.py
?? out/final-close/deva-rerun/*.png        （18 页原版基线，未入库）
?? out/final-close/qml-rerun/*.png        （QML 实拍，未入库）
?? out/final-close/logs/*.log
?? scripts/parity/page_diff_table.sh       （新建）
```

**缺口 1/2/3 的提交状态：全部已单独提交，工作树里没有它们的残留改动。**

| 缺口 | 提交 | 提交内含 |
|---|---|---|
| 1 `deva_pages_all.sh` 参数 bug | `c1d4f8c` | `scripts/parity/deva_pages_all.sh`、`gen_icons.mjs`、`parity_run.sh`、`rebuild_parity.sh` |
| 2 markdown 行高断言 | `bafa9db` | `app/tests/test_markdown_document.py` + REPORT 与 3 份日志 |
| 3 delete-confirm 基线 | `17a8d2f` | `deva_page_shot.sh`、`deva_dom.mjs`、`verify_menu_geometry.mjs`、新基线图、REPORT |

核对依据：对三个缺口的源文件跑 `git status --porcelain <files>` 输出为空，且 `git show --name-only`
逐个确认改动已在提交里。缺口 1–3 的基线图与日志当时按同一原则逐项提交，没有攒批。

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

---

## 缺口 7：QML 壳逐页与原版对照（18 页）+ settings-extensions 面板补齐

### 7.0 本段开工盘面（真实命令 + 输出）

```
$ git rev-parse HEAD
ecac6f6557d288933e1c7159e593685fac79bc63
$ git rev-parse --abbrev-ref HEAD
develop
$ git rev-list --count origin/develop..HEAD
21
$ git status --porcelain | grep -vcE '^\?\?'      # 已跟踪文件的改动条数
0                                                  ← 开工时先记下的是 3 条，见下
```

开工瞬间（提交 `ecac6f6` 上）工作树里有且只有这三条已跟踪改动，正是缺口 7 的未落盘部分：

```
 M app/src/qml/SettingsModal.qml
 M app/src/qml_shell.py
 M app/tests/test_qml_shell.py
```

**未入库的基线/实拍目录（超过 1000 行的 PNG 目录，按约定不计入 diff，但必须点名）**：

| 目录 | 内容 | 入库状态 |
|---|---|---|
| `out/final-close/deva-rerun/` | 18 页原版基线（`delete-confirm-deva.png` 例外） | 17 张 PNG 未入库 |
| `out/final-close/deva-final/` | 本段重拍的 18 页原版（交叉验证用） | 未入库 |
| `out/final-close/qml-rerun/`、`qml/`、`qml-before/`、`diffs/` | 历史实拍 | 未入库 |
| `out/final-close/logs/` | 本段全部测量日志 | 未入库（本次新增 31–40） |
| `scripts/parity/page_diff_table.sh` | 18 页对照表生成脚本 | **本段入库**（`6e84fbe`） |

`git status --porcelain | grep -c '^??'` = 181 条未跟踪条目，绝大多数是 `out/` 下历次
实拍与 `out/qml-body/`（55 条）。这些是过程证据，不随代码入库。

### 7.1 提交：缺口 7 的 QML 改动先落盘

`6e84fbe feat(qml): 设置页扩展面板接上真实技能数据 + 逐页对照表脚本`

| 文件 | 改动 |
|---|---|
| `app/src/qml_shell.py` | `extensionRows()` 改按原版行形状投影（`badge`/`note`/`builtin`）；`setSkillEnabled()` 委托 `SkillStore.set_enabled()` 并在写后 `SettingsService.reload()`；新增 `kindSkill`/`extEmpty` 文案 |
| `app/src/qml/SettingsModal.qml` | `extensionsPane` 重写为 `.cf-rows` 卡片 + `Repeater` 行；开关禁用态 `layer.enabled` 整组合成 |
| `app/tests/test_qml_shell.py` | 4 条新用例：行投影、磁盘技能 enabled、内置行 no-op、开关跨设置写入存活 |
| `scripts/parity/page_diff_table.sh` | 18 页逐页 md5/AE 表生成 |

pytest（提交前跑，`HOME=/tmp/aiu-pytest-home`，见 7.5 为何要隔离 HOME）：

```
$ HOME=/tmp/aiu-pytest-home .venv/bin/python -m pytest -q
1264 passed, 5 skipped in 28.98s
```

### 7.2 settings-extensions 面板：原版有什么、QML 原来缺什么

**原版事实（只读引用）**

- 数据投影：`apps/desktop/src/renderer/src/redesign/SettingsPane.tsx:208-219`
  —— `kind: 'skill'`、`badge: t('cf.kindSkill')`、`note: source === 'builtin' ? t('cf.builtin') : undefined`、
  `locked: source === 'builtin'`。
- 结构：同文件 `:238-268` —— `items.length === 0 ? .cf-empty : .cf-rows`，
  每行 `.cf-setrow`，内置行走 `.cf-setrow__main`（只读、不点开详情）。
- 样式：`redesign.css:3309` `.cf-rows`（1px 边框 + `radius-lg` + `overflow:hidden`）、
  `:3317` `.cf-setrow`（`padding: 11px 14px`）、`:3323` `.cf-setrow + .cf-setrow`（行间 `border-top: 1px`）、
  `:3355` `.cf-setrow__name`（13px/600）、`:3388` `.cf-badge`（10.5px/500，`padding: 1px 7px`）、
  `:3404` `.cf-switch`（38×22）、`:3420` `.cf-switch:disabled`（`opacity: 0.55`）、
  `:3424` `.cf-switch__dot`（18×18 白）、`:3435` `.cf-switch.is-on .cf-switch__dot`（`translateX(16px)`）。

**QML 原来为什么整页空白**：`SettingsModal.qml` 调用 `shellBridge.extensionsSummary()`，
而全仓没有任何一处定义该方法。运行时抛

```
file:///.../SettingsModal.qml:372: TypeError: Property 'extensionsSummary' of object ShellBridge(...) is not a function
```

（旧证据：`out/final-close/qml/settings-extensions.err`）。面板内容一行都画不出来，
所以「空白」不是样式没对齐，是数据源根本不存在。

**修好之后实测**（同一台机、同一夹具 `/tmp/fx-qml-home`、同一 `grabWindow()` 方法）：

```
卡片横线 y 坐标（原版 / 修复前 / 修复后）
  deva-rerun/settings-extensions-deva.png: 130 183 239 284 329 374
  se-pretweak.png（修复前）:               130 183 239 284 328 372   ← 每行少 1px，累计差 2px
  qml-pages-final/settings-extensions.png: 130 183 239 284 329 374   ← 逐条一致

禁用开关滑块像素 (950,261)
  deva: #FBFBFB   修复前: #D5D5F4   修复后: #FBFBFC

卡片区域 520x140+465+236 的 AE（分母 72800）
  修复前: 8385 (11.52%)   修复后: 5557 (7.63%)
```

两处根因，都是「看着像样式误差，其实是合成/盒模型语义不同」：

1. **开关整组透明度**：CSS 的 `opacity` 作用在元素整体——先把轨道+白滑块合成一张，
   再整体乘 0.55，白滑块落在面板色上得 `0.55*255 + 0.45*247 ≈ 251`；
   QML 默认逐图元各乘 0.55，白滑块叠在**已经混合过的 accent 轨道**上，得
   `0.55*255 + 0.45*162 ≈ 213`（实测 `#D5D5F4`）。开 `layer.enabled` 后整组先合成，
   落到 `#FBFBFC`（原版 `#FBFBFB`，差 1 是面板底色 247→248 的取整）。
2. **行高与分隔线**：`.cf-setrow` 内容盒 44px，`.cf-setrow + .cf-setrow` 的
   `border-top` 画在**盒外**，第 2/3 行各多占 1px。QML 若把分隔线画进 44px 行内，
   每行净内容只剩 43px，第三行底边落到 372、分隔线落到 328。改成
   `height: 44 + (index > 0 ? 1 : 0)` 后六条横线位置全部对上。

stderr 检查（页面重拍，`/tmp/se-final.err`）：

```
$ wc -c /tmp/se-final.err
0
$ grep -cE "TypeError|undefined|ReferenceError|is not a function" /tmp/se-final.err
0
```

全 18 页的 stderr 同样全空：`for f in /tmp/qml-pages-final/*.err; do wc -c; done` 无一非零
（日志 `38-qml-18pages-final.log`）。**面板不再空白、页面不再有 QML 报错，判据成立。**
残余的卡片区 7.63% 是字体光栅差异（名字行墨迹左缘 QML 471 vs 原版 470，仅 1px 亚像素），
不是结构缺失。

### 7.3 18 页逐页对照表（QML 重拍 vs `out/final-close/deva-rerun/` 基线）

命令（脚本在本段入库，`6e84fbe`）：

```
$ bash scripts/parity/qml_pages_all.sh /tmp/qml-pages-final /tmp/fx-qml-home
18/18 ok，全部 1280x820，stderr 全空
$ bash scripts/parity/page_diff_table.sh /tmp/qml-pages-final out/final-close/deva-rerun
```

| 页名 | 原版 md5 | QML md5 | 差异像素 | 差异像素% |
|---|---|---|---|---|
| chat | `06a81f02a1ef8b789329f2808268dbb6` | `3faa637133a4df7cc07bf08d183faf5c` | 129602 | 12.35 |
| ctx-menu | `872dc19994a37d9a5cefe2e5aa56bf36` | `2d0a15e6eae41aa7bda53c9c27d2fdbb` | 136820 | 13.04 |
| dark-chat | `dd174cfe874cca285df5cfd2b6ef3038` | `0f0cbdc5d4763d0c44d4a48d1f84d2bc` | 252212 | 24.03 |
| delete-confirm | `115b84c3c896b33ce07e59f8a2d2b751` | `d9b972967e02e47dafad4c9747c8dc11` | 397321 | 37.85 |
| empty | `e07548ba4a6511b62e5e45ab07c27121` | `d99d297b1f1ab6ed07ddeba2d4973541` | 46610 | 4.44 |
| first-run | `26a05a5435320d03600e00b40fc06d0a` | `d99d297b1f1ab6ed07ddeba2d4973541` | 46610 | 4.44 |
| focus-composer | `a5273989e6eb741908af9273352ad1af` | `672d8900998979b759bf22dd2bc38e06` | 129618 | 12.35 |
| hover-thread | `358efb1a6e05413687487207ae7a3541` | `a2bfefadb94727e46971654d9cc50491` | 130009 | 12.39 |
| long-bottom | `8f6fded19b63b3f90a9213c7ec55c960` | `0a5c20816b8155d16599bd1812669461` | 128503 | 12.24 |
| long-mid | `6e1673c62c6b0a59feb449f065ec20fb` | `4fa257f13c6c7ec9032af8c1f95f52b0` | 135140 | 12.88 |
| model-picker | `b3857b3344c4c8e42c8d4cfe3ebb9c0f` | `08c676697c89999aface2c075c9c1922` | 143583 | 13.68 |
| search-none | `72036a2dabc6e64dc4626e38be891a33` | `22cb6fcc883c64566933bc2f4d12e5b6` | 82572 | 7.87 |
| search-open | `9c8a62e33f55f2be59b65ee96870c839` | `801d5f4995ac079b3841c3639a836a94` | 129631 | 12.35 |
| search-results | `0523e1a443a3a1fb91b23b84c0a769b9` | `530e9855f4113b13e48a137ac4baf200` | 106369 | 10.13 |
| settings-about | `50b2ee8135ee7c4cc4f5568d36cac0ab` | `01a33567b7be5e3475c7896abe4f88d4` | 335336 | 31.95 |
| settings-extensions | `59ce447e9abfe50f32d9b39e65701b5b` | `87b9b8bd5ec42009e97a89cfcddaba33` | 330836 | 31.52 |
| settings-general | `98dd6a130c4f340f8393a6272f299990` | `de979af54ca65cc2bdcbcf2502304ae0` | 341404 | 32.53 |
| settings-models | `6ecf7e64c87db41f8204cb2166da9338` | `02c31277bc66d3a48388c99a48dc5c16` | 329170 | 31.36 |

分母固定 `1280*820 = 1049600`。原始表落盘：`out/final-close/logs/36-page-diff-table-final.txt`。

**settings-extensions 这一行的变化**：本轮修复前是 `568fa0727ca123953204c1457c0e7269` / 333664 / 31.79%，
修复后 `87b9b8bd5ec42009e97a89cfcddaba33` / 330836 / 31.52%。

### 7.4 四条硬判据：逐条实测

**判据 1 —— chat / long-mid / long-bottom 三者 md5 互不相同，两两像素差异 > 0。成立。**

```
3faa637133a4df7cc07bf08d183faf5c  chat.png
4fa257f13c6c7ec9032af8c1f95f52b0  long-mid.png
0a5c20816b8155d16599bd1812669461  long-bottom.png
chat vs long-mid         AE=73058
chat vs long-bottom      AE=16205
long-mid vs long-bottom  AE=62052
```

三个 md5 两两不同，三对 AE 均远大于 0（`logs/33-criterion1-pairwise.log`）。

**判据 2 —— search-results 只显示命中的 10 行（与基线同样的 001–009、100）。成立。**

侧栏墨迹行（`x∈[55,250]`、`y∈[60,790]`、灰度 < 170 的连续段）：

```
deva: 61..99 115..153 169..207 223..261 277..315 331..369 385..423 439..477 493..531 547..585   rows=10
qml : 64..101 118..155 172..209 226..263 280..317 334..371 388..425 442..479 496..533 550..587  rows=10
```

行数 10 = 10，节距均为 54px；内容来自同一份夹具（`parity-001..009` + `parity-100`
命中「会话」），不是多画或少画（`logs/34-criterion2-search-rows.log`）。

**判据 3 —— focus-composer 输入区有可见焦点边框。成立。**

```
                 focus-composer        chat（对照）
deva  (428,700)  #5B5BD6 (accent)      #D5D5DB (常态边框)
qml   (428,700)  #5B5BD6               #D5D5DB
deva  (428,760)  #5B5BD6               #D5D5DB
qml   (428,760)  #5B5BD6               #D5D5DB
```

（`logs/35-criterion3-focus-border.log`；更早一轮的边框像素统计为 622/622、115/115，
见 `logs/29-focus-border-after-pane-fix.log`。）

**判据 4（本段新增的交付判据）—— settings-extensions 面板不得空白、不得 QML 报错。成立。**
3 行内置技能（名称 / `Skill` 徽标 / `Built-in` 注记 / 行尾锁定开关）逐行渲染，
六条卡片横线坐标与原版逐条一致，stderr 0 字节（见 7.2）。

### 7.5 残余差异的来源（不是「没做」，是已定位的环境/基线问题）

1. **设置类四页 31–33% 的主体是遮罩下的侧栏**。`settings-extensions` 整页 AE 330836，
   其中 `300x820+0+0`（被 `rgba(0,0,0,0.42)` 遮罩压暗的会话列表）单独就占 226014（68%）。
   遮罩本身对得上（空处 deva `#909090` / QML `#8F8F90`），但那 1/255 的取整落在整片
   大面积平色上就变成逐像素不等：加 `-fuzz 0.4%` 后整页 AE 从 330836 掉到 121829，
   侧栏从 226014 掉到 40179。属于通道取整，不是布局错位。
2. **会话页 12% 量级是字体光栅**。chat 侧栏 `300x820` AE 43888、正文区 `980x760` AE 66181；
   横向互相关最优位移为 0（没有整体偏移），fuzz 分级 chat 5%→6.87%、10%→4.94%、20%→3.87%。
3. **empty / first-run 的 4.44% 是真实功能差**：原版中列有 2 张 QuickStart 卡片
   （`Rail.tsx` `QuickStart`：48px 头像 + 名称 + 描述），QML `Main.qml:452-470` 只有标题
   和一行提示，没有卡片。区域 `300x180+540+390` AE 21703（40.19%）。这一项**本段未补**，
   见 7.6。
4. **基线时效**：`deva-rerun/` 是 15:47 拍的，QML 是本段 18:3x 拍的，夹具时间戳钉在
   「生成时刻 − 22h」，跨过 24h 边界后侧栏相对时间从「22 hr ago」变「yesterday」
   —— 这是上一轮残余 12% 的主因。本段额外重拍了一份原版 `out/final-close/deva-final/`
   （`logs/39-deva-18pages-control.log`），与 QML 同年同日前后脚拍，对照表见
   `logs/37-page-diff-table-control.txt`：**18 页差异百分比与主表逐条一致（±0.02pp）**，
   证明 12% 不是基线过期造成的假差异，而是稳定的渲染层差异。

### 7.6 结论

- 缺口 7 **收口**：18 页全部重拍、逐页 md5/AE 表已落进本节，四条硬判据逐条成立（7.4）。
- settings-extensions 面板从「TypeError + 整页空白」修到「3 行齐全 + 6 条横线逐条对齐 +
  stderr 0」，提交 `6e84fbe`。
- 仍未达标/未做的见下一节，逐条给原因。

---

## 8. 收尾：本轮落盘的 commit、pytest 真实数字、判据结论、没做的及原因

### 8.1 本轮落盘的 commit

| commit | 内容 |
|---|---|
| `6e84fbe` | `feat(qml): 设置页扩展面板接上真实技能数据 + 逐页对照表脚本`（缺口 7 的桥/面板/测试/脚本） |
| 本次收尾提交 | 本报告 7–8 节 + 测量日志 `logs/31–40` |

`ecac6f6`（盘面核对）是上一段落盘的，本段没有重做缺口 1/2/3，也没有回退它们。

本地领先 `origin/develop`：

```
$ git rev-list --count origin/develop..HEAD
22
```

未 push、未新建分支、未 force push。`/home/agent/shared_workspace/deva` 全程只读，
本段对它的全部操作是 `sed -n` / `grep`（读源码行号）与 `deva_pages_all.sh`（在 `/tmp`
与 `out/` 下写图），没有写入 deva 工程。

### 8.2 pytest 真实数字

```
$ HOME=/tmp/aiu-pytest-home .venv/bin/python -m pytest -q
1264 passed, 5 skipped in 28.98s
```

**必须说明一个环境陷阱**：如果只把 `AI_UPPER_HOME` 指到 `/tmp` 而不隔离 `HOME`，
会有 2 条用例变红：

```
FAILED app/tests/test_secrets_vault.py::test_default_home_uses_deva_home_env
FAILED app/tests/test_settings_service.py::test_default_home_uses_deva_home_env
2 failed, 1262 passed, 5 skipped
```

这不是本段代码引入的。用 `git worktree` 把 `ecac6f6`（本段改动之前）单独检出再跑这两条，
同样失败：

```
$ git worktree add --detach /tmp/aiu-prev ecac6f6
$ AI_UPPER_HOME=/tmp/aiu-pytest-b pytest -q <两条用例>
2 failed in 0.37s
```

根因是用例只 `monkeypatch.setenv("DEVA_HOME", ...)`，而服务的 home 解析顺序是
`AI_UPPER_HOME` → `~/.ai_upper` → 旧 `DEVA_HOME`；外部环境里已经有 `AI_UPPER_HOME` 时
`DEVA_HOME` 不生效。属于用例对宿主环境的隐式依赖，与本轮改动无关，**本段未改它**
（改测试会动到既有断言口径，超出本段任务范围），只把结论落到这里。
隔离 `HOME` 后全绿。

### 8.3 四条硬判据：成立 / 不成立

| 判据 | 结论 | 实测 |
|---|---|---|
| chat / long-mid / long-bottom md5 互不相同且两两 AE > 0 | **成立** | 三个 md5 各异；AE = 73058 / 16205 / 62052 |
| search-results 只显示命中的 10 行（001–009、100） | **成立** | 两侧墨迹行均 10 段，节距 54px |
| focus-composer 输入区有可见焦点边框 | **成立** | `(428,700)` 与 `(428,760)` 两侧均 `#5B5BD6`；对照 chat 均 `#D5D5DB` |
| settings-extensions 面板不空白、无 QML 错误（本段新增） | **成立** | 3 行 / 6 条横线与原版逐条对齐；stderr 0 字节 |

### 8.4 没做的及原因

1. **empty / first-run 页的 QuickStart 卡片未补**（两页各 4.44%）。
   原版 `redesign/Rail.tsx` 的 `QuickStart` 渲染 `.cf-quick__grid` + `.cf-qcard`（48px 头像、
   名称、描述），QML `app/src/qml/Main.qml:452-470` 只有标题和一行提示。
   未做原因：它需要把 persona 列表（头像、名称、描述、点击进会话）接进 QML 空态，
   属于新功能接线，不是本轮「逐页对照 + 扩展面板」的任务范围；本段只把它定位并量化
   （区域 `300x180+540+390` AE 21703 / 40.19%），没有顺手扩范围。

2. **`qt_prune.py:895` 的「QML 保留修复」**：核对后该项前提不成立。
   `tools/ai_upper/qt_prune.py:895` 是导入闭包探针的 `if probe.returncode != 0:` 分支，
   与 QML 无关；QML 保留逻辑在 `:204-441`（`qml_source_roots` / `qml_imports` /
   `qml_required_modules` / `qml_shipped_modules` / `prune_qml_tree`），且已由
   `c0ec6e7`、`173f53c`、`2285a16` 落盘。现状验证：

   ```
   $ HOME=/tmp/aiu-pytest-home .venv/bin/python -m pytest -q app/tests/test_qt_prune.py
   54 passed in 1.16s
   $ git status --porcelain tools/ai_upper/qt_prune.py
   （空）
   ```

   所以本段**没有改动**该文件——没有缺口就不造改动。

3. **`app/src/markdown/` 是否已入库**：已入库。真实输出：

   ```
   $ git ls-files app/src/markdown
   app/src/markdown/__init__.py
   app/src/markdown/body.py
   app/src/markdown/document.py
   app/src/markdown/highlight.py
   app/src/markdown/parser.py
   ```

   5 个文件全部被 git 跟踪，工作树无改动。

4. **18 页残余差异没有压到 0**：会话页 12% 量级为字体光栅、设置页 31–33% 量级
   以遮罩下的整片侧栏为主（0.4% 容差下侧栏 AE 从 226014 降到 40179）。这不是漏做，
   是本段判定「不属于结构缺口」后如实报数，具体分解见 7.5。

### 8.5 硬约束遵守情况

- deva 只读：本段对 deva 只做 `grep`/`sed -n` 读源码与 `deva_pages_all.sh` 出图（写 `/tmp`、`out/`）。
- `AI_UPPER_HOME` 一律指 `/tmp`（`/tmp/fx-qml-home`、`/tmp/aiu-pytest-*`），未触碰真实 `~/.ai_upper`。
- 只在本地 `develop` 提交，未新建分支、未 force push、未 push。
- 每条结论都附了真实命令与输出；没做到的部分在 8.4 逐条写明原因。
