# Deva → py_upper 迁移计划（契约主轴：158 个 IPC 通道）

> 状态：第一阶段（骨架 + 首批业务 + 首批界面）的**计划与契约文档**。
> 本文只回答「Deva 的哪个能力，在新工程落到哪个模块、怎么处置、有什么坑」，
> 不代表表中标 P1 的条目已经实现。表里的「处置」是**目标**，不是现状；
> 实现进度以阶段收尾时的「已完成 / 未完成」清单为准。

- 参考工程（只读）：`/home/agent/shared_workspace/deva`，commit `109937f85b5d1b0c0a95c8875390e07ddccdf544`（2026-11-12）
- 目标工程：`/home/agent/shared_workspace/py_upper`（PySide6 6.11.2 + Qt 原生 + MVVM + Cython 打包链）
- 生成方式：`audit-tools/gen_migration_plan.py`（通道清单来自 `audit-tools/scan_deva_ipc.py` 的全量扫描，
  断言「158 条 / 154 handle / 4 on」后才出表，行数由脚本核对）

## 0. 口径对齐：153 / 154 / 158 / 164 是怎么来的

四个数字都真实存在过，混淆点在于**数的是什么**。以本表为准的口径是 **158 个唯一通道**。

| 数字 | 含义 | 来源 | 是否作为契约 |
|---:|---|---|---|
| 153 | 早期统计口径下的 `handle` 条目数；本次全量扫描**复现不出** | 第一版统计（脚本已不存，无法回溯） | 否，口径来源不明，已作废 |
| 154 | 主进程 `ipcMain.handle(...)` 的**注册条目数** | 全量扫描（允许跨行） | 是，158 的子集 |
| 4 | 主进程 `ipcMain.on(...)` 的注册条目数 | `config.ts:86`（`config:get-sync`）、`terminal.ts:100/104/108`（`terminal:input`/`resize`/`dispose`） | 是，158 的子集 |
| **158** | **主进程唯一通道数 = 154 handle + 4 on** | 全量扫描，去重后 158 | **是，本表主轴** |
| 164 | 「handler 条目数」：158（主进程）+ 6（Web 侧等价注册） | `apps/web/src/backend/index.ts:84-89`：`window:minimize`、`window:toggle-maximize`、`window:close`、`window:is-fullscreen`、`window:set-overlay`、`app:get-platform` | 否，Web 部署形态的重复实现 |

三点补充，避免后续再被数字带偏：

1. **121 / 125 是错误扫描的产物，已作废（本脚本实测：125 条、漏 33 条）。** 只用单行正则
   `ipcMain\.(handle|on)\(\s*['"]` 匹配时，跨行写法（`ipcMain.handle(` 换行后才是通道名字面量）
   全部漏掉，主进程只剩 125 条（含 4 条 `on`），差的 33 条正是 `chat:*`（18 条）、`deliverables:*`（4）、
   `git:*`（4）、`remote:*`（2）、以及 `fs:paste-attachment`/`mcp:set-secret`/`secrets:set`/
   `tasks:preview`/`tasks:run-now`。改成 `re.S` 跨行匹配后是 158，复现命令见下。
2. **158 是通道数，不是 handler 数。** 4 条 `ipcMain.on` 是单向事件（同步读配置、终端输入/改尺寸/销毁），
   没有返回值。迁移时它们不是「请求-响应」形状：`config:get-sync` 在 Qt 单进程里退化为直接同步读，
   终端三条随终端域一起延后（P3）。
3. **Web 侧的 6 条不是新能力。** `apps/web/src/backend/index.ts:84-89` 注册的正是主进程 `main/index.ts:301-318`
   那 6 条窗口/平台通道的 Web 替身（返回 `undefined`/`false`），属于把桌面主进程搬到浏览器壳里时的占位实现。
   它们不增加契约，但说明「窗口控制」在新工程里同样应退化到 View 层直调 Qt，而不是做成服务。

复现命令（只读 Deva，不改动）：

```bash
python3 audit-tools/scan_deva_ipc.py            # 重扫并打印：entries 158 / unique 158 / handle 154 / on 4
python3 audit-tools/gen_migration_plan.py       # 断言 158 后生成本文
```

## 1. 158 行契约映射表

列含义：

- **通道**：Deva 主进程实际注册的 IPC 名（`ipcMain.handle` 或 `ipcMain.on`）。
- **Deva 位置**：`源文件:行号`，行号是通道名字面量所在行（跨行写法取 `ipcMain.` 那一行）。
- **新工程落点**：按 py_upper 现有 MVVM 分层的命名（`app/src/mvvm/services|models|view_models|views`），
  `services/x.py::Class.method` 是建议形态；标「无（不迁移）」的是明确不搬的。
- **处置**：`直搬` / `重写` / `丢弃` / `待定`，括号里是阶段（P1 本阶段、P2、P3）。
- **依赖**：新实现要依赖的模块或外部能力。
- **风险**：迁移时最容易踩空的地方；「待定」行写的是为什么现在定不下来。

