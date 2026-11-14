### browser:state
- 入参: 无（handler 不接收参数）
- 出参: `BrowserUiState`：`{ open: boolean, pinned: boolean, active: string | null, tabs: BrowserUiTab[], current: Record<sessionId, tabId>, operating: Record<sessionId, { tab: string, action: string, label?: string }>, handoff: Record<sessionId, { tab: string, reason: 'login'|'captcha'|'upload'|'confirm'|'other', message: string, who?: string }> }`；`BrowserUiTab = { id, sessionId, personaId?, title, url, loading, canGoBack, canGoForward }`。同名事件 `browser:state` 另以 60ms 合并推给主窗口与外框。
- 错误/边界: 无显式错误；只报 `visibleTabs()` 选中的 `kind === 'window'` 网页（shown、该对话有 handoff、窗口展开且为该标签、pinnedPreview），off-screen 与后台网页不出现；`url === 'about:blank'` 时 url/title 归空串。
- 原版位置: `main/services/browser/host.ts:554`（handler）+ `uiState:131` / `visibleTabs:121` / `push:172`；preload `preload/index.ts:1405`（onState:1408）

### browser:open
- 入参: `opts?: { tab?: string; sessionId?: string }`，整体可省略（默认 `{}`）；两个字段均可选
- 出参: `{ ok: true }`（恒为 true）
- 错误/边界: 无显式错误；`tab` 不存在时 `showWindow` 只展开窗口、不切标签；省略 tab 且 sessionId 无当前标签时传 `null`；若运行时把 opts 传成 null，`opts.tab` 会抛 TypeError 使 invoke reject。
- 原版位置: `main/services/browser/host.ts:556`（handler）+ `showWindow:327` / `currentBySession:344`（pages.ts:344）；preload `preload/index.ts:1414`

### browser:dock
- 入参: 无
- 出参: `{ ok: true }`
- 错误/边界: 无显式错误；窗口不存在/已销毁/已处于收起态时 `dock()` 直接 return，仍回 `{ ok: true }`。
- 原版位置: `main/services/browser/host.ts:561`（handler）+ `dock:347`；preload `preload/index.ts:1417`

### browser:close-session
- 入参: `sessionId: string`
- 出参: `{ ok: true } | { ok: false }`
- 错误/边界: `sessionId` 非 string，或该对话正在等用户操作（`handoffs.has(sessionId)`）时返回 `{ ok: false }` 且不关任何标签；其余返回 `{ ok: true }`。
- 原版位置: `main/services/browser/host.ts:566`（handler）+ `closeSessionPages:356`（pages.ts:356）；preload `preload/index.ts:1419`

### browser:preview-pinned
- 入参: `tab: string | null`
- 出参: `{ ok: true }`
- 错误/边界: 无显式错误；非 string 一律按 `null`（取消固定）处理；仅触发一次状态推送，不校验标签是否存在。
- 原版位置: `main/services/browser/host.ts:572`（handler）+ `push:172` / `isPageInUse:92`；preload `preload/index.ts:1422`

### browser:live-start
- 入参: `tab: string`
- 出参: `boolean`（`pageById(tab)` 不存在时同步 false，否则为 `startLive` 的 Promise 结果）
- 错误/边界: `pageById` 只认 `kind === 'window'` 的标签，off-screen 标签回 false；CDP `Page.startScreencast` 失败或期间状态被替换时 `startLive` 内部 catch 并回 false；已在该标签推流时直接回 true。
- 原版位置: `main/services/browser/host.ts:579`（handler）+ `startLive:28`（live.ts:28） / `pageById:535`；preload `preload/index.ts:1425`

### browser:live-stop
- 入参: 无
- 出参: `{ ok: true }`
- 错误/边界: 无显式错误；当前没有在推流时 `stopLive()` 直接 return；`Page.stopScreencast` 的失败被 `.catch(() => {})` 吞掉。
- 原版位置: `main/services/browser/host.ts:582`（handler）+ `stopLive:71`（live.ts:71）；preload `preload/index.ts:1426`

### browser:pin
- 入参: `on: boolean`
- 出参: `{ ok: true }`
- 错误/边界: 无显式错误；只有严格 `true` 才置顶，其余（含 undefined/truthy 非 true）一律取消置顶。
- 原版位置: `main/services/browser/host.ts:586`（handler）+ `setPinned:367`；preload `preload/index.ts:1432`

