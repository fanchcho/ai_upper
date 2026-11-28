# Git 页面：版本事实与结构差异

本轮基线 HEAD=origin/develop=4d37256363941eba0e6b23aec7afeb8ba9ba851e。git log -6：4d37256、dd3f91e、515b587、e8fdc2c、fc27ef4、183d770。唯一初始残留是未跟踪的本目录（版本命令记录与 diff）；逐条重新运行核对后保留，不能算上一轮已完成的界面交付。两张上传图重新打开：84978b1ef406aa95 是大表单 Git 页，dcf8eecef6de5557 是缺密钥警告。

## 版本事实

原始命令及输出见 version-commands.txt。本地 deva 根 package.json 无 version；apps/desktop/package.json 是 0.1.17。HEAD：25c29354f0fc449f43e6e9eabdd5462ab447cc85，2026-11-28 12:55:07 +0800。describe 输出 deva-agent-v0.8.52-6-g25c2935，是插件标签，不能当桌面版本。

ai_upper 的 app/src/mvvm/services/provider_registry.py:35-36 注释声明与 deva 基线一致，常量 APP_VERSION=0.1.16；qml_shell.py:456-458 读取它；qml/SettingsModal.qml:16/1637 显示它。app/pyproject.toml:19 的0.17.33是 Python 项目版本，另一个版本体系。docs/audit/qml-shell-audit.md:249 起记录只读 deva 的视觉基线，但未钉住 deva commit SHA。

**只能证实声明基线0.1.16，不能宣称整个移植版完整对应该版本。** 既有后续移植横跨更新功能，不存在可验证的全库单一上游SHA。当前原版桌面包比声明基线高一个补丁版本。v0.1.16=718908ea7938c2f223e418519783eb1befdd7f9a，v0.1.17=d045ccafd1d0c6595c829a8e72fa1b20ad58817d；v0.1.16..HEAD有92个提交，不代表移植版漏了92项。

用户实际运行的原版客户端没有提供 About 版本/构建SHA。无法证明本地克隆比它新或旧，未猜版本、未改动 deva、未擅自同步。当前界面实施目标只明确为本地0.1.17/25c2935。

## 不能误归因于版本的差异

`git show v0.1.16:apps/desktop/src/renderer/src/redesign/GitWidget.tsx` 中159-160行已描述分层 ContextMenu 与 CommitModal；490行已渲染 ContextMenu。当前GitWidget相对该tag只有14行新增、1行删除，主要补 GitIdentityForm 和身份错误恢复。大表单并非旧版原版结构，而是移植简化。完整diff在original-version.diff。

下表原版路径相对 deva/apps/desktop/src/renderer/src；移植路径相对 ai_upper/app/src。

