# 历史段错误：故障指令已细化，根因未归因

五轮正序 test_bot_roundtrip.py + test_qml_links.py，各3 passed；一轮逆序亦3 passed。crash-1..5.log/exit、reverse.log/exit保存原文。环境PYTHONFAULTHANDLER=1、offscreen、software、AI_UPPER_HOME=/tmp/ai-upper-boundary-*，ulimit -c unlimited，无Qt预载，无断言改动。只能记为未复现。

既有core .tmp/phone-evidence/crash/pytest-qml-links.core，使用 .tmp/deep-boundary/runtime/usr/bin/gdb -batch .venv/bin/python-real CORE，thread apply all bt full / frame 3 / info registers / x/20i $pc-56 / x/4gx $x19。本轮原文core-gdb.log、receiver-instructions.log。

新证据：notifyInternal2+24把receiver存入x19；+28从receiver+8读私有指针；+40加0x58；+56执行ldar x21,[x0]时x0=0x58。receiver=0x22c6e670，其+8确为0。与Qt6.11.2 qcoreapplication.cpp:1098-1105的receiver->d_func()->threadData.loadAcquire一致。直接故障是对空私有指针偏移0x58的读取；不是QTextDocument析构函数中的直接栈，也不是网络线程中的直接故障。

这不足以解释是谁清空/破坏receiver私有指针、为何定时器仍投递到该对象。没有该对象分配/销毁历史、Qt调试符号和稳定触发序列，无法证明UAF、Qt自身bug或Python ownership哪一个是根因；仍未归因，不称已修复。bot历史故障没有可归属core，只有processEvents的faulthandler记录，亦未归因。

顺序实验只覆盖两个目标模块的正/逆排列，尚未完成全套前序测试的二分最小化：当前没有稳定失败oracle，不能将通过的半集当排除证据。没有修改生产生命周期。需要失败轮记录对象身份及销毁轨迹后才能继续缩减。
