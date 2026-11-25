# ai_upper 剩余未完成项收口报告（A–J）

仓库：`/home/agent/shared_workspace/ai_upper`（实体目录，分支 `develop`）
参考原版：`/home/agent/shared_workspace/deva`（**只读**，本轮未写入任何文件）
开工 HEAD：`4a1a02328250a7b1234a86c27558fd2afccae7d8`（= 开工时 `origin/develop`）
报告版本戳：开工 `4a1a023` + 本轮提交（见 §3，最后一条就是本报告的提交；交付时 `git rev-parse HEAD` 即它）
运行隔离：所有应用/测试进程的 `AI_UPPER_HOME` 均指向 `/tmp/...`，未触碰真实 `~/.ai_upper`。

---

## 0. 第 0 步：只读对账（先贴命令与输出）

```
$ git -C /home/agent/shared_workspace/ai_upper log --oneline -12
4a1a023 test: 重拍18页并记录硬判据与真实差异 / verify full page parity
8266faa test: 记录 CI 排队状态及独立进程高分屏对照 / record CI and HiDPI evidence
0ebe4f0 fix(qml): 对齐侧栏标题行盒并记录模态残差 / align thread line boxes
223274c fix: 打包 emoji fallback 修复缺字形 / bundle emoji fallback font
b752b0e fix(markdown): 对齐列表引用组合间距并记录表格残差 / align composed block spacing
0617c04 docs: 补齐 A/B/C 证据入口 / restore closeout report index
71ff27b test: 仅扫描受控源码并验证旧名变异 / scope branding scan to tracked paths
25883ce test: 记录最终代码全量回归及环境归因 / record final regression evidence
c141d0d fix(markdown): 复用原生断图图标 / render native broken-image placeholder
88b2de2 fix(markdown): 代码块独立横向滚动 / scroll overflowing code independently
7f304e9 test(parity): 复核旧结构缺口并重算D3归因 / verify structural fixes and D3 residuals
8455309 docs(test): 汇总并入项实测和开放缺口 / summarize merged review evidence and gaps

$ git status --porcelain
（开工时：只有 out/ 下历史证据与 .tmp/ 的 untracked；tracked 修改 0 条）
$ git rev-parse HEAD
4a1a02328250a7b1234a86c27558fd2afccae7d8
$ git ls-remote origin refs/heads/develop
4a1a02328250a7b1234a86c27558fd2afccae7d8	refs/heads/develop
```

开工时工作区里没有半成品源码改动：`git status --porcelain --untracked-files=no` 为空。
`out/final-close/REPORT.md` 的 §10 停在 `610dcbd` 且写着「26 条未 push」，
`out/TEST-REPORT.md` 最后一节停在 `0ebe4f0`（`ab66967` 起算），两者都落后于 HEAD
`4a1a023`；`origin/develop` 实际已等于 HEAD。**旧报告的版本戳与 push 结论均不可信，本轮以磁盘与
`git ls-remote` 为准。**

报告小节落盘数字（对账用，均为当时值）：

| 报告 | 版本戳 | 最后落盘的关键数字 |
|---|---|---|
| `out/final-close/REPORT.md` | `610dcbd`（§10；正文缺口 1–3 在 `17a8d2f` 前后） | 18 页表 md5/AE；旧 delete-confirm 140125B→161499B / `115b84c3…`；pytest 1267 passed / 5 skipped |
| `out/TEST-REPORT.md` | 最后一节 `0ebe4f0`（起点 `ab66967`） | 18 页差异 9.62%–35.88%；四判据成立；1360 passed / 5 skipped；CI 停在 0617c04 failure |
| `out/latest-parity/REPORT.md` | D 轮（2026-11-22/23，deva `61f6a35`） | 18 页 md5/差异表；四判据成立；设置内部残差未闭环 |

---

## 1. 判定表（A–J，开工时 → 本轮结果）

