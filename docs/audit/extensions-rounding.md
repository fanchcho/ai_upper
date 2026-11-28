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

## 2026-11-28 收口复核（不改生产）

F85/F56/F41 等本轮功能变更没有触碰正文/阴影 token；`git diff` 对照 `ExtensionDetail.qml`、`Theme.qml`、`SoftShadow.qml` 仍无生产样式改动。复跑 `scripts/parity/closeout/phase-session.py` 与 `measure_phases.py` 的原始结果继续为：相位 0/1 六段文字部分差 1px，0.5 相位六段重合；亮色阴影 (700,700) 137 vs 138，暗色相位相关 1 灰阶。结论维持「引擎栅格化/合成，未归零」；没有加坐标补偿、没有改 token。完整原始日志 `out/final-port/phase-rerun.log`、`out/final-port/phase-measurements.json`。

## 2026-11-28 环境收尾实际复跑（41e8894 应用代码）

执行 `AI_UPPER_HOME=/tmp/ai-upper-environment-phase .venv/bin/python scripts/parity/closeout/phase-session.py`，随后 `python scripts/parity/closeout/measure_phases.py`。新日志与暗亮原始图归档 `docs/audit/environment-closeout/phase.log`、`phase-measure.log`、`phase/`。

两主题相位0文字原版415/444/477/509/542/575，Qt416/445/477/510/543/575；相位0.5两端416/445/478/510/543/576；相位1原版416/445/478/510/543/576，Qt417/446/478/511/544/576。亮色阴影(700,700)相位0/.5分别137与138，相位1均137；暗色相位1蓝通道11与12，相位0/.5一致。再次支持相位相关栅格化/合成差异，未归零；没有发现可证的token错误，不改生产token、不加坐标补偿。

## 2026-11-28 深入归因：hinting、描边/圆角与合成入口

本轮只在探针中改变变量，生产 Theme.qml / SoftShadow.qml / ExtensionDetail.qml 均未改，未添加坐标补偿、未修改 token。新的 Qt 暗亮截图与几何位于 `docs/audit/deep-boundary/pixel/`；对照用 `docs/audit/environment-closeout/phase/deva-*.png` 的上轮原版基准，明确**不是本轮重新运行 Electron 的同场截图**。

### 正文真实 TextEdit：四种 hinting × 两相位

`scripts/parity/deep_pixel_probe.py` 使用真实 Main.qml / ExtensionDetail.qml，在独立 fixture 改 QFont.hintingPreference，读取生效值与 sceneY。Default 与 Vertical 两主题均逐像素一致；NoHinting 相位0与默认分别有暗2866/亮2864像素不同，FullHinting 有3439/3444像素不同（ROI 486,411,900,600）。FullHinting 的行起点变为416/444/476/509/542/574，仍不能同时匹配原版415/444/477/509/542/575。默认相位0.5的本轮行起点416/445/478/510/543/576，与已有原版同相位起点一致，但字形内部仍有差异。

因此 hinting 确实能改变字形/墨迹边缘；没有证据支持将 Full/NoHinting 当成生产修复。字体轮廓、字体后端与 hinting 并未被证明等价，不能写成已归零。数值见 pixel/measurements.json 与 pixel-measure.log，原始图完整保留。

### 阴影：排除采样点的圆角与描边假设

对真实320px高菜单阴影，分别取相位0/.5、radius12/0、border.width1/0。两主题全部8组合在(700,700)仍分别为暗(11,11,12)、亮(138,138,138)。关闭菜单阴影后变为暗(13,13,15)、亮(142,142,142)，确认实验确实操作到了目标阴影。这个采样点的残差不是圆角半径或描边导致；不能把该结论外推到整个圆角边缘。原版既有相位0亮色为(137,137,137)，残差未归零。

### 合成模式与颜色入口

`scripts/parity/deep_composite_probe.py` 在软件 Canvas 中检查默认 globalCompositeOperation，实际为 source-over；显式指定 source-over 与默认结果完全一致，排除该探针的模式差异。

