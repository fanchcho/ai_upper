# 多选界面性能现场核查（2026-11-25）

结论：确认左栏右键 Select 后的多选态，未复现 120 会话下单勾选/全选卡顿；复现并修复同一多选条的批量归档重复全量发布和中间正文渲染。不能据此宣称用户原始勾选症状已经解决。

## 范围和验收

- [x] 从当前 develop 磁盘重新对账，不沿用以前性能报告结论。
- [x] 通过 Studio clarify 确认多选态入口（当前运行没有 bot_decision_request）。
- [x] 相同真实 QML 窗口、相同夹具、相同鼠标事件和计时方法修复前后测量。
- [x] 最小修复批量归档/移回重复发布；保持失败计数、退出选择和单条操作语义。
- [x] 相关 QML、bridge、会话 ViewModel 和存储测试通过。
- [ ] 用户实际数据/桌面上的单勾选卡顿：未复现，原因尚未验证。

本轮未访问 deva，未改依赖 pin，未 push、未建分支。运行的 AI_UPPER_HOME 均为 /tmp/ai-upper-picker-*；其余新增临时文件在仓库 .tmp/picker-engineering。

## 磁盘对账与处置

执行命令：`pwd`、`git branch --show-current`、`git status --short`、`git log --oneline -n 20`、`git stash list`、`git ls-files --others --exclude-standard`、`git diff --stat`、`git reflog -n 8 --date=iso`。

输出：实体路径 /home/agent/shared_workspace/ai_upper，分支 develop，起点 a27ee63；受控文件 diff 为空、stash 为空。最近四条为 a27ee63 插件集成、8de00f0 QML 插件设置、c82d564 原生控制/设置写入、74384d0 窗口装饰修复。完整最近 20 条在 `.tmp/picker-engineering/log-before.txt`。

`git ls-files --others --exclude-standard app` 无输出。`git ls-files app/src/qml` 有 20 个受控文件；没有残留独立探针脚本。`rg -n 'probe|perf_counter|elapsed|benchmark' app/src/qml --glob '*.qml'` 仅命中 Main.qml:80 的历史截图注释，没有运行时测量代码。

原始状态和未跟踪清单分别保存为 status-before.txt、untracked-before.txt；逐文件保留决定（路径、大小、依据）在 artifact-decisions.json。现存未跟踪文件集中于 .tmp 和 out：包括本地 Qt 库、历史截图、日志、测量脚本和历史 checkout。保留这些证据和工具，不凭名称认定为前两轮产物；无法从磁盘证明哪些具体文件属于被叫停执行。受控 out/conversation-picker-lag 下同样存在历史探针，保留已提交证据，不加载其结论。

处置：没有回退受控代码、没有删除未知历史产物；在本地 `.git/info/exclude` 明示排除 `/.tmp/`、`/out/` 的未跟踪文件（受控文件不受影响），使后续修改清单可审查。此为保留与隔离，并非声称物理删除了历史输出；可删除这两条本地规则恢复显示。

## 入口和同步数据流

- Main.qml:104–106 保存 selectMode/selectedSessions，当前选择状态在 QML 自身；没有专门的 Python selection ViewModel。
- Main.qml:619 起 sessionList 是 ListView，model 为 listedSessions（182），来源为 ShellBridge._publish 写入 sessions/archivedSessions 属性。
- Main.qml:665 点击：右键打开菜单，选择态左键调用 toggleSelect，普通左键调用 activate（本轮不改普通切换路径）。
- Main.qml:1855 startSelect → 1860 toggleSelect：复制 JS 数组、indexOf/splice/push、重新赋值 selectedSessions；661 的 selected 绑定更新可见行的勾选和背景。
- Main.qml:1873 toggleSelectAll：遍历 listedSessions 构造 id 数组。没有 Python slot、IPC、逐行 setData/invalidate、modelReset 或读盘调用。`rg -n 'QAbstract|setData|modelReset|invalidate' app/src/qml_shell.py app/src/qml/Main.qml app/src/qml/ThreadRow.qml` 无匹配。
- ThreadRow.qml:36 勾选框、60 Avatar、70 起普通 Text。Avatar.qml:22 为本地 SVG Image；每行无 TextEdit/QTextDocument，也没有勾选动画。
- 批量条 Main.qml:1885 archiveSelected 原先对每个 id 同步调用 ShellBridge.archiveSession/unarchiveSession。QML context property 是同进程 QObject slot，运行在 GUI 线程，不经过 Web IPC。
- ShellBridge.archiveSession:669 → ChatHost.set_archived（mvvm/webui/host.py:378）→ ChatSessionStore.set_archived（mvvm/services/chat_session_store.py:448）→ save。host 沿用忙碌检查，壳沿用失败反馈。
- 原先每次归档当前会话都会 `_rows`、回退到下一会话、`_render`，随后 `_publish` 全量写 sessions 和 archivedSessions。当前发布位置 qml_shell.py:1435，行投影 1414 → qml_shell_sessions.py:168 load_sessions；这是整份 QVariantList 替换和全量会话投影，不是 QAbstractItemModel 的显式 reset 信号。

