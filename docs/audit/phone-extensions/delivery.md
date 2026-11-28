# 手机扩展协议本轮交付

## 范围与起点

只处理附件上传、交付文件下载、计划/权限交互卡、任务管理、主屏幕安装票据。没有重盘已验收 81 项，未重跑 F62 真人扫码、F84/fcitx、F06/macOS 或像素对照。

初始对账原文：
```
$ git log --oneline -6
1ad23b2 docs: record remote QR delivery regression and unresolved crash evidence
e286d6e fix: accept fresh phone QR after device revocation in the same browser
5f1ef48 fix: keep QR encoder import compatible with Python 3.8
a49cd37 feat: connect phone QR LAN and relay channels to persistent chat host
60ebbfc feat: add Feishu device authorization QR creation and owner persistence
ea5bf9d docs: record repeated bot test regression and unfinished parity work
$ git status --porcelain
$ git rev-parse HEAD
1ad23b2febb53e981ff9092e2af00117d06998fd
$ git ls-remote origin refs/heads/develop
1ad23b2febb53e981ff9092e2af00117d06998fd	refs/heads/develop
```

工作树初始干净，无需处置前轮残留。`1ad23b2` 仍是当前 HEAD 的祖先；没有回退、force、分支/tag 或依赖 pin 修改。deva 仅只读获取代码和既有工具；所有应用/测试 home 位于 /tmp，临时脚本文件与浏览器 profile 在仓库 .tmp。

## 本轮五项

|能力|独立提交（全 SHA 及推送回执见 pushes.md）|真实验证与依据|
|---|---|---|
|附件上传|564d226|upload.md；phone-readback.json；phone-browser-dark/light-lan/relay.png|
|交付文件下载|b5d2c30|download.md；download/phone-readback.json；模型 present_files → 交付边车 → 浏览器保存 txt/bin → 字节对比|
|交互卡|b3885d0|cards.md；cards/cards-*.json；计划批准、挂载跳过、允许真实写文件、拒绝真实不写文件|
|任务管理|cd28ad9|tasks.md；tasks/tasks-*.json；暂停/恢复/真实运行/查看任务对话/删除，tasks.json 与会话重开读回|
|安装票据|b53779c|install.md；install/install-*.json；隔离浏览器存储兑换独立设备、真实回合、重放拒绝、原浏览器刷新恢复|

每项均 LAN/relay × 暗亮四组，总计 20 组。本机模型 fixture 通过真实 HTTP 返回工具/文本，ChatHost、工具、加密 WebSocket、QML/浏览器键鼠与磁盘均真实执行；不是替换 host 回调。relay 是 127.0.0.1 opaque fixture，不冒充公网服务。

原版引用行号与明确语义差异分别落在五份专题报告。任务页保持原版移动端只读详情和动作；没有创建未要求的手机编辑器。原版手机挂载只可跳过，不能选择电脑路径。现有宿主 approvalEnabled 的批准/拒绝也走真实持久化审批，不将该额外宿主能力说成原版通用授权协议。

## 未完成 / 未验证 / 风险

- **未完成（外部验证）**：公网 relay、第二台物理设备 LAN、真手机扫码及跨移动网络。本轮只有本机 LAN/relay fixture 证据。
- **未完成（安装宿主验证）**：真实 iOS/Android 的系统安装提示、主屏幕图标及独立存储。隔离 BrowserWindow 只证明 install 票据和独立凭证语义。
- **未验证**：F62 真人授权/真实应用创建与邀请兑换、外部推送送达。沿用既有报告，不重试。
- **未验证**：F84 真实 fcitx preedit。沿用 `docs/audit/bot-detail/ime-abi.log:434` 原文 `undefined symbol: _ZTI20QGenericUnixServices, version Qt_6_PRIVATE_API`，合成事件不算成功。
- **未验证**：F06 macOS 红绿灯，无 macOS 宿主；保留 Linux 分支证据，不标不适用。
- **未归零**：MCP 同数据像素 94.123% / 94.729% 与正文/阴影既有边界，引用 `docs/audit/bot-detail/remaining.md`，本轮不重跑、不改 token/坐标。
- **未完成（历史崩溃归因）**：test_bot_roundtrip.py:48 既有多轮未复现，未归因；上一轮 test_qml_links.py:143 段错误也未归因，不宣称已修复。
- 本轮原生文件选择器报 `No GSettings schemas are installed on the system`，`file-chooser-failure.log` 与 `.tmp/phone-extensions/file-chooser.core`、`file-chooser-second.core` 两次 Electron core 保留；第二份 ELF NT_PRPSINFO 已确认进程名为 electron。上传以 CDP 选择真实磁盘文件验证，不声称 GTK 原生选择器成功。
- 真实 UI 日志保留缺少 system D-Bus、Qt socket disconnect、QML 关闭时 `saveError of null` 等警告；没有删除日志制造无警告成功态。

## 回归

完整回归退出码 0，原始日志 `full.log`：
```text
1486 passed, 9 skipped in 556.32s (0:09:16)
```
即 **1486 passed / 9 skipped / 0 failed**。本轮未出现 Python 段错误；不据此认定历史崩溃修复。命令：
```
ulimit -c unlimited
AI_UPPER_HOME=/tmp/ai-upper-mobile-extensions-full PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests -q
```
没有 Qt 预载。`git diff 1ad23b2 --name-status -- app/tests` 只有五个新增测试文件，既有断言/测试未改。