| 项 | 开工时判定 | 依据（commit / 证据） | 本轮动作 | 最终结论 |
|---|---|---|---|---|
| A | 已完成（bafa9db） | `bafa9db`；`out/final-close/logs/19-line-height-rootcause.log`、`21-assertion-mutation-check.log` | 复跑命名测试 1 passed；全量 pytest 发现 1 条字体回退红项，另修（`579f40e`） | 已完成 |
| B | 已完成（17a8d2f） | `17a8d2f`；`deva-rerun/delete-confirm-deva.png` 161499B / `115b84c3…` | 复核坐标与截图（真删除确认框） | 已完成 |
| C | 已完成（9c09128 + 4a1a023），但证据版本旧 | `9c09128`、`4a1a023` | 本轮两端重拍、重算整表、四判据复检 | 已完成 |
| D | 未完成：final-pass 仅 QML 16/18、deva 5/18 有 rc | `out/final-parity/final-pass/**/*.rc` | 两端各 18/18 全量复采 | 已完成 |
| E | 未完成：TEST-REPORT 版本戳停在 `0ebe4f0` | `out/TEST-REPORT.md` 尾节 | 写入 4a1a023+579f40e 的逐页数字与四判据 | 已完成 |
| F | 未做：未查 HEAD `4a1a023` 的 CI | — | 查 GitHub API：run 45217331247 `completed/failure`，逐 job 已记录 | 已完成（真实终态为红） |
| G | 已完成（7be5e48 等） | `7be5e48`；`test_qml_settings_models.py` 47 passed | 逐项复核 deva 源码值与 QML 实测值 | 已完成 |
| H | 已完成（cddf2fb 后续） | `cddf2fb`；`test_qml_context_menu.py` 3 passed | 复核第 5 项 Delete / 红色 / 可点可关 | 已完成 |
| I | 已完成（窗口按钮 + 滚动条） | `test_qml_window_controls.py`、`test_qml_scrollbars.py` 4 passed | 实测 deva/QML thumb 行为并记录 | 已完成 |
| J | 未完成 | 旧 `out/TEST-REPORT.md` §第3项 | 两种修法实测均无效，记录未达标数值与原因 | 未达标（未修） |

---

## 2. 逐项结论

### A. pytest 红项：`test_renderer_font_and_line_height_are_stable_across_calls`

**判定：不是实现回归，是旧断言锁错量纲；已在 `bafa9db` 修正，本轮复跑通过。**

- 旧断言把 `line_height()` 返回的**百分比**当成像素用：`pct(28) != pct(14)`。
  `ProportionalHeight` 是相对字体行距的百分比，字体行距与字号成正比，14px 与 28px 的百分比
  本来就该几乎相同（实测均 113.986…，`out/final-close/logs/19-line-height-rootcause.log`）。
- 现断言（`app/tests/test_markdown_document.py:551-576`）按定义反算：
  `spacing * pct / 100 == px * factor`（14/28/56 三档），再断言像素随字号 2×、4× 单调；
  缓存键的覆盖另由 `test_font_and_line_height_caches_are_keyed_on_their_inputs` 用
  `cache_info()` 锁住。仍然锁住「缓存键完整 + 行高公式正确」这两个行为，不依赖字体回退。
- 本轮实测：`1 passed in 0.27s`，rc=0（`out/final-closeout/logs/pytest-A-named.log` / `.rc`）。

**全量 pytest 附带发现的一条真红（本轮修掉）：**
`app/tests/test_qml_broken_image.py::test_broken_image_paints_icon_and_keeps_alt_inline`
断言 alt 文本宽度恰好 `42 ± 1/16`（3 个 CJK 字 × 14px）。这是字体回退依赖：

| 环境 | 实测 alt 宽度 | 结果 |
|---|---:|---|
| 本机 + Noto Sans CJK | 41.953125 | 旧断言通过 |
| 本机空 fontconfig（模拟无 CJK） | 45.0 | 旧断言红 |
| GitHub runner（CI 注解原文） | 25.171875 | 8 个 native-integration job 全红 |

