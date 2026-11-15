# QML TextEdit + 带边框 QTextFrame → 段错误（证据）

复现脚本：`out/qml-body/bordered_frame_segfault.py`

同一段 QML（`TextEdit { readOnly: true }` + `Component.onCompleted` 把文档塞进
`QQuickTextDocument`）、同一份「前文 / frame / 后文」结构，只有线的画法不同：

| case | 画法 | 退出码 | 截图 |
| --- | --- | --- | --- |
| `border` | `QTextFrameFormat.setBorder(1.0)` | **139**（SIGSEGV） | 无（进程在 grabWindow 前崩） |
| `border0` | `setBorder(0.0)` | 0 | `frame-border0.png` |
| `cell` | 1×2 表格，左列 3px 背景（引用竖线实现） | 0 | `frame-cell.png` |

执行（仓库根目录，2026-11-15）：

```
QT_QPA_PLATFORM=offscreen .venv/bin/python out/qml-body/bordered_frame_segfault.py --case border  ; echo $?  # 139
QT_QPA_PLATFORM=offscreen .venv/bin/python out/qml-body/bordered_frame_segfault.py --case border0 ; echo $?  # 0
QT_QPA_PLATFORM=offscreen .venv/bin/python out/qml-body/bordered_frame_segfault.py --case cell    ; echo $?  # 0
```

原始输出在 `segfault-{border,border0,cell}.log`，退出码汇总在
`segfault-summary.txt`。

## 因此得到的实现约束

- 正文层任何地方都不出现 `border > 0` 的 `QTextFrame`；
- 分隔线 / h2 下划线 = 固定 1px 行高的空块 + 背景色；
- 引用竖线 = 1×2 表格左列背景；
- 代码块 = 单列表格（单元格背景 + 逐边 1px 边框），不是 frame；
- 回归锁：`app/tests/test_markdown_document.py::test_no_rendered_frame_has_a_border`。
