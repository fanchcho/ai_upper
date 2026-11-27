# 当前盘点口径复核

当前89项按JSON逐行重算：已实现81、只有界面0、未移植4，另不适用4；没有待判定。三态合计85，不适用4单列。组合项尚缺原版行为时保守留未移植，已实现的部分另写证据，不用部分实现升级整个功能。

F62：原版 BotsPane.tsx:27-168 添加/搜索/详情，:447-635 详情状态/用户/邀请码/回复模式，:640-735 三种范围和多选。现有 RemoteBots.qml 已有三个平台添加、状态和管理；独立详情、搜索、多选范围、完整扫码仍缺，未完成，不再写“飞书/Web创建完全没有”。

F64：PhonePane.tsx:1-220 与 remote/web/phone.ts:1-180 证明是真实 QR、LAN/relay、设备管理；Electron只承载IPC，不构成不适用理由。web_pairing.py本机浏览器配对已有真实证据，但手机QR/LAN/relay完整往返未完成。

F84：真实环境未验证。原始历史日志 docs/audit/remaining-seven/ime-plugin.log 保留：Qt插件版本不匹配；系统Qt6.8成功加载插件后仍 QInputMethodEvent count=0、文本nihao、fcitx Controller1.State=0/CurrentInputMethod空。d105a24合成QInputMethodEvent证明防误发，不是fcitx真实输入成功，本轮不重复宣称打通。

F06：本轮在真实Linux QML窗口验证 macChrome=false、FramelessWindowHint存在、ExpandedClientAreaHint/NoTitleBarBackgroundHint不存在；暗亮截图与nonmac.json记录flags。宿主非macOS无法验证红绿灯成功态；原版macOS全屏布局仍未移植，保留未移植而非以环境理由改不适用。

原版引用均相对于只读deva/apps/desktop/src；移植版引用相对于app/src。原已验收85项状态未重做；本轮改的是过时证据文字和计数出处。
