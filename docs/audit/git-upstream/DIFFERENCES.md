# 第二张图：最新上游对照与本轮修复

对照对象是用户明确点名的 `/home/agent/.hermes-web-ui/upload/default/84978b1ef406aa95.png`：深色、旧移植 Git 大表单，显示身份输入、分支名、remote/URL、diff和“最近提交”对象字符串。第一张 dcf8eecef6de5557.png 是服务商启用但缺密钥的警告。不能从静态图证明底层仓库状态，也没有依据把“第二张”替换成我们此前生成的 git-version 截图。

原版依据固定为 upstream main `013c5d7eb4cd0907e02bc8717219a0bef42fb1fc`，独立浅克隆 `/tmp/deva-upstream-n5zv9nfb/deva`。下表原版路径相对 `apps/desktop/src/renderer/src`，移植路径相对 `app/src`。本地deva定制副本与上游的区别另见GitWidget.diff、ModelSettings.diff，不再混用。

## 不能都归结为“版本旧”

只读命令：

```text
$ git -C /home/agent/shared_workspace/deva diff --stat v0.1.16..013c5d7eb4cd0907e02bc8717219a0bef42fb1fc -- apps/desktop/src/renderer/src/redesign/GitWidget.tsx
(无输出，exit 0)
$ git -C /home/agent/shared_workspace/deva rev-parse v0.1.16:apps/desktop/src/renderer/src/redesign/GitWidget.tsx 013c5d7eb4cd0907e02bc8717219a0bef42fb1fc:apps/desktop/src/renderer/src/redesign/GitWidget.tsx
33fc9dc551e0b9a8e41efebb2075447a418d6b83
33fc9dc551e0b9a8e41efebb2075447a418d6b83
```

GitWidget两版本源码相同；大表单是移植简化产生的结构差异。2595779已经改了默认入口，本轮不冒领这一步。此前报告用本地定制GitIdentityForm说明“新版上游增加身份表单”不适用于本次上游main：最新上游GitWidget中没有该表单。保留已接受的条件身份恢复增量，不回退它，也不把它称为上游原样UI。

## 按五类逐项核对

| 类别 | 项目与原版依据 | 移植依据/结果 |
|---|---|---|
| 结构不同 | 主入口是branch chip →菜单；GitWidget.tsx:458/490。菜单拉取/推送/获取/提交/分支/刷新：432–438 | Main.qml:1895；GitMenu.qml:58（rows）。2595779已替换默认大表单，本轮未重做 |
| 结构不同 | 分支分组、当前勾选、逐分支操作；GitWidget.tsx:359–423 | GitMenu.qml:59–74；本轮真实本地/远端列表、跟踪计数、空态和滚动见BRANCHES.md |
| 结构不同 | 独立460px提交弹窗；GitWidget.tsx:741–787 | GitMenu.qml:113，独立弹窗已存在；本轮按CSS修标题15px/600、输入高120、按钮高30、meta margin与bar gap |
| 缺项 | 分支超过8项筛选、视口限高滚动；GitWidget.tsx:355；redesign.css:483–521 | GitMenu.qml:83起；筛选已有，本轮补真实Flickable和ScrollBar。40项滚轮验证通过 |
| 缺项 | 每个本地分支的upstream为title，当前标记为Check；GitWidget.tsx:363–365 | GitMenu.qml:65起将upstream及↑/↓数字明示；数字是用户本轮追加验收要求，上游本身没有逐行数字 |
| 缺项 | menu/modal都有`--shadow`；redesign.css:447–457、app.css:2732；tokens.css:82/149 | GitMenu.qml:28/117起。本轮补现有SoftShadow，参数保持token；渲染后端残差未归零 |
| 缺项 | 未合并分支删除需要第二次确认及提交数；GitWidget.tsx:284–309 | GitMenu.qml的delete仍只请求非强制删除，缺第二次确认；未完成，未用原始error冒充完整流程 |
| 多余项 | 上游主菜单无常驻user.name/email/remote名/URL、diff、最近提交、全部暂存/全部丢弃；GitWidget.tsx:425–440 | 这些在旧GitPanel.qml:80–148。已不从默认Git按钮打开；兼容实例Main.qml:1676仍保留，未删除旧验证入口 |
| 多余项 | 上游main无GitIdentityForm的条件身份恢复表单 | GitMenu.qml:126–133保留条件恢复扩展；来自本地定制对照，不能当上游同构证据 |
| 文案不同 | 上游commitTitle/placeholder/AI生成/停止/取消/提交；i18n/messages.ts:1313–1330 | GitMenu.qml:123–140保持同文案；主菜单以中文“获取远端更新”替代旧Fetch，新/改名输入只在prompt出现 |
| 文案不同 | 上游主菜单没有“最近提交” | 旧GitPanel.qml:135–137已在4d37256读取short/subject并有“暂无提交”；本轮核对保留，不重复声称修复 |
| 颜色不同 | modal遮罩明确black42%；app.css:2720–2731 | 之前使用Qt默认遮罩实测暗#4a4a4b/亮#bbbbbb；本轮显式42%黑，实测#111113/#949494，固定点(900,200) |
| 颜色不同 | 普通菜单transparent、danger文字与14%hover底；redesign.css:458–481 | GitMenu.qml:100–104；本轮补危险hover14%，不将所有按钮统一红描边 |
| 颜色不同 | 提交primary；生成/取消ghost；GitWidget.tsx:755–783；app.css:2550–2577 | GitMenu.qml:137–140使用原有SettingsButton变体，局部GitActionButton只调整尺寸，不波及其它页面 |
| 颜色不同 | 警告warning8%底、40%warning+60%border、warning文字；ModelSettings.tsx:462–467，app.css:4929–4941 | SettingsModal.qml:895–923与规则一致；原版如此，本轮不改token。浅色对比度不足4.5的事实保留，不称可访问性已闭环 |