CI 注解（`out/final-closeout/ci/annotations-linux.json`）原文：
`FAILED tests/test_qml_broken_image.py::... - assert 25.171875 == 42 ± 0.0625`。
修法（`579f40e`）：用 `QFontMetricsF(document.defaultFont()).horizontalAdvance("示意图")`
现场量同一串文字，断言 alt 宽度等于该值（abs=1/16），仍锁住「16px 图标槽 + alt 完整内联」。
两种字体环境均复测通过（`A-broken-image-with-cjk-fonts.log` = 41.953125；
`A-broken-image-no-cjk-fonts.log` = 45.0）。

**全量 pytest（本报告最终代码）：1360 passed, 5 skipped, 0 failed, rc=0**（212.60s），
原始日志 `out/final-closeout/logs/pytest-full-final.log`，退出码 `pytest-full-final.rc`。

### B. delete-confirm 基线坐标

**判定：已完成（`17a8d2f`），现脚本坐标正确，截图确实是删除确认框。**

- 现脚本 `scripts/parity/deva_page_shot.sh` 的 `delete-confirm` 分支点 `(234, 227)`；
  注释里写明旧坐标 `(225,205)` 落在 Archive 项（183..212）上，截到的是「Archived … Undo」。
- 依据 `out/final-close/logs/22-menu-geometry.json`：menu rect `(160,90,148,157)`，5 个
  menuitem 高 29、从 y=96 起，Delete 中心 `(234,227)`（y=226.5 四舍五入）。
- 本轮复核实拍：`out/final-closeout/deva/delete-confirm-deva.png`（160097 B，
  md5 `be692372160f073c87faa9a2f645b8d4`）显示的是
  `Delete conversation “对比用会话：一条完整回合”?` 确认框（Cancel / 红色 Delete），不是 toast。
- 已入库的基线 `out/final-close/deva-rerun/delete-confirm-deva.png`：161499 B，
  md5 `115b84c3c896b33ce07e59f8a2d2b751`（`out/final-close/REPORT.md:372-373` 同值）。
  旧基线错因与新旧对比见 `REPORT.md` 缺口 3 节（旧 140125 B / `6642766e…` 为 Archive toast）。

### C. 缺口 7：18 页重拍与逐页比对

**判定：已完成。两端各重拍 18 页（QML 18/18 rc=0、deva 18/18 rc=0），整表如下。**

命令：

```sh
bash scripts/parity/deva_pages_all.sh out/final-closeout/deva   # rc=0, 18 页
bash scripts/parity/qml_pages_all.sh out/final-closeout/qml /tmp/fx-qml-home  # rc=0, 18 页
python3 -I scripts/parity/page_diff18.py out/final-closeout/deva out/final-closeout/qml  # rc=0
```

