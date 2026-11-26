# A 项：HiDPI 左侧图标消失与裁剪（2026-11-26）

本轮定位并修复可重复的 HiDPI 故障：Qt Quick software 后端的 layered Shape，在 DPR=1.5 被错误裁剪，在 DPR=2 图标区域空白，只剩选中指示条。此前只跑 DPR=1，因此漏掉了该故障。未通过改变主题颜色掩盖问题。

## 逐项验收

1. **绘制方式已确认**：修前 Main.qml:359 的 Icon 使用 IconData.qml:9/11/13/15/17 中的 messageCircle/users/alarmClock/bot/cog 路径。Icon.qml:30 的 Shape、:33 的 layer.enabled、:36 的 scale、:44 起的 ShapePath/PathSvg 绘制这些路径。不是 Text/IconLabel 字体图标，也不是 Image.source 的磁盘 SVG/PNG。
2. **DPI 矩阵完成**：offscreen + software，QT_SCALE_FACTOR={1,1.5,2} × QT_ENABLE_HIGHDPI_SCALING={0,1} × dark/light，共12组，修前修后各一轮，每组常态/悬停截图、左栏裁图及像素 JSON。开关为0时实际 DPR 仍跟随 scale，日志记录实际 DPR，未假定该开关能关闭 Qt6 的缩放。
3. **字体路径不适用**：导航图标没有字体族或私有 Unicode 字形。探针没有加载任何图标字体；fontDatabase/addApplicationFont 缺失实验不能解释这个 Shape 图标，因此不伪造该分支测试。
4. **资源排查与修复后 Image 验证完成**：修前路径来自打包的 IconData.qml 常量，既无外部图标路径也无 Image.status。QML 按磁盘目录分发：源码 app/src/qml，包内 assets/qml，非 qrc；package.py:292/310 复制整个树，qml_shell.py:142 选择加载入口。dist 内 Icon.qml/IconData.qml 均存在，但属于旧构建，不能当成本次修复产物。修后 Image.source 是同路径生成的 data:image/svg+xml URI，非空，导航 Image.status 实测 Ready=1。大窗口 DPR2、3600×2000 实测正常。
5. **后端验证完成**：xvfb-run -a + software 复现DPR2消失；llvmpipe OpenGL成功，旧Shape在这个后端正常。修后两后端均正常。主机并非无GL能力，上轮 offscreen 默认上下文失败不能代表 Xvfb+llvmpipe 不可用。
6. **修复与正反验证完成**：同Lucide路径改用内存SVG Image，sourceSize=size×Screen.devicePixelRatio，移除 layered Shape。未改主题 token、逻辑尺寸、几何位置或选中条。保留既有图标 API（name/size/color/strokeWidth/filled）。既有滚动裁剪测试通过，无需恢复有缺陷的 layer。
7. **回归与提交**：见文末及 out/icon-dpi/git-final.txt。

## 根因证据与边界

修前所有导航Icon的逻辑x=18、width=height=20，选中y=80、未选中y=124；name非空，enabled=true，opacity=1，QML颜色是正确的accent/fgSubtle。DPR2截图对应区域却完全只有背景，实测对比度1.000。说明颜色属性正确不代表像素被绘制，故障发生在Shape离屏层栅格化/裁剪链路。

单变量实验：

- 同一源码，仅用dist旧版的无layer Icon.qml替换：DPR2图标恢复。
- 把layer从Shape移到外层Icon Item：DPR2仍消失（parent-layer截图/日志）。
- 旧layered Shape改用llvmpipe OpenGL：DPR2正常。
- 使用同路径SVG Image：software与OpenGL、1/1.5/2倍均正常。

由此可定位到Qt软件后端layered Shape的HiDPI组合，不是资源不存在、缺字、主题token、disabled或布局逻辑坐标问题。未对Qt C++内部做调试，不宣称已确定某一条Qt内部指令或上游bug编号。复现了用户最关键的图标截断/消失/仅有紫色条特征；没有用户设备原始framebuffer，不能声称截图每个黑色残影都逐像素一致。

## 实际像素与位置

坐标为物理像素，bbox为图标区域内与背景对比度>1.5的像素范围，端点包含。

|软件后端暗色|修前选中bbox|修前未选中bbox|修后选中bbox|修后未选中bbox|
|---|---|---|---|---|
|DPR1|19,82–35,98|19,126–36,141|19,82–35,98|19,126–36,141|
|DPR1.5|28,120–54,132（截断）|28,189–55,198（截断）|28,122–54,148|28,188–55,213|
|DPR2|无图标像素|无图标像素|38,163–72,197|38,251–73,284|

以下修后数值在1、1.5、2倍及两种HiDPI开关中一致；alpha边缘有正常抗锯齿差异。

|主题/状态|图标实际像素|所在背景|对比度|
|---|---|---|---:|
|dark 未选中|#71717a|#191919|3.638|
|dark 选中|#7c7cf0|#303030|3.770|
|dark hover|#e4e4e7|#272727|11.773|
|light 未选中|#8a8a94|#f0f0f2|3.003|
|light 选中|#5b5bd6|#dddddf|3.957|
|light hover|#1f1f24|#e6e6e8|13.166|

