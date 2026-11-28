# 环境边界收尾结果

起点41e8894，status空，没有前轮未跟踪残留。五项分别提交：c7c02dc崩溃复跑、39ccd55相位、394282e输入法、1ab7fb2原生选择器、90f60b6外部边界。均正常push origin develop，无force/tag/pin修改。

本轮全量实际重跑：
```
ulimit -c unlimited
AI_UPPER_HOME=/tmp/ai-upper-environment-full PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests -q
1486 passed, 9 skipped in 557.39s (0:09:17)
```
退出0，1486 passed / 9 skipped / 0 failed。没有预载Qt，app/src及app/tests相对起点零差异。

两处历史Python崩溃五轮专项每轮3 passed，仍未归因；全量通过不能证明修复。本轮另发现Electron core，NT_PRPSINFO身份记录core-identity.log，原件移至.tmp/environment-closeout/probe.core（538877952字节）；确切触发点未定位，不说成pytest崩溃，也不删证据。此前core照旧保留。

未跟踪文件处置：有价值的日志、报告、图像和探针脚本均提交；下载包、隔离schemas、运行profile和core保留在忽略的.tmp/environment-closeout下，不删除，不提交大体积运行环境。没有修改deva。

未完成：Python历史崩溃归因；Electron新core触发点归因；正文/阴影像素归零；F84真实preedit/commit；原生文件选择器成功返回；真手机/第二设备/公网relay/移动网络/外部推送/系统主屏幕安装。F06 macOS无宿主未验证。各项真实失败原文、实验说明和路径分别见crash.md、extensions-rounding.md、ime.md、chooser.md、external.md。
