# IPC 通道契约台账：fs / secrets / personas / skills / config / profile / provider / window / clipboard

> 事实来源：只读审阅 `/home/agent/shared_workspace/deva/apps/desktop/src`（Electron 原版）。行号以实际读到的为准。
> 除 `config:get-sync` 为 `ipcMain.on` + `sendSync` 外，其余均为 `ipcMain.handle` + `ipcRenderer.invoke`；handler 抛出的异常会表现为渲染层 Promise rejection。
> 本文件只记录源码可直接看到的事实，未包含推断。

### fs:paste-attachment

- 入参: `file: { name: string; mime: string; size: number; data: Uint8Array | null }`（preload `pasteAttachment(file)`）
- 出参: `Promise<PickedAttachment>`，即 `{ path, name, ext, size, kind, supported, reason? }`；`path` 由主进程生成 `join(tmpdir(), 'deva-paste', randomUUID(), name)`
- 错误/边界: 有 `data` 时按 sha256 去重、无 `data` 时按 `big:<name>:<size>` 去重，命中直接回同一对象；`name` 经 `pasteName` 清洗（剥路径、替换 Windows 非法字符，空名/`.`/`..`/`image.xxx` 改为中文时间戳名）；判定走 `inspect`（图片 >5MB、PDF >20MB、文本 >512KB 或类型不支持则不读内容）；`data` 为空或判定为不支持时不落盘，`byPath=false`；落盘失败时回滚 `pasted`/`allowed` 并抛出；注册时先递归清空 `PASTE_DIR`
- 原版位置: `main/services/attachments.ts:154-183`（`inspect` 116-134、`pasteName` 137-147、`PASTE_DIR` 103）；preload `preload/index.ts:949-955`

### fs:dropped-entries

- 入参: `paths: unknown`，期望 `string[]`；preload 用 `webUtils.getPathForFile(f)` 从 `File[]` 逐项取路径，取不到填空串
- 出参: `Promise<(DroppedEntry | null)[]>`，逐项为 `{ folder: { path, name } }` 或 `{ file: PickedAttachment }` 或 `null`，顺序与入参一致
- 错误/边界: 入参非数组 → `[]`；元素非字符串或空串 → 该项 `null`；路径 `resolve` 后 `fs.stat` 失败 → `null`；目录 → 加入 `allowedDirs` 并 `trustRoot(abs)`，`name = basename(abs) || abs`；普通文件 → `inspect(abs, st.size)`；既非目录也非文件 → `null`
- 原版位置: `main/services/attachments.ts:189-205`；preload `preload/index.ts:964-973`

### fs:attachment-image

- 入参: `path: unknown, full: unknown`（preload `attachmentImage(path, full = false)`）
- 出参: `Promise<string | null>`；`full === true` 时为原图 `data:<mime>;base64,...`，否则为 `thumbnailDataUrl(buf, mime)` 生成的缩略图 data URI
- 错误/边界: 非字符串或空串 → `null`；路径 `resolve` 后不在本会话 `allowed` 白名单或扩展名非图片 → `null`；读文件抛错或字节数 >5MB → `null`；MIME 先用 `sniffImageMime` 按魔数识别，失败再按扩展名表；缩略图短边 240px、长边 960px，原图已够小或无法解码时原样返回
- 原版位置: `main/services/attachments.ts:209-221`（`image-read.ts:28-47`、`image-read.ts:57-76`）；preload `preload/index.ts:957-958`

### fs:pick-attachments

- 入参: 无（preload `pickAttachments()`）
- 出参: `Promise<PickedAttachment[]>`
- 错误/边界: 有窗口时以该窗口为父调 `dialog.showOpenDialog`，否则无父窗口调用；属性 `openFile + multiSelections`，含「支持的文件 / 图片 / PDF / 所有文件」四组 filters；取消 → `[]`；每个路径 `resolve` 后 `fs.stat` 取体积，stat 失败按 0 处理；统一走 `inspect(abs, size)`，合规者登记进 `allowed` 或 `allowedFiles`；对话框异常直接抛出
- 原版位置: `main/services/attachments.ts:223-259`；preload `preload/index.ts:948`