注意：DPR1.5修前虽然残余像素颜色正确，对比度也能达标，图形仍严重截断。验收同时检查bbox与像素存在性，不能只看对比度。

## 真实命令与日志

所有命令从 /home/agent/shared_workspace/ai_upper 执行。探针装配仓库真实ShellBridge与Main.qml，会话transport为空测试替身，不联网；每次应用home均为/tmp下独立目录。未修改deva原版。

```sh
AI_UPPER_HOME=/tmp/ai-upper-dpi-dark-s2-h1 \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
QT_SCALE_FACTOR=2 QT_ENABLE_HIGHDPI_SCALING=1 \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
.venv/bin/python .tmp/icon-dpi/probe.py dark dark-s2-h1
```

该命令修前日志输出dpr=2、size=[2560,1640]、active/idle/hover contrast=1.0，bbox=null。完整12组环境、命令和退出码见 commands.json；修后见fixed-commands.json。探针脚本也持久保存在out/icon-dpi。

Xvfb尝试序列保留了实际失败：

- xvfb-software.log、xvfb-gl.log：`xvfb-run: error: xauth command not found`，exit3。
- xvfb-software2.log：`xauth: error while loading shared libraries: libXmuu.so.1: cannot open shared object file`。
- 仅在工作区.tmp/icon-dpi/runtime解包xauth/libxmuu1/libgl1-mesa-dri/mesa-libgallium；未改项目依赖pin。
- xvfb-software3.log：平台xcb、software、DPR2，修前对比度1.0。
- fixed-xvfb-gl.log / baseline-xvfb-gl.log：`OpenGL VENDOR: Mesa RENDERER: llvmpipe (LLVM 19.1.7, 128 bits) VERSION: 4.5 ... Mesa 25.0.7-2+deb13u1`。

复跑后端命令（脚本逐项记录环境与命令到backend-commands.json）：

```sh
.venv/bin/python .tmp/icon-dpi/backends.py
```

核心启动方式：

```sh
PATH=$PWD/.tmp/icon-dpi/runtime/usr/bin:$PWD/.tmp/wm/usr/bin:$PATH \
LD_LIBRARY_PATH=$PWD/.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu:$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
LIBGL_DRIVERS_PATH=$PWD/.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu/dri \
AI_UPPER_HOME=/tmp/ai-upper-fixed-xvfb-gl \
QT_QPA_PLATFORM=xcb QT_QUICK_BACKEND=rhi LIBGL_ALWAYS_SOFTWARE=1 \
QSG_RHI_BACKEND=opengl QSG_INFO=1 QT_SCALE_FACTOR=2 \
TMPDIR=$PWD/.tmp/icon-dpi XDG_CACHE_HOME=$PWD/.tmp/icon-dpi/cache \
.tmp/wm/usr/bin/xvfb-run -a -s '-screen 0 4000x2200x24' \
.venv/bin/python .tmp/icon-dpi/probe.py dark fixed-xvfb-gl
```

## 回归与交付边界

新增test_qml_icon_dpi.py用独立进程覆盖3个DPR×2个开关，检查图标存在且完整；同一测试对修前Icon：**4 failed, 2 passed**（1.5/2失败）；修后：**6 passed**。测试编写过程中的QML导入URL/QtQuick类型注册错误已修正，不把测试装配错误当成产品复现。
既有test_qml_workspace_mount.py和test_qml_packaging.py：**8 passed**，含原先需要layer才能通过的滚动裁剪用例。
源码修复未重打所有平台发布包；用户端必须运行新源码或重新构建后的包。现存dist仍为旧构建，不能用它验收新源码。
如用户新构建仍出现残影，可在临时AI_UPPER_HOME下记录启动命令、QT_SCALE_FACTOR、QT_QUICK_BACKEND、QSG_INFO输出及实际加载的assets/qml/Icon.qml版本；不需要提交真实home中的配置或密钥。

最终全量回归命令：

```sh
AI_UPPER_HOME=/tmp/ai-upper-icon-verified \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
XDG_CACHE_HOME=$PWD/.tmp/icon-dpi/cache \
.venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-icon-verified/tests
```

结果：**1422 passed, 9 skipped in 351.18s**，0 failed。完整日志out/icon-dpi/verified-tests.log。git diff --check无输出。

所有截图/JSON/运行脚本位于out/icon-dpi；comparison.png为原始左栏截图截取同一逻辑区域并排展示，不是替代原图。原图命名：dark-s2-h1-normal.png为修前，fixed-dark-s2-h1-normal.png为修后；hover后缀为悬停，rail后缀为左栏裁图。light对应浅色，s1/s1.5/s2对应缩放，h0/h1对应HiDPI开关。

本地develop提交，无push、无新建分支、无依赖pin改动；提交后git log和status保存在out/icon-dpi/git-final.txt。
