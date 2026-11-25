# QML 无边框窗口交付（2026-11-25）

## 基线与验收清单

- [x] develop 基线 `5e7888164d706ee495270ef82cd02cc08bd70cf6`；改前 tracked status 为空。见 environment.log、baseline-log.txt、baseline-status.log。
- [x] 改前真实 Xvfb + Openbox 会话复现，原生标题栏与内容区 QML 控件并存。
- [x] 根窗口 `Qt.Window | Qt.FramelessWindowHint`；内容仍从 (0,0) 开始，1280×820，按钮组 x=1184、96×40。
- [x] 三按钮继续使用 showMinimized / 按 visibility 最大化与还原 / close。
- [x] 三类拖动区调用 startSystemMove；排除头像、导航、搜索框、加号、会话行、正文角色名称和窗口按钮。
- [x] 八方向缩放使用 startSystemResize，指针分别水平、垂直、两种对角线。一般 5px；正文滚动条所在右边区域只占最外侧 1px，保留滚动条 hover/拖动；最大化和全屏禁用缩放。最小尺寸 940×600 不变。
- [x] 真实 WM 操作验证，完整原始命令/输出见 accepted-wm-actions.log；返回码 wm-actions.rc=0，应用退出码 0。
- [x] 最终真实 X11 pytest：3 passed，0 skipped，rc=0（accepted-xcb.log / .rc），包含 flags、frameMargins=0、命中和按钮状态断言。
- [x] 最终全量 QML 回归 201 passed，0 skipped，rc=0（final-regression.log / .rc）。
- [x] 两页受控前后截图及像素比较；尺寸 1280×820，前后变化 0%。
- [x] deva 仅只读查阅，无修改。
- 提交推送及远端核对：提交后生成的 publish.log 记录三个实际 hash 与 ahead/behind。

## 复现与真实会话证据

初始环境缺 Xvfb、Openbox、xprop、xdotool 与若干动态库。apt 索引、deb 下载和解压全部放仓库 .tmp；没有系统安装。Xvfb 固定编译器目录 /usr/bin 改为临时二进制中的 .tmp，链接 .tmp/xkbcomp；键盘数据显式用 .tmp/wm/usr/share/X11/xkb。失败与依赖日志保存在本目录，最终服务器日志 final-xvfb.log、final-openbox.log。

:99 早期启动失败留锁，改前用 :100，最终用全新 :101。均为真实 X11 + Openbox，offscreen 只用于像素回归。命令说明见 commands.sh。

改前 before-xprop.log：
```
_MOTIF_WM_HINTS = 0x3, 0x3e, 0x7e, 0x0, 0x0
_NET_FRAME_EXTENTS = 1, 1, 20, 5
```
改后 accepted-wm-actions.log：
```
_MOTIF_WM_HINTS = 0x2, 0x1, 0x0, 0x0, 0x0
_NET_FRAME_EXTENTS = 0, 0, 0, 0
```
Openbox 仍有用于管理客户窗口的 reparent 容器；这不是可见装饰。改后 frame extents 和 border width 为零。整桌面截图 before-desktop.png / after-desktop.png 包含整个应用窗口与周围桌面，前者有原生标题栏，后者最上方直接是 QML。

最终实际操作（每项 1 次完整序列，未声称压力可靠性测试）：

| 操作 | 实测 |
|---|---|
| 点 QML 最小化 | Normal → Iconic |
| WM 还原 | Iconic → Normal |
| 正文头部拖动 | (160,140) → (230,190)，位移 (+70,+50) |
| 右下角缩放 | 1280×820 → 1370×880，增量 (+90,+60) |
| 点 QML 最大化 | 1600×1100，两个 MAXIMIZED 状态原子出现 |
| 再点 QML 最大化 | 还原至 1370×880，状态原子消失 |
| 点 QML 关闭 | 客户窗口从 _NET_CLIENT_LIST 消失，应用 rc=0 |

中途原始失败日志保留用于追溯：首轮滚动条被缩放区覆盖，已通过右缘 mask 修复；mask 缺类型签名和边界检查由新增测试发现并修复。早期操作脚本在启动 2 秒后就点击，120 会话夹具尚在装配，事件未处理；最终等待 10 秒后通过。最终判断只使用 accepted-*、final-regression 和 controlled-pixels 日志。

## deva 只读依据与 API

`/home/agent/shared_workspace/deva/apps/desktop/src/renderer/src/redesign/redesign.css`：
- 125：图标栏 drag；134、139：导航按钮和头像 no-drag。
- 539：会话栏头部 drag；555：搜索框 no-drag。
- 1083：正文头部 drag；1090、1119：角色/操作按钮 no-drag。
- 1130：空态 40px dragbar。

`/home/agent/shared_workspace/deva/apps/desktop/src/main/index.ts:311-318` 对应 minimize、toggle maximize、close。未找到自定义拖动区双击最大化逻辑，也未实测 Electron 的系统默认双击行为，因此本轮不添加双击最大化。

已核对官方 Qt Window 文档：https://doc.qt.io/qt-6/qml-qtquick-window.html 和 Item containmentMask 文档：https://doc.qt.io/qt-6/qml-qtquick-item.html#containmentMask-prop 。当前仓库 PySide6 依赖固定 6.11.2；本次没有验证其他 Qt 版本、Windows、macOS 或 Wayland。

## 像素回归

controlled-before-* 用 git 基线 Main.qml 副本（.tmp/baseline-qml）实际重新渲染；controlled-after-* 用最终源码，同一隔离夹具、渲染环境和时间窗口。首次 before-* 与 after-* 跨过“21 hr ago → 22 hr ago”，产生 0.045350610% 时间文字变化，因此改用连续受控重拍，未掩盖首次结果（pixels.log 保留）。

严格 RGB 不同像素数 / (1280×820)，参照已有 out/latest-parity/deva 下同名参考图：

| 页面 | 对 deva 改前 | 对 deva 改后 | 本轮前后变化 |
|---|---:|---:|---:|
| chat | 10.455792683% | 10.455792683% | 0.000000000% |
| settings-general | 30.274676067% | 30.274676067% | 0.000000000% |

参考图来自此前环境；当前字体/夹具环境与它存在差异（截图中 CJK 字体缺失），本轮证明没有新增视觉差异，不声称达到跨环境视觉一致。当前机器没有另拍 Electron 原版。

## 变更

- app/src/qml/Main.qml：无边框标志、3 类拖动命中区、8 方向缩放与滚动条排除。
- app/tests/test_qml_window_controls.py：flags、frameMargins、最小尺寸、3 拖动区正反命中、8 边正反命中与最大化禁用测试；沿用原按钮像素与点击状态测试。
- scripts/parity/verify_frameless_wm.py：真实 X11 输入与窗口状态断言、整桌面截图、几何 JSON。
- scripts/parity/compare_frameless_shots.py：前后/参考图的逐 RGB 像素比较。

所有运行/测试显式设置 AI_UPPER_HOME=/tmp/ai-upper-frameless-20261125，pytest 的单用例 home 也位于此隔离目录，不读取真实 ~/.ai_upper。其余临时工具与副本在仓库 .tmp。
