# 本轮收尾

基线6f8ab29，产品app/与依赖pin及既有测试无修改。既有已验收项不重做。

- 15eeaac9339acf0e2f5bed597bf7d4448c8c054a：默认Qt插件隔离构建尝试，SDK缺失，未完成。abi.md及原始configure日志。
- a8ecb7e7c7807c41da64dd048885c558c618ada0：本地OpenAI HTTP fixture中文回合闭环，生产入口/真实ChatHost/重开存储。第二轮补dark/light-roundtrip.png，readback/session归档对应最后一轮，旧轮保留git历史，四份HTTP请求分属两轮。
- 524aa1e5bd13fbb0947c3ae62e5ed7d8f69fea1d：历史崩溃三轮通过及gdb原生栈，根因未完成。qml-core-gdb.log随上一提交入库，归属崩溃专题。
- aaa3beb75bdab4331e4f7ded997b1c35eae4d007：同版本Electron/Chromium/Skia及CSS阴影调用链取证闭环；像素仍未归零。

正常push均为To github.com:fanchcho/ai_upper.git，依次6f8ab29..15eeaac、15eeaac..a8ecb7e、a8ecb7e..524aa1e、524aa1e..aaa3beb，紧随ls-remote均等于上列完整SHA refs/heads/develop。

全量命令：AI_UPPER_HOME=/tmp/ai-upper-next-final PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests -q。ulimit -c unlimited，无Qt预载。full.log：1486 passed, 9 skipped in 557.53s (0:09:17)，0 failed，full.exit=0。两处历史崩溃没有重现，不宣称修复。

未完成：默认Qt6.11.2插件配套、两处历史段错误根因、字体/阴影完整逐像素归因与归零。Qt源码地址可达但本轮未构建完整SDK，缺SDK不是永久不可行结论。外部模型及真手机/第二设备LAN/公网relay移动网络/外部推送/iOS Android系统安装/F06 macOS均未验证。

没有外部并发提交；未跟踪有效材料已提交，隔离源码/开发依赖/core保留.tmp。deva只读，无真实用户home写入。