### fs:open-folder

- 入参: 无（preload `openFolder()`）
- 出参: `Promise<OpenFolderResult | null>`，即 `{ path: string; name: string } | null`
- 错误/边界: 对话框 `properties: ['openDirectory']`，标题「打开项目文件夹」；`res.canceled` 或 `filePaths` 为空 → `null`；取首个路径 `resolve` 后 `trustRoot(dir)` 登记为受信根；`name = basename(dir) || dir`
- 原版位置: `main/services/workspace.ts:43-51`；preload `preload/index.ts:939`

### fs:reveal-folder

- 入参: `dirPath: unknown`（preload `revealFolder(path: string)`）
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 非字符串、空串或 `isInsideRoot(dirPath)` 为 false → `{ ok: false }`；`fs.stat` 失败或不是目录 → `{ ok: false }`；否则 `shell.openPath(resolve(dirPath))`，成功返回空串 → `{ ok: true }`，失败返回错误描述 → `{ ok: false }`；文件一律拒绝（避免双击执行）
- 原版位置: `main/services/workspace.ts:55-61`（`isInsideRoot` 见 `fs-guard.ts:79-86`）；preload `preload/index.ts:941-942`

### fs:read-dir

- 入参: `dirPath: string`（preload `readDir(path: string)`）
- 出参: `Promise<DirEntry[]>`，`DirEntry = { name: string; path: string; type: 'dir' | 'file' }`
- 错误/边界: `assertInside(dirPath)` 不通过时抛 `Error('拒绝访问：路径不在已打开的项目内')`；`fs.readdir(..., { withFileTypes: true })` 的异常原样抛出；只保留目录与普通文件（过滤符号链接等）；排序规则：目录在前，同类按 `localeCompare(name)` 升序
- 原版位置: `main/services/workspace.ts:64-79`（`assertInside` 见 `fs-guard.ts:88-92`）；preload `preload/index.ts:943`

### fs:read-file

- 入参: `filePath: string`（preload `readFile(path: string)`）
- 出参: `Promise<ReadFileResult>`，`{ path, content, tooLarge?: boolean, binary?: boolean }`
- 错误/边界: `assertInside(filePath)` 不通过则抛出；`fs.stat` 失败则抛出；`size > 2MB` → `{ path, content: '', tooLarge: true }`；前 `min(len, 8000)` 字节中出现 0 字节即判二进制 → `{ path, content: '', binary: true }`；否则按 utf8 解码返回正文
- 原版位置: `main/services/workspace.ts:82-89`（`MAX_FILE_BYTES` 33、`looksBinary` 35-39）；preload `preload/index.ts:944`

### fs:write-file

- 入参: `filePath: string, content: string`（preload `writeFile(path, content)`）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: `assertInside(filePath)` 不通过则抛出；`fs.writeFile(filePath, content, 'utf8')` 的异常原样抛出；无内容 / 类型校验，也不做父目录预创建
- 原版位置: `main/services/workspace.ts:92-96`；preload `preload/index.ts:945-946`

### secrets:set

- 入参: `providerId: string, key: string`（preload `set(providerId, key)`）
- 出参: `Promise<{ ok: boolean; available: boolean }>`
- 错误/边界: 首次调用 `ensureLoaded()` 读 `<DEVA_HOME>/secrets.json`，不存在则尝试从 `userData/secrets.json` 一次性迁移；`available = safeStorage.isEncryptionAvailable()`；`key` 为空串 → 删除该键并落盘，返回 `{ ok: true, available }`；加密不可用 → `{ ok: false, available }`（拒绝明文写入）；否则 `encryptString(key)` 转 base64 存入并落盘；持久化异常未捕获，会抛出
- 原版位置: `main/services/secrets.ts:122-137`（`ensureLoaded` 36-48、`migrateLegacy` 21-34、`persist` 50-52）；preload `preload/index.ts:1082-1083`

