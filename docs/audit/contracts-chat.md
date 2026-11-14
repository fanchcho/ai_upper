# IPC 通道契约台账：chat（31 条）

> 事实来源：只读审阅 `/home/agent/shared_workspace/deva/apps/desktop/src/main/services/chat.ts`
> 与 `preload/index.ts`（Electron 原版）。行号以实际读到的为准。
> 31 条均为 `ipcMain.handle` + `ipcRenderer.invoke`；handler 抛出的异常表现为渲染层 Promise rejection。
> 事件 `chat:event`（`ChatEventPayload {turnId,sessionId,event}`）与 `chat:sessions-changed`（无
> payload）由 `webContents.send` 推送，不在 158 条 invoke 通道内，本节末尾单列其形状。
> 本文件只记录源码可直接看到的事实，未包含推断。

### chat:send

- 入参: `payload: ChatSendRequest` = `{ sessionId: string, text: string, model: ChatModelConfig{adapter:'anthropic'|'openai'|'responses', providerId, baseURL, model}, workspaceRoot: string | null, attachments?: string[], personaId?: string, focusRoot?: string | null, modelRef?: string, effort?: EffortLevel }`
- 出参: `Promise<{ turnId: string }>`（`sendMessage` → `startTurn` 的 `turnId`；回合本身 fire-and-forget）
- 错误/边界: 该会话已有回合在跑 → 抛 `Error('这个对话正在进行中（可能由手机端或定时任务发起），请等它结束后再发。')`；附件读取期间另一端抢先起一轮 → 再抛同一错误；`ensureSession` 首发绑定 personaId（只补不覆盖）、focusRoot/model/effort 显式提供即落库；`/技能名` 命中角色可用技能时把技能正文预置进本条消息并从原话里剥掉开头那个；附件按 `buildAttachmentPart` 读取（读不到的路径转成 note 拼在问题正文后的括号里）；`text.trim()` 为空但有附件时问题正文回落「请理解并处理上述附件。」；标题为空时 `deriveTitle(text) || deriveTitle(questionText)`；落盘后 `emitTurnStart`（带本轮用户消息的展示形态）再 `runTurn`；`pendingUndo` 随之失效
- 原版位置: `main/services/chat.ts:6090`（handler）+ `sendMessage:5955` / `startTurn:5965`；preload `preload/index.ts:1098`

### chat:insert

- 入参: `payload: ChatInsertRequest` = `{ sessionId: string, text: string, model: ChatModelConfig }`
- 出参: `Promise<ChatInsertResult>` = `{ ok: true } | { ok: false, reason: 'idle' | 'busy' | 'empty' }`
- 错误/边界: `text.trim()` 为空 → `empty`；该会话没有进行中的回合 → `idle`（调用方改走普通发送）；回合不是「可插入的主轮」（定时任务、压缩、回滚期间）→ `busy`；成功则入队 `pendingInserts` 并推送 `inserts{pending:string[]}` 事件；入参里的 `model` 只在「来不及送达、改作下一轮发出」时用作回落
- 原版位置: `main/services/chat.ts:6093`（handler）+ `insertMessage:2668` / `insertableTurns:2665`；preload `preload/index.ts:1100`

### chat:withdraw-inserts

- 入参: `sessionId: string`
- 出参: `Promise<{ text: string }>`，为全部待送达插入消息按 `'\n\n'` 合并后的原文；没有则空串
- 错误/边界: 无显式错误；取走即清空该会话队列并推送 `inserts{pending:[]}`；不校验会话是否存在
- 原版位置: `main/services/chat.ts:6094`（handler）+ `takeInserts:2683`；preload `preload/index.ts:1103`

### chat:compact

