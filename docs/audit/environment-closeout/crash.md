# 历史崩溃复跑

在 41e8894 应用代码上，连续5个独立进程执行：
```
AI_UPPER_HOME=/tmp/ai-upper-crash-retry-N PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests/test_bot_roundtrip.py app/tests/test_qml_links.py -q
```
每轮3 passed，分别6.26/6.09/5.84/5.90/6.31秒，退出0。ulimit -c unlimited，未预载Qt、未改断言。日志 crash-1.log 到 crash-5.log、退出码 crash-exits.log。没有新崩溃，因此没有新的 faulthandler 崩溃栈/core，不能伪造。历史栈 docs/audit/remote-qr-phone/full-regression.log 与 core .tmp/phone-evidence/crash/pytest-qml-links.core 保留。

结论：两处均未复现、未归因，仍属风险。本轮无足够证据定位实现错误，因此没有盲改生命周期或断言。后续全量结果另记。
