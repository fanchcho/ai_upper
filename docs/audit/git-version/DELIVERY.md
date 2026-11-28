# 实现与验证交付（尚非全部闭环）

Git 默认用户入口现在使用 GitMenu.qml，旧 GitPanel.qml 保留内部兼容入口；4d37256 的提交字段修复不回退。新版菜单按原版0.1.17主菜单及分支层级实现，独立460逻辑像素提交弹窗；新增重新暂存、冲突拒绝和条件身份恢复路径。菜单通过点击时记录Git按钮位置向上展开。应用版本号没有伪装整体升级。

暗亮真实窗口均1280×1060逻辑像素、DPR1、offscreen/software；dark/light-menu.png、branches.png、created.png、commit.png、warning.png 均为真实QML窗口grabWindow，没有拼图、缩放或假文案。原版结构依据和前后差异表在VERSION.md。没有运行原版完整客户端同状态对照，本轮不能声称逐像素闭环。

真实交互脚本 scripts/parity/git_display/menu_interaction.py：真实鼠标点击新入口 → Fetch → 分支列表 → 新建分支输入 → 确认 → 提交弹窗输入 → 提交；所有操作调用真实ShellBridge和git进程，本地裸仓库仅为本地fixture。dark/light-interaction.json记录新分支new-menu-branch、FETCH_HEAD真实hash、a6dcb8e Commit through original-style modal，以及独立git status读回空串。没有外部模型调用或公网推送验证。退出清理原有Main.qml:69 saveError null警告原文保留在runtime.log，不伪称无日志错误。

固定像素采样与几何见 samples.json，脚本 menu_pixels.py。菜单暗底#2a2a2e、边#2f2f33、字#e4e4e7，正文11.266:1；亮底#ffffff、边#e6e6ea、字#1f1f24，16.410:1。警告暗底#363227、字#fcc419，7.945:1；亮底#f5efe6、字#d9860b，2.494:1。浅色文字可读性问题来自原版规则，本轮按用户新版对齐指令保持并明确报告，不改token。

未完成／未验证：

- 不能证明用户实际客户端就是本地0.1.17构建；缺实际客户端版本/构建号。
- 新菜单是结构迁移的可用增量，不是完整GitWidget复刻：未合并分支强制删除二次确认未实现；身份作用域使用CheckBox，原版是select；菜单阴影、部分图标与hover差异没有完成原版同状态逐像素比较。
- 身份缺失恢复、远程分支删除、冲突合并、中止合并、AI生成/停止等本轮没有真实交互覆盖，不把已有后端或静态接线算成新UI已验证。
- 旧GitPanel内部兼容实例尚未移除；用户Git按钮已不进入它，旧测试覆盖旧入口，因此单独保留新入口真实交互证据。
- macOS实际宿主未验证；所有截图明确是Linux，不冒领macOS。

测试首个命令误指定不存在的test_git_service.py，exit4、no tests ran，原始regression.log保留。正确的Git专项为4 passed in 9.87s，既有断言未改。全量结果完成后追加，不能用专项代替全量。

最终代码的Git专项补跑：4 passed in 9.84s（final-focused.log）。全量开始后修正过菜单锚点，最终锚点另由暗亮真实点击与专项验证；全量日志不冒称冻结在最终代码上的整轮。

全量原文：`1486 passed, 9 skipped in 563.10s (0:09:23)`；工具会话退出0。既有测试文件未修改、未预载Qt；未发生本轮段错误。
