# 单实例独立复核

保留外部提交 4bee356，不将提交自述当作验收。原版 main/index.ts:276-286 的第二实例唤起机制，移植为数据目录 QLockFile 与 QLocalServer/QLocalSocket；启动时先取锁，再构造设置/宿主/窗口，避免第二实例启动调度器。

本轮真实复核：`AI_UPPER_HOME=/tmp/ai-upper-recheck-single QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests/test_single_instance.py app/tests/test_py38_compat.py app/tests/test_qt_compat.py -q --basetemp=$PWD/.tmp/final-port/compat-recheck`

结果 20 passed in 8.96s，其中 single-instance 启动两个真实应用进程，第二进程退出码 0，第一个收到真实 socket 激活并打印 SINGLE INSTANCE ACTIVATE。offscreen 不具备真实窗口管理器焦点语义，平台 raise/requestActivate 的视觉效果未验证。源码经 Qt 兼容层惰性构造，不含空 QObject/Signal 替身。
