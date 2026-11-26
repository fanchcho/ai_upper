# 工作区图标与挂载修复报告

工作目录 `/home/agent/shared_workspace/ai_upper`；起点 `b011b65`，develop，初始 `git status --porcelain` 无输出。未修改 deva、依赖 pin，未 push，未创建分支。第一条执行命令为用户要求的 log/status 对账；最近 8 条提交见 git-start.log。

## 要求核对

- [x] 先看用户截图，确认对应本仓库界面后才修改。
- [x] A：offscreen 复现、根因排除、保留图标修复、同数据同尺寸截图。
- [x] B：核实现状、单实例目录选择、会话绑定与持久化、路径保护、取消不变。
- [x] 真实 QTest 鼠标点击输入栏和目录窗口 Open 按钮；落盘、重开与新 bridge 恢复受信根验证。
- [x] 全量 pytest：1401 passed、9 skipped、0 failed，退出码 0。
- [x] develop 本地修复提交 6e59c784b43c95cfea6b30aae9f71171e4e8d975；证据提交后的最终状态见 FINAL_STATE.txt。
- [x] 未验证的平台行为及实际验证边界明确记录。

## 第 0 步：截图归属与定位

已打开原始 macOS 截图，复制为 user.png。图中不是“多个文件夹窗口”，而是正文下方交付文件卡的三列图标残影。与本仓库 Main.qml 的结构、文字、模型默认值和坐标关系一致，不触发“不是本产品立即停止”的分支。

命令及真实命中见 inspection.log。修复后行号：

| 特征 | 文件与行号 | 判定 |
|---|---|---|
| 模型默认 deepseek-v4.1-flash | app/src/qml/Main.qml:143 | 输入栏模型下拉文案 |
| Message + persona 占位 | Main.qml:1450 | 正文下方 composer |
| Mount workspace | Main.qml:1508、1525 | composer 工具栏 |
| 文件 model / 每行高度 | Main.qml:1228、1233 | deliveries 的交付文件卡 |
| 文件名 / 体积与目录 | Main.qml:1261、1276 | `sizeText + " · " + dir`；路径是动态数据，不应硬编码 `/Users/` |
| MB 格式 | app/src/qml_shell_sessions.py:34、50 | `%.1f MB`，截图的 5.9 MB 符合此格式 |
| 三列图标 | Main.qml:1252、1302、1309 | 左侧文件图标、右侧 reveal、copy |

## A：根因与反证

Main.qml:1065 的 bodyScroll 已设置 clip:true（1072）；deliveryCol 下 Repeater 使用 deliveries，delegate 固定 60 高。Icon.qml:30 起使用 Shape、24×24 坐标与 size/24 缩放，软件后端的 Shape 绘制在滚动裁剪之外留下历史像素。窗口中同时存在文字正常裁掉、Shape 残影越界的现象。

这是本环境 **Qt 6.11.2 software Shape + ancestor clip + 滚动重绘** 的实测问题；未定位 Qt C++ 内部具体缺陷，不声称已证明 macOS 后端的内部实现相同。最小反证：只撤掉 Icon.qml 的独立 layer，原测试稳定在输入框 `(478,685)` 读到 `#808088`，1 failed、退出 1（regression-before.log）；恢复后通过。

逐项排除：

1. model/count：一个 Repeater，直接以 deliveries 为 model；24 条合成文件记录，每行 60 高，正常可见区域行距正确；没有第二个图标行 model。
2. y 绑定：左图标 anchors.centerIn 在 44×44 行内容盒中；右侧 Row anchors.verticalCenter 属于本行；未绑定外层 y 或 index 错位。
3. anchors/Column：原始 delegate 没有同时设置 top/bottom/height 冲突，截图中各行文字、底线、背景位置正常。添加点击区域期间发现的 Row 子项 anchors 警告已消除：MouseArea 放在 Row 的同级。
4. 背景/水印：三个残影列与实际图标 x 一致；背景是纯色 Rectangle/SoftShadow，没有循环贴图。
5. 字体 fallback：Icon 是 PathSvg/ShapePath，未用字体字形；缺失中文字体导致测试截图汉字方框是另一环境问题。
6. Tile：`rg -n 'fillMode:.*Tile' app/src/qml` 无匹配、退出 1；Icon 本身没有 Image，主题没有把图标当贴图。

修复 Icon.qml:30–33：在内部 Shape 上设置 layer.enabled=true，将单枚矢量合成到自身边界，再由祖先裁剪。没有隐藏图标或减少记录。通用 Icon 修复覆盖左图标和右侧操作图标。

before.png / after.png 均 1200×800，24 条相同数据，contentY 依次 0..476、步长 17，同一代码路径与软件后端。pixels.log：三列输入框区域暗像素 36→0、21→0、37→0；可见文字/体积/路径区域差异 0 像素。整个文件行区域有 2826 像素差，来自图标渲染层抗锯齿变化，不声称逐像素一致。回归测试还断言行内文件图标仍存在。