- 入参: `payload: ChatCompactRequest` = `{ sessionId: string, model: ChatModelConfig, workspaceRoot: string | null }`
- 出参: `Promise<{ turnId: string }>`
- 错误/边界: 立即返回 `turnId`；压缩在后台进行，先推 `compacting{active:true}`，结束时 `finally` 必推 `compacted{scope:'manual', status:'none'|'compacted'|'failed', message?}` 与 `done{stopReason:'end_turn'}`；会话不存在时 `status` 保持 `'none'`；异常被捕获后以 `status:'failed'` + 异常 message 推 `compacted`；成功时 `pendingUndo` 失效并落盘；期间 `compacting` 集合阻止后台通知起轮
- 原版位置: `main/services/chat.ts:6101`（handler）；preload `preload/index.ts:1106`

### chat:create-session

- 入参: `payload: ChatCreateSessionRequest` = `{ sessionId: string, personaId?: string, focusRoot?: string | null, modelRef?: string }`
- 出参: `Promise<{ ok: true }>`
- 错误/边界: `ensureSession(sessionId, {personaId, focusRoot, model: modelRef})` 后立即 `saveProject`——空对话由此成为真实持久化会话、跨重启存活；已存在的会话只补 personaId、显式提供才覆盖 focusRoot/model；不校验 sessionId 之外任何字段
- 原版位置: `main/services/chat.ts:6151`（handler）；preload `preload/index.ts:1109`

### chat:set-model

- 入参: `payload: ChatSetModelRequest` = `{ sessionId: string, modelRef: string }`
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 会话尚未建档 → `{ ok: false }`（不建档，模型仍由覆盖层随首发落库）；否则写 `session.model`、落盘、`syncTaskModel` 同步任务对话、`markMemberSetting('modelSet')` → `{ ok: true }`；不改 `updatedAt`
- 原版位置: `main/services/chat.ts:6165`（handler）；preload `preload/index.ts:1112`

### chat:set-effort

- 入参: `payload: ChatSetEffortRequest` = `{ sessionId: string, effort: EffortLevel }`
- 出参: `Promise<{ ok: true }>`（恒真）
- 错误/边界: 会话不存在或 `effort` 不是合法档位 → 不做任何事，仍回 `ok:true`；合法则写 `session.effort`、落盘、`markMemberSetting('effortSet')`；不改 `updatedAt`
- 原版位置: `main/services/chat.ts:6177`（handler）+ `isEffortLevel`；preload `preload/index.ts:1115`

### chat:set-focus

- 入参: `payload: ChatSetFocusRequest` = `{ sessionId: string, focusRoot: string | null }`
- 出参: `Promise<{ ok: true }>`（恒真）
- 错误/边界: 会话存在且是成员会话（有 `parentId`）→ 走 `setMemberFolder(main, member, focusRoot)`，不写成员会话自己的字段；普通会话 → 写 `session.focusRoot` 并落盘；未建档的惰性会话无操作（仍由覆盖层随首发落库）；不改 `updatedAt`
- 原版位置: `main/services/chat.ts:6190`（handler）；preload `preload/index.ts:1118`

### chat:rename-session

- 入参: `payload: ChatRenameSessionRequest` = `{ sessionId: string, title: string }`
- 出参: `Promise<{ title: string } | null>`，`null` = 会话尚未建档
- 错误/边界: 标题先 `replace(/\s+/g,' ').trim()` 再截 `TITLE_MAX`；结果为空时恢复自动标题：取展示形态里第一条 `role==='user' && !notify` 的消息，`deriveTitle(其正文) || deriveTitle(附件名拼串)`；写入并落盘，**不改 `updatedAt`**（列表顺序不变）
- 原版位置: `main/services/chat.ts:6207`（handler）+ `deriveTitle` / `TITLE_MAX`；preload `preload/index.ts:1121`

### chat:set-archived

- 入参: `payload: ChatSetArchivedRequest` = `{ sessionId: string, archived: boolean }`
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 归档一个**正在跑回合**的会话 → `{ ok: false }`（渲染层按清单复原）；会话尚未建档 → `setSessionArchived` 回 false → `ok:false`；成功则落盘且不改 `updatedAt`
- 原版位置: `main/services/chat.ts:6226`（handler）+ `setSessionArchived`；preload `preload/index.ts:1124`

