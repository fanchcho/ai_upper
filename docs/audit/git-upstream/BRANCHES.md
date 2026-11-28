# 分支列表真实交互

本轮基于 8ee1a55，未回退 2595779 的菜单实现。修复 git_service.branches 没有逐分支 ahead/behind 字段、QML 没有展示跟踪关系、长列表没有可靠滚动容器、空列表没有文案的问题。上游 GitWidget.tsx:359–370 已有本地/远端分组与当前分支标记；逐分支显式 upstream 和领先/落后数字是本轮用户要求，上游仅将 upstream 放在 title，不冒称上游已有这些数字。

实现：app/src/mvvm/services/git_service.py:112–135，真实 for-each-ref + rev-list --left-right --count；app/src/qml/GitMenu.qml:49–62 生成显示项，74–100 使用限高 Flickable、滚动条、完整名称 tooltip 和空态。符号引用通过 %(symref) 排除，未硬编码 origin/HEAD 文本。

复现：scripts/parity/git_display/branches_interaction.py before|after dark|light。在仓库根目录以 AI_UPPER_HOME=/tmp/独立目录、QT_QPA_PLATFORM=offscreen、QT_QUICK_BACKEND=software、LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu 运行 .venv/bin/python。脚本加载完整 Main.qml/ShellBridge，真实 QTest 鼠标/滚轮操作，真实 git 子进程和本地 bare remote；没有网络或模型回合。导入的模型 transport 未被调用，不作为任何模型成功证据。

暗亮各一次，after-dark.json / after-light.json 与原始 .log：

- 本地 main（当前）→ origin/main：↑1 ↓0；behind → origin/main：↑0 ↓1；feature/a、feature/b 无 upstream；远端 origin/main。fixture 建立了 origin/HEAD，列表未出现符号引用。
- 鼠标点击 feature/a → 切换分支；独立 git branch --show-current 返回 feature/a。
- 再建40个本地分支，内容高1656，面板高1044，窗口高1060；真实滚轮使 contentY 达623.61/623.56。没有撑破窗口。
- 新空仓库真实 git branches 返回 []，界面读回“暂无分支”。

before/after × dark/light 的 main/branches PNG 都是1280×1060、DPR1真实窗口抓图，没有缩放/拼接。branch-samples.json 为固定点取样：底(543,750)、边(540,750)、正文(599,719)。本轮不改token，颜色应前后一致。原用户上传是1025×1746物理像素的macOS截图；本轮Linux验证不冒领macOS同DPR复现。

before 图是本轮起点2595779的菜单，不是用户历史旧表单。after-long-list、after-scrolled、after-empty为附加场景，不能混作同状态前后对照。