| 页名 | 原版 md5 | QML md5 | 差异像素 | 差异% |
|---|---|---|---:|---:|
| chat | `9c4dc3818ebfe7f924ed0e8fdf5f13aa` | `f2be6eb13555c9169ddac03b00b12dbd` | 101645 | 9.68% |
| empty | `a844e59207651c1d5cc168679e6bd180` | `e56462d7a538be35dae1b166403f4784` | 13231 | 1.26% |
| first-run | `caacdfd6b9fcb410c2353634ce4571e5` | `e56462d7a538be35dae1b166403f4784` | 13231 | 1.26% |
| search-open | `0e5081333e568b1f8dc9cf738b2e023d` | `c7d6a0afee0b0b2607da766a66ebeb83` | 101674 | 9.69% |
| search-results | `6060a072aa967d1695a188ea8938057c` | `8ae395397ec65c3168b6d3ce125cd588` | 97969 | 9.33% |
| search-none | `f3ce8014ddd3e090afac62ca206fd3be` | `91453b4433c64e607308cf8bc7c34f19` | 80236 | 7.64% |
| ctx-menu | `775281f1454332483a79a778d7caf287` | `2f781b594357448527ba567a85da7a15` | 112022 | 10.67% |
| delete-confirm | `be692372160f073c87faa9a2f645b8d4` | `7d9d228793e2fdc9df887f4b7eb4c47e` | 376592 | 35.88% |
| model-picker | `a995f021cf98893e99668cea6b650bbb` | `1b3f341e2f2dfb642cd24747fe2f4383` | 106001 | 10.10% |
| hover-thread | `761a3ffb30f7706e0d7e6bd307ae1019` | `0c585b653775874533df29fb230d36dc` | 101606 | 9.68% |
| focus-composer | `16b7195e3fcde1d0afa4d2b27f44d075` | `417cb2e5b529df1d1d59bd57f32ef199` | 101661 | 9.69% |
| long-mid | `e00fa639bd71e6defdc0c23cb376cbbe` | `84c1f302c8c0b2d7bf50f4f340691002` | 123810 | 11.80% |
| long-bottom | `ed2401581de1b5092c00a61a9e5a43c1` | `86c008488de2d19c6376ea8fc8408c8b` | 113509 | 10.81% |
| settings-general | `362ac5425c08a297507fe2b1afded788` | `781e621b9d0d996b8e1b73e8563c4f6b` | 307749 | 29.32% |
| settings-models | `a2da4612ed8512b580a1bef64c449e93` | `cd0fa0efec154bfa0b6b442cf09900ac` | 306596 | 29.21% |
| settings-extensions | `2b552b719406e6a87bb86a36af2078ff` | `84070ce0e7e722f512d5da336a7ceb7f` | 301405 | 28.72% |
| settings-about | `3a476f4934fc5939eb109529efb1bc8f` | `284e760ac34641f70ac4455db8fb71b0` | 298179 | 28.41% |
| dark-chat | `0eaeeea88bdde5b8397f8e74bb6a9ba5` | `98d1cad59184096bd2bce57a3d452b40` | 101022 | 9.62% |

原始逐行输出：`out/final-closeout/logs/page-diff18.log`；脚本口径：三通道任一非零计 1 个差异像素，
分母 1280×820 = 1,049,600。

**四条硬判据逐条：**

1. **long-mid / long-bottom / chat 三者 md5 互不相同、两两像素差异 > 0 —— 成立。**
   `HARD_DIFFERENT chat vs long-mid AE=81299 max=241`；
   `chat vs long-bottom AE=29711 max=216`；`long-mid vs long-bottom AE=73309 max=241`；
   三个 md5 各异（`out/final-closeout/logs/criterion1.log`）。
2. **search-results 只显示命中 10 行 —— 成立。** 探针原文 `SEARCH_RESULTS count 10`
   （`out/final-closeout/logs/hard-probe.log`，ListView `count==10` 断言通过）。
3. **focus-composer 输入区有可见焦点边框 —— 成立。** 输入卡片矩形 `(428,658,780,146)`，
   四边中点取色全部 `#5b5bd6`（91,91,214），`out/final-closeout/logs/hard-probe.log`。
4. **右键第 5 项 Delete → 确认 → 真删除 —— 成立。** 原鼠标探针
   `test_menu_geometry_and_delete_confirm_flow` + `test_qml_sidebar.py`：`3 passed in 17.02s`，rc=0
   （`out/final-closeout/logs/hard-clicks.log`）；确认前 120 条，确认后 119 条。

### D. final-pass 逐页 rc 复采

**判定：已完成。两端各 18/18 页都有真实 rc，stderr 全 0 字节。**

| 页 | QML rc | QML stderr | deva rc | deva stderr |
|---|---:|---:|---:|---:|
| chat | 0 | 0B | 0 | 0B |
| empty | 0 | 0B | 0 | 0B |
| first-run | 0 | 0B | 0 | 0B |
| search-open | 0 | 0B | 0 | 0B |
| search-results | 0 | 0B | 0 | 0B |
| search-none | 0 | 0B | 0 | 0B |
| ctx-menu | 0 | 0B | 0 | 0B |
| delete-confirm | 0 | 0B | 0 | 0B |
| model-picker | 0 | 0B | 0 | 0B |
| hover-thread | 0 | 0B | 0 | 0B |
| focus-composer | 0 | 0B | 0 | 0B |
| long-mid | 0 | 0B | 0 | 0B |
| long-bottom | 0 | 0B | 0 | 0B |
| settings-general | 0 | 0B | 0 | 0B |
| settings-models | 0 | 0B | 0 | 0B |
| settings-extensions | 0 | 0B | 0 | 0B |
| settings-about | 0 | 0B | 0 | 0B |
| dark-chat | 0 | 0B | 0 | 0B |