| 区块/字段/行为 | 原版文件:行号 | 原移植文件:行号 | 本轮处理 |
|---|---|---|---|
| 入口分支名、ahead/behind | redesign/GitWidget.tsx:462-486 | qml/Main.qml:1893 原来固定Git | 新入口显示真实分支与上下游计数 |
| 主菜单顺序 | redesign/GitWidget.tsx:426-440 | qml/GitPanel.qml:80-148 整块表单 | qml/GitMenu.qml:39，拉取/推送/获取/提交/分支/刷新 |
| 分支钻取与本地/远程分组 | redesign/GitWidget.tsx:360-398 | qml/GitPanel.qml:125-131 平铺输入与按钮 | GitMenu.rows 分组，超过8分支出现筛选 |
| 单分支切换/改名/删除 | redesign/GitWidget.tsx:399-423 | 改名、删除分支无对应UI；桥存在 | GitMenu 单分支菜单，当前分支禁用切换/删除 |
| 新建分支输入 | redesign/GitWidget.tsx:240 | qml/GitPanel.qml:127 常驻 | 独立分支 prompt |
| 危险确认 | redesign/GitWidget.tsx:322-334 | qml/GitPanel.qml:63 直接丢弃 | 删除分支独立确认；不在新主菜单显示全量丢弃 |
| 独立提交弹窗、改动数 | redesign/GitWidget.tsx:745-753 | qml/GitPanel.qml:119 内联单行框；commit函数没有可见提交按钮 | GitMenu.qml:85 起，独立460px弹窗与多行消息 |
| 提交前刷新/暂存/冲突拒绝 | redesign/GitWidget.tsx:703-728 | qml/GitPanel.qml:53 直接commit | GitMenu.submit 重新读取并暂存，拒绝未合并项 |
| 身份名/邮箱 | redesign/GitIdentityForm.tsx:39-50 | qml/GitPanel.qml:110-112 常驻 | 提交身份错误后才展开 |
| 身份作用域 | redesign/GitIdentityForm.tsx:52-58 | 只有gitSetConfig桥，旧UI固定false | 新UI local/global（目前CheckBox而非原版select，仍有结构差异） |
| AI生成/取消/提交 | redesign/GitWidget.tsx:768-800 | qml/GitPanel.qml:116-117 生成/取消常驻，缺提交按钮 | 独立弹窗ghost生成/停止、取消及primary提交 |
| remote名/URL常驻表单 | 当前GitWidget主菜单没有该表单 | qml/GitPanel.qml:143-146 | 新入口不显示；没有虚构原版字段 |
| 最近提交 | 当前主菜单没有该列表 | qml/GitPanel.qml:133-138 | 新入口不显示；4d37256已修正的short/subject绑定保留，未回退 |
| 状态列表/diff | 当前主菜单没有该大区块 | qml/GitPanel.qml:86-99/132 | 新入口不显示 |
| 菜单尺寸/分隔 | redesign/redesign.css:447-515，min148、padding5+border1、分隔1、行padding7/9、13px | 480×760大面板 | 新主菜单148宽，padding6含边，分隔9高含上下留白，行33高；分支菜单300宽。逐像素一致尚未验证 |
| danger语义 | redesign/redesign.css:476-480 菜单danger文字/hover底 | SettingsButton危险实色按钮 | 菜单用danger文字，确认按钮danger实色 |
| 警告条 | features/settings/ModelSettings.tsx:477-483；styles/app.css:4929-4941 | qml/SettingsModal.qml:895-923 | 保留warning 8%底、40/60边；按本轮原版要求两主题正文均warning，撤回上轮浅色fg取舍；浅色对比度不足如实报告 |

旧 GitPanel 仍装配在Main供现有内部调用/测试使用，但默认Git点击不再打开它。其旧测试通过不证明新版菜单；新版必须以menu_interaction.py的真实点击、Fetch、创建分支、提交和Git读盘为证。未声称已删除旧实现。

## 其它页面受影响范围（只列、不改）

v0.1.16-changed-files.txt和v0.1.17-changed-files.txt是完整原版src变更路径；路径变化不等于对应功能未移植。

- 模型设置：高级请求头、决策provider可达性、密钥/配置持久化错误及重试（ModelSettings、ProviderAdvanced、store/models）。
- 模型选择与输入：ModelMenu/ModelPanel、EffortPicker、ContextRing、Composer、context-usage。
- 角色与记忆：ProfilePanel/View、PersonaFolderField/Prompt、RoleMemoryTab、MemoryDetail/editor。
- 任务、权限与交付：TasksPane、TaskDecisionField、TaskConfirmCard、MountCard、DeliverablesCard、blocks。
- 设置与扩展：SettingsPane、store/extensions、useMcpTextDraft，以及main/preload的相关变更。
- 壳/主题/语言：Rail、ChatFirstShell、Conversation、ThemeContext、chatFontSize、messages及styles。

以上仅版本差异范围，未重做全站审计，未把这些路径记成“全部缺失”。About版本不整体升级为0.1.17，避免把单页推进冒充全站升级。