### chat:list-sessions

- 入参: `workspaceRoot: string | null`（签名兼容渲染层，实现完全忽略）
- 出参: `Promise<ChatSessionMeta[]>`，按 `updatedAt` 倒序；**包含**成员会话（带 `parentId`，渲染层不列进左侧列表但打开成员对话时要读它的模型与文件夹）
- 错误/边界: 无显式错误；列表里每个非空 `focusRoot` 都 `trustRoot` 登记为受信根（否则重启后 `git:status` / `fs:*` 首行 `assertInside` 抛「拒绝访问」，表现为 git 丢失）
- 原版位置: `main/services/chat.ts:6233`（handler）+ `listSessions`；preload `preload/index.ts:1133`

### chat:load-session

- 入参: `sessionId: string`, `workspaceRoot: string | null`（后者忽略）
- 出参: `Promise<DisplayMessage[]>`；会话不存在 → `[]`
- 错误/边界: 载入即自愈——非忙碌会话里悬空的 `tool_use` 被补成「未完成」并落盘（崩溃/强退遗留），工具卡随之定格而不是永远转圈；忙碌时不动（那时的悬空是工具正在执行）；`DisplayMessage` 由完整 `toDisplayMessages` 用十个展示边车（proposals / notices / asks / summaries / plans / autotasks / todos / subagent 元数据 / background / durations）重建
- 原版位置: `main/services/chat.ts:6277`（handler）+ `loadDisplay` / `displayOf`；preload `preload/index.ts:1136`

### chat:attachment-image

- 入参: `sessionId: unknown`, `ref: unknown`, `full: unknown`
- 出参: `Promise<string | null>`
- 错误/边界: 非 string 的 `sessionId`/`ref` → `null`；`ref` 须匹配 `^(\d+):(\d+):`；该下标消息必须是 `role==='user'` 且 content 为数组；该块必须是 `image`，且重算的 `imageRef(msgIndex, partIndex, data)` 与 `ref` 完全相等（内容指纹防止删轮/回滚后下标错位取错图）；`full === true` → `data:<mime>;base64,<data>`；否则 `thumbnailDataUrl`，缩略失败 → `null`
- 原版位置: `main/services/chat.ts:6285`（handler）+ `imageRef` / `thumbnailDataUrl`；preload `preload/index.ts:1139`

### chat:attach-session

- 入参: `sessionId: string`
- 出参: `Promise<{ messages: DisplayMessage[], turnId: string | null, startedAt: number | null }>`
- 错误/边界: 历史与进行中回合**同一时刻取出**（渲染层据此接上别处发起、仍在跑的一轮，此后到达的流事件都晚于快照，不会漏 `done`）；空闲时 `turnId` 与 `startedAt` 均为 `null`；消息侧与 `chat:load-session` 同一实现（含悬空修复）
- 原版位置: `main/services/chat.ts:6306`（handler）+ `busySessions` / `busySince`；preload `preload/index.ts:1145`

### chat:resolve-proposal

- 入参: `sessionId: string`, `toolUseId: string`, `status: 'accepted' | 'rejected'`
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 会话不存在 → `{ ok: false }`；否则写 `proposals[toolUseId] = status` 边车并落盘，推 `card_resolved{card:'agent', toolUseId, status}`（其它端据此把名片收成终态）→ `{ ok: true }`；不校验该 toolUseId 是否真是 `propose_agent` 调用
- 原版位置: `main/services/chat.ts:6331`（handler）+ `resolveProposal:6320`；preload `preload/index.ts:1185`

### chat:resolve-autotask