### secrets:has

- 入参: `providerId: string`（preload `has(providerId)`）
- 出参: `Promise<boolean>`，即 `Boolean(store[providerId])`
- 错误/边界: 先 `ensureLoaded()`；只判断密文键是否存在，不解密、不回显明文；无该键返回 `false`
- 原版位置: `main/services/secrets.ts:140-143`；preload `preload/index.ts:1084`

### secrets:delete

- 入参: `providerId: string`（preload `delete(providerId)`）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: 先 `ensureLoaded()`；无条件 `delete store[providerId]` 并落盘，键不存在也返回成功（幂等）；落盘异常未捕获，会抛出
- 原版位置: `main/services/secrets.ts:145-150`；preload `preload/index.ts:1085-1086`

### secrets:list

- 入参: 无（preload `list()`）
- 出参: `Promise<string[]>`，即 `Object.keys(store)`（已配置密钥的键名）
- 错误/边界: 先 `ensureLoaded()`；只返回键名，不含任何密文或明文
- 原版位置: `main/services/secrets.ts:153-156`；preload `preload/index.ts:1087`

### secrets:available

- 入参: 无（preload `available()`）
- 出参: `Promise<boolean>`，`safeStorage.isEncryptionAvailable()` 的同步返回值
- 错误/边界: handler 为同步函数，不调用 `ensureLoaded()`，不读写任何文件；仅反映当前环境加密能力
- 原版位置: `main/services/secrets.ts:159`；preload `preload/index.ts:1088`

### personas:list

- 入参: 无（preload `list()`）
- 出参: `Promise<PersonaRecord[]>`，IPC 出口传 `withImages=true`，故每项带 `avatarImage` data URI
- 错误/边界: 目录 `<DEVA_HOME>/personas` 不存在 → `[]`；只扫描 `.md` 文件，文件名主体须通过 `isSafeId`（字母数字开头、最长 64、禁 `.`/`..`）；单个文件读失败跳过不抛；`enabled` 取自 `config.personas.enabled[id] === true`；排序先按 `config.personas.order` 排名，未列出的排在后面并按 `name` 本地化排序
- 原版位置: `main/services/personas.ts:488`（`listPersonas` 187-220、`enabledMap` 112-117、`orderList` 130-135、`isSafeId` 144-146）；preload `preload/index.ts:1025`

### personas:get

- 入参: `id: string`（preload `get(id)`）
- 出参: `Promise<PersonaRecord | null>`，带 `avatarImage`
- 错误/边界: `isSafeId(id)` 不通过 → `null`；读 `<id>.md` 失败（不存在等）→ `null`；解析容错，`name` 缺省回落 id，`prompt` 为正文 trim 后的结果
- 原版位置: `main/services/personas.ts:489`（`getPersona` 223-231、`parsePersona` 168-181）；preload `preload/index.ts:1026`

### personas:upsert

- 入参: `input: PersonaUpsertInput` = `{ id?, name, description?, avatar?, model?, prompt?, enabled? }`（preload `upsert(input)`）
- 出参: `Promise<PersonaRecord>`，落盘后经 `getPersona(id, true)` 读回；读回失败时返回内存构造的同形状记录
- 错误/边界: `name` trim 后为空 → `'未命名提示词'`；`id` 存在且 `isSafeId` 通过则覆盖该文件，否则用 `makeId(name)`（slug + 8 位随机 hex，且回避已存在文件）新建；写文件异常被吞掉，仍返回记录；`enabled` 为布尔则按其设置，新建且未传 → 默认 `false`；`avatarImage` 不入 upsert 入参
- 原版位置: `main/services/personas.ts:490-492`（`upsertPersona` 259-297、`makeId` 153-166、`composePersonaMd` 242-256）；preload `preload/index.ts:1027-1028`

### personas:remove

