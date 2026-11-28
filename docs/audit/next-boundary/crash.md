# 两处历史段错误：新增栈定位，根因仍未完成

环境与通过轮一致：PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software，AI_UPPER_HOME=/tmp/ai-upper-crash-next-N，ulimit -c unlimited，LD_LIBRARY_PATH仅既有wm运行库。未预载Qt，未改测试。

三轮 .venv/bin/python -m pytest app/tests/test_bot_roundtrip.py app/tests/test_qml_links.py -q：3 passed，耗时6.83/5.83/6.23秒，退出均0。没有新core。

用隔离gdb对既有.tmp/phone-evidence/crash/pytest-qml-links.core取info proc cmdline、info proc mappings、thread apply all bt，完整输出qml-core-gdb.log（该日志因qml-*.log选择已随前一个本地回合提交入库，归属本专题，不冒领为回合证据）。gdb显示SIGSEGV；主线程#3 QCoreApplication::notifyInternal2，#4 QTimerInfoList::activateTimers，#9 QEventDispatcherGlib::processEvents，#10/#11 QtTest。信号处理器raise位于#0/#1。不是直接崩在QTextDocument删除函数；这只能将故障时刻定位到事件/定时器投递，不能证明接收对象是否已释放。

源码核对：test_qml_links.py:143是QTest.mouseClick，finally为ticker.stop/window.close/engine.deleteLater；deleteLater异步销毁使“前一个测试的延迟事件或对象寿命”仍是待证假设。该栈没有接收对象类型、地址的有效寿命证据，不能据此改析构顺序。未排除QTextDocument或其owner间接悬挂，只排除“已获得文档析构直接故障栈”的说法。

test_bot_roundtrip.py:48为qapp.processEvents；旧faulthandler在docs/audit/parity-close/full.log，后台HTTP初始化线程与主线程processEvents并存，不能将后台线程存在当根因。本次未找到可明确归属于该bot崩溃的core，无法给其原生栈。其finally没有显式host.shutdown而只close controller等是生命周期审查线索，非证据充分的修复依据。

结论：两处仍未归因、未复现、仍属风险。下一步需要可重复故障及带符号的Qt接收对象/定时器所有者记录，或bot对应core；不能用三轮通过宣称修复。本轮无生产改动。