每页 rc 落盘为 `out/final-closeout/{qml,deva}/<page>.rc`，stderr 为同名 `.err`；
批次汇总日志 `logs/qml-18pages.log` / `logs/deva-18pages.log`（各 18 行 `ok ... rc=0`，
批次 rc 0）。注：deva 首次全量跑时容器缺 `libgtk-3/libnss3`，18 页全部起不来；
补齐运行库后单进程重跑，18/18 成功。中途中还有一次两条 deva 批次互相覆盖输出目录的无效运行，
其产物已删除、未计入本表；最终一次干净运行的 rc/err 在 `out/final-closeout/{qml,deva}/`。

### E. `out/TEST-REPORT.md`

已追加「2026-11-25 收口（HEAD 4a1a023 + 579f40e）」小节：18 页逐页数字、四条硬判据、
全量 pytest 实数、CI 真实终态、J 未达标数值。版本戳与当前 HEAD 对齐（见文件尾部）。

### F. HEAD 的 CI 真实终态

**判定：已完成（查询到真实终态：失败，不是 queued，也不是「应该会绿」）。**

查询时间（UTC）：`2026-11-25T00:17:28Z`；run id `45217331247`；
HEAD `4a1a02328250a7b1234a86c27558fd2afccae7d8`。

```
runs?branch=develop&per_page=10:
4a1a02328250 completed failure 2026-11-23T16:30:44Z https://github.com/fanchcho/ai_upper/actions/runs/45217331247
```

逐 job（`out/final-closeout/ci/jobs-4a1a023.json`，15 个 job）：

| job | 结论 |
|---|---|
| Build Tool Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | success（6 个） |
| native-integration (windows-11-arm, windows-arm64) | **failure** — step 10 Unit tests |
| native-integration (windows-2025, windows-x86, pyserial) | **failure** — step 10 |
| native-integration (macos-15, macos-arm64) | **failure** — step 10 |
| native-integration (ubuntu-24.04, linux-x86_64) | **failure** — step 10 |
| native-integration (macos-15-intel, macos-x86_64) | **failure** — step 10 |
| native-integration (windows-2025, windows-x86_64) | **failure** — step 10 |
| native-integration (ubuntu-24.04-arm, linux-arm64) | **failure** — step 10 |
| native-integration (windows-2025, windows-x86_64, py3.8.10) | **failure** — step 10 |
| aggregate-artifacts | skipped |

失败根因来自 check-run 注解（job log API 匿名 403，workflow 已把 pytest 尾巴写成公开注解）：
`FAILED tests/test_qml_broken_image.py::test_broken_image_paints_icon_and_keeps_alt_inline
- assert 25.171875 == 42 ± 0.0625`（`out/final-closeout/ci/annotations-linux.json`）。
即 8 个原生集成 job 全部是同一个字体回退断言红；已在 `579f40e` 修复，但**该修复尚未推送，
所以 CI 仍停在 4a1a023 的红色终态**——本报告不把「已修」写成「CI 已绿」。

### G. 设置 · Models 面板与 provider 细节

**判定：已完成，逐项与 deva 源码值一致；数据面的 provider 数量差是 fixture/config 差异，不是控件缺失。**

