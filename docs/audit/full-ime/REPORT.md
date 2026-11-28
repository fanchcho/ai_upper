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
