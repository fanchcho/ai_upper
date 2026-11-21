# 本次会话（2026-11-21）复验证据

不是新做一遍删除，而是**在 HEAD `b98d59e` 上独立复验**上一轮（`a191a9c`…`4db9671`）的删除结论。

- `logs/`：全部原始命令输出（编号即引用号，报告 §9 逐条对应）
- `shots/`：18 张 offscreen 实拍 PNG + 1 张 Essentials venv 启动图（1280×820）

## 生成方式（关键命令）

| 日志 | 命令 |
|---|---|
| `01-grep-all.log` | `grep -rnE 'QtWebEngine\|QtWebChannel' .`（排除 out/.git/build/dist/.venv/deva/.cache） |
| `02-ast-imports.log` | Python `ast` 解析 190 个 py 文件的 `Import`/`ImportFrom` |
| `03-essentials-imports.log` | `/tmp/qwe-verify-venv`（只有 `PySide6-Essentials`+`shiboken6`）逐个 import |
| `04-essentials-launch.log` | 同 venv 跑 `app/src/main.py`，`AI_UPPER_HOME=/tmp/qwe-verify-home` |
| `05/06/34-pytest-*.log` | `cd app && env -u AI_UPPER_HOME -u DEVA_HOME .venv/bin/python -m pytest tests -q` |
| `13-build-head.log` | `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tools/build.py --target linux-arm64` |
| `25-build-baseline.log` | 同命令，cwd=`/tmp/qwe-baseline-src`（`1d53e4a` 的独立检出，pin 用 `PySide6==6.11.2`） |
| `36/38` | 基线产物 `find -iname '*WebEngine*'` 与两侧 `du -sb/-sh` |
| `37-baseline-packaged-launch.log` | 基线产物 headless 实跑（对照，证明两边都能 `QML OK`） |
| `39-reconcile.log` | 对账快照：branch / log / status / diff --stat |
| `40/41/43/44` | 死指令与 CI 扫描、STAGE6 死命令实测、最终汇总扫描 |

## 时间戳

全部日志生成于 2026-11-21 10:00–11:10（+0800）。`shots/` 与 `logs/10-qml-pages.log` 同批。