- 入参: `sessionId: string`, `toolUseId: string`, `action: 'create' | 'dismiss'`, `taskInput?: TaskCreateInput`
- 出参: `Promise<ResolveAutotaskResult>` = `{ ok: true, status: 'created', taskId } | { ok: true, status: 'dismissed' } | { ok: false, error: 'no-session' | 'no-input' | <createTask 的错误码> }`
- 错误/边界: 会话不存在 → `no-session`；幂等：`autotasks[toolUseId].status === 'created' && taskId` 时直接回既有 taskId（防双提交造双任务）；`dismiss` 记 `{status:'dismissed'}` 并推 `card_resolved{card:'autotask',toolUseId,status:'dismissed'}`；`create` 缺 `taskInput` 或非对象 → `no-input`；`createTask({...taskInput, originSessionId:sessionId})` 失败 → 透传其 error 且**不落边车**（名片留待修正后重试）；成功落 `{status:'created',taskId}` 并推 `card_resolved{...,status:'created',taskId}`
- 原版位置: `main/services/chat.ts:6381`（handler）+ `resolveAutotask:6346`；preload `preload/index.ts:1197`

### chat:delete-session

- 入参: `sessionId: string`, `workspaceRoot: string | null`（忽略）
- 出参: `Promise<{ ok: true }>`（恒真）
- 错误/边界: 无显式错误；`purgeSession` 依次：中止该会话进行中的回合（不必先 abort）、取消后台子智能体、关内置网页、删对话文件、清撤销快照、删检查点与子智能体记录、清成员派发与待决 handoff；随后逐个 `purgeSession` 主对话的成员会话；`releaseTasksOwnedBy(sessionId)` 让该对话的定时任务改为独立运行（任务与任务对话保留）
- 原版位置: `main/services/chat.ts:6413`（handler）+ `purgeSession:6395`；preload `preload/index.ts:1148`

### chat:remove-member

- 入参: `sessionId: string`, `memberSessionId: string`
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 主对话不存在、或名单里找不到该且未 removed 的成员 → `{ ok: false }`；成功则 `ref.removed = true`、清 `openTask`、落盘、中止该成员进行中的回合、`publishSessionsChanged()` → `{ ok: true }`；成员会话本体**保留**（可从名单恢复）
- 原版位置: `main/services/chat.ts:6426`（handler）；preload `preload/index.ts:1151`

### chat:abort

- 入参: `turnId: string`
- 出参: `Promise<{ ok: true }>`（恒真）
- 错误/边界: 无显式错误；未知 turnId 也无副作用；中止 = `controller.abort()` + `releasePending(turnId)`（该轮待决 ask 回灌「用户取消了本次询问」、plan 记取消、mount 按未挂载解开）；本轮后续以 `stopReason='aborted'` 收尾
- 原版位置: `main/services/chat.ts:6466`（handler）+ `abortTurn:6444`；preload `preload/index.ts:1125`

### chat:stop-subagent

- 入参: `sessionId: string`, `toolUseId: string`（= 开出它的那次调用 id，即 Task 卡 id）
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: `backgroundSubagents` 里没有该 toolUseId、或它不属于该会话 → `{ ok: false }`；否则置 `stoppedByUser = true` 并 `abort()` → `{ ok: true }`；子智能体照常收尾（Task 卡定格「已停止」，结论随下一轮交给模型，但不为此自动起轮）
- 原版位置: `main/services/chat.ts:6473`（handler）；preload `preload/index.ts:1128`

### chat:reset

- 入参: `sessionId: string`, `workspaceRoot: string | null`（忽略）
- 出参: `Promise<{ ok: true }>`（恒真）
- 错误/边界: 会话不存在 → 仍回 `ok:true`（只清 `pendingUndo` 与磁盘记录）；存在则清空 `messages`，并清 `notices` / `background` / `checkpoints` / `lastKnown` / `baselines` / `restoreNote`，刷新 `updatedAt` 并落盘；撤销快照失效；会话忙碌时不删检查点/子智能体目录（进行中的写入正在用）
- 原版位置: `main/services/chat.ts:6485`（handler）；preload `preload/index.ts:1130`

### chat:delete-turns