- 入参: `id: string`（preload `remove(id)`）
- 出参: `Promise<{ ok: true }>`，始终视为成功
- 错误/边界: `isSafeId` 不通过直接 no-op 但仍返回 `ok:true`；文件不存在时 `rmSync(..., { force: true })` 不报错；连带清除自定义头像、把绑定该角色的定时任务改派 `general`、从技能/MCP 可用角色中剔除、删除 `config.personas.enabled[id]` 与 `order` 中的 id
- 原版位置: `main/services/personas.ts:493-496`（`deletePersona` 340-361）；preload `preload/index.ts:1029`

### personas:set-enabled

- 入参: `id: string, enabled: boolean`（preload `setEnabled(id, enabled)`）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: `Boolean(enabled)` 归一后写入 `config.personas.enabled`；`isSafeId` 不通过则 no-op，仍返回 `ok:true`；不校验角色文件是否存在；落盘走 `setConfig`（同步写，失败静默）
- 原版位置: `main/services/personas.ts:497-500`（`setPersonaEnabled` 380-385、`writeEnabledMap` 119-123）；preload `preload/index.ts:1030-1031`

### personas:reorder

- 入参: `ids: string[]`（preload `reorder(ids)`）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: 非数组按 `[]` 处理；逐项过滤非字符串、`isSafeId` 不通过、重复的 id；不校验角色是否仍存在（陈旧 id 在 list 时自然被忽略）；写入 `config.personas.order`，落盘失败静默
- 原版位置: `main/services/personas.ts:501-504`（`reorderPersonas` 367-378）；preload `preload/index.ts:1033-1034`

### personas:set-avatar-image

- 入参: `id: string, dataUri: string`（preload `setAvatarImage(id, dataUri)`），两者都经 `String(x ?? '')` 归一
- 出参: `Promise<string>`，成功为落盘后读回的 data URI，参数非法或写失败为 `''`
- 错误/边界: `isSafeId(id)` 不通过 → `''`；dataUri 须匹配 `data:<mime>;base64,<payload>`，MIME 仅接受 webp/png/jpeg(含 image/jpg)，解码后字节数须为 1..2MB；写入前先删同名所有扩展名变体，保证一 id 一图；异常一律返回 `''`
- 原版位置: `main/services/personas.ts:506-508`（`writeAvatarImage` 107-109，落盘见 `avatar-image.ts:63-84`）；preload `preload/index.ts:1039-1040`

### personas:clear-avatar-image

- 入参: `id: string`（preload `clearAvatarImage(id)`）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: `String(id ?? '')` 后若 `isSafeId` 不通过则 no-op；删除 `personas/avatars/<id>.webp|png|jpg` 三个变体，删除异常被吞掉；始终返回 `ok:true`
- 原版位置: `main/services/personas.ts:509-512`（`clearAvatarImage` 103-105，落盘见 `avatar-image.ts:52-60`）；preload `preload/index.ts:1042-1043`

### skills:list

- 入参: 无（preload `list()`）
- 出参: `Promise<SkillRecord[]>`，前 3 项恒为内置 `create-skill`/`create-agent`/`create-mcp`，其后为自定义技能按 `name` 本地化升序
- 错误/边界: `skills` 目录不存在 → 仍返回 `[...BUILTIN_SKILLS]`；目录读失败 → `[]`；仅接受 `isSafeId` 的目录、跳过与保留 id 同名的磁盘目录；无 `SKILL.md` 或读失败跳过；`enabled` 取 `config.skills.enabled[id] !== false`（缺省即启用）；`roles` 取 `config.skills.roles[id]`（缺省 `null` = 全部角色）
- 原版位置: `main/services/skills.ts:753`（`listSkills` 329-357、`parseSkill` 309-326、`isSafeId` 287-289、`RESERVED_IDS` 253）；preload `preload/index.ts:986`

### skills:get

