# QML 三栏壳最小里程碑
改动：新增 `app/src/qml/{Main,Theme}.qml`+`qmldir`（RowLayout 三栏：264px 侧栏 / 300px 会话 ListView / 正文 TextEdit，3 条假会话）、`app/src/qml_shell.py`（markdown 渲染进 `QQuickTextDocument`，headless 等首帧后 `grabWindow()`）；`main.py` 加 `AI_UPPER_UI=qml` 分支，未设置时 WebEngine 路径不变（实跑 `DEVA WEB OK ... bridge=True`，EXIT 0）。
- 原始输出：`out/qml-shell/run.log`（`bash out/qml-shell/run.sh` 生成）
- 富文本：`QML OK ... sessions=3 plain=False png=/home/agent/shared_workspace/py_upper/out/qml-shell/shot.png size=1280x820`，EXIT 0
- 纯文本兜底：`AI_UPPER_QML_PLAIN=1` → `plain=True`、`shot-plain.png`，EXIT 0
- 段错误：未复现（渲染器用表格/1px 空 frame 画线）；`AI_UPPER_QML_PLAIN=1` 为保留兜底，已实跑
- PNG 绝对路径：`/home/agent/shared_workspace/py_upper/out/qml-shell/shot.png`（1280x820，113742 字节）
- pytest（`app/` 下 `python -m pytest tests -q -ra --tb=long`，用例无删改）：**1123 passed, 5 skipped**，EXIT 0