### browser:activate
- 入参: `tab: string`
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；标签不在 `views`（窗口标签）中时 `activateTab` 直接 return，但仍回 `{ ok: true }`。
- 原版位置: `main/services/browser/host.ts:590`（handler）+ `activateTab:373`；preload `preload/index.ts:1433`

### browser:close-tab
- 入参: `tab: string`
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；标签不存在时不做任何事（`closePage` 内部 `if (!p) return`），仍回 `{ ok: true }`。
- 原版位置: `main/services/browser/host.ts:594`（handler）+ `pageById:535` / `closePage:348`（pages.ts:348）；preload `preload/index.ts:1434`

### browser:nav
- 入参: `tab: string`, `what: 'back' | 'forward' | 'reload' | 'stop'`
- 出参: `{ ok: false }`（标签不存在）或 `{ ok: true }`
- 错误/边界: `pageById` 找不到返回 `{ ok: false }`；back/forward 在 `canGoBack()`/`canGoForward()` 为 false 时静默不动作；`what` 为其他值时不做任何导航但仍回 `{ ok: true }`。
- 原版位置: `main/services/browser/host.ts:598`（handler）+ `p.wc.navigationHistory.goBack/goForward`、`p.wc.reload/stop`；preload `preload/index.ts:1435`

### browser:menu
- 入参: `tab: string`, `labels: Record<string, string>`, `at: { x: number; y: number }`
- 出参: `Promise<{ ok: true }>`，在原生菜单关闭的 `popup` 回调里 resolve；标签不存在或宿主窗口已销毁时 `{ ok: false }`
- 错误/边界: 无显式错误分支；`at.x/at.y` 非数值按 0；`labels` 缺项时回退显示键名；复制链接/系统浏览器打开仅对 `http(s)` URL enabled；`Menu.buildFromTemplate(...).popup` 未包 try/catch，构造失败会使 invoke reject。
- 原版位置: `main/services/browser/host.ts:610`（handler）+ `Menu.buildFromTemplate/popup:630`；preload `preload/index.ts:1441`

### browser:thumbnail
- 入参: `tab: string`
- 出参: `string | null`（`capturePage()` 后 `resize({ width: 480 })` 的 data URL）
- 错误/边界: 标签不存在 → null；`capturePage()` 抛错 → null；截图为空图（`img.isEmpty()`）→ null。
- 原版位置: `main/services/browser/host.ts:639`（handler）+ `p.wc.capturePage:643` / `resize:645`；preload `preload/index.ts:1444`

### browser:handoff
- 入参: `sessionId: string`, `answer: 'done' | 'skip'`
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；该对话没有进行中的 handoff 时 `respondHandoff` 无操作；`answer === 'done'` 解析为 `'done'`，否则解析为 `'skipped'`。
- 原版位置: `main/services/browser/host.ts:650`（handler）+ `respondHandoff:524`；preload `preload/index.ts:1446`

### browser:stop
- 入参: `sessionId: string`
- 出参: `{ ok: boolean }`，`ok` 即 `sessionAborter(sessionId)` 的返回值
- 错误/边界: 该对话没有进行中的回合时返回 `{ ok: false }`；有则中止回合并返回 `{ ok: true }`；无论结果都会调用 `clearOperating(sessionId)`。`sessionAborter` 由 chat.ts 注入。
- 原版位置: `main/services/browser/host.ts:654`（handler）+ `clearOperating:468` / 注入处 `main/services/chat.ts:6459`；preload `preload/index.ts:1449`

### browser:ready
- 入参: 无
- 出参: `BrowserUiState`（与 browser:state 相同形状）
- 错误/边界: 无显式错误；先调用 `push()` 触发一次广播，再同步返回当前 `uiState()`。
- 原版位置: `main/services/browser/host.ts:660`（handler）+ `push:172` / `uiState:131`；preload `preload/index.ts:1407`

### terminal:list-shells
- 入参: 无
- 出参: `ShellProfile[]`，每项只含 `{ id: string, label: string, isDefault?: boolean }`
- 错误/边界: 无显式错误；`detectShells()` 结果模块级缓存，仅首次真正探测；探测不到时回落列表（Windows 为 cmd，POSIX 为 /bin/sh）并标 isDefault；`path`/`args` 不外泄。
- 原版位置: `main/services/terminal.ts:87`（handler）+ `detectShells:103`（shells.ts:103） / `detectWindows:34` / `detectPosix:80`；preload `preload/index.ts:1223`