- 入参: `id: string`（preload `get(id)`）
- 出参: `Promise<SkillRecord | null>`
- 错误/边界: 命中内置 id 直接返回内置常量（恒 `enabled:true`、`roles:null`、`source:'builtin'`）；`isSafeId` 不通过 → `null`；读 `<id>/SKILL.md` 失败 → `null`；自定义项数据取自 frontmatter 与正文
- 原版位置: `main/services/skills.ts:754`（`getSkill` 359-369）；preload `preload/index.ts:987`

### skills:remove

- 入参: `id: string`（preload `remove(id)`）
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 内置保留 id → `{ ok: false }`；`isSafeId` 不通过 → `{ ok: false }`；目录存在时用 `shell.trashItem` 移入系统回收站，抛错 → `{ ok: false }` 且不改启用态；目录本就不存在视为成功；成功后删 `config.skills.enabled[id]` 并 `setRoles('skills', id, null)`
- 原版位置: `main/services/skills.ts:755`（`deleteSkill` 440-458）；preload `preload/index.ts:990`

### skills:set-enabled

- 入参: `id: string, enabled: boolean`（preload `setEnabled(id, enabled)`）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: 内置保留 id 直接 no-op（内置恒启用，不入 enabled 映射）；`isSafeId` 不通过 no-op；写入 `config.skills.enabled[id] = (enabled === true)`；始终返回 `ok:true`
- 原版位置: `main/services/skills.ts:756-759`（`setSkillEnabled` 460-466）；preload `preload/index.ts:991-992`

### skills:set-roles

- 入参: `id: string, roles: string[] | null`（preload `setRoles(id, roles)`）
- 出参: `Promise<{ ok: boolean }>`
- 错误/边界: 内置保留 id 或 `isSafeId` 不通过 → `{ ok: false }`；`roles` 非数组一律按 `null` 处理（= 全部角色）；数组会去重并剔除空串/非字符串，写入 `config.skills.roles[id]`；`null` 时删除该键；不做角色存在性校验；成功返回 `{ ok: true }`
- 原版位置: `main/services/skills.ts:761-765`（`setRoles` 见 `ext-roles.ts:40-49`）；preload `preload/index.ts:994-995`

### skills:import

- 入参: 无（preload `import()`）；文件由原生对话框选择
- 出参: `Promise<SkillImportResult>` = `{ ok: boolean; id?: string; name?: string; error?: string }`
- 错误/边界: 对话框 filters 为 `zip`/`md` 与所有文件；取消或无选中 → `{ ok:false, error:'cancelled' }`；`.md` 走单文件导入、`.zip` 走技能包导入、其它扩展名 → `unsupported-type`；导入异常 → `import-failed`；其它错误码：`missing-name`、`bad-zip`、`no-skill-md`、`unsafe-path`、`too-many-files`（>200 文件）、`too-large`（单文件 >10MB 或总计 >20MB）、`write-failed`；成功后自动 `setSkillEnabled(id, true)` 并返回 `{ ok:true, id, name }`
- 原版位置: `main/services/skills.ts:767-781`（`importSkillFromFile` 627-639、`importZipSkill` 569-621、`writeImportedSkill` 540-566、限额 256-258）；preload `preload/index.ts:988`

### config:get-sync

- 入参: 无（preload `getSync()`，走 `ipcRenderer.sendSync('config:get-sync')`）
- 出参: 同步返回整份配置对象 `Record<string, unknown>`（`evt.returnValue = config`，即内存中的同一对象引用）
- 错误/边界: 注册时与每次调用前都 `ensureLoaded()`；配置文件不存在或 JSON 解析失败视为空配置 `{}`，不抛错；只读接口，不做写回
- 原版位置: `main/services/config.ts:86-89`（`ensureLoaded` 37-48）；preload `preload/index.ts:978`

### config:get

- 入参: 无（preload `get()`）
- 出参: `Promise<Record<string, unknown>>`，整份内存配置对象
- 错误/边界: 先 `ensureLoaded()`；读文件失败或解析失败回落 `{}`；返回对象与主进程共享引用，不含密钥（密钥另存 `secrets.json`）
- 原版位置: `main/services/config.ts:92-95`；preload `preload/index.ts:979`

