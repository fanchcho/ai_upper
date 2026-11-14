# IPC 通道契约台账：git / tasks / memory / mcp

来源工程：`/home/agent/shared_workspace/deva/apps/desktop/src`（只读审阅）。行号以实际读到的内容为准。

### git:available

- 入参: 无参数（preload `available()` 不传参）
- 出参: `{ available: false }` 或 `{ available: true, version: string, path: string }`；`version` 为 `git --version` 的 stdout trim 后去掉开头 `git version` 前缀，`path` 为 `resolveGitPath()` 解析结果
- 错误/边界: 无显式错误（不 throw）；未定位到 git 或 `--version` 退出码非 0 时返回 `{ available: false }`
- 原版位置: main/services/git.ts:625（handler） + resolveGitPath:152、runGitRaw:180

### git:status

- 入参: `dir: string`
- 出参: `GitStatus` = `{ isRepo: boolean, root: string, branch: string|null, detached: boolean, upstream: string|null, ahead: number, behind: number, remotes: string[], mergeInProgress: boolean, staged: GitFileStatus[], unstaged: GitFileStatus[], conflicts: GitFileStatus[] }`；每项 `GitFileStatus` = `{ path: string, rel: string, name: string, dir: string, letter: 'M'|'A'|'D'|'U'|'R'|'C'|'T', staged: boolean, unstaged: boolean, conflicted: boolean, untracked: boolean }`
- 错误/边界: `assertInside(dir)` 越界时 throw `拒绝访问：路径不在已打开的项目内`；`git status` 退出码非 0 时返回 `emptyStatus(dir)`（`isRepo:false`，其余字段为空/0）；文件列表经 `insideRootFlags` 过滤，根外文件被剔除；`root` 取 `rev-parse --show-toplevel` 失败时回落 `resolve(dir)`
- 原版位置: main/services/git.ts:638（handler） + parsePorcelainV2:311、emptyStatus:253、listRemotes:518、assertInside（main/services/fs-guard.ts:90）

### git:diff

- 入参: `dir: string`, `filePath: string`, `opts: { staged?: boolean; untracked?: boolean }`（默认 `{}`）
- 出参: `GitDiffLine[]`，每项 `{ type: 'ctx'|'add'|'del'|'hunk', oldNo?: number, newNo?: number, text: string }`
- 错误/边界: `assertInside(dir)` 与 `assertInside(resolve(filePath))` 越界时 throw；`git diff` 退出码非 0 → 返回 `[]`；`opts.untracked` 时文件 stat 失败 → `[]`；文件 > 2MB → 单条 `{ type:'hunk', text:'(文件过大，未显示)' }`；二进制 → 单条 `{ type:'hunk', text:'(二进制文件)' }`
- 原版位置: main/services/git.ts:681（handler） + diffUntracked:463、parseUnifiedDiff:418、looksBinary:456

### git:stage

- 入参: `dir: string`, `paths: string[]`
- 出参: `{ ok: true }` 或 `{ ok: false, message: string }`（`message` 为 git stderr trim）
- 错误/边界: `assertInside(dir)` 越界时 throw；`safeAbsPaths`→`assertAllInside` 任一越界即 throw；`paths` 非数组或全为空/非字符串时返回 `{ ok: false, message: 'no paths' }`
- 原版位置: main/services/git.ts:703（handler） + safeAbsPaths:506、runGitPaths:240、assertAllInside（main/services/fs-guard.ts:110）

### git:unstage

- 入参: `dir: string`, `paths: string[]`
- 出参: `{ ok: true }` 或 `{ ok: false, message: string }`（`message` 为 git stderr trim）
- 错误/边界: `assertInside(dir)` 越界时 throw；`assertAllInside` 越界 throw；无有效路径 → `{ ok: false, message: 'no paths' }`；有 HEAD 走 `reset -q HEAD`，无 HEAD 走 `rm --cached -q`
- 原版位置: main/services/git.ts:712（handler） + safeAbsPaths:506、runGitPaths:240

### git:discard

- 入参: `dir: string`, `trackedPaths: string[]`, `untrackedPaths: string[]`
- 出参: 恒为 `{ ok: true }`
- 错误/边界: `assertInside(dir)` 越界时 throw；`assertAllInside` 越界 throw；`checkout HEAD` 的退出码未被检查；未跟踪文件删除失败被 `.catch(() => {})` 吞掉，仍返回 `{ ok: true }`
- 原版位置: main/services/git.ts:725（handler） + safeAbsPaths:506、runGitPaths:240