原版只读对照：deva/apps/desktop/src/renderer/src/features/chat/DeliverablesCard.tsx:185–240 是“左缩略图/图标，中间名称与体积路径，右 reveal/copy”的同一信息层级。本次保持已有层级、行高和文本坐标；原版按类型绘制 File/缩略图，本仓库原有通用 folder 图标未借机重构。

## B：根因与修复

起点 Main.qml:1494–1521 的 mountChip 仅 Row、Item/Icon、Text；无 MouseArea/TapHandler、无目录对话框、无 Python 槽位调用。源文件未 import QtQuick.Dialogs。Python 启动仅由 trusted_workspace_from_env()/DEVA_APP_WORKSPACE 登记根（原 qml_shell.py:1639–1642），已有 store.set_focus 尚未接到 chip。故原有点击不可能一次触发多个目录窗，截图中的“很多窗口”是 A 的图标残影。

新增 Main.qml:21 单实例 FolderDialog，Main.qml:1538 点击区域只有一个 open()；visible 和 Python pending-session 双重防重复。accept/reject 各一条静态 handler，无 connect 循环或逐次 new。

qml_shell.py:1197 beginWorkspace 固定当前会话，未选会话给明确提示；1206 cancel 清理待选状态而不写盘；1210 acceptWorkspace 仅接受待处理用户选择、本地存在目录、R_OK/X_OK 权限，切换会话或非法路径拒绝，resolve(strict=True) 规范化软链，store.set_focus 落盘后注册共享 guard。启动时 :346 恢复已落盘规范目录信任；:1613 向 QML 发布 focusRoot，chip 显示目录名。

安全语义与原版一致：用户在系统选择器选中的新目录就是新授权根，不能用“必须在旧根内”阻止首次挂载。没有 pending 选择时的直接提交被拒绝；挂载后文件工具继续使用 WorkspaceGuard，根之外及内部指向外部的软链被拒绝。原版参考 Composer.tsx:473、chat.tsx:2076 与 workspace.ts:41–49。系统 OS 权限失败会提示，不静默成功。

测试 test_qml_workspace_mount.py：QTest.mouseClick 打进主 QQuickWindow，断言对话框 visible 和唯一可见附属窗口；取消后 session 文件逐字节不变；selectedFolder 由测试设为夹具目录，再通过真实鼠标点击 Qt Quick 对话框 Open；新建 ChatSessionStore 读磁盘、切换会话回来、新 bridge 恢复根均断言。覆盖非目录、远程 URL、不存在、无 pending、会话切换、无会话，以及路径逃逸。

**pytest 验证边界**：目录项选择使用 selectedFolder 注入；对话框打开和确认按钮均真实鼠标。后续独立真实目录行验证见下方补充。dialog.png 是实际独立 Qt Quick 选择窗，不是主窗口截图。该 Qt fallback 截图仍显示默认 cwd 列表，因此不将截图本身作为“已选择夹具路径”的证据，选中结果由落盘断言证明。

## 命令与输出

所有命令在仓库运行。初次直接启动失败 `ImportError: libEGL.so.1`，使用仓库已有 `.tmp/wm/usr/lib/aarch64-linux-gnu` 修复运行环境，未安装/修改依赖 pin。

```bash
AI_UPPER_HOME=/tmp/ai-upper-mount-before LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python .tmp/repro_mount.py before
# rows 24 scroll 598.0 1610.8125 backend software ; exit 0
AI_UPPER_HOME=/tmp/ai-upper-mount-final-image LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python .tmp/repro_mount.py after
# rows 24 scroll 598.0 1610.8125 backend software ; exit 0
AI_UPPER_HOME=/tmp/ai-upper-mount-mouse LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software PYTHONPATH=app/src MOUNT_EVIDENCE=$PWD/out/workspace-mount .venv/bin/python -m pytest app/tests/test_qml_workspace_mount.py -q -s --basetemp=/tmp/ai-upper-mount-mouse-tests
# 2 passed in 12.80s ; exit_code=0
AI_UPPER_HOME=/tmp/ai-upper-mount-full LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software PYTHONPATH=app/src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-mount-full-tests
```

逐字日志：inspection.log、before.log、after.log、regression-before.log、targeted.log、mouse.log、pytest-full.log。截图脚本持久副本 repro_mount.py；修复 diff 在 fix.diff。初轮定向测试使用仓库 .tmp 夹具，后续及全量统一使用 /tmp 隔离 AI_UPPER_HOME，从未使用真实 ~/.ai_upper。

## 未验证与限制