### config:set

- 入参: `patch: Record<string, unknown>`（preload `set(patch)`）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: `setConfig` 对非对象 patch 直接返回（不抛错）；顶层浅合并，值为 `undefined` 时删除该键；同步写 `<DEVA_HOME>/config.json`，写失败静默（内存态已更新）；无 schema 校验
- 原版位置: `main/services/config.ts:98-101`（`setConfig` 72-80、`persist` 50-56）；preload `preload/index.ts:981-982`

### profile:get

- 入参: 无（preload `get()`）
- 出参: `Promise<UserProfile>` = `{ avatar: string; avatarImage: string }`
- 错误/边界: `config.profile.avatar` 为非空字符串则用之，否则回落内置 `DEFAULT_USER_AVATAR`（固定 Humation spec，且不写回配置）；`avatarImage` 读 `<DEVA_HOME>/profile/avatar.<webp|png|jpg>`，无图或读失败 → `''`
- 原版位置: `main/services/profile.ts:49`（`getProfile` 35-41、`DEFAULT_USER_AVATAR` 23-24、`readAvatarImage` 见 `avatar-image.ts:38-49`）；preload `preload/index.ts:1005`

### profile:set-avatar

- 入参: `spec: string`（preload `setAvatar(spec)`，经 `String(spec ?? '')` 归一）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: `spec.length > 4096` 时存空串（即视为清除，回落默认头像），否则原样存入；与已有 `config.profile` 做对象展开合并后 `setConfig`；始终返回 `ok:true`，无内容合法性校验
- 原版位置: `main/services/profile.ts:50-53`（`setProfileAvatar` 43-46、`AVATAR_SPEC_MAX` 21）；preload `preload/index.ts:1006`

### profile:set-avatar-image

- 入参: `dataUri: string`（preload `setAvatarImage(dataUri)`，经 `String(dataUri ?? '')` 归一）
- 出参: `Promise<string>`，成功为落盘后读回的 data URI，失败/清除为 `''`
- 错误/边界: 空串 → 删除 `profile/avatar.*` 全部变体并返回 `''`；非空走 `writeAvatarImage`：须匹配 `data:<mime>;base64,<payload>`，MIME 仅 webp/png/jpeg，解码字节数须为 1..2MB；写前先清同名变体；任何失败返回 `''`
- 原版位置: `main/services/profile.ts:55-62`（`writeAvatarImage` 见 `avatar-image.ts:63-84`）；preload `preload/index.ts:1008-1009`

### provider:list-models

- 入参: `cfg: ProbeConfig` = `{ adapter: 'anthropic' | 'openai' | 'responses'; providerId: string; baseURL: string }`（preload `listModels(cfg)`）
- 出参: `Promise<ListModelsResult>` = `{ ok: boolean; models?: string[]; kind?: ErrorKind; message?: string }`，成功时 `models` 为去重并按 `localeCompare` 升序的 id 列表
- 错误/边界: 密钥经 `getSecret(cfg.providerId) ?? ''` 在主进程解密；`baseURL` trim 并去除尾部斜杠；网关地址取 `opencodeModelsURL`，否则 anthropic 拼 `/v1/models`、其余拼 `/models`；头部 anthropic 用 `x-api-key` + `anthropic-version: 2023-06-01`，其余用 `Authorization: Bearer`，均附加 `providerHeaders`；15s 超时以 AbortError 中断；非 2xx → `{ ok:false, kind, message }`（kind 来自 `httpError`：auth/rate_limit/context_length/output_limit/effort_unsupported/server/invalid_request 等）；响应非 JSON → `models: []`；网络异常 → `kind:'network'`，超时文案为「请求超时（15s）」；函数不抛出
- 原版位置: `main/services/provider.ts:74-100`（`TIMEOUT_MS` 28、`httpError` 见 `providers/types.ts:302-378`、`opencodeModelsURL` 见 `providers/opencode.ts:54-66`）；preload `preload/index.ts:1091-1093`