但是**相同 RGBA 值的 QColor 与 CSS rgba 字符串入口不等价**：

| 主题/alpha | QColor 输入 | CSS rgba 字符串输入 | 既有 Chromium 中心采样 |
|---|---|---|---|
| dark .16 | 55,55,77 | 55,55,78 | 55,55,78 |
| light .10 | 238,238,250 | 238,238,251 | 238,238,251 |

这将前文笼统的合成量化结论细化为**颜色解析/alpha精度到合成入口的差异**；不是token数值不一致，也不是source-over选错。只对这里的矩形中心采样成立，不是全页修复依据。

继续复制真实 SoftShadow 实现到 .tmp，仅把 shadowColor 的 QColor 改为由相同通道构造的 CSS rgba 字符串（scripts/parity/deep_shadow_color_probe.py），暗亮全部图像均 **0 changedPixels**（pixel/shadow-color-difference.json）。所以矩形填充发现不能直接外推为阴影修复，没有将这项实验改动写入生产。

结论：**正文与阴影未归零；未发现本轮可证的生产样式错误**。新增排除项是该采样点的圆角/描边、Canvas默认合成模式；进一步定位了颜色入口的量化差异。阴影 blur 核/量化、字体后端的更深差异仍未完成。

复现：`AI_UPPER_HOME=/tmp/ai-upper-deep-pixel-<unique> XDG_DATA_HOME=$PWD/.tmp/deep-boundary/pixel-data QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/deep_pixel_probe.py dark`（light 独立home）；相同Qt环境运行 deep_composite_probe.py / deep_shadow_color_probe.py；系统 `python3 scripts/parity/deep_pixel_measure.py` 计算图像数值。截图 *-reference-left.png 左侧是已保留原版基准，右侧为本轮 Qt，非完整同场像素验收。

## 2026-11-28 完整输入法轮：字体 raster 与 blur 后端

没有重做已验收页面对照。新增脚本 scripts/parity/font_backend_probe.py 在真实Main.qml的正文TextEdit上切换renderType=0/1，通过QQmlProperty写入（避免Python枚举转换错误），两主题实际截图差异均0像素；结果docs/audit/raster-backend/font-results.json。这只说明当前software backend下该开关不能消除差异，不宣称两种硬件字体后端全都等价，也不把hinting整体排除为所有像素的因素。

当前venv qVersion实测6.11.2；官方同版本源码 https://github.com/qt/qtdeclarative/blob/v6.11.2/src/quick/items/context2d/qquickcontext2dcommandbuffer.cpp 的paintShapeAndShadow明确将shadow画入ARGB32_Premultiplied，调用qt_image_boxblur(shadowImage,qMax(1,qRound(blur/2)),true)，之后SourceIn着色再drawImage。原文件只读下载于.tmp/blur-backend/qt-current.cpp，不改第三方代码。

scripts/parity/blur_backend_probe.py 对复制场景中的真实生产SoftShadow分别使用原始blur与+0.2/+0.8/+1。dark30→30.2/30.8与light24→24.2/24.8均0像素差；到31/25分别改变6763/12122像素。与qRound(blur/2)的阶跃一致，docs/audit/raster-backend/blur-differences.json及blur-profile.json保留逐行尾部采样。这将阴影差异进一步定位到软件Canvas的离散box-blur路径。

Skia当前源码使用sigma驱动的Blur接口，但本轮未取得Electron33所捆绑Skia的精确revision及完整CSS box-shadow调用链，所以不能用Skia main源码证明历史Chromium截图每个灰阶的根因。未宣称找到同版本算法的一一对应关系。

结论：正文和阴影仍未归零。字体renderType开关在当前software环境无效果；Qt blur半径量化已被源码与真实图像实验证实，但尚未证明是全部跨引擎残差的唯一来源。没有发现可证的生产样式错，未改SoftShadow/Theme token，未加坐标补偿。