### terminal:create
- 入参: `opts: { cols: number, rows: number, cwd: string | null, shellId?: string | null }`（shellId 可选）
- 出参: `{ id: string }`，id 形如 `t1`、`t2`（`t${++seq}`）
- 错误/边界: 无显式错误返回；同步返回 id，不等待 PTY 真正起来；cols/rows/cwd 不做校验，由 pty-host 兜底（`cols || 80`、`rows || 24`、cwd 不存在回主目录）；spawn 失败由 pty-host 补发 `terminal:exit`（exitCode -1）；`ensureChild()` 的 `utilityProcess.fork` 未包 try/catch，fork 抛错会使 invoke reject。
- 原版位置: `main/services/terminal.ts:91`（handler）+ `ensureChild:50` / `send:45` / `resolveShell:116`（shells.ts:116） / `handleCreate:55`（pty-host.ts:55）；preload `preload/index.ts:1224`

### terminal:input
- 入参: `id: string`, `data: string`
- 出参: 无返回值，事件 `terminal:data`（该会话 pty 输出）/ `terminal:exit`（进程退出）
- 错误/边界: 无显式错误；id 在 pty-host 中没有对应会话时 `sessions.get(msg.id)?.write` 静默忽略；宿主未就绪时消息进入 pending 队列，spawn 后冲刷。
- 原版位置: `main/services/terminal.ts:100`（handler）+ `send:45` / `flush:39` / pty-host.ts:84；preload `preload/index.ts:1226`

### terminal:resize
- 入参: `id: string`, `cols: number`, `rows: number`
- 出参: 无返回值，事件 `terminal:data` / `terminal:exit`（均为该会话后续 pty 事件）
- 错误/边界: 无显式错误；pty-host 中 `resize` 抛错（尺寸过小或会话已结束）被 try/catch 吞掉；id 不存在时无操作。
- 原版位置: `main/services/terminal.ts:104`（handler）+ `send:45` / pty-host.ts:87；preload `preload/index.ts:1227`

### terminal:dispose
- 入参: `id: string`
- 出参: 无返回值，事件 `terminal:exit`（kill 后 pty 退出触发，exitCode 由进程给出）
- 错误/边界: 无显式错误；先从 `activeIds` 删除再下发 dispose；pty-host 中 `kill()` 抛错被吞掉，会话仍从 `sessions` 删除；id 不存在时无影响。
- 原版位置: `main/services/terminal.ts:108`（handler）+ `send:45` / pty-host.ts:94；preload `preload/index.ts:1229`

### deliverables:inspect
- 入参: `sessionId: unknown`, `toolUseId: unknown`（两者均非 string 即按无效处理）
- 出参: `DeliverableInfo[]`，每项 `{ path: string, name: string, dir: string, size: number | null, openable: boolean }`
- 错误/边界: 参数非 string、会话不存在、找不到该 tool_use、或该调用不是 `present_files` 时返回空数组；`fs.stat` 失败或目标非普通文件时 `size: null`；`openable` 仅由扩展名是否在 `OPENABLE` 决定。
- 原版位置: `main/services/deliverables.ts:70`（handler）+ `deliveredPaths:39` / `OPENABLE:18`；preload `preload/index.ts:1384`

### deliverables:thumbnail
- 入参: `sessionId: unknown`, `toolUseId: unknown`, `index: unknown`
- 出参: `string | null`（data URL）
- 错误/边界: `index` 非整数、路径取不到、或目标不是文件 → null；系统缩略图失败（Linux 不支持/无缩略图）回落到 `app.getFileIcon`；图标为空或抛错 → null。
- 原版位置: `main/services/deliverables.ts:88`（handler）+ `deliveredPath:59` / `createThumbnailFromPath:94` / `getFileIcon:100`；preload `preload/index.ts:1387`

### deliverables:open
- 入参: `sessionId: unknown`, `toolUseId: unknown`, `index: unknown`
- 出参: `{ ok: boolean }`
- 错误/边界: 路径取不到、扩展名不在 `OPENABLE`、或目标不是文件 → `{ ok: false }`；`shell.openPath` 成功返回空串，返回非空错误描述时 → `{ ok: false }`。
- 原版位置: `main/services/deliverables.ts:108`（handler）+ `OPENABLE:18` / `deliveredPath:59` / `shell.openPath:114`；preload `preload/index.ts:1390`