### window:set-overlay

- 入参: `symbolColor: string`（preload `setOverlaySymbolColor(color)`）
- 出参: `Promise<void>`（handler 无返回值）
- 错误/边界: `mainWindow` 为 null 直接返回；`win32` → `setTitleBarOverlay({ color: '#00000000', symbolColor, height: 40 })`；`linux` 忽略传入色值，按 `symbolColor === '#e4e4e7'` 判暗色，底色 `#1e1e20` / `#ffffff`，height 40；其它平台 no-op
- 原版位置: `main/index.ts:301-309`（常量 `OVERLAY_SYMBOL` 77、`OVERLAY_BG` 78）；preload `preload/index.ts:934-935`

### window:minimize

- 入参: 无（preload `minimize()`）
- 出参: `Promise<void>`
- 错误/边界: `mainWindow?.minimize()`；窗口为 null 时静默 no-op，不抛错
- 原版位置: `main/index.ts:311`；preload `preload/index.ts:923`

### window:toggle-maximize

- 入参: 无（preload `toggleMaximize()`）
- 出参: `Promise<void>`
- 错误/边界: `mainWindow` 为 null 直接返回；`isMaximized()` 为真则 `unmaximize()`，否则 `maximize()`；不返回最大化状态
- 原版位置: `main/index.ts:312-315`；preload `preload/index.ts:924`

### window:close

- 入参: 无（preload `close()`）
- 出参: `Promise<void>`
- 错误/边界: `mainWindow?.close()`，窗口为 null 时 no-op；窗口的 `close` 事件另有拦截逻辑：非退出流程下，win32 默认 `closeToTray !== false`、其它平台 `closeToTray === true` 时 `preventDefault()` 并 `hide()`，即可能只是隐藏而非退出
- 原版位置: `main/index.ts:316`（`close` 拦截见 161-170）；preload `preload/index.ts:925`

### window:is-fullscreen

- 入参: 无（preload `isFullScreen()`）
- 出参: `Promise<boolean>`，即 `mainWindow?.isFullScreen() ?? false`
- 错误/边界: 窗口为 null 返回 `false`；仅为状态查询，不改变窗口状态；全屏变化另有主进程推送事件 `window:fullscreen`（`enter-full-screen`/`leave-full-screen` 时发送 true/false），preload 以 `onFullScreen` 订阅
- 原版位置: `main/index.ts:317`（推送见 156-157）；preload `preload/index.ts:927-932`

### app:get-platform

- 入参: 无
- 出参: `Promise<string>`，即 `process.platform`
- 错误/边界: 已注册 `ipcMain.handle`，但 preload 未提供对应的 invoke 方法；渲染层实际取平台用的是 `api.platform = process.platform`（preload 直接暴露），故该通道由渲染层直接调用的路径未在 preload 出现
- 原版位置: `main/index.ts:318`；preload `preload/index.ts:921`（`platform: process.platform`，无 invoke）

### clipboard:read-text

- 入参: 无（preload `readText()`）
- 出参: `Promise<string>`，`clipboard.readText()` 的返回值；剪贴板无文本时为空串
- 错误/边界: 同步 handler，只读纯文本，不落盘、不持久化；不涉及权限校验或异常捕获
- 原版位置: `main/services/clipboard.ts:15`；preload `preload/index.ts:1375`

### clipboard:write-text

- 入参: `text: unknown`（preload `writeText(text: string)`）
- 出参: `Promise<{ ok: true }>`
- 错误/边界: 非字符串时用 `String(text)` 强转后写入（`null` 会写成字符串 `"null"`）；只写纯文本，无长度限制与内容校验；始终返回 `ok:true`
- 原版位置: `main/services/clipboard.ts:18-21`；preload `preload/index.ts:1376-1377`
