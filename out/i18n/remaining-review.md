# 本轮收口清单

**本轮零未解释残留已达成。** 逐条依据、命令、stdout/stderr、截图和未验证项见 REPORT.md 的 2026-11-26 小节与 final/。

- [x] 742 条旧候选逐条复核：298 resolved / 444 out_of_scope / 0 needs_review；final/review-742.csv。
- [x] 当前 Python/QML 全仓候选扫描：129 resolved / 1949 out_of_scope / 0 needs_review；final/current-scan.csv。重跑：AI_UPPER_HOME=/tmp/ai-upper-final .venv/bin/python out/i18n/close/scan.py。
- [x] 工具卡正文在展示边界翻译；测试原工具对象/模型 payload/会话文件字节不变；159 个 display 模板英文展示无中文残留。
- [x] bootstrap 最小双语路径、verify 项名、GreetingService、构建提示；中英各 7 条实际执行，final/cli-results.json。
- [x] 旧 QWidget 主窗/设置/工具卡中英浅深 20 张截图；正文浅色16.41:1、深色13.12:1；final/screenshots.md、contrast.json。
- [x] QML Theme.qml 无 diff；同一已打开面板中英即时切换实测通过；final/live-settings.txt。
- [x] 每语言 2251 键，资源缺键0；Python翻译调用 846 处，缺键/缺参0。
- [x] 全量 pytest：1414 passed, 9 skipped in 350.50s (0:05:50)；exit=0，final/pytest-final.txt。
- [ ] macOS/Windows 原生窗口、真实发布包与真实系统 locale 更改：未验证，原因详见报告。这些不是已完成测试。

现有 CLI 无 --json / 确认提示入口；没有新增或虚构相应操作。CI annotation 字段和模型协议字段保留。
