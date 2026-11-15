# QML 三栏壳最小里程碑

改了什么：新增 `app/src/qml/Theme.qml`、`app/src/qml/Main.qml`（RowLayout 三栏：264px 侧栏 / 300px 会话 ListView / 正文 TextEdit）与 `app/src/qml/qmldir`；新增 `app/src/qml_shell.py`（3 条假会话、`ShellBridge` 把 markdown 渲染进 `QQuickTextDocument`、headless 等首帧后 `grabWindow()`）；`app/src/main.py` 加 `AI_UPPER_UI=qml` 分支，未设置时 WebEngine 路径逐字未动。

实跑（`bash out/qml-shell/run.sh`，原始输出见 `out/qml-shell/run.log`）：
- 富文本：`QML OK platform=offscreen title='ai_upper · QML 壳' sessions=3 plain=False png=.../out/qml-shell/shot.png size=1280x820`，EXIT 0
- 纯文本降级：同参数加 `AI_UPPER_QML_PLAIN=1` → `plain=True`、`shot-plain.png`，EXIT 0

段错误：本轮**未复现**（正文渲染器已用表格/1px 空 frame 表达线，见 out/qml-body/SEGFAULT-EVIDENCE.md），故未触发退化；`AI_UPPER_QML_PLAIN=1` 为保留的纯文本兜底开关，已实跑通过。
WebEngine 旧路径回归：`AI_UPPER_HEADLESS=1 python app/src/main.py` → `DEVA WEB OK ... bridge=True`，EXIT 0。
PNG 绝对路径：`/home/agent/shared_workspace/py_upper/out/qml-shell/shot.png`（1280x820，113742 字节；PNG 头校验见 run.log）。
pytest（`app/` 下 `python -m pytest tests -q -ra --tb=long`，全量未删未跳）：**1123 passed, 5 skipped**，EXIT 0。