### deliverables:reveal
- 入参: `sessionId: unknown`, `toolUseId: unknown`, `index: unknown`
- 出参: `{ ok: boolean }`
- 错误/边界: 路径取不到或不是文件 → `{ ok: false }`；其余调用 `shell.showItemInFolder(p)` 后恒回 `{ ok: true }`（该 API 无回执）。
- 原版位置: `main/services/deliverables.ts:118`（handler）+ `deliveredPath:59` / `shell.showItemInFolder:123`；preload `preload/index.ts:1393`

### remote:get-state
- 入参: 无
- 出参: `{ bots: BotView[] }`，`BotView = { id: string, platform: 'feishu'|'telegram', name: string, region?: 'cn'|'intl', username?: string, enabled: boolean, state: 'off'|'connecting'|'connected'|'error', error?: string, replyMode: 'stream'|'final', scope: { mode: 'all'|'personas'|'sessions', personas: string[], sessions: string[] }, users: { id: string, name?: string, pairedAt: number }[] }`
- 错误/边界: 无显式错误；机器人按 `createdAt` 升序；未注册到 hub 的通道由 `channelState` 回 `{ state: 'off' }`；`region` 仅飞书有值，`username` 仅 settings 里有字符串时才有。
- 原版位置: `main/services/remote/index.ts:209`（handler）+ `publicState:80` / `channelState:76`（hub.ts:76） / `listBots:103`（store.ts:103）；preload `preload/index.ts:1464`

### remote:scan-start
- 入参: `platform: Platform`（`'feishu' | 'telegram'`）, `opts?: { token?: string }`（可选，仅 Telegram 用）
- 出参: `{ ok: true, scanId: string, qr: string, link?: string, expiresAt: number } | { ok: false, error: string }`；类型声明里的 `userCode?` 在实现中从不返回
- 错误/边界: 平台不是 feishu/telegram → `{ ok: false, error: '暂不支持这个平台。' }`；飞书异常 → `{ ok: false, error: '获取二维码失败：<msg>' }`；Telegram 异常原样回 message（Token 格式不对、机器人已添加过都在此抛出）；异步结果（done/denied/expired/cancelled/error，含密钥保存失败）经 `remote:scan` 事件推回；`QRCode.toDataURL` 未捕获异常会使 invoke reject。
- 原版位置: `main/services/remote/index.ts:213`（handler）+ `feishuScan:136` / `telegramScan:159` / `QRCode.toDataURL:269` / `scans:188`；preload `preload/index.ts:1466`

### remote:scan-cancel
- 入参: `scanId: string`
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；scanId 不存在时 `scans.get(scanId)?.()` 无操作；取消后该扫码的后续结果经 `remote:scan` 以对应状态推回。
- 原版位置: `main/services/remote/index.ts:277`（handler）+ `scans` Map:188 / `scan.cancel:233`；preload `preload/index.ts:1473`

### remote:set-enabled
- 入参: `id: ChannelId`（string）, `enabled: boolean`
- 出参: `{ ok: true } | { ok: false, error: string }`
- 错误/边界: 机器人不存在 → `{ ok: false, error: '机器人不存在。' }`；启用时 `launch` 返回错误文案（凭据丢失、适配器构造失败）→ `{ ok: false, error }`；停用时 `stopChannel` 内部吞掉停止异常后照常 `{ ok: true }`。适配器 `start()` 的失败被 `startChannel` 内部 catch 成通道 state=error，不会反映到本返回值。
- 原版位置: `main/services/remote/index.ts:282`（handler）+ `launch:100` / `startChannel:81`（hub.ts:81） / `stopChannel:138`（hub.ts:138） / `updateBot:125`（store.ts:125）；preload `preload/index.ts:1474`

### remote:set-reply-mode
- 入参: `id: ChannelId`, `mode: ReplyMode`（`'stream' | 'final'`）
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；只有 `mode === 'final'` 保留，其余一律写成 `'stream'`；`id` 不存在时 `updateBot` 无操作，仍回 `{ ok: true }`。
- 原版位置: `main/services/remote/index.ts:298`（handler）+ `updateBot:125`（store.ts:125） / `push:206`；preload `preload/index.ts:1476`

### remote:set-scope
- 入参: `id: ChannelId`, `scope: ReplyScope`（`{ mode, personas: string[], sessions: string[] }`）
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；scope 经 `normalizeScope` 归一：非对象的输入回 `DEFAULT_SCOPE`，mode 非 `personas`/`sessions` 一律 `all`，两个清单去重并剔除非字符串/空串；id 不存在时无操作。
- 原版位置: `main/services/remote/index.ts:304`（handler）+ `normalizeScope:47`（store.ts:47） / `DEFAULT_SCOPE:40` / `updateBot:125`；preload `preload/index.ts:1478`

