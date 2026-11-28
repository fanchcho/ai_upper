# 三项边界推进回执

基线379f435fd770207cc9541b01cfcd55d560f1ecba与远端相同，工作树干净；无外部提交或残留覆盖。生产app目录相对基线diff为空，依赖pin与既有断言未改。deva未改，运行home均/tmp，未访问真实用户配置。

|专题|提交及即时远端SHA|证据与结论|
|---|---|---|
|崩溃|8298a6ad383b3a3df414a015843acd7457053368|crash.md/core-gdb.log/receiver-instructions.log：QML直接故障为空私有指针的0x58偏移读取，根因仍未归因；bot无可归属core。五轮正序及逆序均3 passed，只计未复现。|
|相位|183d7701b46977f4cc65d6e5015f23c0c4102088|phase-matrix.json及暗亮matrix图，正文与阴影未归零；详见extensions-rounding.md新增节。|
|Wayland|fc27ef46812afa64a95ec201524a6b2a75d5a675|wayland.md、nested/、nested-dbus.log、wayland-independent.json：嵌套Weston的真实Wayland键盘→fcitx→中文提交→本地fixture回合及重开读盘通过；不扩大到物理桌面或原生text-input协议。|

三次push原文在push-crash/pixel/wayland.log。所有实验均为真实渲染/进程/core，只有模型端是明确标识的本地fixture。

全量命令：ulimit -c unlimited；AI_UPPER_HOME=/tmp/ai-upper-boundary-full PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests -q。未预载Qt。full.log首次完整运行：1486 passed, 9 skipped in 557.03s (0:09:17)，exit0，0 failed，无本轮段错误；没有用重跑覆盖首次失败。测试与独立实验并行，生产代码及断言始终未变。

未完成：两处历史段错误的根因、稳定最小复现与全前序顺序二分；正文/阴影跨引擎像素归零。未验证：物理Wayland桌面及原生text-input协议、F06 macOS、真手机扫码、第二台物理设备LAN、公网relay/移动网络、外部推送、iOS/Android系统级安装、真实外部模型；缺对应环境/设备/凭据，不用本机fixture替代。

工作树新增文件全部归档；隔离运行依赖留在.tmp/remaining-boundaries以便复现。Weston已终止，退出日志追加保留。首轮嵌套启动退出127但无有效stderr，已纠正文档，不能猜测其失败原因。