| 项 | deva 只读源码实测值 | QML 实现/实测 | 证据 |
|---|---|---|---|
| Providers 标题 | `.models__title` 15px/700，`.models__head` 高 28、下距 16（`app.css:4475-4486`） | `modTitle` 15px/700，head `(20,16,28)` | `test_qml_settings_models.py::test_models_panel_structure_and_drilldown` 断言 |
| 28×28 加号 | `.models__add-btn` 28×28、border 1px `var(--border)`、radius（`app.css:4493-4502`） | `addBtn` 28×28、radius 8、border 1 `#e6e6ea` | 同上 + 截图 `qml/settings-models.png` |
| 描边容器 | `.models__rows` border 1px + radius-lg（`app.css:4509-4515`） | `modRows (20,60,510,54)` radius 12、border 1 | 同上 |
| 52px 行高 | `.provider-row min-height:52px; padding:10px 14px`（`app.css:4519-4530`） | row height 52、主列 x=36、dot (14,21) 10×10 | 同上；像素实测容器顶 244、首分隔线 297 → 52+1 |
| provider 详情下钻 + Wrench | `ModelSettings.tsx` 列表→`detail`，`.provider-detail` 顶部 Wrench 按钮 | row.onClicked → `openProvider`；`providerWrench` visible → `openAdvanced()` | 同测试：`view=="detail"`、`selectedId=="p1"`、wrench 点击后 `view=="advanced"` |
| 自定义请求头界面 | `ProviderAdvanced.tsx` 的 header 行：name 34% 保留、值可编辑、Add header | `advancedView` + `addHeaderBtn`/`headerRows`，写回走 `setProviderHeaders()` | `test_qml_settings_models.py` 47 passed（含 `test_header_rows_*`） |
| About 版本单一来源 | `apps/desktop/package.json` version `0.1.16` | `provider_registry.APP_VERSION = "0.1.16"`，QML `root.appVersion = shellBridge.appVersion()`，QML 无版本字面量 | `app/src/mvvm/services/provider_registry.py:33-40`；`SettingsModal.qml:15-16,1496` |

补充：deva `settings-models-deva.png` 比 QML 多一个 `Add decision model` 按钮和一条
`TypeSafe · Jev` 决策模型行——那是 deva store 的 `seedProviders` 数据（decision 用途），
QML 只投影 `config.json` 里的 provider 列表（fixture 只有 Anthropic）。属数据投影差异，
不在本项七个控件核对范围内；未改。

### H. 右键菜单第 5 项与 `confirmLayer` 的 MouseArea

**判定：已完成（`cddf2fb` 已修，本轮复核）。**

- `Main.qml:2005-2009`：5 项依次 `New chat / Rename / Select / Archive / Delete`；
  第 5 项 `danger: true`，`color: modelData.danger ? Theme.danger : Theme.fg`（2031/2036）。
- `confirmLayer`（`Main.qml:2057`）下：`confirmBackdrop` 有 `MouseArea { onClicked: window.cancelDelete() }`
  （点背板关闭）；`confirmDialog` 有 `MouseArea { onClicked: {} }`（吞点击防穿透）；
  `confirmDelete` / `confirmCancel` 各自可点。
- 实测：`test_menu_geometry_and_delete_confirm_flow` 断言菜单中心 y = `[110.5,139.5,168.5,197.5,226.5]`、
  Delete hover `(229,72,77)` alpha 34–38、点击后 `confirmOpen==true`、点确认后 120→119；
  与 `test_qml_sidebar.py` 一起 **3 passed in 17.02s，rc=0**（`logs/hard-clicks.log`）。

### I. 窗口控制三按钮与滚动条

**判定：已完成；原版 thumb 行为已实测。**

- 窗口控件：`Main.qml:2349+` 的 `windowControls` 96×40，三枚 `WindowControlButton`
  32×40（minimize/maximize/close），几何取自 deva `main/index.ts:79-116` 与实拍
  （最小化 10×2 @1195,23；最大化 10×10 @1227,15；关闭 X @1259,15；图标 #5F6368）。
  `test_qml_window_controls.py` 用 `QTest.mouseClick` 断言真实状态变化：4 passed。
