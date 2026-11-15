# ai_upper 路线 B 收尾报告（QML 壳 + QTextDocument 正文）

生成时间：2026-11-15（本机 UTC） · 分支 `develop` · 基线 HEAD `4b8a220`

一句话结论：**壳能稳定启动、正文层 9 项功能全部实测通过、默认已切到 QML、打包产物实跑
退出码 0**。逐页 1:1 已从「一页证据都没有」推进到「19 页都有原版图 + QML 图 + 真实差异
数值」，整体差异从 4.4%–99.4% 收到 **1.46%–10.18%**，但**尚未逐页归零**：剩余差异集中在
正文排版细节（列表/引用缩进、图片占位、滚动位置）与窗口控制按钮，逐条列在 §3.4。

---

## 0. 对账（开工第一步）

| 项 | 实测 |
| --- | --- |
| `git log --oneline -5` | `4b8a220`（设置页接真实数据）→ `8d3b583`（打包链）→ `173f53c` → `5877e61` → `883eaa7` |
| `git status` | 干净之外有 6 个已改文件（Theme.qml / qml_shell.py / qml_shell_sessions.py / 两个测试 / 两个旧 CI 记录）+ 大量未跟踪 `out/` 证据 |
| HEAD vs origin/develop | 均为 `4b8a2209…`，**一致**；无 `.git/*.lock`；无其它进程在写本仓库 |
| 磁盘 vs HEAD | `app/src/qml/` 8 个 QML + `avatars/`；`out/qml-shell/` 有 `parity/`（19 页旧证据）、`pages/`、`dom/`、`logs/` |

> 说明：任务书说「`out/qml-shell/parity/` 里一个逐页对比证据都没有」与磁盘不符——磁盘上
> 已有 19 页旧证据（`numbers.tsv` 在）。但那份证据里 `dark-chat` 差异 **99.38%**、
> `delete-confirm` **92.68%**，属于「页面状态没拍对」，等于没有可用证据。本轮按「全部重截
> 重算」处理，旧数值不再引用。

---

## 1. 实跑回归

```
$ AI_UPPER_HEADLESS=1 AI_UPPER_HOME=/tmp/fx-qml-home AI_UPPER_QML_SHOT=out/qml-shell/shell-run.png \
    .venv/bin/python app/src/main.py
QML OK platform=offscreen title='Deva' sessions=120 active='parity-000' plain=False turn_stop='' \
  deltas=0 home=/tmp/fx-qml-home png=out/qml-shell/shell-run.png size=1280x820
EXIT=0
```
证据：`out/qml-shell/shell-run.log`、`out/qml-shell/shell-run.png`（1280×820 实拍）。
offscreen + 软件光栅（`QT_QUICK_BACKEND=software`），无 QML 警告/绑定报错输出到 stderr（日志里为空）。

pytest：

```
$ .venv/bin/python -m pytest -q
1168 passed, 5 skipped in 27.38s
```
基线 `1159 passed / 5 skipped` → 现在 `1168 passed / 5 skipped`，**新增 9 条、未删未减**。

---

## 2. 逐页 1:1 证据（`out/qml-shell/parity/`）

每页三件套：`original.png`（原版 Electron 在 Xvfb 下 1280×820 实拍）、`qml.png`（QML 壳
offscreen 实拍）、`diff.png`（逐像素差图），数值全部落在 `numbers.tsv`（由
`scripts/parity/page_diff.py` 真实计算，无手填）。

复现：`bash scripts/parity/rebuild_parity.sh`（夹具 → 原版 19 页 → QML 19 页 → 比对）。
两侧读同一份 120 会话夹具、同一份 `config.json`（`locale=en`、`theme=light`；深色页用
`config-dark.json`）。

