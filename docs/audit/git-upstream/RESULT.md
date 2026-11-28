# 本轮交付与验收边界

版本事实已钉到上游main013c5d7，并与本地定制副本分开；分支列表验收已完成；提交弹窗的已证实样式错误已修。**整页逐像素复刻和全部高级Git交互未完成**，不得将这份增量交付写成全页无差异。

| 用户要求 | 结果与证据 |
|---|---|
| 不回退2595779、只读对账 | 初始HEAD/远端2595779、工作树干净；VERSIONS.md；收尾祖先检查exit0见final-version-readback.json |
| local/latest/声明基线分开 | VERSIONS.md、upstream.json、clone.log。收尾本地外部变化8acfbd4单列，不冒领 |
| 确认第二张截图 | DIFFERENCES.md，明确84978b1ef406aa95旧Git大表单，不替换成自生成截图 |
| 结构/缺项/多余项/文案/颜色五类 | DIFFERENCES.md含固定最新上游与QML行号，保留不适用的旧本地定制说明纠正 |
| 暗亮前后截图及样本 | style-before与style-final同1280×1060、相同fixture内容；page-samples.json；中间style-after明确仅为过程记录 |
| 具体分支与跟踪、远端排除符号引用 | BRANCHES.md、after-dark/light.json、after-dark/light-branches.png |
| 多项滚动/空态/切换读回 | 40分支滚轮，contentHeight1656、height1044；contentY>623；暂无分支；git独立读回feature/a |
| 输入/Fetch/真实提交 | style-final/*-interaction.json：FETCH_HEAD、new-menu-branch、a6dcb8e、status空 |
| 每步提交推送 | 8ee1a55版本；9864fab分支；8fcbe32样式；PUSHES.txt |
| 全量回归 | 最终代码1486 passed / 9 skipped / 0 failed，558.47秒，工具exit0；pytest-final.log |

本轮应用交互均使用/tmp隔离home及本地真实git/bare仓库；Qt QTest真实事件经过完整Main.qml/ShellBridge。模型transport未参与Git动作，不把它作为模型成功证据。未修改测试断言、依赖pin、Theme token、公共SettingsButton、deva原目录或真实~/.ai_upper。

focused/dark-commit-filled.png、light-commit-filled.png补录实际键盘输入后的聚焦输入框，能看见文本、描边与光标。focused/*-interaction.json仍由后续真实提交及git log/status独立读回确认；不是仅设置QML属性。focused-samples.json为聚焦描边和已启用主按钮取样。

最初pytest-full.log为1486 passed / 9 skipped / 0 failed，559.71秒，工具exit0；但期间发现并修正了提交框样式，它不是冻结在最终代码上的一轮。最终代码运行使用pytest-final.log，命令：

```sh
AI_UPPER_HOME=$(mktemp -d /tmp/ai-upper-git-final-tests-XXXXXX) QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONFAULTHANDLER=1 .venv/bin/python -m pytest app/tests -q
```

最终代码对应8fcbe32785bd02056a32a784c67edcb097d877d9；该轮启动前全部应用改动已落盘，之后只写证据文档。提交前后应用代码树会核对一致。

最终原文：`1486 passed, 9 skipped in 558.47s (0:09:18)`，进程退出0；没有本轮段错误。未预载Qt、未改既有测试文件。`git diff 8fcbe32 -- app/src app/tests app/pyproject.toml`为空，app树为`46daca7f0faf1fb54ef2c216512249fa43ea5526`。这仅证明本轮未复现历史崩溃，不宣称历史两处已归因或修复。

未完成/未验证逐项见DIFFERENCES.md末节：用户实际客户端版本、上游Electron同DPR对照、强制删除第二次确认和提交数、冲突toast快捷操作、未覆盖的高级真实交互、浅色warning低对比度、引擎阴影残差。没有对应macOS环境，不能将Linux截图冒充用户真机结果。旧已验收功能与环境受限项没有重跑或升级结论。