- 滚动条：`DevaScrollBar`（`Main.qml:215`）width 8、padding 2、thumb 4px、track 透明，
  `policy: ScrollBar.AsNeeded`，挂在侧栏（585）与正文（994）两个 Flickable。
- **原版「不滚动时 thumb 是否隐藏、隐藏后是否占位」实测（deva 1280×820 基线）：**
  - `empty-deva.png`（无溢出）：x=1250..1278 全白，**thumb 完全不渲染**；正文容器一直延伸到
    窗口右缘 x=1280，**不占 8px 槽位**（隐藏后不占位）。
  - `chat-deva.png`（有溢出、静止）：x=1274..1277 有连续 417px 高的 thumb（4px 宽，常态色
    `(209,209,209)` 于白底）；即**有溢出时 thumb 静止也可见，不是 overlay 自动隐藏**。
  - QML 同形：`qml/chat.png` x=1274..1277 有 423px thumb；`qml/empty.png` 无。
  （像素探针见 §2 证据脚本；测试 `test_qml_scrollbars.py` 另锁 8px 轨道/4px thumb/颜色 token。）

### J. Markdown 残差（表格底边 / 表后间距 / 行推进）

**判定：未达标。三种可试的 QML 层修法都实测无效，保留数值与原因，未改产品代码。**

| 子项 | 本轮实测 | 原版实测 | 结论 |
|---|---|---|---|
| 表格底边 | QML `chat.png` 底边 y=217,218 **两行**（两行都是实色 `(230,230,234)`，宽 209px） | deva `chat-deva.png` y=224 **单行** | 未达标 |
| 表格行推进 | 行顶 94/129/165/199（Δ35/36/34），边框行 77.5/113/147.5/183/217.5，平均 **35.0px** | 行顶 96/132/166/201（Δ36/34/35），边框 86/121/155/190/224，平均 **34.5px**（CSS 计算值 13×1.65+12+1 = 34.45 → 实测 34.4375） | 未达标 |
| 表后盒间距 | 上一轮探针：最后 cell 内容盒底→后段起点 **14.5px**（表格 margin-bottom 已 12px） | 原版 **12px** | 未达标 |

原因（本轮实测，不是猜测）：

1. **行推进不可达**：Qt 把表格行高量化到整像素。参数扫描
   `FixedHeight = 34.0 / 34.25 / 34.4375 / 34.45` 全部得到 **35.0px** 行距；
   `34.5 / 35.0` 得到 **36.0px**（`out/final-closeout/logs/J-rowheight-sweep.log`）。
   `34.4375` 落在 34.0–34.45 区间内只能取到 35，物理上取不到 34.4375；
   这是 `QTextTable` 行高整数量化，不是 CSS 参数没抄对。
2. **底边两行不可由边框属性修**：`QQuickTextEdit` 只画表格级边框、不画单元格边框——
   把 `table_fmt.setBorder(0.0)` 后整张表的网格**全部消失**（`J-experiments.log` 第 3 行
   `border rows: []`）。把末行单元格 `setBottomBorder(0.0)`（让表格级边框单独画）后，
   底边仍是两行（217/218 → 218/219，只是整体下移 1px）。表格对象在文档里的 y 落在
   `.5` 半像素（行顶 2.5/37.5/…），1px 边框在 QQuickTextEdit 里被光栅成两行实色，
   属引擎绘制路径；要像素级单行只能自绘表格，代价远超本项收益。
3. **表后间距**：`QTextTable` 自动创建的尾块会吃掉/追加基线留白；`setBottomMargin(12)`
   已设到最大有效值，剩余 2.5px 来自尾块行盒（Qt 文档布局而非 CSS），无配置项可调。

两种实验的补丁均已回滚（`git status --porcelain app/src/markdown/document.py` 为空），
实验截图保留在 `out/final-closeout/j/`（`chat-lastrow-border0.png`、`chat-tableborder0.png`）
供复核；未把失败候选留在产品代码里。

---

## 3. 本轮提交与远端对比

本段新增提交（本地 `develop`）：