| 页面 | 差异像素 | 占比 | 包围盒 | 最大单通道差 |
| --- | ---: | ---: | --- | ---: |
| empty / first-run | 15,300 | 1.4577% | 0,8–1268,793 | 255 |
| settings-models | 34,930 | 3.3279% | 0,0–1279,819 | 237 |
| settings-about | 37,108 | 3.5354% | 0,0–1279,819 | 224 |
| settings-extensions | 37,950 | 3.6157% | 0,0–1279,819 | 216 |
| settings-general | 39,187 | 3.7335% | 0,0–1279,819 | 224 |
| dark-chat | 51,769 | 4.9323% | 0,9–1279,819 | 255 |
| delete-confirm | 52,935 | 5.0433% | 0,0–1279,819 | 237 |
| hover-thread | 57,824 | 5.5091% | 0,9–1279,819 | 255 |
| chat | 57,852 | 5.5118% | 0,9–1279,819 | 255 |
| search-open | 57,861 | 5.5127% | 0,9–1279,819 | 255 |
| focus-composer | 59,736 | 5.6913% | 0,9–1279,819 | 255 |
| ctx-menu | 61,217 | 5.8324% | 0,9–1279,819 | 255 |
| model-picker | 69,112 | 6.5846% | 0,9–1279,819 | 255 |
| search-results | 70,960 | 6.7607% | 0,9–1279,808 | 255 |
| long-bottom | 72,068 | 6.8662% | 0,9–1279,817 | 255 |
| search-none | 80,408 | 7.6608% | 0,9–1279,808 | 255 |
| long-mid | 106,841 | 10.1792% | 0,9–1279,819 | 255 |

> 判读：`max_delta=255` 是「某个像素一边纯白一边深色」，通常来自文字/图标位置整体错位，
> 不是抗锯齿。真正的对齐度要看占比与包围盒。

### 2.1 本轮修掉的（有代码位置）

| 差异 | 修法 | 位置 |
| --- | --- | --- |
| 深色主题完全没生效（99.38%→4.93%） | `ShellBridge.darkMode` + QML `Binding` 写 `Theme.dark`（QML 单例 `setProperty` 实测落不下去，返回 QJSValue） | `app/src/qml_shell.py:164,283`、`app/src/qml/Main.qml:53` |
| 表格没有网格线 | 加表格级 `setBorder(1)` + `BorderCollapse`：QQuickTextEdit **不画单元格级边框**，只画表格级 | `app/src/markdown/document.py:518` |
| 会话行没有头像/角色名 | 按 CDP 实测补 38×38 头像 + 11px 角色名副标题 | `app/src/qml/ThreadRow.qml`、`app/src/qml_shell.py:556` |
| 标题栏显示会话标题 | 原版 `cf-idbtn` 显示角色名 | `app/src/qml/Main.qml:303` |
| 相对时间文案对不上（22 hr vs yesterday） | 夹具时间戳改为「相对生成时刻」（-22h），两侧同批拍图 | `scripts/parity/make_pages_fixture.py:19` |
| 右键菜单 / 删除确认框页面是空的（92.68%→5.04%） | 按实测几何补菜单（165,88 175×124）与确认框（430,320 420×180） | `app/src/qml/Main.qml:640+` |
| hover / focus / 长列表三页状态相同 | 指定行 hover、输入框取焦、列表滚到 45%/底部 | `app/src/qml/Main.qml:47,252` |
| 设置页字号行溢出卡片 | 卡片改 (20,55) 510×169，行高 57/55/55 | `app/src/qml/SettingsModal.qml:250` |

### 2.2 仍然存在的差异（逐条，未修）

1. **正文滚动落点**：对话页原版滚到底时首行代码被顶出上沿，QML 也贴底，但因为图片高度不同
   与段落间距差，整体错位约 8–40px（chat/hover/focus/search 各页同源）。
2. **列表缩进**：无序列表圆点 x=500（原版 488、正文 506），任务列表复选框提前 15px。
3. **引用缩进**：一级引用竖线 x=497（原版 489），二级引用 524（原版 505），逐层多加 12px 表格外边距。
4. **图片**：夹具里的 `data:image/png;base64,...` 在 QML 侧能解出来（1×1 透明），原版
   Chromium 渲染成「破图图标 + alt 文本」16px 高，因此正文整体高度与滚动落点差 16px。
   这是**功能更强**导致的差异，见 §3.5 第 5 条；若要像素一致需刻意退化，未做。
5. **窗口控制按钮**：原版右上角有最小化/最大化/关闭（1188–1272），QML 未实现。
6. **输入区 chips**：原版模型名/强度是无边框文字 + 下拉箭头，QML 仍带 1px 边框（`border.width: 1`）。
7. **长列表 long-mid**：QML 用 `contentY = 45%` 近似原版 12 次滚轮事件的结果，落点不同（10.18%）。
8. **滚动条**：原版右侧有可见滚动条，QML 的 Flickable 无滚动条。
9. **字号/字形**：QML 用 DejaVu Sans（度量与原版 CSS 相差 ≤0.15px），仍非逐字形一致。