完整修复前源码存档为 Main-before.qml 和 bridge-before.py，来自 `git show HEAD:<path>`（本轮提交前 HEAD=a27ee63）。新方法 archiveSessions 在 qml_shell.py:703，逐项调用原 host 服务，只在批次结束后执行一次最终回退/渲染与一次 publish。没有把共享 store 移到后台线程。

## 实测方法和复现命令

工作目录均为仓库根。脚本 `.tmp/picker-engineering/measure.py` 使用现有 test_qml_context_menu._build_window：120 条真实落盘会话、真实 ShellBridge/host/store、Main.qml、30 ms ticker。QTest.mouseClick(delay=0) 命中右键菜单 Select、会话行、全选和归档按钮；每次记录事件派发返回及 processEvents + grabWindow 完成时间，截图断言非空。勾选和全选各十次，批量归档每个全新进程一次，共修复前后三组独立运行。帧指标是 offscreen 抓帧完成时间，不是物理显示器呈现延迟。

```bash
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" \
AI_UPPER_HOME=/tmp/ai-upper-picker-bootstrap PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python .tmp/picker-engineering/measure.py .tmp/picker-engineering/after
python .tmp/picker-engineering/repeat.py
```

measure.py 内用 mkdtemp(prefix='ai-upper-picker-') 将每次用户数据隔离到 /tmp。repeat.py 在 finally 中恢复修复源码，前后使用同一 measure.py。初次加载失败 `ImportError: libEGL.so.1`，通过仓库已有 `.tmp/wm/usr/lib/aarch64-linux-gnu` 设置 LD_LIBRARY_PATH 后成功，未装包或修改依赖。

初次测量（ms）：

| 操作 | 修复前抓帧完成 | 修复后抓帧完成 | 口径 |
|---|---:|---:|---|
| 单行勾选 | 1.081 | 1.038 | 十次中位数 |
| 全选/取消全选 | 2.540 | 2.197 | 十次中位数 |
| 批量归档 120 条 | 3798.382 | 209.767 | 每进程一次 |

单勾选/全选的 `_rows`、`_render`、`_publish` 计数均为零；归档从 240/120/120 降为 2/1/1。before*.json、after*.json 保存全部原始样本，before.png/after.png 保存实际多选界面。

## 验证与限制

```bash
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" \
AI_UPPER_HOME=/tmp/ai-upper-picker-tests QT_QPA_PLATFORM=offscreen \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
app/tests/test_qml_context_menu.py app/tests/test_qml_shell.py \
app/tests/test_chat_sessions_vm.py app/tests/test_chat_session_store.py \
--basetemp=/tmp/ai-upper-picker-pytest -q
```

输出：`87 passed in 61.63s (0:01:01)`，退出码 0，完整日志 `.tmp/picker-engineering/pytest.log`。新增真实鼠标批量归档/移回断言，以及 busy/missing/空批次、当前会话回退、发布次数断言。`git diff --check` 无输出。

尚存同步文件保存成本，120 条约 210 ms；更大库和慢盘未验证。普通勾选/全选在该夹具下未卡顿，用户现场症状不能宣布已修复。桌面 GPU/实际长正文/并发流式输出组合未验证。截图有中文缺字方框，故只证明真实界面运行、勾选和操作条状态，不证明字体视觉对齐。未运行全项目 pytest，未操作 CI。

三组重复实测输出（`python .tmp/picker-engineering/repeat.py`，退出码 0）：

```text
before: batch grab ms = [3496.778, 3645.206, 3798.382], median = 3645.206
after: batch grab ms = [214.631, 127.581, 209.767], median = 209.767
```