| commit | 内容 |
|---|---|
| `579f40e` | test(qml)：断图 alt 宽度改用现场字体度量（修 CI 8 个 native job 的红项） |
| `dc89438` | docs(closeout)：A–J 对账、18 页重拍表、四判据、CI 终态、J 未达标证据（主报告） |
| `75f20af` | docs(test-report)：TEST-REPORT 版本戳改为自指，避免再次落后 |
| 本提交 | docs(closeout)：§3 补记上述提交链（仅文档；`git log -1` 即此哈希） |

远端对比：交付回执里给出 `git rev-parse HEAD` 与 `git ls-remote origin refs/heads/develop`
的原始输出；两者必须相同（本报告提交即 `develop` 的 HEAD）。

---

## 4. 全量 pytest（真实数字）

```
$ QT_QPA_PLATFORM=offscreen AI_UPPER_HOME=/tmp/co-full .venv/bin/python -m pytest -q
1360 passed, 5 skipped in 212.60s (0:03:32)
rc=0
```

- 原始日志：`out/final-closeout/logs/pytest-full-final.log`；退出码 `pytest-full-final.rc`
- 5 skipped 与仓库既有 skipped 集一致（无新增 skip）。
- 命名红项单独跑：`1 passed in 0.27s`，rc=0（`logs/pytest-A-named.log`）。
- 诚实备注：本轮第一次全量跑（`logs/pytest-full-4a1a023.log`，`rc=1`）是在 apt 安装
  `fonts-noto-cjk` 过程中启动的，字体配置在测试中途改变导致 `test_qml_broken_image` 假红；
  该次不计入结论，字体稳定后的最终全量即上面的 1360 passed。

---

## 5. 18 页对照表与四条硬判据（汇总）

见 §2.C 的整表与四条判据结论：**四条全部成立**（md5 两两不同且 AE>0、search-results=10 行、
focus-composer 四边 `#5b5bd6`、Delete 确认流程 120→119）。

---

## 6. 没做的及原因

| 项 | 状态 | 原因 |
|---|---|---|
| J 表格底边单行 / 34.4375px 行推进 / 12px 表后距 | 未达标 | Qt `QTextTable` 行高整数量化（34.0–34.45 只能得 35px）；QQuickTextEdit 只画表格级边框且 1px 在 .5px 位置光栅成两行；单元格边框完全不画。需自绘表格才能达标，超出本轮范围，已留实测与两种失败候选证据。 |
| CI 变绿 | 未完成 | `579f40e` 修复了根因，但本轮未 push（硬约束：先本地提交，网络可用才 push）。正文 F 记录的仍是 `4a1a023` 的红色终态，不把「已修」写成「已绿」。 |
| deva 侧 `Add decision model` 按钮 / decision provider 行 | 未做 | 属 deva store 的 `seedProviders` 数据，QML 只投影 `config.json`；不在 G 的七项控件核对范围，未擅自造数据。 |
| 设置弹窗内部像素残差（settings-general/extensions/about 的字体行盒） | 未做 | 上周已定性为字体行盒/字重栅格残差，本轮未再改；18 页差异百分比仍如实列出（28%–29%）。 |

---

## 7. 环境说明（可复核）

- 容器初始缺 `libegl1/libgtk-3/libnss3/libasound2/xvfb/xdotool/imagemagick/fonts-noto-cjk`，
  本轮用 apt 安装后：Qt 可 import、Electron 可起 Xvfb 窗口、ImageMagick 可截图。
  这些是**运行环境**依赖，未写入仓库。
- 没有 `libegl` 时先用 deva electron 的 `libEGL.so` 做临时 shim 跑过命名测试；安装 `libegl1`
  后已不需要 shim，最终 pytest 直接在系统库下运行。
- 旧证据里的 18 页数字与本轮不同，是因为本轮是**两端同时重拍**的新基线（fixture 时间戳也会影响
  「22 hr ago」文案），不是把旧值改小；逐页 md5 与差异见 §2.C。
