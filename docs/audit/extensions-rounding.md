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