菜单外框148px、padding5+border1、分隔1px+上下4px、字13px：redesign.css:447–495；移植GitMenu.qml:26–28/90–101。分支300宽是容纳本轮upstream数字的选择，非上游固定300。提交框CSS20px内边距+1px边框在Qt写padding21，属于盒模型换算，不是坐标补偿。输入宽418；按钮AI69×30、提交52×30，全部来自真实QML几何读回。标题15px/600取app.css:2744；120px输入、meta4/0/10及按钮栏margin12/gap8取redesign.css:1320–1348。

## 真实交互、前后图、取样

同一脚本scripts/parity/git_display/menu_interaction.py，参数主题和证据目录；style-before为本轮尺寸修正前，style-final为最终实现。style-after为首次尺寸修正后、发现Qt默认遮罩仍错误的中间记录，明确不当最终图。

全部截图1280×1060逻辑/物理、DPR1，Linux offscreen/software真实QQuickWindow.grabWindow。前后均同fixture内容、相同菜单/弹窗状态；不是用户原macOS2x尺寸复刻，也不是上游Electron同数据截图。

暗亮两套：真实点击Git → 获取远端更新，FETCH_HEAD读回14debe2baa41a9b8076e864aa34aff0e4c35ce92；真实输入新分支、git branch读回new-menu-branch；真实键盘输入提交信息并点提交，git log读回`a6dcb8e Commit through original-style modal`，独立git status为空。使用/tmp本地bare remote，未宣称公网Fetch。日志的退出清理Main.qml:69 saveError-null原文保留，不将其抹成无错误。

固定点与字形纯色点在page-samples.json，脚本page_pixels.py从PNG读取：

| 项目 | 暗色 | 浅色 |
|---|---|---|
| 菜单/输入面底 | #2a2a2e | #ffffff |
| 菜单分隔/外边 | #2f2f33 | #e6e6ea |
| 输入边框 | #3d3d42 | #d5d5db |
| 占位符 | #a1a1aa；5.577:1 | #5c5c66；6.608:1 |
| 主文字 | #e4e4e7；11.266:1 | #1f1f24；16.410:1 |
| 警告底/边/字 | #363227 / #816b29 / #fcc419；7.945:1 | #f5efe6 / #e1c091 / #d9860b；2.494:1 |

没有改主题token、坐标补偿、依赖pin或既有测试断言。仅改GitMenu页及真实branch查询；公共SettingsButton/Theme未改，避免连带影响已对齐页面。

## 落后范围：不把源码变更数当缺失功能数

只读`git rev-list --count v0.1.16..013c5d7...`为20；`git diff --name-status ... -- apps/desktop/src`为72条，原始列表upstream-since-0.1.16.txt。声明版本差一个patch，不存在能证明全移植代码严格等于0.1.16的单一基线。不能说“全库落后20项”或“72功能未移植”。

- 模型/输入：ProviderAdvanced、ModelSettings、ModelMenu/Panel、EffortPicker、ContextRing、Composer、provider-headers。
- 角色/记忆：ProfilePanel/View、RoleMemoryTab、MemoryDetail/editor、PersonaFolderField/Prompt，以及main的memory/role-home。
- 会话/成员：chat-members/turns/inserts、members、agent-loop、ThreadSelect、MemberBar。
- 交付/权限/移动：DeliverablesCard、MountCard、mobile/cards及remote-views。
- 提供商/外部渠道：dsml、openai、opencode、feishu、telegram、hub。

仅列受版本差异影响的源码范围，本轮不做全站重写，不将已经实现的项目重新判成缺失。

## 未完成 / 未验证

- 用户实际客户端版本/构建仍未知；无法断言它比哪个clone新。
- 原版完整Electron与Qt同状态同DPR逐像素对照未完成；当前是固定上游源码规则 + Qt真实渲染。macOS宿主未验证。
- 未合并分支强制删除二次确认/计数未实现；上游merge冲突toast带abort快捷操作未同构，当前显示原始错误与已有中止入口。其余未覆盖的远程删除、冲突合并、AI生成/停止不冒充本轮已验证。
- 浅色warning对比度2.494:1，原版同规则；未解决原版自身的可访问性问题。
- SoftShadow仍为Qt实现，不能以补上阴影等同消除既有引擎像素残差。