- 入参: `sessionId: string`, `workspaceRoot: string | null`（忽略）, `turnIndices: number[]`
- 出参: `Promise<DisplayMessage[]>`，删除后按完整 `toDisplayMessages` 重建的展示气泡（渲染层就地替换；会话不存在 → `[]`）
- 错误/边界: 非数组的 `turnIndices` 按 `[]`；`deleteTurns` 按轮下线切分（见 `turnRanges`）后删除对应区间；撤销快照失效；落盘并回收 blob；推 `todos` 事件（`turnId` 为空串）；前置约束：渲染层仅在非流式时发起
- 原版位置: `main/services/chat.ts:6517`（handler）+ `deleteTurns`；preload `preload/index.ts:1161`

### chat:todos

- 入参: `sessionId: string`
- 出参: `Promise<TodoState>` = `{ active: { id, title, items, createdAt, updatedAt } | null }`
- 错误/边界: 会话不存在 → `{ active: null }`；只读；此后变化走 `todos` 事件推送
- 原版位置: `main/services/chat.ts:6538`（handler）+ `todoState`；preload `preload/index.ts:1163`

### chat:todo-cancel

- 入参: `sessionId: string`
- 出参: `Promise<TodoState>`（取消后的状态）
- 错误/边界: 会话不存在 → `{ active: null }`；有当前清单且会话**不忙**时才受理：把清单 id 追加进 `todoCancelled`、写 `todoCancelNote`（下一条用户消息里告知模型）、落盘并推 `todos`；忙碌时不受理（模型正推进它，取消了也会被立刻写回），仍返回当前状态
- 原版位置: `main/services/chat.ts:6545`（handler）+ `todoUserCancelNote`；preload `preload/index.ts:1166`

### chat:rewind-list

- 入参: `sessionId: string`
- 出参: `Promise<{ turns: RewindTurnStat[], canUndo: boolean }>`；会话不存在 → `{ turns: [], canUndo: false }`
- 错误/边界: 无显式错误；`turns` 为每轮的改动量（文件数 / +N −M / 是否跑过命令），`canUndo` 即该会话是否有未消费的撤销快照
- 原版位置: `main/services/chat.ts:6566`（handler）+ `summarizeTurns` / `turnToolIds` / `pendingUndo`；preload `preload/index.ts:1169`

### chat:rewind-preview

- 入参: `sessionId: string`, `turn: number`
- 出参: `Promise<{ files: RewindFile[], commands: string[] } | null>`
- 错误/边界: 会话不存在、`turn` 非整数、或越界（`<0` 或 `>=` 轮数）→ `null`；只读，每次都由主进程重算计划（不信任渲染层回传的预览）；路径只来自检查点记录、链接跳过
- 原版位置: `main/services/chat.ts:6576`（handler）+ `planRewind` / `publicPreview`；preload `preload/index.ts:1172`

### chat:rewind-apply

- 入参: `req: ChatRewindApplyRequest` = `{ sessionId: string, turn: number, mode: 'both' | 'conversation' | 'code', force?: string[] }`
- 出参: `Promise<{ ok: true, messages: DisplayMessage[], restored: string[], skipped: { rel, reason }[] } | { ok: false, error: 'no-session' | 'busy' | 'bad-turn' }>`
- 错误/边界: 会话不存在 → `no-session`；会话忙碌或已在回滚中 → `busy`；`turn` 非整数/越界 → `bad-turn`；`mode` 决定是否恢复文件与是否删轮；`code` 模式若有恢复文件，会把回滚说明写进 `restoreNote` 并追加 `{kind:'notice',code:'restored'}` 提示；`both`/有恢复文件时记撤销快照；删除对话轮时清 `lastInputTokens`（防下一轮误触发压缩）；结束前推迟一拍 `wakeForNotices`
- 原版位置: `main/services/chat.ts:6592`（handler）+ `planRewind:6646` / `applyFiles` / `deleteTurns` / `buildRestoreNote`；preload `preload/index.ts:1175`

### chat:rewind-undo

