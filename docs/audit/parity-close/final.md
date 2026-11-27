# 本轮结果（部分交付，未完成项明确保留）

89项：81已实现且可用、0只有界面、4未移植，另4不适用；无待判定。四个未移植组合项F06/F62/F64/F84已有部分代码但没有完整验收。JSON逐行计数核对通过，所有89行有evidence/port_anchor/deva_refs。未重新验收其余81项。

开场HEAD和远端d105a24，工作树干净，baseline.txt原始记录；既有提交保留。

本执行提交：c727879 计数/证据纠偏；3afc9cc Linux非macOS实窗标志验证与暗亮截图；177b3ac 机器人搜索及配置字段，真实键鼠和配置读盘。deva只读、AI_UPPER_HOME=/tmp、无依赖pin及既有测试断言更改。

推送原文：
```
To github.com:fanchcho/ai_upper.git
   d105a24..c727879  develop -> develop
c727879a649a9c5c7ebcd97d87686d10f21d5a97 refs/heads/develop
To github.com:fanchcho/ai_upper.git
   c727879..3afc9cc  develop -> develop
3afc9cc9dbeb4f7610bbe618cb93ab375b76b78c refs/heads/develop
To github.com:fanchcho/ai_upper.git
   3afc9cc..177b3ac  develop -> develop
177b3ac607f2434bf4cde040c99608c903dddc49 refs/heads/develop
```

最终重跑命令：
```
AI_UPPER_HOME=/tmp/ai-upper-parity-close-regression2 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests -q --basetemp=$PWD/.tmp/parity-close/pytest2
```
结果：1480 passed / 9 skipped / 0 failed，566.90秒；full-retry.log。首次全量full.log在test_bot_roundtrip.py:48 processEvents段错误，没有最终计数；单跑bot-isolation.log 1 passed。未预载Qt、未改断言，间歇/顺序崩溃原因未完成定位，不能忽略。

未完成：F62完整独立详情、角色/会话范围多选、扫码邀请全流程；F64真实手机QR/LAN/relay及跨设备会话往返。这些是实现欠项，不是缺凭据就能解释，也不标不适用。

未验证：F84真实fcitx preedit，保留remaining-seven/ime-plugin.log错误，合成QInputMethodEvent仅是合成；F06 macOS成功态，宿主Linux只验证非mac分支。外部渠道有效凭据/推送仍沿用未验证，不制造替身成功。