### git:commit

- 入参: `dir: string`, `message: string`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: GitFailReason, message: string }`；`reason` 由 `classifyCommitError` 得出（`identity-needed` / `empty` / `error`）
- 错误/边界: `assertInside(dir)` 越界时 throw；`message` 非字符串或 trim 后为空 → `{ ok: false, reason: 'empty' }`（无 message）；提交信息写入 `getDevaHome()` 下的临时文件，finally 中 unlink（失败忽略）
- 原版位置: main/services/git.ts:740（handler） + classifyCommitError:498

### git:set-config

- 入参: `dir: string`, `name: string`, `email: string`, `global: boolean`
- 出参: 恒为 `{ ok: true }`
- 错误/边界: `assertInside(dir)` 越界时 throw；`name`/`email` trim 后为空则跳过对应 `git config` 调用；`git config` 的退出码未被检查，失败也返回 `{ ok: true }`
- 原版位置: main/services/git.ts:756（handler）

### git:branches

- 入参: `dir: string`
- 出参: `GitBranch[]`，每项 `{ name: string, current: boolean, remote: string|null, upstream: string|null }`；本地分支 `remote:null`，远程分支 `upstream:null` 且 `current:false`
- 错误/边界: `assertInside(dir)` 越界时 throw；`for-each-ref` 退出码非 0 → 返回 `[]`；跳过 `refs/remotes/*/HEAD` 这类 `symref` 行
- 原版位置: main/services/git.ts:770（handler） + listRemotes:518

### git:checkout

- 入参: `dir: string`, `ref: string`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: GitFailReason, message: string }`
- 错误/边界: `assertInside(dir)` 越界时 throw；`ref` 非字符串或空 → `{ ok: false, reason: 'error' }`（无 message）；失败时 stderr 匹配 `local changes|would be overwritten` → `reason:'dirty'`，否则 `'error'`
- 原版位置: main/services/git.ts:797（handler）

### git:create-branch

- 入参: `dir: string`, `name: string`, `checkout: boolean`
- 出参: `{ ok: true }` 或 `{ ok: false, message: string }`（本通道不带 `reason`）
- 错误/边界: `assertInside(dir)` 越界时 throw；`name` 非字符串或 trim 后为空 → `{ ok: false, message: 'empty name' }`；`checkout` 为真走 `checkout -b`，否则 `branch`
- 原版位置: main/services/git.ts:807（handler）

### git:checkout-remote

- 入参: `dir: string`, `remoteRef: string`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: GitFailReason, message?: string }`；`safeRef` 失败时为 `{ ok: false, reason: 'error', message: 'invalid ref' }`
- 错误/边界: `assertInside(dir)` 越界时 throw；`remoteRef` 不是非空字符串、以 `-` 开头或含空白/NUL → 返回 `badRef`；失败时 stderr 匹配 `local changes|would be overwritten` → `'dirty'`，否则 `'error'`
- 原版位置: main/services/git.ts:817（handler） + safeRef:514、badRef:523

### git:merge

- 入参: `dir: string`, `ref: string`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: GitFailReason, message: string }`；`reason` 由 `classifyRemoteError(stdout+stderr)` 得出
- 错误/边界: `assertInside(dir)` 越界时 throw；`safeRef(ref)` 失败 → `badRef`（`reason:'error', message:'invalid ref'`）；冲突信息在 stdout，`message` 为 stdout 与 stderr 拼接后 trim；执行 `git merge --no-edit <ref>`
- 原版位置: main/services/git.ts:827（handler） + safeRef:514、classifyRemoteError:483

### git:merge-abort

- 入参: `dir: string`
- 出参: `{ ok: true }` 或 `{ ok: false, message: string }`
- 错误/边界: `assertInside(dir)` 越界时 throw；执行 `git merge --abort`
- 原版位置: main/services/git.ts:838（handler）

### git:delete-branch

- 入参: `dir: string`, `name: string`, `force: boolean`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: 'error', message: string }`，或未合并时 `{ ok: false, reason: 'unmerged', count: number, message: string }`；`count` 取 `rev-list --count HEAD..<name>`（失败为 0）
- 错误/边界: `assertInside(dir)` 越界时 throw；`safeRef(name)` 失败 → `badRef`；stderr 匹配 `not fully merged` → `reason:'unmerged'`，否则 `'error'`；`force` 决定 `-D` / `-d`
- 原版位置: main/services/git.ts:845（handler） + safeRef:514、badRef:523

### git:rename-branch

- 入参: `dir: string`, `oldName: string`, `newName: string`
- 出参: `{ ok: true }` 或 `{ ok: false, message: string }`（本通道不带 `reason`）
- 错误/边界: `assertInside(dir)` 越界时 throw；`oldName` 或 `newName.trim()` 未通过 `safeRef` → `badRef`（`{ ok:false, reason:'error', message:'invalid ref' }`）；执行 `git branch -m <oldName> <newName.trim()>`
- 原版位置: main/services/git.ts:859（handler） + safeRef:514、badRef:523

### git:delete-remote-branch

- 入参: `dir: string`, `remote: string`, `branch: string`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: GitFailReason, message: string }`
- 错误/边界: `assertInside(dir)` 越界时 throw；`remote`/`branch` 未通过 `safeRef` 或 `remote` 不在 `listRemotes(dir)` 中 → `badRef`；执行 `git push <remote> --delete <branch>`（超时 `REMOTE_TIMEOUT`）；失败 `reason` 由 `classifyRemoteError(stderr)` 得出
- 原版位置: main/services/git.ts:867（handler） + safeRef:514、listRemotes:518、classifyRemoteError:483

### git:log

- 入参: `dir: string`, `depth?: number`（缺省 30；实际取 `Math.max(1, Math.min(500, depth))`）
- 出参: `GitCommit[]`，每项 `{ oid: string, short: string, author: string, email: string, timestamp: number, subject: string }`；`timestamp` 为 `%at` 乘 1000
- 错误/边界: `assertInside(dir)` 越界时 throw；`git log` 退出码非 0（如空仓库）→ 返回 `[]`
- 原版位置: main/services/git.ts:878（handler）

### git:init

- 入参: `dir: string`
- 出参: `{ ok: true }` 或 `{ ok: false, message: string }`
- 错误/边界: `assertInside(dir)` 越界时 throw；执行 `git init`
- 原版位置: main/services/git.ts:893（handler）

### git:fetch

- 入参: `dir: string`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: GitFailReason, message: string }`
- 错误/边界: `assertInside(dir)` 越界时 throw；执行 `git fetch --prune`（超时 `REMOTE_TIMEOUT`）；失败 `reason` 由 `classifyRemoteError(stderr)` 得出
- 原版位置: main/services/git.ts:900（handler） + classifyRemoteError:483

### git:pull

- 入参: `dir: string`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: GitFailReason, message: string }`
- 错误/边界: `assertInside(dir)` 越界时 throw；执行 `git pull`（超时 `REMOTE_TIMEOUT`）；失败 `reason` 由 `classifyRemoteError(stderr)` 得出
- 原版位置: main/services/git.ts:909（handler） + classifyRemoteError:483

### git:push

- 入参: `dir: string`, `setUpstreamBranch: string | null`
- 出参: `{ ok: true }` 或 `{ ok: false, reason: GitFailReason, message: string }`
- 错误/边界: `assertInside(dir)` 越界时 throw；`setUpstreamBranch` 为非空字符串时执行 `git push -u origin <branch>`，否则执行 `git push`（超时 `REMOTE_TIMEOUT`）；失败 `reason` 由 `classifyRemoteError(stderr)` 得出
- 原版位置: main/services/git.ts:918（handler） + classifyRemoteError:483

### git:generate-commit-message

- 入参: `dir: string`, `model: GitGenModel`（`{ adapter: 'anthropic'|'openai'|'responses', providerId: string, baseURL: string, model: string }`）, `locale?: 'zh-CN'|'en'`, `reqId?: string`
- 出参: `GitGenerateResult` 两种形状：成功 `{ ok: true, text: string }`，用户中断时 `{ ok: true, text: string, aborted: true }`；失败 `{ ok: false, reason: GitFailReason, message?: string }`
- 错误/边界: `assertInside(dir)` 越界时 throw（在返回对象之外）；`model` 缺失或 `model.model` 非非空字符串 → `{ ok:false, reason:'error', message:'no-model' }`；diff 命令失败 → `reason:'error'` + stderr；无任何 diff（含未跟踪文件拼入后仍空）→ `{ ok:false, reason:'empty' }`（无 message）；仅 `locale==='en'` 视为英文，其余回退 `zh-CN`；patch 超过 24000 字符截断；60s 定时 abort、窗口 destroyed 时 abort；用户中断（id 已不在 `genControllers`）返回 `aborted:true`；有错误且无文本 → `reason=genReason(errKind)`；清洗后为空 → `{ ok:false, reason:'error', message:'empty-response' }`；异常 → `{ ok:false, reason:'error', message: err.message }`
- 原版位置: main/services/git.ts:934（handler） + cleanCommitMessage:603、commitSystemPrompt:571、normGenLocale:562、commitUserText:587、diffUntracked:463、genReason:615、streamChat（main/providers）

### git:cancel-commit-message

- 入参: `reqId: string`
- 出参: `boolean`；找到并中断返回 `true`，无对应进行中请求返回 `false`
- 错误/边界: 无显式错误（同步 handler，不 throw）
- 原版位置: main/services/git.ts:1032（handler） + genControllers:539

### tasks:list

- 入参: 无参数
- 出参: `TaskRecord[]`，按 `createdAt` 升序；每项含 `{ id, title, prompt, schedule, auth, sessionId, ownerSessionId?, originSessionId?, status, createdAt, updatedAt, lastRunAt, nextRunAt, consecutiveErrors, runs }`
- 错误/边界: 无显式错误；`tasks.json` 缺失或解析失败 → 空数组（`ensureLoaded` 捕获异常）
- 原版位置: main/services/tasks.ts:480（handler） + listTasks:104、ensureLoaded:47

### tasks:get

- 入参: `id: string`
- 出参: `TaskRecord | null`（不存在为 `null`）
- 错误/边界: 无显式错误
- 原版位置: main/services/tasks.ts:481（handler） + getTask:109

### tasks:create

- 入参: `input: TaskCreateInput`（`{ title: string, prompt: string, schedule: TaskSchedule, auth: TaskAuthorization, originSessionId?: string, ownerSessionId?: string }`；handler 固定把 `originSessionId` 覆盖为 `undefined`）
- 出参: `CreateTaskResult` = `{ ok: true, task: TaskRecord }` 或 `{ ok: false, error: 'invalid-input'|'invalid-tz'|'invalid-cron'|'invalid-once'|'expired' }`
- 错误/边界: `input` 非对象、`prompt` trim 后为空、`schedule` 缺失/非对象 → `invalid-input`；`schedule.tz` 无效 → `invalid-tz`；`recurring` 的 cron 非法或 `nextRun` 为 null → `invalid-cron`；`once` 的 `nextRun` 为 null → `invalid-once`；`first` 为 null 且为 once → `expired`；`title` 为空时取 `prompt` 前 30 字符；`sessionId` 恒为 `task-<id>`；`ownerSessionId` 仅通过 `validOwner` 时才写入
- 原版位置: main/services/tasks.ts:483（handler） + createTask:178、sanitizeAuth:166、validOwner:130、parseCron/isValidTimeZone/nextRun（main/services/schedule.ts）

### tasks:update

- 入参: `input: TaskUpdateInput`（`{ id: string, title?, prompt?, schedule?, auth?, ownerSessionId?: string|null }`）
- 出参: `TaskRecord | null`（`id` 不存在为 `null`）
- 错误/边界: 无显式错误（不 throw）；`title` 为空串时保留原标题；`prompt` trim 后为空则不更新；`schedule` 仅在 `isValidTimeZone` 且 cron/once 合法时应用，否则静默忽略；`ownerSessionId` 为 null 或不合格会话按独立运行处理
- 原版位置: main/services/tasks.ts:486（handler） + updateTask:231、validOwner:130

### tasks:delete

- 入参: `id: string`
- 出参: 恒为 `{ ok: true }`（任务不存在也返回 ok）
- 错误/边界: 无显式错误；若任务带 `ownerSessionId`，调用注入的 `purgeSessionImpl` 删除其任务对话
- 原版位置: main/services/tasks.ts:489（handler） + deleteTask:286

### tasks:set-status

- 入参: `id: string`, `status: TaskStatus`（`'active'|'paused'|'completed'|'error'`）
- 出参: `TaskRecord | null`（不存在为 `null`）
- 错误/边界: 无显式错误；`status==='active'` 时清零 `consecutiveErrors` 并重算 `nextRunAt`，若为 `once` 且 `nextRunAt` 为 null 则回落 `completed`
- 原版位置: main/services/tasks.ts:493（handler） + setTaskStatus:344

### tasks:preview

- 入参: `schedule: TaskSchedule`, `locale: 'zh-CN'|'en'`, `allowPast?: boolean`（handler 归一：`locale === 'en' ? 'en' : 'zh-CN'`，`allowPast === true`）
- 出参: `PreviewScheduleResult` = `{ ok: true, description: string, nextRunAt: number|null }` 或 `{ ok: false, error: 'invalid-input'|'invalid-tz'|'invalid-cron'|'invalid-once' }`
- 错误/边界: 无显式 throw；`schedule` 缺失/非对象 → `invalid-input`；tz 无效 → `invalid-tz`；`recurring` 的 cron 非法或 `nextRun` 为 null → `invalid-cron`；`once` 的 `nextRun` 为 null 且（未允许过去或墙钟不可解析）→ `invalid-once`；`allowPast` 为真且墙钟合法时返回 `{ ok:true, nextRunAt:null }`
- 原版位置: main/services/tasks.ts:497（handler） + previewSchedule:434

### tasks:run-now

- 入参: `id: string`
- 出参: `{ ok: boolean, reason?: string, already?: 'running'|'queued' }`
- 错误/边界: scheduler 未装载 → `{ ok: false, reason: 'scheduler-not-ready' }`；任务不存在 → `{ ok: false, reason: 'not-found' }`；运行器返回 `enqueued` → `{ ok: true }`；已在运行/排队 → `{ ok: true, already: 'running'|'queued' }`（不当作错误）
- 原版位置: main/services/tasks.ts:504（handler） + setTaskRunner:470、getTask:109

### memory:list

- 入参: `root?: string`
- 出参: `MemorySnapshot` = `{ entries: MemoryEntry[], used: number, budget: number, maxEntries: number, maxChars: number }`；`MemoryEntry` = `{ id: string, content: string, createdAt: number, updatedAt: number }`
- 错误/边界: `ipcScope`：`root` 为 `undefined`/`null` → 全局；非空字符串 → 项目作用域；空串/纯空白/非字符串 → throw `memory: invalid root`；文件缺失或损坏 → 空条目（不抛错）
- 原版位置: main/services/memory.ts:339（handler） + ipcScope:328、snapshot:309、listMemories:96

### memory:write

- 入参: `content: string`, `id?: string`, `root?: string`
- 出参: `MemoryIpcResult` = `{ ok: true, snapshot: MemorySnapshot }` 或 `{ ok: false, code: MemoryErrorCode }`（`code: 'empty'|'tooLong'|'full'|'budget'|'notFound'|'duplicate'`）
- 错误/边界: `ipcScope(root)` 非法 root 时 throw `memory: invalid root`；`content` 经 `String(content ?? '')` 转换；正文规整后为空 → `code:'empty'`；超单条字数 → `'tooLong'`；带 `id` 但不存在 → `'notFound'`；带 `id` 且与另一条内容相同 → `'duplicate'`；无 `id` 且与已有条目逐字相同 → handler 刻意返回 `{ ok:false, code:'duplicate' }`（虽 writeMemory 本身返回幂等成功）；条目已满 → `'full'`；超总量预算 → `'budget'`；`id` 为空串视为未传
- 原版位置: main/services/memory.ts:340（handler） + writeMemory:169、ipcScope:328、snapshot:309

### memory:delete

- 入参: `id: string`, `root?: string`
- 出参: 恒为 `{ ok: true, snapshot: MemorySnapshot }`（`id` 不存在也返回 ok）
- 错误/边界: `ipcScope(root)` 非法 root 时 throw `memory: invalid root`；`id` 经 `String(id ?? '')`
- 原版位置: main/services/memory.ts:349（handler） + deleteMemory:223、ipcScope:328

### memory:clear

- 入参: `root?: string`
- 出参: 恒为 `{ ok: true, snapshot: MemorySnapshot }`
- 错误/边界: `ipcScope(root)` 非法 root 时 throw `memory: invalid root`
- 原版位置: main/services/memory.ts:354（handler） + clearMemories:233、ipcScope:328

### mcp:list

- 入参: 无参数
- 出参: `McpServerView[]`；每项 = `McpServerConfig` 字段（`id, name, description, transport, command?, args?, env?, url?, headers?`）加 `{ enabled: boolean, roles: string[]|null, scope:'global', source:'custom', status: McpStatus, toolCount: number, lastError: string|null, missingSecrets: string[], tools: { name: string, fqName: string, description: string }[] }`；按 `name` localeCompare 排序
- 错误/边界: 无显式错误；`mcp.json` 缺失/损坏 → 空数组；非法 id 的条目被跳过
- 原版位置: main/services/mcp.ts:633（handler） + listServers:182、viewOf:156、listServerConfigs（main/services/mcp-config.ts:185）

### mcp:get

- 入参: `id: string`
- 出参: `McpServerConfig | null`（id 非法或不存在为 `null`）
- 错误/边界: 无显式错误；`isSafeId` 不通过返回 `null`
- 原版位置: main/services/mcp.ts:634（handler） + getServerConfig（main/services/mcp-config.ts:196）、isSafeId:87

### mcp:upsert

- 入参: `input: McpServerInput`（`{ id?, name: string, description?, transport: 'stdio'|'sse'|'http', command?, args?, env?, url?, headers?, enabled? }`）
- 出参: `McpServerConfig`（写入后的最终记录；不含运行期状态）
- 错误/边界: 无显式错误（同步）；`name` trim 后为空 → 存为 `'未命名 MCP'`；`id` 缺失或非法 → 据 name 生成唯一 id（slug，冲突加 `-2` 等）；`transport` 非 `sse`/`http` → 回落 `stdio`；`args` 仅保留字符串项，env/headers 丢弃空键；新建且未给 `enabled` 时默认关闭
- 原版位置: main/services/mcp.ts:635（handler） + upsertServer（main/services/mcp-config.ts:204）

### mcp:remove

- 入参: `id: string`
- 出参: 恒为 `{ ok: true }`
- 错误/边界: 无显式错误；先 `forget(id)` 撤运行态，再 `deleteServer(id)`（清配置、启用态、角色、`mcp:<id>:` 前缀密钥）；非法 id 时 `deleteServer` 直接返回，仍回 `{ ok: true }`
- 原版位置: main/services/mcp.ts:636（handler） + forget:473、deleteServer（main/services/mcp-config.ts:245）

### mcp:set-roles

- 入参: `id: string`, `roles: string[] | null`
- 出参: `{ ok: boolean }`；服务不存在 → `{ ok: false }`，否则 `{ ok: true }`
- 错误/边界: 无显式错误；`roles` 非数组时按 `null`（= 全部角色）处理；数组仅保留非空字符串并去重；写后 `broadcast(id)`，不触发重连
- 原版位置: main/services/mcp.ts:642（handler） + setRoles（main/services/ext-roles.ts:40）、getServerConfig（main/services/mcp-config.ts:196）

### mcp:set-enabled

- 入参: `id: string`, `enabled: boolean`
- 出参: 恒为 `{ ok: true }`
- 错误/边界: 无显式错误；`enabled` 经 `Boolean(...)`；非法 id 时 `setEnabled` 直接返回（仍回 `{ ok: true }`）；写入后由配置变更通知触发 `reconcile`
- 原版位置: main/services/mcp.ts:649（handler） + setEnabled（main/services/mcp-config.ts:177）

### mcp:retry

- 入参: `id: string`
- 出参: `McpServerView | null`（`reconcile` 后重新读取配置，不存在为 `null`）
- 错误/边界: 无显式错误（`reconcile` 内部把失败降级为状态 `error`，不向外抛）；未启用时只会落到 `disconnected`，不会连上
- 原版位置: main/services/mcp.ts:654（handler） + reconcile:384、viewOf:156、getServerConfig（main/services/mcp-config.ts:196）

### mcp:set-secret

- 入参: `id: string`, `field: string`, `value: string`
- 出参: `{ ok: boolean, available: boolean }`
- 错误/边界: 无显式 throw；`field` trim 后为空 → `{ ok: false, available: true }`；`value` 为空串 → 删除该密钥并返回 `{ ok: true, available }`；加密不可用且 `value` 非空 → `{ ok: false, available: false }`；写入键为 `mcp:<id>:<field>`；成功后若服务已启用则防抖重连；非字符串 value 按空串处理
- 原版位置: main/services/mcp.ts:660（handler） + setSecret（main/services/secrets.ts:75）、scheduleReconcile:421

### mcp:has-secret

- 入参: `id: string`, `field: string`
- 出参: `boolean`（键 `mcp:<id>:<field.trim()>` 是否存在）
- 错误/边界: 无显式错误；`field` 为空时查询 `mcp:<id>:` 前缀键，实际恒为 `false`
- 原版位置: main/services/mcp.ts:675（handler） + hasSecret（main/services/secrets.ts:93）