- 入参: `sessionId: string`
- 出参: `Promise<{ ok: true, messages: DisplayMessage[], restored: string[], skipped: string[] } | { ok: false, error: 'no-undo' | 'busy' }>`
- 错误/边界: 会话不存在或无撤销快照 → `no-undo`；会话忙碌或正在回滚 → `busy`；执行时先消费快照，把文件写回回滚前字节（只动回滚后未再被改过的），对话状态整体换回快照，落盘并回收 blob，推 `todos`
- 原版位置: `main/services/chat.ts:6684`（handler）+ `undoFiles` / `pendingUndo`；preload `preload/index.ts:1178`

### chat:ask-response

- 入参: `payload: AskResponse` = `{ key: string, answers: string[] | null }`（`null` = 取消）
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: `pendingAsk` 里没有该 key（已被另一端答过 / 已由 abort 释放）→ `{ ok: false }`；先到者生效：键随即删除，后到一律 false；推 `interaction_resolved{key, kind:'ask', answers}`
- 原版位置: `main/services/chat.ts:6751`（handler）+ `answerAsk:6718`；preload `preload/index.ts:1200`

### chat:plan-response

- 入参: `payload: PlanResponse` = `{ key: string, decision: 'approve' | 'keep' | 'ignore' | 'cancelled', feedback?: string }`
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 无待决计划 → `{ ok: false }`；只有 `decision === 'keep'` 且 `feedback` 为非空字符串时才把 feedback 回灌给模型（trim 后空则不带）；推 `interaction_resolved{key, kind:'plan', decision, feedback?}`
- 原版位置: `main/services/chat.ts:6755`（handler）+ `decidePlan:6729`；preload `preload/index.ts:1203`

### chat:mount-response

- 入参: `payload: MountResponse` = `{ key: string, path: string | null }`
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 无待决挂载请求 → `{ ok: false }`；`path` 非字符串/空串/`stat` 失败/不是目录 → 一律按 `null`（暂不挂载）；有效目录则 `trustRoot(abs)` 后作为结果；推 `interaction_resolved{key, kind:'mount', path: dir|null}`
- 原版位置: `main/services/chat.ts:6759`（handler）+ `answerMount:6763`；preload `preload/index.ts:1206`

---

## 事件（非 invoke 通道）

### chat:event

- 形状: `ChatEventPayload { turnId: string, sessionId: string, event: ChatStreamEvent }`；`turnId` 为空串表示「不属于任何回合」（`todos` / `inserts` / `inserts_returned` / `card_resolved` 这类会话级推送）
- `ChatStreamEvent` 判别联合（`type` 字段）：`text_delta{text}` / `thinking_delta{text}` / `tool_call{id,name,args,depth?,agent?,parent?,bg?}` / `tool_result{id,name,summary,isError,depth?,agent?,parent?,bg?}` / `ask_user{key,questions}` / `plan_review{key,plan}` / `todos{state}` / `todo_done{id,title,items}` / `mount_request{key,tool,path,member?}` / `usage{input,output,cacheRead?,cacheWrite?}` / `reconnecting{attempt,max}` / `stream_reset` / `auto_retry{reason,attempt,max,limit?}` / `error{kind,message}` / `compacted{scope,status,message?}` / `compacting{active}` / `interaction_resolved{key,kind,answers?,decision?,feedback?,path?}` / `card_resolved{card,toolUseId,status,taskId?}` / `turn_start{user: DisplayMessage}` / `insert{text}` / `inserts{pending}` / `inserts_returned{text}` / `done{stopReason,durationMs?}` / `member_report` / `member_progress{groups}`
- 原版位置: `main/services/chat.ts:86-180`（类型）/ `publishChatEvent:2555` / `emit:2559` / `emitTurnStart:2569` / `emitTodos:2564` / `emitInserts:2673`；preload `preload/index.ts:1210`

### chat:sessions-changed

- 形状: 无 payload；渲染层收到后 `refreshSessions()` 重拉 `chat:list-sessions`
- 触发：新会话建档 / 删除 / 改名 / 归档 / 成员增删等在别处改变清单的操作
- 原版位置: `main/services/chat.ts:2552-2558`（`onSessionsChanged` 订阅）+ `publishSessionsChanged`；preload `preload/index.ts:1216`