### 1.1 对话与消息（chat）（31 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `chat:send` | `main/services/chat.ts:6090` | `services/chat_service.py::ChatService.send` | 重写（P1） | provider_gateway / chat_session_store / secrets_vault | Deva 的 send 是把模型循环、工具、压缩、子智能体都写在一个函数里的数千行；P1 只重写「单轮文本流式 + 错误归一 + 重连」这条主干，工具循环见 P2 清单，未实现的部分不得假装可用 |
| `chat:insert` | `main/services/chat.ts:6093` | `services/chat_service.py::ChatService.insert` | 丢弃（本阶段） | 会话消息数组 | 编辑器「插入消息」是 Lexical 编辑器专属交互，Qt 原生输入区没有对应物；P2 若做选区插入再单独评估 |
| `chat:withdraw-inserts` | `main/services/chat.ts:6094` | `services/chat_service.py::ChatService.withdraw_inserts` | 丢弃（本阶段） | 同上 | 依赖 chat:insert 的存在，一并丢弃 |
| `chat:compact` | `main/services/chat.ts:6101` | `services/chat_service.py::ChatService.compact` | 待定（P2） | compaction + model-view 截取规则 | 压缩触发依赖 usage.input 与字符估算两套阈值，且摘要消息要参与「模型可见范围」计算；机制已读通但工作量独立，P1 不做 |
| `chat:create-session` | `main/services/chat.ts:6151` | `services/chat_session_store.py::ChatSessionStore.ensure_session` | 重写（P1） | data/chats 目录布局 | Deva 新建只入内存与索引、首次 save 才落盘；若改成建即落盘，会多出空会话文件并让左侧列表出现空标题项 |
| `chat:set-model` | `main/services/chat.ts:6165` | `services/chat_session_store.py::ChatSessionStore.set_model` | 重写（P1） | config.models.providers + model_resolver | 会话内模型引用是 `providerId:modelId` 字符串且「空串 = 回落全局默认」；用 null 表达会导致旧数据读不出来 |
| `chat:set-effort` | `main/services/chat.ts:6177` | `services/chat_session_store.py::ChatSessionStore.set_effort` | 重写（P2） | provider_gateway 思考参数 | 思考等级要映射到三家不同字段（anthropic thinking / openai reasoning_effort / 兼容端点），P1 不做思考 UI，先存字段 |
| `chat:set-focus` | `main/services/chat.ts:6190` | `services/chat_session_store.py::ChatSessionStore.set_focus` | 重写（P1） | workspace_guard.trust_root | focusRoot 同时是终端 cwd 与权限作用域键；P1 只存值并登记受信根，终端域在 P3 |
| `chat:rename-session` | `main/services/chat.ts:6207` | `services/chat_session_store.py::ChatSessionStore.rename_session` | 重写（P1） | _index.json | 只改标题与索引，不动 updatedAt（Deva 的列表顺序语义）；动 updatedAt 会让重命名把会话顶到最前 |
| `chat:set-archived` | `main/services/chat.ts:6226` | `services/chat_session_store.py::ChatSessionStore.set_archived` | 重写（P1） | _index.json | 归档项在左侧列表默认隐藏，取消归档不改顺序；P1 界面只做隐藏/显示，不做「已归档浮层」 |
| `chat:list-sessions` | `main/services/chat.ts:6233` | `services/chat_session_store.py::ChatSessionStore.list_sessions` | 重写（P1） | _index.json + 目录扫描自愈 | 索引损坏时必须能扫描 chats/*.json 重建；只读索引会在索引丢失时显示空列表（Deva 的老 bug 已修，不要退回去） |
| `chat:load-session` | `main/services/chat.ts:6277` | `services/chat_session_store.py::ChatSessionStore.load_session` | 重写（P1） | compacted 拆分文件（.jsonl） | 压缩拆分文件缺失/损坏时 Deva 只载入主文件后续部分并把 notices 前移；Python 侧若直接抛错，长对话会在重开后打不开 |
| `chat:attachment-image` | `main/services/chat.ts:6285` | `services/media_store.py::MediaStore.read_attachment_image` | 待定（P2） | data/media/<sha256> | 附件图片外置为 blob 是 storage 格式的一部分，但 P1 的输入区不支持贴图，先不实现读取通道 |
| `chat:attach-session` | `main/services/chat.ts:6306` | `services/chat_service.py::ChatService.attach_session` | 待定（P2） | members | 成员会话是「一主对话多成员」模型，牵涉 parentId 过滤与删除级联；P1 单会话模型不引入 |
| `chat:resolve-proposal` | `main/services/chat.ts:6331` | `services/chat_service.py::ChatService.resolve_proposal` | 待定（P2） | proposals 边车 | 提案卡来自 propose_agent 工具，P1 没有工具循环，先没有可解析对象 |
| `chat:resolve-autotask` | `main/services/chat.ts:6381` | `services/chat_service.py::ChatService.resolve_autotask` | 待定（P3） | autotasks 边车 + tasks 域 | 定时任务全套在 P3；P1 不建空实现 |
| `chat:delete-session` | `main/services/chat.ts:6413` | `services/chat_session_store.py::ChatSessionStore.delete_session` | 重写（P1） | 拆分文件 + media blob 清理 | 删除要连带删 .compacted-*.jsonl；否则重开同 id 会把旧早期记录拼回来 |
| `chat:remove-member` | `main/services/chat.ts:6426` | `services/chat_service.py::ChatService.remove_member` | 待定（P2） | members | 同 chat:attach-session |
| `chat:abort` | `main/services/chat.ts:6466` | `services/chat_service.py::ChatService.abort` | 重写（P1） | provider_gateway（取消令牌） | 取消要同时打断 SSE 读取与退避等待：Deva 用 AbortSignal，Python 侧用 threading.Event + socket 超时；只在读取间隙检查会吞掉 60s 空闲窗口 |
| `chat:stop-subagent` | `main/services/chat.ts:6473` | `services/chat_service.py::ChatService.stop_subagent` | 丢弃（本阶段） | subagents 进程 | 子智能体是独立进程 + 后台状态边车，P1 没有；P2 工具域一起做 |
| `chat:reset` | `main/services/chat.ts:6485` | `services/chat_service.py::ChatService.reset` | 待定（P2） | 会话消息 + 边车清理 | 「重置」要清哪些边车（checkpoints/asks/summaries）需逐项对齐，P1 不做以免清掉数据 |
| `chat:delete-turns` | `main/services/chat.ts:6517` | `services/chat_service.py::ChatService.delete_turns` | 待定（P2） | 轮次边界判定（model-view） | 按轮删除要用「真实用户轮」判定并修剪边车；规则已读通，但 P1 界面没有轮次操作入口 |
| `chat:todos` | `main/services/chat.ts:6538` | `services/chat_service.py::ChatService.todos` | 丢弃（本阶段） | todos 日志 | 待办清单由 todo_write 工具产生，P1 无工具循环 |
| `chat:todo-cancel` | `main/services/chat.ts:6545` | `services/chat_service.py::ChatService.todo_cancel` | 丢弃（本阶段） | todos 日志 | 同上 |
| `chat:rewind-list` | `main/services/chat.ts:6566` | `services/chat_service.py::ChatService.rewind_list` | 待定（P2） | checkpoints + lastKnown/baselines | 文件检查点回滚需要写入前备份，P1 不做写入类工具，因此没有检查点可列 |
| `chat:rewind-preview` | `main/services/chat.ts:6576` | `services/chat_service.py::ChatService.rewind_preview` | 待定（P2） | 同上 | 同上 |
| `chat:rewind-apply` | `main/services/chat.ts:6592` | `services/chat_service.py::ChatService.rewind_apply` | 待定（P2） | 同上 | 同上 |
| `chat:rewind-undo` | `main/services/chat.ts:6684` | `services/chat_service.py::ChatService.rewind_undo` | 待定（P2） | 同上 | 同上 |
| `chat:ask-response` | `main/services/chat.ts:6751` | `services/chat_service.py::ChatService.ask_response` | 待定（P2） | asks 边车 + ask_user 工具 | 依赖工具循环，P2 |
| `chat:plan-response` | `main/services/chat.ts:6755` | `services/chat_service.py::ChatService.plan_response` | 待定（P2） | plans 边车 + exit_plan 工具 | 依赖计划模式，P2 |
| `chat:mount-response` | `main/services/chat.ts:6759` | `services/chat_service.py::ChatService.mount_response` | 待定（P2） | 挂载工作区卡片 | 依赖写入类工具触发的挂载卡，P2 |

### 1.2 Git 工作区（git）（24 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `git:available` | `main/services/git.ts:625` | `services/git_service.py::GitService.available` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:status` | `main/services/git.ts:638` | `services/git_service.py::GitService.status` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:diff` | `main/services/git.ts:681` | `services/git_service.py::GitService.diff` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:stage` | `main/services/git.ts:703` | `services/git_service.py::GitService.stage` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:unstage` | `main/services/git.ts:712` | `services/git_service.py::GitService.unstage` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:discard` | `main/services/git.ts:725` | `services/git_service.py::GitService.discard` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:commit` | `main/services/git.ts:740` | `services/git_service.py::GitService.commit` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:set-config` | `main/services/git.ts:756` | `services/git_service.py::GitService.set_config` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:branches` | `main/services/git.ts:770` | `services/git_service.py::GitService.branches` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:checkout` | `main/services/git.ts:797` | `services/git_service.py::GitService.checkout` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:create-branch` | `main/services/git.ts:807` | `services/git_service.py::GitService.create_branch` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:checkout-remote` | `main/services/git.ts:817` | `services/git_service.py::GitService.checkout_remote` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:merge` | `main/services/git.ts:827` | `services/git_service.py::GitService.merge` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:merge-abort` | `main/services/git.ts:838` | `services/git_service.py::GitService.merge_abort` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:delete-branch` | `main/services/git.ts:845` | `services/git_service.py::GitService.delete_branch` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:rename-branch` | `main/services/git.ts:859` | `services/git_service.py::GitService.rename_branch` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:delete-remote-branch` | `main/services/git.ts:867` | `services/git_service.py::GitService.delete_remote_branch` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:log` | `main/services/git.ts:878` | `services/git_service.py::GitService.log` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:init` | `main/services/git.ts:893` | `services/git_service.py::GitService.init` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:fetch` | `main/services/git.ts:900` | `services/git_service.py::GitService.fetch` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:pull` | `main/services/git.ts:909` | `services/git_service.py::GitService.pull` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:push` | `main/services/git.ts:918` | `services/git_service.py::GitService.push` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:generate-commit-message` | `main/services/git.ts:934` | `services/git_service.py::GitService.generate_commit_message` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |
| `git:cancel-commit-message` | `main/services/git.ts:1032` | `services/git_service.py::GitService.cancel_commit_message` | 丢弃（P3） | 系统 git 命令（QProcess） | Deva 用 Electron 的 child_process + 受信根校验；Qt 原生路线改用 QProcess 直调 git。P1 不做 git 面板；注意 --porcelain 解析与错误码语义要重新对齐，不能直接套 Node 的字符串处理 |

### 1.3 内置浏览器（browser）（16 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `browser:state` | `main/services/browser/host.ts:554` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:open` | `main/services/browser/host.ts:556` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:dock` | `main/services/browser/host.ts:561` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:close-session` | `main/services/browser/host.ts:566` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:preview-pinned` | `main/services/browser/host.ts:572` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:live-start` | `main/services/browser/host.ts:579` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:live-stop` | `main/services/browser/host.ts:582` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:pin` | `main/services/browser/host.ts:586` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:activate` | `main/services/browser/host.ts:590` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:close-tab` | `main/services/browser/host.ts:594` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:nav` | `main/services/browser/host.ts:598` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:menu` | `main/services/browser/host.ts:610` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:thumbnail` | `main/services/browser/host.ts:639` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:handoff` | `main/services/browser/host.ts:650` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:stop` | `main/services/browser/host.ts:654` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |
| `browser:ready` | `main/services/browser/host.ts:660` | `无（不迁移）` | 丢弃 | 无 | 路线已定：Qt 原生界面，不嵌 Chromium/WebEngine。内置浏览器（标签、钉住、缩略图、交接）没有 Qt 原生等价物；若日后需要浏览，只能外开系统浏览器，且 Deva 的「agent 操作浏览器」能力会整体缺失——这是路线选择的直接代价，需在验收时明示 |

### 1.4 手机端远程（remote）（10 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `remote:get-state` | `main/services/remote/index.ts:209` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:scan-start` | `main/services/remote/index.ts:213` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:scan-cancel` | `main/services/remote/index.ts:277` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:set-enabled` | `main/services/remote/index.ts:282` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:set-reply-mode` | `main/services/remote/index.ts:298` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:set-scope` | `main/services/remote/index.ts:304` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:delete-bot` | `main/services/remote/index.ts:311` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:pair-code` | `main/services/remote/index.ts:319` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:pair-cancel` | `main/services/remote/index.ts:321` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |
| `remote:remove-user` | `main/services/remote/index.ts:326` | `无（不迁移）` | 丢弃 | 无 | 手机端远程控制依赖 Web 服务端 + 配对/扫码链路，是另一套部署形态；Qt 桌面单体应用没有承载点。若确需远程，应作为独立服务重做，不是搬运 |

### 1.5 文件与工作区（fs）（9 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `fs:paste-attachment` | `main/services/attachments.ts:154` | `services/attachment_service.py::AttachmentService.paste_attachment` | 待定（P2） | 剪贴板 + 白名单目录 | 附件走白名单目录而非受信根，与 fs 其余通道的校验模型不同；P1 输入区不支持贴图/贴文件，先不实现 |
| `fs:dropped-entries` | `main/services/attachments.ts:189` | `services/attachment_service.py::AttachmentService.dropped_entries` | 待定（P2） | QDragEnterEvent/QDropEvent | 拖放附件需要 Qt 的事件重写（View 层）与路径白名单（服务层）两段，P2 与输入区增强一起做 |
| `fs:attachment-image` | `main/services/attachments.ts:209` | `services/attachment_service.py::AttachmentService.attachment_image` | 待定（P2） | media blob | 同 chat:attachment-image |
| `fs:pick-attachments` | `main/services/attachments.ts:223` | `services/attachment_service.py::AttachmentService.pick_attachments` | 待定（P2） | QFileDialog（多选） | P1 不做附件 |
| `fs:open-folder` | `main/services/workspace.ts:43` | `services/workspace_guard.py::WorkspaceGuard.choose_root` | 重写（P1） | QFileDialog + trust_root | Qt 文件对话框是模态阻塞调用，须在 View 层弹、把选中的路径交回服务；在服务里弹对话框会让无界面测试挂死 |
| `fs:reveal-folder` | `main/services/workspace.ts:55` | `services/workspace_guard.py::WorkspaceGuard.reveal_folder` | 重写（P1） | QDesktopServices.openUrl | 只允许受信根内的目录（Deva 的规则：对文件 openPath 等于双击执行）；QDesktopServices 对文件同样会执行，校验必须在调用前 |
| `fs:read-dir` | `main/services/workspace.ts:64` | `services/workspace_guard.py::WorkspaceGuard.read_dir` | 重写（P1） | 受信根 + realpath 校验 | 目录在前、按名排序的语义要保留；越界必须抛「拒绝访问：路径不在已打开的项目内」原文案，界面据此显示 |
| `fs:read-file` | `main/services/workspace.ts:82` | `services/workspace_guard.py::WorkspaceGuard.read_file` | 重写（P1） | 2MB 上限 + 二进制嗅探 | 上限 2MB、前 8000 字节含 NUL 判二进制、超限返回 tooLarge 而非抛错——三条都是线上行为，少一条会让大文件把界面卡死或把二进制当文本灌进编辑器 |
| `fs:write-file` | `main/services/workspace.ts:92` | `services/workspace_guard.py::WorkspaceGuard.write_file` | 重写（P1） | 受信根 + realpath 校验 | 写入要沿用原子写（同目录 .tmp + os.replace）还是裸写需定：Deva 的 workspace 侧是裸写、chat-store 侧才原子写，两者语义不同，不要合并 |

### 1.6 MCP 服务（mcp）（9 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `mcp:list` | `main/services/mcp.ts:633` | `services/mcp_service.py::McpService.list` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |
| `mcp:get` | `main/services/mcp.ts:634` | `services/mcp_service.py::McpService.get` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |
| `mcp:upsert` | `main/services/mcp.ts:635` | `services/mcp_service.py::McpService.upsert` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |
| `mcp:remove` | `main/services/mcp.ts:636` | `services/mcp_service.py::McpService.remove` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |
| `mcp:set-roles` | `main/services/mcp.ts:642` | `services/mcp_service.py::McpService.set_roles` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |
| `mcp:set-enabled` | `main/services/mcp.ts:649` | `services/mcp_service.py::McpService.set_enabled` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |
| `mcp:retry` | `main/services/mcp.ts:654` | `services/mcp_service.py::McpService.retry` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |
| `mcp:set-secret` | `main/services/mcp.ts:660` | `services/mcp_service.py::McpService.set_secret` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |
| `mcp:has-secret` | `main/services/mcp.ts:675` | `services/mcp_service.py::McpService.has_secret` | 丢弃（本阶段） | MCP stdio/HTTP 客户端 | MCP 服务器进程管理与工具桥接是一整块独立能力，且 P1 没有工具循环可挂载。Python 侧虽有 mcp SDK，但引入即等于引入未要求的业务面 |

### 1.7 角色（personas）（8 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `personas:list` | `main/services/personas.ts:488` | `services/persona_service.py::PersonaService.list` | 待定（P2） | personas 存储 + 头像 blob | 角色决定对话的系统提示与默认模型，牵涉会话绑定与头像存储；P1 用固定系统提示，先不建角色管理界面 |
| `personas:get` | `main/services/personas.ts:489` | `services/persona_service.py::PersonaService.get` | 待定（P2） | personas 存储 + 头像 blob | 角色决定对话的系统提示与默认模型，牵涉会话绑定与头像存储；P1 用固定系统提示，先不建角色管理界面 |
| `personas:upsert` | `main/services/personas.ts:490` | `services/persona_service.py::PersonaService.upsert` | 待定（P2） | personas 存储 + 头像 blob | 角色决定对话的系统提示与默认模型，牵涉会话绑定与头像存储；P1 用固定系统提示，先不建角色管理界面 |
| `personas:remove` | `main/services/personas.ts:493` | `services/persona_service.py::PersonaService.remove` | 待定（P2） | personas 存储 + 头像 blob | 角色决定对话的系统提示与默认模型，牵涉会话绑定与头像存储；P1 用固定系统提示，先不建角色管理界面 |
| `personas:set-enabled` | `main/services/personas.ts:497` | `services/persona_service.py::PersonaService.set_enabled` | 待定（P2） | personas 存储 + 头像 blob | 角色决定对话的系统提示与默认模型，牵涉会话绑定与头像存储；P1 用固定系统提示，先不建角色管理界面 |
| `personas:reorder` | `main/services/personas.ts:501` | `services/persona_service.py::PersonaService.reorder` | 待定（P2） | personas 存储 + 头像 blob | 角色决定对话的系统提示与默认模型，牵涉会话绑定与头像存储；P1 用固定系统提示，先不建角色管理界面 |
| `personas:set-avatar-image` | `main/services/personas.ts:506` | `services/persona_service.py::PersonaService.set_avatar_image` | 待定（P2） | personas 存储 + 头像 blob | 角色决定对话的系统提示与默认模型，牵涉会话绑定与头像存储；P1 用固定系统提示，先不建角色管理界面 |
| `personas:clear-avatar-image` | `main/services/personas.ts:509` | `services/persona_service.py::PersonaService.clear_avatar_image` | 待定（P2） | personas 存储 + 头像 blob | 角色决定对话的系统提示与默认模型，牵涉会话绑定与头像存储；P1 用固定系统提示，先不建角色管理界面 |

### 1.8 定时任务（tasks）（8 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `tasks:list` | `main/services/tasks.ts:480` | `services/task_service.py::TaskService.list` | 丢弃（本阶段） | scheduler + 独占会话 | 定时任务依赖调度器常驻与「任务独占会话」模型，P1 是单机单窗口无调度器；P3 若做需重新设计线程模型 |
| `tasks:get` | `main/services/tasks.ts:481` | `services/task_service.py::TaskService.get` | 丢弃（本阶段） | scheduler + 独占会话 | 定时任务依赖调度器常驻与「任务独占会话」模型，P1 是单机单窗口无调度器；P3 若做需重新设计线程模型 |
| `tasks:create` | `main/services/tasks.ts:483` | `services/task_service.py::TaskService.create` | 丢弃（本阶段） | scheduler + 独占会话 | 定时任务依赖调度器常驻与「任务独占会话」模型，P1 是单机单窗口无调度器；P3 若做需重新设计线程模型 |
| `tasks:update` | `main/services/tasks.ts:486` | `services/task_service.py::TaskService.update` | 丢弃（本阶段） | scheduler + 独占会话 | 定时任务依赖调度器常驻与「任务独占会话」模型，P1 是单机单窗口无调度器；P3 若做需重新设计线程模型 |
| `tasks:delete` | `main/services/tasks.ts:489` | `services/task_service.py::TaskService.delete` | 丢弃（本阶段） | scheduler + 独占会话 | 定时任务依赖调度器常驻与「任务独占会话」模型，P1 是单机单窗口无调度器；P3 若做需重新设计线程模型 |
| `tasks:set-status` | `main/services/tasks.ts:493` | `services/task_service.py::TaskService.set_status` | 丢弃（本阶段） | scheduler + 独占会话 | 定时任务依赖调度器常驻与「任务独占会话」模型，P1 是单机单窗口无调度器；P3 若做需重新设计线程模型 |
| `tasks:preview` | `main/services/tasks.ts:497` | `services/task_service.py::TaskService.preview` | 丢弃（本阶段） | scheduler + 独占会话 | 定时任务依赖调度器常驻与「任务独占会话」模型，P1 是单机单窗口无调度器；P3 若做需重新设计线程模型 |
| `tasks:run-now` | `main/services/tasks.ts:504` | `services/task_service.py::TaskService.run_now` | 丢弃（本阶段） | scheduler + 独占会话 | 定时任务依赖调度器常驻与「任务独占会话」模型，P1 是单机单窗口无调度器；P3 若做需重新设计线程模型 |

### 1.9 技能（skills）（6 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `skills:list` | `main/services/skills.ts:753` | `services/skill_service.py::SkillService.list` | 待定（P2） | skills 目录扫描 + frontmatter | 技能是「按需加载的提示片段」，要配合工具清单/listing 注入模型上下文；P1 无工具循环，注入点不存在 |
| `skills:get` | `main/services/skills.ts:754` | `services/skill_service.py::SkillService.get` | 待定（P2） | skills 目录扫描 + frontmatter | 技能是「按需加载的提示片段」，要配合工具清单/listing 注入模型上下文；P1 无工具循环，注入点不存在 |
| `skills:remove` | `main/services/skills.ts:755` | `services/skill_service.py::SkillService.remove` | 待定（P2） | skills 目录扫描 + frontmatter | 技能是「按需加载的提示片段」，要配合工具清单/listing 注入模型上下文；P1 无工具循环，注入点不存在 |
| `skills:set-enabled` | `main/services/skills.ts:756` | `services/skill_service.py::SkillService.set_enabled` | 待定（P2） | skills 目录扫描 + frontmatter | 技能是「按需加载的提示片段」，要配合工具清单/listing 注入模型上下文；P1 无工具循环，注入点不存在 |
| `skills:set-roles` | `main/services/skills.ts:761` | `services/skill_service.py::SkillService.set_roles` | 待定（P2） | skills 目录扫描 + frontmatter | 技能是「按需加载的提示片段」，要配合工具清单/listing 注入模型上下文；P1 无工具循环，注入点不存在 |
| `skills:import` | `main/services/skills.ts:767` | `services/skill_service.py::SkillService.import` | 待定（P2） | skills 目录扫描 + frontmatter | 技能是「按需加载的提示片段」，要配合工具清单/listing 注入模型上下文；P1 无工具循环，注入点不存在 |

### 1.10 密钥（secrets）（5 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `secrets:set` | `main/services/secrets.ts:122` | `services/secrets_vault.py::SecretsVault.set_secret` | 重写（P1） | keyring | 后端不可用时写入必须拒绝（Deva 同语义），返回 {ok:false, available:false}；用 base64 当加密或写 config.json 都是违规 |
| `secrets:has` | `main/services/secrets.ts:140` | `services/secrets_vault.py::SecretsVault.has_secret` | 重写（P1） | keyring | 只报布尔，不返回任何密文片段 |
| `secrets:delete` | `main/services/secrets.ts:145` | `services/secrets_vault.py::SecretsVault.delete_secret` | 重写（P1） | keyring | 后端不可用时的删除应报不可用而不是静默成功（否则用户以为删掉了） |
| `secrets:list` | `main/services/secrets.ts:153` | `services/secrets_vault.py::SecretsVault.list_keys` | 重写（P1） | keyring | 只返回键名与 has 布尔，绝不返回值本身；Deva 的键名形如 mcp:<serverId>:<field>，P1 用 providerId 作键。注意 Deva 没有 secrets:get 通道——取密钥是主进程内部调用（providers/index.ts 的 getSecret），新工程同样只在进程内取用，不暴露读取通道 |
| `secrets:available` | `main/services/secrets.ts:159` | `services/secrets_vault.py::SecretsVault.available` | 重写（P1） | keyring（系统钥匙串） | 本容器 keyring 解析到 fail 后端（priority 0，无 SecretService）；必须如实返回「不可用」，绝不可退回明文文件——这是硬约束 |

### 1.11 终端（terminal）（5 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `terminal:list-shells` | `main/services/terminal.ts:87` | `services/terminal_service.py::TerminalService.list_shells` | 丢弃（本阶段） | QProcess + pty / pywinpty | 终端要真 pty（Deva 用 node-pty）；Qt 只有 QProcess 管道，无 pty 时交互式程序（git rebase、ssh）行为不对。P3 再做，届时需引入 pywinpty/ptyprocess 并在 pyproject 声明理由 |
| `terminal:create` | `main/services/terminal.ts:91` | `services/terminal_service.py::TerminalService.create` | 丢弃（本阶段） | QProcess + pty / pywinpty | 终端要真 pty（Deva 用 node-pty）；Qt 只有 QProcess 管道，无 pty 时交互式程序（git rebase、ssh）行为不对。P3 再做，届时需引入 pywinpty/ptyprocess 并在 pyproject 声明理由 |
| `terminal:input` | `main/services/terminal.ts:100` | `services/terminal_service.py::TerminalService.input` | 丢弃（本阶段） | QProcess + pty / pywinpty | 终端要真 pty（Deva 用 node-pty）；Qt 只有 QProcess 管道，无 pty 时交互式程序（git rebase、ssh）行为不对。P3 再做，届时需引入 pywinpty/ptyprocess 并在 pyproject 声明理由 |
| `terminal:resize` | `main/services/terminal.ts:104` | `services/terminal_service.py::TerminalService.resize` | 丢弃（本阶段） | QProcess + pty / pywinpty | 终端要真 pty（Deva 用 node-pty）；Qt 只有 QProcess 管道，无 pty 时交互式程序（git rebase、ssh）行为不对。P3 再做，届时需引入 pywinpty/ptyprocess 并在 pyproject 声明理由 |
| `terminal:dispose` | `main/services/terminal.ts:108` | `services/terminal_service.py::TerminalService.dispose` | 丢弃（本阶段） | QProcess + pty / pywinpty | 终端要真 pty（Deva 用 node-pty）；Qt 只有 QProcess 管道，无 pty 时交互式程序（git rebase、ssh）行为不对。P3 再做，届时需引入 pywinpty/ptyprocess 并在 pyproject 声明理由 |

### 1.12 窗口（window）（5 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `window:set-overlay` | `main/index.ts:301` | `无（不迁移）` | 丢弃 | 无 | overlay 是 Windows 自定义标题栏的云母/遮罩效果（Electron setBackgroundMaterial 一类），Qt 无等价 API；P1 用系统标题栏，直接丢弃 |
| `window:minimize` | `main/index.ts:311` | `views/main_window.py::MainWindow._on_minimize` | 重写（P1） | QMainWindow.showMinimized | Qt 原生自带最小化；Deva 的 window:* 是自定义无边框标题栏的一部分，P1 用系统标题栏，通道退化为直调控件方法，不再经服务层 |
| `window:toggle-maximize` | `main/index.ts:312` | `views/main_window.py::MainWindow._on_toggle_maximize` | 重写（P1） | QMainWindow.showMaximized/showNormal | 要按 isMaximized() 在两态间切换；重复调用 showMaximized 不会还原 |
| `window:close` | `main/index.ts:316` | `views/main_window.py::MainWindow.closeEvent` | 重写（P1） | QWidget.close | 关闭前要把未保存的会话落盘（Deva 由 chat 层保证已落盘）；closeEvent 里做 I/O 会卡界面，须先保证发送完即存 |
| `window:is-fullscreen` | `main/index.ts:317` | `views/main_window.py::MainWindow._is_fullscreen` | 重写（P1） | QWidget.isFullScreen | P1 界面不提供全屏切换入口，通道仅保留查询语义；Deva 渲染层用它隐藏标题栏 |

### 1.13 交付文件（deliverables）（4 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `deliverables:inspect` | `main/services/deliverables.ts:70` | `services/deliverable_service.py::DeliverableService.inspect` | 待定（P2） | present_files 工具 + 文件预览 | 交付卡由 present_files 工具产生；P1 无工具循环。缩略图要在 Qt 侧重做（QImageReader），不能搬 Electron 的 nativeImage |
| `deliverables:thumbnail` | `main/services/deliverables.ts:88` | `services/deliverable_service.py::DeliverableService.thumbnail` | 待定（P2） | present_files 工具 + 文件预览 | 交付卡由 present_files 工具产生；P1 无工具循环。缩略图要在 Qt 侧重做（QImageReader），不能搬 Electron 的 nativeImage |
| `deliverables:open` | `main/services/deliverables.ts:108` | `services/deliverable_service.py::DeliverableService.open` | 待定（P2） | present_files 工具 + 文件预览 | 交付卡由 present_files 工具产生；P1 无工具循环。缩略图要在 Qt 侧重做（QImageReader），不能搬 Electron 的 nativeImage |
| `deliverables:reveal` | `main/services/deliverables.ts:118` | `services/deliverable_service.py::DeliverableService.reveal` | 待定（P2） | present_files 工具 + 文件预览 | 交付卡由 present_files 工具产生；P1 无工具循环。缩略图要在 Qt 侧重做（QImageReader），不能搬 Electron 的 nativeImage |

### 1.14 记忆（memory）（4 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `memory:list` | `main/services/memory.ts:339` | `services/memory_service.py::MemoryService.list` | 待定（P2） | memory 文件 + 清单注入 | 记忆是注入系统提示的条目集合，P1 不做记忆管理界面；存储格式简单，但注入时机依赖 listing 机制 |
| `memory:write` | `main/services/memory.ts:340` | `services/memory_service.py::MemoryService.write` | 待定（P2） | memory 文件 + 清单注入 | 记忆是注入系统提示的条目集合，P1 不做记忆管理界面；存储格式简单，但注入时机依赖 listing 机制 |
| `memory:delete` | `main/services/memory.ts:349` | `services/memory_service.py::MemoryService.delete` | 待定（P2） | memory 文件 + 清单注入 | 记忆是注入系统提示的条目集合，P1 不做记忆管理界面；存储格式简单，但注入时机依赖 listing 机制 |
| `memory:clear` | `main/services/memory.ts:354` | `services/memory_service.py::MemoryService.clear` | 待定（P2） | memory 文件 + 清单注入 | 记忆是注入系统提示的条目集合，P1 不做记忆管理界面；存储格式简单，但注入时机依赖 listing 机制 |

### 1.15 自动更新（update）（4 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `update:get-state` | `main/services/updater.ts:270` | `无（明确不做）` | 丢弃 | 无 | 自动更新链（electron-updater + 签名校验 + 增量包）在 Qt 路线下要整体重做，且需要代码签名证书与发布渠道。本阶段明确不做；打包/签名只在 py_upper 既有工具链范围内验证，不承诺线上更新 |
| `update:check` | `main/services/updater.ts:271` | `无（明确不做）` | 丢弃 | 无 | 自动更新链（electron-updater + 签名校验 + 增量包）在 Qt 路线下要整体重做，且需要代码签名证书与发布渠道。本阶段明确不做；打包/签名只在 py_upper 既有工具链范围内验证，不承诺线上更新 |
| `update:download` | `main/services/updater.ts:272` | `无（明确不做）` | 丢弃 | 无 | 自动更新链（electron-updater + 签名校验 + 增量包）在 Qt 路线下要整体重做，且需要代码签名证书与发布渠道。本阶段明确不做；打包/签名只在 py_upper 既有工具链范围内验证，不承诺线上更新 |
| `update:install` | `main/services/updater.ts:273` | `无（明确不做）` | 丢弃 | 无 | 自动更新链（electron-updater + 签名校验 + 增量包）在 Qt 路线下要整体重做，且需要代码签名证书与发布渠道。本阶段明确不做；打包/签名只在 py_upper 既有工具链范围内验证，不承诺线上更新 |

### 1.16 配置（config）（3 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `config:get-sync` | `main/services/config.ts:86` | `services/settings_service.py::SettingsService.get_config_sync` | 重写（P1） | 同上 | Deva 用同步通道避免首帧闪烁（FOUC）；Qt 侧本来就是同进程调用，保留一个同步读方法给界面首帧即可，不需要单独通道语义 |
| `config:get` | `main/services/config.ts:92` | `services/settings_service.py::SettingsService.get_config` | 重写（P1） | config.json（明文）+ 顶层浅合并 | Deva 的配置是明文 JSON、顶层浅合并、undefined 删键；Python 侧注意 None 与「键不存在」的区别——用 None 表示删除会与「显式设 null」混淆 |
| `config:set` | `main/services/config.ts:98` | `services/settings_service.py::SettingsService.set_config` | 重写（P1） | 同上 + 原子写 | 写盘要原子（.tmp + os.replace）；写到一半被杀会把配置文件截断，下次启动丢全部设置 |

### 1.17 个人资料（profile）（3 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `profile:get` | `main/services/profile.ts:49` | `services/profile_service.py::ProfileService.get` | 待定（P2） | profile.json + 头像 blob | 个人资料只影响界面显示（头像/昵称），P1 不建设置页的账户区；存储与 personas 头像共用 blob 目录，P2 一起做 |
| `profile:set-avatar` | `main/services/profile.ts:50` | `services/profile_service.py::ProfileService.set_avatar` | 待定（P2） | profile.json + 头像 blob | 个人资料只影响界面显示（头像/昵称），P1 不建设置页的账户区；存储与 personas 头像共用 blob 目录，P2 一起做 |
| `profile:set-avatar-image` | `main/services/profile.ts:55` | `services/profile_service.py::ProfileService.set_avatar_image` | 待定（P2） | profile.json + 头像 blob | 个人资料只影响界面显示（头像/昵称），P1 不建设置页的账户区；存储与 personas 头像共用 blob 目录，P2 一起做 |

### 1.18 剪贴板（clipboard）（2 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `clipboard:read-text` | `main/services/clipboard.ts:15` | `services/clipboard_service.py::ClipboardService.read_text` | 重写（P1） | QGuiApplication.clipboard | Qt 剪贴板只在 GUI 线程可用；从工作线程调用会崩或返回空，服务层必须把调用切回主线程（QMetaObject.invokeMethod 或信号） |
| `clipboard:write-text` | `main/services/clipboard.ts:18` | `services/clipboard_service.py::ClipboardService.write_text` | 重写（P1） | QGuiApplication.clipboard | 同上；X11 下写剪贴板后进程退出内容即丢，需 setClipboard 常驻与否按平台定 |

### 1.19 应用信息（app）（1 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `app:get-platform` | `main/index.ts:318` | `services/desktop_service.py::DesktopService.platform_name` | 重写（P1） | sys.platform / QSysInfo | Deva 返回 Node 的 process.platform（'win32'/'darwin'/'linux'）；Python 的 sys.platform 是 'win32'/'darwin'/'linux'，恰好一致，但别混用 QSysInfo.productType()（返回 'windows'/'macos'） |

### 1.20 服务商（provider）（1 条）

| 通道 | Deva 位置 | 新工程落点 | 处置 | 依赖 | 风险 |
|---|---|---|---|---|---|
| `provider:list-models` | `main/services/provider.ts:74` | `services/provider_gateway.py::ProviderGateway.list_models` | 重写（P1） | 标准库 urllib / http.client（流式） | Deva 走 Chromium 网络栈以继承系统证书与代理；Python 用 urllib 默认只认 certifi/系统 CA，企业网下可能失败——P1 如实报网络错误，不静默降级。15s 超时、anthropic 用 x-api-key、其余 Bearer 的差异要保留 |

**表内合计：158 行。** 处置分布见下表（脚本统计，非手填）：

| 处置 | 条数 |
|---|---:|
| 直搬 | 0 |
| 重写 | 32 |
| 待定 | 44 |
| 丢弃 | 82 |
| **合计** | **158** |

关于「直搬 = 0」：Deva 是 TypeScript/Electron，目标是 Python/Qt，**没有一行可以字面直搬**。
所以这里的「直搬」只用于语义完全等价、且不需要改数据格式的条目；本表没有这样的条目，
全部要么重写（语义照搬、实现重做）、要么丢弃、要么因为依赖未就绪而待定。
表中「重写」不等于「从头设计」——风险列写的就是必须照搬、不能想当然改掉的那些语义。

## 2. 渲染层按功能域聚合（不逐条搬 869 个函数）

Deva 渲染层是 React 18：49 个文件、28132 行、869 个函数/组件条目，其中
`redesign/ChatFirstShell.tsx` 一个文件就有 8958 行 / 292 条。按函数逐条迁移没有意义——
语法、状态管理、样式体系全部不同。这里按**功能域**给出 Qt 原生对应做法与工作量。

工作量单位：人日（1 人，熟悉 PySide6，不含联调与打磨）；估算基于本表与源码体量，属**工程判断**，
不是实测。

| 域 | Deva 载体（文件:行数/条目） | Qt 原生做法 | 工作量 | 覆盖范围声明 |
|---|---|---|---:|---|
| 会话列表 | `redesign/ChatFirstShell.tsx` 中列表段、`store/chat.tsx`（2453 行/74） | `QListWidget`/`QListView` + 自定义 delegate；数据来自 `chat_session_store.list_sessions()`；右键菜单做重命名/删除/归档 | 2–3 | 创建/切换/重命名/删除/归档；**不做**拖拽排序、成员会话、按项目分组（Deva 已无分桶） |
| 聊天与富文本 | `features/chat/blocks.tsx`（2325/77）、`features/chat/Markdown.tsx`（130/5）、`redesign/composer-editor.ts`（535/31） | `QTextBrowser` + `QTextDocument.setMarkdown()`（Qt 6.11 实测能出 `<table>`/`<pre>`）；流式增量用「重新 setMarkdown 全文」或按块追加，代码块走 `QSyntaxHighlighter` 可选 | 5–8 | 文本 Markdown、流式追加、代码块、自动滚底、Enter 发送 / Shift+Enter 换行；**不做**工具卡、思考块、附件卡、Lexical 的 @ 提及与斜杠命令 |
| 终端 | `terminal.ts` + `@lydell/node-pty` | 需 pty：`QProcess` 只是管道，交互式程序行为不对；真要做得引入 `pywinpty`/`ptyprocess` 或自己 fork | 4–6 | P3；本阶段不做，通道随域延后 |
| 设置 | `features/settings/ModelSettings.tsx`（733/22）、`ModelDetail.tsx`（311/7） | `QDialog` + `QFormLayout`（模型/服务商/BaseURL/密钥）；密钥输入 `QLineEdit.Password`，保存走 `SecretsVault`，不可用时工具栏常驻提示而非静默失败 | 2–4 | P1 只做「服务商 + 模型 + 密钥」一页；**不做**角色/技能/MCP/远程/更新的设置分区 |
| 主题与 i18n | `theme/ThemeContext.tsx`（103/8）、`theme/chatFontSize.ts`（39/4）、`i18n/messages.ts`（2919 行） | 主题：`QPalette` + QSS 变量替换，或两套 `.qss`；i18n：`QTranslator` + `.ts/.qm`（`lupdate/lrelease`），或先只做中英字典 dict + `tr()` | 2–3 | P1 只做浅色/深色切换与字号；**不做** Deva 的完整文案表（2919 行）逐条搬——按界面实际用到的字符串重建 |
| 拖拽布局 | `redesign/resizable.tsx`（145/8）、`redesign/ChatFirstShell.tsx` 的拖拽段 | `QSplitter` 天然可拖；需要停靠面板用 `QDockWidget` | 0.5–1 | P1 左侧列表与聊天区用 `QSplitter`；**不做**可拖拽的浮动卡片/多面板编排 |
| 托盘·更新·快捷键 | `redesign/UpdateSection.tsx`（144/6）、`updater.ts` | 托盘 `QSystemTrayIcon`；快捷键 `QShortcut`/`QKeySequence`；更新：**不做** | 1–2（不含更新） | 托盘与快捷键 P2；自动更新与签名链明确不做（见 §3.3） |

渲染层的三类「不迁移」理由：

1. **Lexical 编辑器**（`composer-editor.ts`、`attachments.tsx`）是浏览器 contenteditable 生态，
   Qt 的 `QTextEdit` 没有等价扩展点；P1 用纯文本多行输入 + Enter/Shift+Enter 语义，富文本输入不承诺。
2. **xterm.js / node-pty** 依赖真 pty，Qt 无内置；见终端行。
3. **Web 侧那套**（`apps/web/`）是同一批业务代码的浏览器外壳，不构成新能力；Qt 路线不迁。

## 3. 阶段划分

### 3.1 本阶段（P1，即本次交付范围）

- **业务层**（`app/src/mvvm/services/`，pydantic 模型）：
  - `provider_gateway.py`：Anthropic / OpenAI 兼容两套流式适配，归一化 `StreamEvent`，
    HTTP 错误 → `NormalizedError(kind, retryable, message)`，重连 6 次 + 指数退避（封顶 30s）+ 60s 空闲判定。
  - `chat_session_store.py`：读写 Deva 的 `data/chats/<id>.json` + `_index.json`，能读旧数据（含 `compacted` 拆分）。
  - `workspace_guard.py`：受信根 + realpath 越界拒绝，文案与 Deva 一致。
  - `settings_service.py`（明文 `config.json`，顶层浅合并）、`secrets_vault.py`（keyring，后端不可用即拒绝）。
- **界面**（Qt 原生）：左侧会话列表（增删改查）、聊天视图（Markdown + 流式 + 代码块 + 滚底）、
  输入区（Enter 发送 / Shift+Enter 换行）、设置页（服务商/模型/密钥）。
- **工程**：接入 py_upper 既有装配处与入口，保持原有 377 个测试全绿。

### 3.2 后续阶段

- **P2（对话能力补齐）**：工具循环与路径沙箱（agent 文件工具）、压缩（`chat:compact`）、
  按轮删除/回滚、附件与图片、角色、技能、记忆、交付卡、思考等级 UI。
- **P3（工作区与运维）**：Git 面板、终端（pty）、定时任务、MCP。
- **P4（可选）**：多窗口、主题细调、i18n 完整化。

### 3.3 明确不做（并把风险摊开）

| 项 | 原因 | 风险 / 代价 |
|---|---|---|
| 自动更新与签名链（`update:*`） | Qt 路线的更新器要整体重做，且需要代码签名证书与发布渠道 | 用户需手动替换安装包；打包只验证 py_upper 既有构建链，不承诺线上更新 |
| 内置浏览器（`browser:*` 16 条） | 路线明确不嵌 Chromium/WebEngine | agent 的浏览器操作能力整体缺失；只能外开系统浏览器 |
| 手机端远程（`remote:*` 10 条） | 依赖 Web 服务端 + 配对链路，属另一部署形态 | 无远程控制；如需，应作为独立服务重做 |
| 内置终端（`terminal:*` 5 条） | 需真 pty，Qt 无内置，引入需新依赖 | P3 之前无终端；`focusRoot` 只存值不提供终端 cwd |
| 渲染层 Lexical 富文本 | 无 Qt 等价物 | 输入区只支持纯文本 + Markdown 语义，不支持 @ 提及/附件内联 |

## 4. 关键事实与「待确认」

已从源码确认（可直接作为实现依据）：

- 存储：`<DEVA_HOME>/data/chats/<id>.json`（一对话一文件）+ `_index.json`（仅元信息，缺失则扫描重建）；
  压缩后早期消息拆到 `<id>.compacted-<time>.jsonl`；媒体外置到 `data/media/<sha256>`。
- `DEVA_HOME` 缺省 `~/.deva`；`config.json` 明文；`secrets.json` 为 Electron `safeStorage` 的 base64 密文。
- 受信根只约束**渲染层发起**的 fs/git IPC（`fs-guard.ts`）；agent 文件工具自 2026-10-09 起不设路径限制。
- Provider 常量：`STREAM_IDLE_MS = 60_000`、`MAX_RECONNECT = 6`、退避 `retryAfterMs ?? 1000*2**attempt` 封顶 30s。
- `httpError` 的状态码映射与 `inbandError` 的带内错误归类（上下文超限/输出上限）必须照搬语义。

待确认（拿不准，先按保守实现）：

- **`anthropic-version` 取值**：Deva 写死 `2023-06-01`；新工程是否跟随，取决于目标模型是否需要更新的 beta 头。
- **`safeStorage` 密文迁移**：Deva 的 `secrets.json` 用 Electron 的 DPAPI/Keychain 加密，Python 无法直接解；
  P1 的策略是「不读旧密文，要求用户在新工程重填一次密钥」，需产品确认可接受。
- **压缩边界判定**依赖 `model-view.ts` 的 `modelFirst`/`modelRange` 规则；P1 只按原样读写 `compacted` 字段，
  不重新计算拆分点（即：能读旧数据，但新增长对话暂不做压缩）。
- **`focusRoot` 的权限作用域键**（`projectKey`：sha1 前 24 位）在 P1 只存不用，因为 P1 没有工具权限层。