- macOS 原生 FolderDialog 外观、鼠标操作及 Metal 渲染：未验证，本机是 Linux offscreen。
- Qt C++ 内部根因及 macOS 与 Linux 是否同一个 Qt bug：未验证；可确认同形缺陷已在 Linux 重现并通过最小修复消失。
- GPU 性能与高 DPI 抗锯齿：未验证，通用 Icon 独立 layer 有资源成本；本次提供软件渲染像素回归。
- OS 拒绝权限的真实目录：代码有 R_OK/X_OK 检查，权限拒绝分支使用 os.access 替身测试，未创建其他用户所有的不可访问目录测试；非目录、非法 URL、根逃逸已测试。
- 完全不输入路径、只靠逐层双击导航：未验证；补充脚本已验证地址栏定位后真实鼠标点选目录行及 Open。
- 本轮未打包 macOS 应用；未声称已交付 macOS 安装包。

## 全量检查发现的问题与收敛

首轮全量输出 `4 failed, 1397 passed, 9 skipped in 286.78s`，完整保留 pytest-full.log；执行会话随后返回退出码 143（未取得 pytest 正常退出），不计通过。

- 三条 settings_models 失败为真实回归：外层 Icon 的 layer 引入额外视觉子项，破坏已有 Row 的结构断言。最终把 layer 限定在 Icon 内部 Shape，未修改原测试断言。49 条相关测试通过（layer-targeted.log，退出 0）。
- 另一条 qt_prune 失败由本轮命令额外设置 PYTHONPATH 引起：测试要求宿主环境逐项一致，而闭包探针有意替换 PYTHONPATH。原有 conftest 已配置 sys.path，不需要这个环境变量；最终全量去除多余 PYTHONPATH，不改该测试/生产逻辑。
- 最终全量由持久脚本 run_full.py 执行，真实子进程退出码写入 pytest-final.exit，日志 pytest-final.log。保留所有旧断言，新增 2 个测试，无新增 skip。

官方 API 核验（Context7/smart-search 本运行时未提供，采用 Qt 官方文档）：[FolderDialog](https://doc.qt.io/qt-6/qml-qtquick-dialogs-folderdialog.html) 的 selectedFolder/accepted、原生与 fallback 行为；[Shape](https://doc.qt.io/qt-6/qml-qtquick-shapes-shape.html) 的软件/GPU renderer 区别。不能据文档推断本机已验证 macOS。

最终全量命令（由 `python .tmp/run_mount_full.py` 启动，报告目录有同内容副本）：

```bash
env -u PYTHONPATH AI_UPPER_HOME=/tmp/ai-upper-mount-final-full LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest app/tests -q -rs --basetemp=/tmp/ai-upper-mount-final-full-tests
```

截图对应关系：user.png 原图；before.png 修前；after.png 最终 Shape 内层修复；dialog.png Linux 实际独立选择窗。截图中的汉字缺字为本机字体环境限制，未修改字体配置。

## 实际目录行点击补充证据

`dialog_mouse.py` 打开 Mount workspace 后，向真实地址输入框写入测试目录的父路径，QTest.keyClick(Return) 导航，再 QTest.mouseClick 文件夹行，断言 selectedFolder 对应测试目录；真实点击 Open 后读 store 验证持久化。这里没有向 selectedFolder 注入值。

```bash
AI_UPPER_HOME=/tmp/ai-upper-mount-real-row LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python .tmp/dialog_mouse.py
```

实际输出（dialog-mouse.log）：

```
selected after real row click /tmp/ai-upper-mount-real-row/home/aaa-chosen
real row click + Open persisted /tmp/ai-upper-mount-real-row/home/aaa-chosen
exit_code=0
```

`dialog-selection.png` 直接显示高亮的 aaa-chosen 文件夹，是优先用于检查实际选中状态的截图；先前 dialog.png 留存为对照。

## 最终结果

最终生产改动 3 个文件，新增测试文件 1 个；源代码提交：`6e59c784b43c95cfea6b30aae9f71171e4e8d975`（develop）。

真实全量输出：

```
1401 passed, 9 skipped in 285.81s (0:04:45)
exit_code=0
```

0 failed。9 个原有条件 skip：Windows 专属 2；需显式开启的构建 E2E 2；缺少 cc/patchelf/readelf 的 native deployment 1；需要 Studio 宿主能力的接口 4。全部原因见 pytest-final.log，未移除测试、未削弱既有断言、未新增 skip。

`git diff --check` 无输出，退出 0。证据完成后本地追加报告提交；最终两条提交与 `git status --porcelain` 原始输出位于同目录 FINAL_STATE.txt。没有 push。

可直接转述给用户：已修复交付文件卡的文件夹图标滚动后成列重叠、覆盖输入框的问题，正常文件图标、名称、大小和路径保留；Mount workspace 现在能弹出目录选择窗，确认后保存到当前会话，取消不改变工作区，重开会话仍保留。Linux 上已用真实鼠标点击目录行及 Open，并验证落盘；同数据前后截图显示三列残影消失，全量测试 1401 通过、9 项条件跳过、0 失败。macOS 原生对话框和 Metal 渲染尚未验证，需要 macOS 实机复测。
