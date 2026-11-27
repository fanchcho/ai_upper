# 2026-11-27 残差归因实验与复扫

## 磁盘与实验边界

起始status为空，HEAD与ls-remote均4e4ee73efca9cbfcaffe35af0c267eff9250b051。未回退99387aa/4cb98879。只修改ExtensionDetail.qml两处尺寸token：Check14→15，caret12→15。deva只读；原版CDP临时DOM位移和实验色块不写源码。所有运行显式AI_UPPER_HOME=/tmp；临时探针位于.tmp/extensions-rounding。

## 已归零：Check真实token错误

原版components/Select.tsx:306的Check size=15、:259的ChevronDown size=15；旧移植分别14/12。不是抗锯齿理由。改后暗亮check墨迹bbox均[951,392,961,399]，与原版一致；改前[952,393,961,400]。真实打开菜单后截图compare-{dark,light}-menu.png。旧图沿用out/extensions-final/compare-*-menu-after.png作为改前，不重跑已提交版本。

## 引擎取整，未归零：正文

固定字体、字号、block margin与lineHeight，不改生产正文。只在隔离探针移动真实TextEdit的y；实测mapToScene依次(486,411)/(486,411.5)/(486,412)。原版.md同样transform translateY，宽度/字号不变。暗亮结果相同：

|同移量|原版六块墨迹起点|Qt六块墨迹起点|差值|
|---|---|---|---|
|0|415,444,477,509,542,575|416,445,477,510,543,575|+1,+1,0,+1,+1,0|
|0.5|416,445,478,510,543,576|416,445,478,510,543,576|0,0,0,0,0,0|
|1|416,445,478,510,543,576|417,446,478,511,544,576|+1,+1,0,+1,+1,0|

同token、同位移，仅亚像素相位改变即可消除又恢复差值，说明该fixture的残差来自两端字形定位栅格化。生产代码不加0.5px补偿，原始残差保留；不将这一实验外推所有字体、所有Markdown。

## 引擎取整/合成，未归零：圆底与外环

本机三方依据：原版tokens.css dark bg-selected=rgba(124,124,240,.2)、accent-tint=.16，light分别rgba(91,91,214,.12)/.1；Theme同值。纯色背景dark #2a2a2e/light #fff。对照20/40px、整数/0.5px坐标、矩形/圆形，所有设置相同。

8项依次alpha1:(坐标0/尺寸20,0/40,.5/20,.5/40)，alpha2同序。dark矩形20%两端均#3b3b55；16%原版均#37374e，Qt均#37374d。light矩形12%两端#ebebfa；10%原版#eeeefb、Qt#eeeefa。无字体/无图标参与，证明外环1通道不是字号或字体抗锯齿，是RGBA栅格合成量化路径。

dark圆形20%原版20px为#3a3a54、40px为#3b3b55；Qt均#3b3b55。相同token因图元尺寸/覆盖路径变化而变化，生产页面圆底采样的1通道差不能靠换token全局修。实际页面旧采样仍原版#3b3b55/Qt#3b3b54，未归零。矩阵composite-matrix.json与compare-*-flat/circle.png是独立实验，不冒充实际页面归零证据。

## 引擎取整，未归零：阴影

原版tokens.css:82浅色0 6px 24px黑12%，:149暗色0 8px 30px黑50%，SoftShadow完全同参数。只移动实际菜单y，不改token：

|菜单同移|light原版(700,660)|light Qt(700,660)|差|
|---|---|---|---|
|0|252|251|−1|
|0.5|251|251|0|
|1|251|250|−1|

dark同点依次原版41/41/40、Qt41/40/40（蓝通道）；差值也随相位改变。表明模糊栅格覆盖取整，不是固定token错误。生产保持原参数，尾部1灰阶未归零；没有宣称Qt与Chromium整个模糊核等价。

## 页面复扫与未完成登记

- 实际菜单打开态首行active底色、所有角色勾选、外环继续正常；check已归零，外环合成残差如上。两个角色堆叠、描述、圆底、菜单阴影均在同fixture截图中复核。
- 新发现：原版AvatarStack max=3，超过三角色会显示余量遮罩；移植Repeater仍全部展开。未修，本fixture只有两个指定角色，不能声称覆盖。
- 新发现：原版Select.tsx:197–209支持ArrowDown/ArrowUp/Home/End键导航；移植菜单未实现相应活动行键导航。未修；鼠标选择不能替代键盘行为。
- 原版成功保存密钥仍无OS凭据服务，未验证。不可用提示沿用上轮真实backend=none键盘/自动保存测试，本轮生产未改该路径；不假造Saved。
- 三个额外入口/SettingsModal/路由/既有测试不改。整页整体1:1仍未完成，新增差异如实登记。

## 命令及证据

