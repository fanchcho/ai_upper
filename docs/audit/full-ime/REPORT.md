# 完整应用 F84：匹配 Qt 组合真实输入通过

基线8b432c0。topPadding属于ApplicationWindow，Qt6.9引入（官方 https://doc.qt.io/qt-6/qml-qtquick-controls-applicationwindow.html#topPadding-prop）。6.8没有自动safe-area padding；改为Component.onCompleted检测属性存在后置0，新版保持原先显式0行为，旧版不再解析不存在的属性。没有改布局token或坐标。

系统PySide6 6.8.2还通过QObject.emit分发信号；ShellBridge同名方法原来把字符串信号当宿主事件入队。现在字符串转发super().emit，字典仍原样入队，修复主题信号与队列错误。两项生产修改可分别反向应用diff回退；没有修改依赖pin。

## 真实生产入口

scripts/parity/full_app_ime.py实际执行qml_shell.run(False)，加载生产Main.qml、真实ChatHost、真实SettingsService/ChatSessionStore，无fake transport/model。探针仅在ticker建立后安排观测与外部xdotool键鼠。完整应用在系统Qt6.8.2、fcitx Qt插件、私有DBus、Xvfb下启动；dark/light commit截图包含完整应用。

D-Bus日志ime-dark/light-dbus.log含CreateInputContext、FocusIn、ProcessKeyEvent、CommitString。QML实际preedit n/ni/ni h/ni ha/ni hao，commit你好。dark/light-readback.json保留真实文本、事件与会话路径。探针把输入框收到的中文传给真实renameSession写入会话title，再新建ChatSessionStore重新加载，storedTitle=你好。**持久化是会话标题，不能冒充消息回合存储成功**。

真实Return发送得到原始错误“Not configured yetAvailable models (select a default model in settings): Please go to the settings page to fill in the service address, model and API key”；messages=[]，不虚构模型成功。首次无模型失败保留first-no-model.log。没有合成QInputMethodEvent。

## 隔离运行与回退

scripts/parity/full_app_ime_run.sh <唯一后缀>，先确保已有隔离依赖目录。脚本只为子进程设置系统Qt6.8.2的QML_IMPORT_PATH/QT_PLUGIN_PATH/LD_LIBRARY_PATH；SVG模块额外apt-get download并dpkg-deb -x到.tmp/deep-boundary/qt-runtime，无系统安装。Python先加载系统PySide6，再追加现有venv中非Qt依赖搜索路径。仓库默认.venv Qt6.11.2完全不变；不用该脚本即恢复默认环境。系统库与默认venv不混载。

默认Qt+系统fcitx的历史ABI错误仍保留../environment-closeout/ime-abi.log。这里通过的是用户指定的“系统Qt6.8.2+匹配插件”组合，不宣称默认Qt插件ABI已修复。无macOS或物理设备结论升级。

退出时Main.qml saveError空对象警告仍保留；不影响本次输入和存储断言，但未伪称日志完全无警告。

## 归档补充

实际/tmp会话文件另复制为dark-session.json与light-session.json，均title=你好、messages=[]，与重开存储结果一致。qml-ime-dark-*是最早旧探针未建会话的失败中间证据，不能用于成功验收；成功证据文件名为dark/light-preedit.png、dark/light-commit.png及dark/light-readback.json。最早旧探针断言失败后未退出，已终止其本执行进程，失败日志仍保留。

默认环境全量以final-tests.log/exit为准；full.log是修复过程中提前启动的探索轮，期间代码继续修改，不能作为最终版本验收。

旧失败探针退出时仍持有被后续轮次复用的日志描述符，导致暗色日志末尾追加空洞/终止信息；已将污染副本保留.tmp/full-ime/late-writer-*，正式三份日志恢复为bdf9d26中已经提交且具有成功事件的原始快照。没有删改成功轮输出，退出后已确认无探针残留进程。

## 最终回归

AI_UPPER_HOME=/tmp/ai-upper-full-ime-final-tests PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests -q

final-tests.log：1486 passed, 9 skipped in 558.50s (0:09:18)，0 failed；final-tests.exit=0。默认Qt6.11.2环境，无预载、无既有断言修改，无新段错误。两处历史段错误仍未归因，不宣称修复。探索轮full.log不作为最终验收。

专题推送原文：
```
To github.com:fanchcho/ai_upper.git
   8b432c0..bdf9d26  develop -> develop
bdf9d26e9adc8e68ce1345354aaf30800abf7c03 refs/heads/develop
To github.com:fanchcho/ai_upper.git
   bdf9d26..302e069  develop -> develop
302e0698c86d9a52c113afdac7599c433188df29 refs/heads/develop
```

未完成：默认Qt6.11.2匹配fcitx插件未提供（系统Qt6.8.2路径已验证）；无模型配置下消息回合未验证；正文/阴影未归零；历史Python段错误未归因。真手机/第二物理设备/公网relay移动网络/外部推送/iOS Android系统安装/F06 macOS均保持未验证。没有重做已验收功能。