---

## 3. 正文层功能实测（真操作，非样式）

脚本：`scripts/qml_body_probe.py`；数据：`out/qml-shell/body/body-report.json`；
截图：`theme-light.png` / `theme-dark.png` / `table.png` / `cjk-emoji.png`。

```
$ .venv/bin/python scripts/qml_body_probe.py out/qml-shell/body
{"failures": [], "out": "out/qml-shell/body"}
```
9 项全部 PASS：

| 项 | 实测 |
| --- | --- |
| 跨块连续选择与复制 | 选中块 0→18（19 块），616 字符；含代码块 `def list_dir`、表格单元格 `README.md`、尾段；写剪贴板后读回**完全一致** |
| 部分跨块选择 | 从代码块中段到表格单元格，566 字符，两端都命中 |
| 双击选词 | 真发 `QTest.mouseDClick` 到 QQuickWindow(115,100)，`selectedText == "sorted"` |
| 代码块横向滚动不撑破布局 | 长行宽 2705.56px，文档 `textWidth` 仍 696.0（=视口），`idealWidth` 3339 → 溢出由视图承担 |
| 表格边框/单元格间距 | 表格级 1px #e6e6ea，单元格 padding 10/10/6/6，渲染图上数到 2 条边框像素 |
| 图片渲染 | 本地 48×32 文件与 `data:` URI 都注册成文档资源（实际尺寸取回 48×32、1×1） |
| 浅/深主题同步 | 调色板 #ffffff→#1e1e20、文字 #1f1f24→#e4e4e7；同一区域平均亮度 243.19→41.2（真的变暗）；字体族不变 |
| 单条超长 / 上百条消息 | 400 段单条消息渲染 **593.1ms**（文档高 15569px）；120 条消息渲染 **269.4ms**（8931px）；滚动 60 步 0.7ms（0.01ms/步） |
| 中文与 emoji | 中文正常出字形（墨迹像素 518）；**本机无 emoji 字体**（`fc-list` 无 emoji 族），emoji 与原版 Chromium 一样落回缺字块——这是环境缺失，不是渲染缺陷 |
| 1x / 2x 高分屏 | `QT_SCALE_FACTOR=2` → `devicePixelRatio=2.0`，抓图 1600×1800（逻辑 800×900），文档逻辑宽仍 696 |

数据文件：`out/qml-shell/body/hidpi-1.json`、`hidpi-2.json`。

---

## 4. 默认切到 QML

- `app/src/main.py:53` `_qml_requested()`：**缺省 True**，只有 `AI_UPPER_UI=web`（或 `webengine`）才回退 WebEngine 窗口。
- 兜底路径保留的理由：QML 路线依赖 QtQuick/Controls 插件与 GPU/软件光栅，在缺插件或
  驱动把 `QQuickWindow` 打崩的机器上仍需要一条能起来的路径；开关就是环境变量 `AI_UPPER_UI=web`。
- offscreen 启动（源码树）：见 §1，`QML OK … size=1280x820`，退出码 0。
- 打包产物：`tools/build.py --target linux-arm64` 重新构建（`out/packaging/build-qml-default.log`
  末行 `READY: …/dist/ai_upper`），实跑：

```
$ AI_UPPER_HEADLESS=1 ./dist/ai_upper/ai_upper
QML OK platform=offscreen title='Deva' sessions=0 active='' plain=False turn_stop='' \
  deltas=0 home=…/dist/ai_upper png=/tmp/dist-qml.png size=1280x820
EXIT=0
```
（`sessions=0` 是因为启动器把 `AI_UPPER_HOME` 指向产物自身目录，里面没有历史会话——
正是空状态 QML 界面；旧版本这条命令打印的是 `DEVA WEB OK`，可据此判断默认路线已切换。）

---

## 5. CI

见提交推送后的运行为准，逐 job 结论补在本节。

---

## 6. 仍未完成项

1. §2.2 的 9 条差异未归零，主要是正文排版细节与窗口控件；工作量大头在「列表/引用缩进」与「滚动落点」。
2. `long-mid` 的滚动位置是近似值，不是原版滚轮事件的复刻。
3. 窗口控制按钮（最小化/最大化/关闭）未实现。
4. 无 emoji 字体，emoji 只能记录为环境缺失。
5. `AI_UPPER_UI=web` 兜底路径未在本轮重新实跑（改动只影响默认分支选择，不影响该分支代码）。