### remote:delete-bot
- 入参: `id: ChannelId`
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；先 `stopChannel`（内部 catch 停止失败），再按前缀 `remote:<id>:` 删密钥、删配置；三者均幂等，机器人不存在也回 ok。
- 原版位置: `main/services/remote/index.ts:311`（handler）+ `stopChannel:138`（hub.ts:138） / `deleteSecretsByPrefix:108`（secrets.ts:108） / `deleteBot:120`（store.ts:120）；preload `preload/index.ts:1480`

### remote:pair-code
- 入参: `id: ChannelId`
- 出参: `{ code: string, expiresAt: number }`（code 为 6 位数字串，有效期 10 分钟）
- 错误/边界: 无显式错误；不校验机器人是否存在；新码顶替同通道旧码，输错 5 次作废，过期时间 `PAIR_TTL_MS`。
- 原版位置: `main/services/remote/index.ts:319`（handler）+ `issuePairCode:167`（hub.ts:167） / `PAIR_TTL_MS:162`；preload `preload/index.ts:1481`

### remote:pair-cancel
- 入参: `id: ChannelId`
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；该通道没有进行中的邀请码时 `pairing.delete` 无副作用。
- 原版位置: `main/services/remote/index.ts:321`（handler）+ `cancelPairCode:175`（hub.ts:175）；preload `preload/index.ts:1483`

### remote:remove-user
- 入参: `id: ChannelId`, `userId: string`
- 出参: `{ ok: true }`（恒真）
- 错误/边界: 无显式错误；用户不存在时配置无变化；移除时一并删除该用户 chatId 对应的会话绑定，随后 `notifyState`。
- 原版位置: `main/services/remote/index.ts:326`（handler）+ `removePairedUser:179`（hub.ts:179） / `updateChannelConfig`（store.ts）；preload `preload/index.ts:1484`

### update:get-state
- 入参: 无
- 出参: `UpdateState` 判别联合：`{ phase: 'idle' } | { phase: 'checking' } | { phase: 'latest' } | { phase: 'available', release: { version, pageUrl }, mode: 'auto'|'manual'|'portable', file: string | null } | { phase: 'downloading', release, percent } | { phase: 'downloaded', release } | { phase: 'error', stage: 'check'|'download', message, release? }`
- 错误/边界: 无显式错误；直接返回模块内存中的 `state`，不发起任何网络请求。
- 原版位置: `main/services/updater.ts:270`（handler）+ `state:39` / `setState:45` / `shared/update.ts:24`；preload `preload/index.ts:1452`

### update:check
- 入参: 无
- 出参: 无（`Promise<void>`）；结果经 `update:state` 事件推送
- 错误/边界: 当前 phase 为 `checking`/`downloading`/`downloaded` 时直接 return，不重查；API 与网页都失败等异常 → `{ phase: 'error', stage: 'check', message }`；版本不高于本机或所需文件尚未传完 → `{ phase: 'latest' }`（不算错误）。
- 原版位置: `main/services/updater.ts:271`（handler）+ `check:186` / `latestRelease:122` / `compareVersions:59`；preload `preload/index.ts:1453`

### update:download
- 入参: 无
- 出参: 无（`Promise<void>`）；进度经 `update:state`（`downloading` + percent）推送，结果经同一事件推送
- 错误/边界: 没有 `found`、或 phase 已是 `downloading`/`downloaded` → 直接 return；`mode !== 'auto'` 时 `shell.openExternal` 打开直链/Release 页后 return（该分支未包 try/catch，失败会 reject）；auto 模式查不到更高版本时抛出 `latest.yml not found in this release`，被捕获后 `{ phase: 'error', stage: 'download', ... }`。
- 原版位置: `main/services/updater.ts:272`（handler）+ `download:238` / `getUpdater:220` / `autoUpdater.checkForUpdates:249`；preload `preload/index.ts:1454`

### update:install
- 入参: 无
- 出参: 无（`Promise<void>`）；成功即调用 `quitAndInstall(true, true)` 退出并安装
- 错误/边界: phase 不是 `downloaded` 或 `updater` 为 null 时直接 return（不安装）；执行前先 `settleActiveTurns(3000)` 收尾进行中的回合并落盘；无显式错误返回。
- 原版位置: `main/services/updater.ts:273`（handler）+ `install:259` / `settleActiveTurns:1776`（chat.ts:1776） / `quitAndInstall:265`；preload `preload/index.ts:1455`