out/extensions-rounding/measurements.json：各位移下墨迹上下界、check bbox、阴影RGB；composite-matrix.json：尺寸/坐标/形状矩阵；dark-final.log/light-final.log：真实TextEdit坐标。最初探针误选隐藏HTML项，输出不变，已收紧为实际readOnly正文；最终JSON来自修正后的probe，不以无效位移得结论。

复现入口scripts/parity/rounding/capture.py与reference.py；flat.py/flat-reference.py、circle-run.py/circle-reference.py为独立合成实验。所有原版来源只读，截图并排左原版右Qt。生产截图compare-dark/light-menu.png、compare-dark/light-skill.png；实验图compare-dark/light-flat.png、circle.png。

全量命令：AI_UPPER_HOME=/tmp/ai-upper-round-tests LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-round-tests/tests

最终全量：1429 passed, 9 skipped in 365.85s (0:06:05)，0 failed。git diff --check通过，既有测试/SettingsModal/Main零改动。正常推送后SHA与远端回读保存out/extensions-rounding/git-verification.json，整体目标因新增已登记行为差异继续open。


## 开发工程师复核：2026-11-27，本轮 fdb2299 后

重新运行真实 Electron 与 Qt 的矩形/圆形合成矩阵，未改生产 token 或增加坐标补偿。
脚本：`scripts/parity/feature_review/rounding_session.py`；日志：`out/feature-review/rounding-session.log`。
原始图与 32 条采样保存在 `out/feature-review/rounding/`，覆盖两主题、矩形/圆形、20/40px、0/0.5px 相位。

- dark 16% 矩形：Chromium `(55,55,78)`、Qt `(55,55,77)`，四组合均复现。
- light 10% 矩形：Chromium `(238,238,251)`、Qt `(238,238,250)`，四组合均复现。
- dark 20% 圆形：20px 时 Chromium `(58,58,84)`、Qt `(59,59,85)`；40px 两者一致。

这些新证据支持**合成量化/覆盖路径差异，未归零**，不支持改颜色 token。正文和菜单阴影的相位实验本轮未复跑，前文属于历史证据；不可把本次纯色图元实验外推成它们的新验收。C10 因此仅推进合成部分，整体未完成。

## 2026-11-27 续做：更细相位与图元矩阵（C10）

起点对账：HEAD=origin/develop=b25dc1b，工作树干净；本轮未回退 4e4ee73 / 99387aa / 4cb98879 / a563434。生产源文件 `ExtensionDetail.qml`、`Theme.qml`、`SoftShadow.qml` 与 a563434 零差异；未改任何 token、未加坐标补偿。新增的只是探针脚本与 `out/extensions-rounding/*.json`。

### 1. 正文：0.25/0.33/0.5/0.66/0.75/1.0 相位扫描

`scripts/parity/rounding/phase_sweep.py` 仍是「只移动真实生产 TextEdit 的 y」，不改字体、字号、block margin、lineHeight。浅色实测（`out/extensions-rounding/phase-sweep.json`）：

|delta|scene_y|六块墨迹起点（正文六段）|
|---|---|---|
|0|411.0|416,445,477,510,543|
|0.25|411.25|416,445,478,510,543|
|0.33|411.33|416,445,478,510,543|
|0.5|411.5|416,445,478,510,543|
|0.66|411.66|417,445,478,511,543|
|0.75|411.75|417,445,478,511,543|
|1.0|412.0|417,446,478,511,544|

同一文本、同一 token，仅亚像素相位变化就让不同段落分别跳 0 或 1px，且跳变点不一致；这不是固定样式偏移（固定偏移会在所有相位保持同一差值）。结论维持「引擎取整，未归零」，且不把该 fixture 外推到所有字体/所有 Markdown。

### 2. 圆底/外环：尺寸×相位×alpha 矩阵

`scripts/parity/rounding/shape_sweep.py`：矩形与圆形、尺寸 18/20/22/40px、坐标相位 0/0.25/0.5、dark alpha .20/.16、light .12/.10。结果（`out/extensions-rounding/shape-sweep.json`）：Qt 对同一 alpha 的全部 24 个组合输出**完全相同**：

- dark：59,59,85（alpha .20）与 55,55,77（alpha .16），24/24 组合一致；
- light：235,235,250（.12）与 238,238,250（.10），24/24 组合一致。

而旧 `composite-matrix.json` 里 Chromium 同 token 会随图元尺寸/相位变化（dark 圆 20px 为 58,58,84，40px 为 59,59,85；.16 的 40px 蓝通道 78 vs Qt 77）。这组新证据说明：生产页面圆底/外环残留的 1 通道差不可能靠改 token 或改尺寸修好——Qt 在该矩阵内对 token 是常量响应，Chromium 不是；差异属 RGBA 栅格合成路径。实际页面采样仍是原版 #3b3b55 / Qt #3b3b54、外环 #37374e / #37374d、light 阴影尾部 #fcfcfc / #fbfbfb，**未归零**，生产未改。

### 3. 本轮未发现可证的样式错误

再次对照 `deva/apps/desktop/src/renderer/src/styles/tokens.css` 与 `Theme.qml`：`--bg-selected` dark `rgba(124,124,240,.2)`、light `rgba(91,91,214,.12)`；`--accent-tint` .16/.10；阴影 light `0 6px 24px rgba(0,0,0,.12)`、dark `0 8px 30px rgba(0,0,0,.5)`，两边逐值相同。没有发现应当修复的真实样式错，因此本轮不修改生产代码。

## 2026-11-27 同数据字段纵向布局核对（C 第二处边界）

`scripts/parity/final_port/compare_identical.py` 在两端同一份 `config.json`/`mcp.json`/`skills`/`personas`、同一滚动偏移（Qt 与原版均 142）下，读取原版 DOM `ext-field__label` 的 `rect.y` 与 Qt 几何文件的 label y。浅色与深色结果逐项为：

|字段 label|原版 y|Qt y|差|
|---|---|---|---|
|Available to|163|163|0.0|
|Transport|233.5|233.5|0.0|
|Command|304|304|0.0|
|Arguments|374.5|374.5|0.0|
|Environment variables|490.5|490.5|0.0|
|Discovered tools|614.5|614.5|0.0|

两主题六个字段全部 `delta=0.0`：同数据下字段纵向布局已对齐，没有需要修的纵向实现差。此前「字段纵向布局仍有明显差异」来自非同数据 fixture，不能作为当前实现的结论。像素整体仍有差异（`compare-identical.json` dark 94.119% / light 94.729% 相等），属字体抗锯齿与水平字宽等残留，不是纵向布局错，也未加坐标补偿或改 token。结论追加于此，作为 C 的第二处边界记录。

## 本轮独立复跑：字段同数据对照与边缘展开（2026-11-27）

没有接受 812fd57 / a27d0c8 的完成口径。本轮执行 `AI_UPPER_HOME=/tmp/ai-upper-final-layout .venv/bin/python scripts/parity/final_port/identical_os.py`，真实私有 D-Bus + GNOME Secret Service，Qt 输入并保存后复制同一 config/mcp/skills/personas fixture 给只读原版。Electron safeStorage 返回 available=true、saved.ok=true、has=true；暗亮实际 Saved 可见。原始命令、输出在 out/final-port/layout-before.log。

两端 1280×820、滚动 142，DOM 与 QML 几何都重新采集。Transport/Command/Arguments/Environment/Discovered tools 的标签顶部在两端严格等于 233.5/304/374.5/490.5/614.5；command 与 env 输入框顶部 326.5/513 也一致。当前 fixture 不再复现“字段纵向相差 63px”。字段布局没有新增修改，没有坐标补偿或 token 调整。对照图 out/final-port/same-fixture-dark.png 与 same-fixture-light.png；字段数据 deva-fields-*.json 与 *-secret-real-os-saved-geometry.json。

菜单确有实现缺口：ExtensionDetail.qml 原来只有 y=parent.height+6。按原版 Select.tsx:73-75,106-124 改为 GAP=6、EDGE=12、below>=220 或 below>=above 时下展，否则上展；可用空间限制高度，同时保留 MAX_H=320。真实点击两种位置、两主题，窗口高度 820：下展 top=227.5、上展 top=333.5，height 都为 320，没有越界。证据 out/final-port/menu-edges.json、menu-{dark,light}-{up,down}.png。测试只在证据 fixture 改变触发器位置，生产代码未增加坐标补偿。

相位命令 `AI_UPPER_HOME=/tmp/ai-upper-final-phase .venv/bin/python scripts/parity/closeout/phase-session.py` 与 `python scripts/parity/closeout/measure_phases.py`，原始日志 out/final-port/phase-rerun.log。结果：

| 相位 | 原版文字起始行 | Qt 文字起始行 | 暗色阴影 (700,700) | 亮色阴影 (700,700) |
|---|---|---|---|---|
| 0 | 415,444,477,509,542,575 | 416,445,477,510,543,575 | 两端 11,11,12 | 原版 137，Qt 138 |
| 0.5 | 416,445,478,510,543,576 | 416,445,478,510,543,576 | 两端 11,11,12 | 原版 137，Qt 138 |
| 1 | 416,445,478,510,543,576 | 417,446,478,511,544,576 | 原版 11,11,11，Qt 11,11,12 | 两端 137 |

结论：字段同数据布局对照可闭环；正文与阴影像素 **未归零**。相位变化会改变误差且 0.5 相位文字起始行重合，支持引擎栅格化/合成归因，不支持把它写成“全部像素一致”。位移只用于实验脚本，未进入生产样式。
