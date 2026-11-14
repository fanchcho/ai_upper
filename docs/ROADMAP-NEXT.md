# 下一轮路线图：未完成项拆解与优先级

来源：`docs/STAGE6-CLOSEOUT-REPORT.md` 的三档清单（档二「已实现未验证」8 项、
档三「未实现」4 组）与 `docs/audit/IPC-158-LEDGER.md` 的 93 条未实现通道。
本文只做拆解，不改动任何实现，也不改写 `out/` 下的历史证据。

工程名统一写 `ai_upper`。

## 口径

- 起点基线：`app/` 全量测试 `939 passed, 5 skipped`（`patchelf` 在 `PATH` 中；
  缺 `patchelf` 时 `938 passed, 6 skipped`），linux-arm64 打包产物可 headless 启动。
- 已验证范围：linux-arm64 单一目标；界面为浅色七页、Xvfb 软渲染、无窗口管理器。
- 「完成」的定义：有测试、有实跑原始输出落盘、结论写进 `docs/BUILD-PROGRESS.md` 台账。
  只有单元测试不算完成；只在一台机器上跑过也不算跨平台完成。
- 禁止的捷径：删测试、把用例标 skip 冒充通过、通道静默返回 `{ok:true}` 假成功、
  用 fallback 吞掉错误。

优先级：

| 级别 | 含义 |
|---|---|
| **P0** | 阻塞发布，或阻塞后续多项任务；不做则「可用」无从谈起 |
| **P1** | 已实现但未验证；决定能不能对外声称「与 Deva 一致」 |
| **P2** | 整域缺失；各自独立，可按使用频率选做，不影响已完成部分 |

规模按单人工作量估：**S** ≈ 1–3 天，**M** ≈ 1–2 周，**L** ≈ 3–5 周，**XL** ≈ 6 周以上。

## 总览

| 编号 | 任务 | 优先级 | 规模 | 前置依赖 |
|---|---|---|---|---|
| R1 | CI 补 Web 层覆盖、lint 与类型检查 | P0 | M | — |
| R2 | Windows / macOS 真产物 | P0 | M | R1 |
| R3 | 真实网络、真实 provider 与 `web_fetch` | P0 | S | 外部密钥与出网 |
| R4 | 真桌面观感、窗口控制与人工验收 | P1 | M | 真机 / GPU / 窗口管理器 |
| R5 | 深色主题七页对比 | P1 | S | R4 的截图流水线 |
| R6 | 工作区挂载交互 | P1 | M | — |
| R7 | 子智能体与 `task` 类工具 | P1 | L | R6 |
| R8 | 流式刷新（40ms 节流）手感 | P1 | S | 真实 provider（R3） |
| R9 | 自定义技能非 ASCII 名排序 | P1 | S | — |
| R10 | `chat:` 域 13 条 | P2 | L | R7、R6 |
| R11 | `git:` 域 24 条 | P2 | L | — |
| R12 | `browser:` 域 13 条 | P2 | XL | R4 |
| R13 | `tasks:` 域 8 条 | P2 | M | — |
| R14 | `mcp:` 域 9 条 | P2 | M | — |
| R15 | `remote:` 域 9 条 | P2 | L | — |
| R16 | `terminal:` 域 5 条 | P2 | M | — |
| R17 | `memory:` 域 4 条 | P2 | S | — |
| R18 | `deliverables:` 域 4 条 | P2 | S | R10（依赖 toolUseId 映射） |
| R19 | `update:` 域 3 条 | P2 | M | R2 |
| R20 | `skills:` 域 1 条 | P2 | S | — |

---

## P0

### R1　CI 补 Web 层覆盖、lint 与类型检查

**目标**
让 CI 能拦住「源码态测试全绿、产物一启动就崩」这一类缺陷，并提供统一的静态检查入口。

现状缺口（均为实测结论）：

1. 渲染层是入库的 Vite 构建产物（`app/assets/renderer/assets/*.js`，约 3.2 MB），
   CI 没有 Node 侧构建或测试步骤；渲染层与原版的偏差只能靠 `scripts/parity/*.sh`
   在本地跑 Xvfb 比对，CI 完全不覆盖。
2. 仓库里没有任何 lint / 格式化配置：不存在 `ruff`、`mypy`、`pyright`、`flake8`、
   `pre-commit` 配置文件，`.github/workflows/` 下只有一个 `validate.yml`，
   其中也没有静态检查步骤。
3. 类型标注有缺口：`app/src/` 共 79 个模块、约 16.5k 行，`Any` 出现 421 处，
   裸 `dict`/`list` 标注 321 处，`# type: ignore` / `# noqa` 共 61 处；
   没有任何工具在 CI 里守着这些数量不再增长。
4. 矩阵只对 `matrix.run == true` 的条目做「完整构建 + 启动」；`linux-arm64` 与
   `windows-x86` 两条 `run: false`，只构建不启动。

**前置依赖**：无（可立即开始）。

**可核查验收标准**

- 新增 `pyproject.toml`（或 `ruff.toml`）配置 `ruff check` 与目标规则集，
  CI 增加一步 `ruff check app/src tools`，且该步在 `develop` 上为绿；
- CI 增加 `web-layer` job：对 `app/assets/renderer` 执行一次 Node 构建
  （`npm ci && npm run build`）并断言产物与入库文件一致（`git diff --exit-code`），
  不一致即说明入库产物不是从当前源码构建的；
- 至少一条 pytest 用例会在 `window.deva` 缺失某个契约方法时失败
  （把 `shim.js` 的通道表与 `bridge.py` 的注册表做集合比对，断言缺一条即报错）；
- 类型检查以「只减不增」的方式接入：先记录当前 `mypy --ignore-missing-imports` 的错误数
  作为基线文件，CI 断言不高于基线；连续三轮下降后再改为硬门禁；
- `validate.yml` 的 `matrix.run == false` 条目在文档里写明「只构建不启动」的原因，
  并在 R2 完成后把 `linux-arm64` 改为 `run: true`。

**预估规模**：M（lint 配置半天，类型基线 2–3 天，渲染层构建校验 2–3 天）。

**风险**

- 直接上 `mypy` 硬门禁会一次爆出数百条错误，逼出大面积 `# type: ignore`，
  反而把类型检查变成装饰。必须先做基线，只允许下降；
- 渲染层源码若不在本仓库，Node 构建校验无法完成——需先确认 Vite 工程是否可入库，
  不可入库时退化为「shim 契约集合比对 + 产物哈希记录」；
- 新增 CI job 会拉长流水线时长，需要对渲染层 job 加缓存，否则每个 PR 多几分钟。

### R2　Windows / macOS 真产物

**目标**
在目标操作系统上真正构建、打包并启动产物，拿到与 linux-arm64 同等级的证据。

现状：本轮只构建并启动了 linux-arm64。`package()` / `qt_prune` / native closure
有覆盖两平台布局的单元测试，但**没有真产物**——不拿 linux 结果冒充。

**前置依赖**：R1（CI 可信之后再谈「CI 上跑过了」）。

**可核查验收标准**

- 在 Windows（x86_64 与 arm64 至少各一）与 macOS（x86_64 与 arm64 至少各一）
  执行 `python tools/build.py --target <target>`，产物名为
  `dist/ai_upper/ai_upper.exe` 与 `dist/ai_upper.app/Contents/MacOS/ai_upper`；
- headless 启动：Windows 用 `AI_UPPER_HEADLESS=1 AI_UPPER_NO_DIALOG=1`，
  macOS 同法，输出包含 `DEVA WEB OK ... bridge=True`，退出码 0；
- `--verify` 在两平台均通过，且 `bundle/ai_upper.dat`（macOS 为
  `Contents/Resources/bundle/ai_upper.dat`）存在、成员列表与源码一致；
- macOS 额外要求 `codesign --verify --deep --strict` 通过；
- 原始输出落盘到 `out/platform/<os>-<arch>/`，并在 `docs/BUILD-PROGRESS.md` 新增小节。

**预估规模**：M（每平台半天到一天，卡点通常在 native 闭包与 Qt 插件）。

**风险**

- Windows 的 `_msi.pyd` / `msi.dll` 类闭包问题只在 CPython ≤3.12 出现，
  R2 若只测 3.13 会漏掉，须同时保留 3.8 兼容 job；
- macOS 签名需要开发者证书，没有证书时只能 ad-hoc 签名，
  此时「签名通过」的结论不适用于发布；
- 交叉构建的静态通过不代表运行通过，必须原生启动，不能用 `--target` 交叉冒充。

### R3　真实网络、真实 provider 与 `web_fetch`

**目标**
用真密钥跑通 Anthropic / OpenAI / Responses 三条链路，并让 `web_fetch` 真抓网页。

现状：无可用密钥、环境不保证出网；离线测试只覆盖事件流解析与工具结果形状。
`app/tests/test_web_e2e_stream.py` 因缺 `DEVA_E2E_PROVIDER` 等变量而 skip，
这条 skip 必须保留到真跑通为止。

**前置依赖**：外部密钥与出网能力（非工程内可解决）。

**可核查验收标准**

- 设 `DEVA_E2E_PROVIDER=1` 与 `ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` /
  `ANTHROPIC_MODEL` 后，`test_web_e2e_stream.py` 由 skip 变为 pass，并把
  `-rs` 输出中该条 SKIPPED 消失作为证据落盘；
- 三种协议各跑通一轮真实对话：请求体、流式增量、`stopReason`、用量统计与实际返回一致，
  原始日志落盘 `out/e2e-provider/<protocol>.log`；
- `web_fetch` 对真实公网页面返回正文字数 > 0 且不含 HTML 标签；对 404、
  超时、超大响应分别返回可读错误而不是空串；
- 错误路径同样验证：无效密钥必须报鉴权错误，不得被重试吞掉。

**预估规模**：S（工程侧主要是补真跑脚本与证据落盘，1–2 天）。

**风险**

- 密钥不能入库；CI 只能用 secrets，且 fork PR 拿不到 secrets，真跑只能在上游仓库执行；
- 代理 / TLS / 企业网络会改变错误形态，日志里必须区分「鉴权失败」「网络不可达」
  「限流」三类，不能统一成一句「请求失败」；
- 真实模型输出不稳定，断言只能落在结构（有内容、有 stopReason）而非具体文本。

---

## P1

### R4　真桌面观感、窗口控制与人工验收

**目标**
在真实显示环境（真显卡、HiDPI、Wayland/X11 + 窗口管理器）里验证界面与窗口行为，
把「Xvfb 软渲染下一致」升级为「实际桌面上可用」。

现状：容器只有 Xvfb 软渲染，当前结论只对 `1400x900x24 + 软渲染` 成立；
`titleBarOverlay` 的最小化 / 最大化 / 关闭三个按钮几何与配色有单测，
但 Xvfb 无窗口管理器，点击行为没有真验过。

**前置依赖**：真机（Windows / macOS / 带 WM 的 Linux 桌面）、GPU 或软件渲染驱动。

**可核查验收标准**

- 在三个平台各截一遍七页，与 `out/parity/deva/` 的原版截图跑同一份
  `scripts/parity/compare.sh`，`fuzz3 ≤ 1` 且 `maxd ≤ 10`；
- HiDPI（200% 缩放）下窗口打开不出现模糊、错位或元素重叠，截图落盘；
- Wayland 会话下 `AI_UPPER_HEADLESS` 未设置时能正常开窗，关闭走完 closeEvent；
- `window:minimize` / `window:toggle-maximize` / `window:close` 三个按钮各点一次，
  由外部工具（`xdotool getwindowgeometry`、Windows `GetWindowRect`、macOS 窗口列表）
  确认窗口状态真的变化，而不是只看界面高亮；
- 键盘焦点、IME 中文输入、拖拽文件到窗口，各由人操作一次并记录。

**预估规模**：M（每平台 1–2 天，IME 与 HiDPI 是主要变量）。

**风险**

- 无头 CI 无法覆盖，只能人工验收，容易漏测且不可回归；
- Wayland 下 `titleBarOverlay` 由 compositor 决定，可能与 X11 行为不同，
  需分别记录而不是取其一；
- 截图对比依赖字体渲染，跨机器的抗锯齿差异会把 `maxd` 推高到阈值以上，
  判定前需固定字体与 DPI。

### R5　深色主题七页对比

**目标**
把浅色七页的对齐结论扩展到深色主题，确认 `window:set-overlay` 切换后
渲染层与标题栏叠加层同时变深。

现状：只实拍浅色七页。`window:set-overlay` 有单测（深色 `symbolColor(#e4e4e7)`
把叠加层底色切到 `OVERLAY_BG_DARK`），但七页没有深色实拍照。

**前置依赖**：R4 的截图流水线与真机（浅色版可先做，深色版需同一环境）。

**可核查验收标准**

- 用原版与移植版在深色主题下各截七页，`compare.sh` 七页全部「已一致」；
- 七页逐张附原版 / 移植版绝对路径，写进 `docs/BUILD-PROGRESS.md`；
- 切换主题时 `window:set-overlay` 被调用且叠加层底色变化，
  用日志或断点确认，不只看界面观感。

**预估规模**：S（复用既有脚本，约 1–2 天）。

**风险**

- 深色主题下抗锯齿差异更明显，`maxd ≤ 10` 的阈值可能需要重新校准并写明依据；
- 若渲染层深色主题依赖系统 `prefers-color-scheme`，Xvfb 下需要显式注入，
  否则两边都跑成同一主题，比对会假绿。

### R6　工作区挂载交互

**目标**
让工作区可以在运行期挂载 / 切换，而不是启动时由 `DEVA_APP_WORKSPACE` 定死。

现状：受信根在启动时登记；运行期没有挂载请求，
`chat:mount-response` 因此无法实现（见 R10）。

**前置依赖**：无（但 R7 与 R10 依赖它）。

**可核查验收标准**

- 新增挂载入口：用户在界面里选目录后，该目录立即成为 `WorkspaceGuard` 的受信根，
  无需重启；
- 挂载后立即用 `read_file` 读该目录下的文件成功，读挂载前被拒的路径也成功，
  读受信根之外的路径仍返回 `拒绝访问：路径不在已打开的项目内`；
- 运行期切换工作区后，旧受信根失效（可用负向用例验证）；
- 至少 3 条 pytest：挂载成功、越界仍拒、切换后旧根失效。

**预估规模**：M（受信根目前是单一实例，需要改成可替换并考虑并发工具调用的时序）。

**风险**

- 挂载中途若已有工具正在执行，切换受信根会导致同一次工具调用前后判定不一致，
  必须在回合边界切换；
- 与 Deva 的差异要写清楚：Deva 只在相对路径时弹挂载卡，本工程是显式挂载入口，
  这条差异应在工具描述与文档中如实标注。

### R7　子智能体与 `task` 类工具

**目标**
补齐 `run_subagent` / `send_to_subagent`，让模型能把调研或独立子任务派给隔离上下文的子智能体。

现状：19 个 Deva 工具中实现了 10 个；`run_subagent` / `send_to_subagent`
定义在 `chat.ts`（不在 `tools.ts`），依赖挂载与多轮编排，均未移植。

**前置依赖**：R6（子智能体需要在已知工作区内工作）。

**可核查验收标准**

- 两个工具注册进工具表，schema 与 Deva 一致（`description` 必填、`agent` 可选、
  `prompt` 必填、`foreground` 可选）；
- 子智能体以自己的会话（`parentId` 指向派生它的调用 id）运行，主对话历史不含其内部工具调用；
- 前台模式：调用阻塞至子智能体结束并直接返回结论；后台模式：立即返回，
  结束后主会话收到一条通知，两者都有实跑日志；
- `chat:stop-subagent` 能按 `toolUseId` 停止后台子智能体（与 R10 联动）；
- 至少 4 条测试：前台返回结论、后台通知、上下文隔离、停止。

**预估规模**：L（会话派生、上下文隔离、并发与取消是主要复杂度）。

**风险**

- 子智能体会放大 token 消耗与工具调用次数，没有预算上限时会失控，
  需要先定并发数与总预算；
- 后台子智能体与「回合结束」的生命周期耦合，进程退出时如何收尾要明确，
  不能用线程静默丢弃；
- 与 `ask_user` 等交互工具的配合：子智能体不能向用户提问，必须在工具描述里写死。

### R8　流式刷新（40ms 节流）手感

**目标**
确认 40ms 节流在长回复下的观感与 CPU 占用可接受。

现状：需要长回复 + 人眼观察，未验证。

**前置依赖**：R3（真实 provider 才能产生真实长回复）。

**可核查验收标准**

- 用真实 provider 生成 ≥2000 token 的回复，录制屏幕或按时间戳采样，
  确认增量连续、无卡顿、无整段跳变；
- 记录渲染进程 CPU 占用峰值，与不节流时的基线对比，写进台账。

**预估规模**：S。

**风险**：主观性强，只能定性记录；不同机器差异大，结论需附环境信息。

### R9　自定义技能非 ASCII 名排序

**目标**
确认中文等非 ASCII 技能名的排序与 Deva 的 ICU `localeCompare` 一致。

现状：实现用 `casefold()`，原版用 ICU `localeCompare`，中文名上可能不同，未实拍。

**前置依赖**：无。

**可核查验收标准**

- 在技能列表里放一组中文 / 中英混合名称，与原版同屏截图对比顺序一致；
- 若不一致，明确记录差异并决定是改用 ICU 规则还是接受差异（不能默默放着）。

**预估规模**：S。

**风险**：PySide6/Python 没有内置 ICU 排序，改用 ICU 需引入额外依赖，
可能不值得——结论可以是「已知差异并记录」。

---

## P2：93 条未实现 IPC 通道（按域分组）

总账：158 = 通过 60 + 已知差异 5 + 未实现 **93**。逐条入参/出参/原版位置见
`docs/audit/IPC-158-LEDGER.md`。下面按域列出，每域给任务级信息，
表里逐条给「这一条要做什么 / 怎么算通过」。

统一要求（对全部 93 条成立）：

- 实现前先在台账把该行的「移植版实现位置」与「测试方式」填上，
  不能只在桥里塞一个返回 `{ok:true}` 的空实现——假成功比未实现更糟；
- 前端调用路径必须走真实 UI（渲染层能点到），只写桥内函数不算完成；
- 依赖尚未存在的子系统时，宁可继续显式 reject 也不做半套。

### R10　`chat:` 域 13 条

**目标**：补齐对话域里依赖边车（sidecar）与队列的通道。
**前置依赖**：R7（子智能体）、R6（挂载）。
**预估规模**：L（`chat.ts` 原版约 6800 行，涉及的边车彼此耦合）。
**风险**：`chat:rewind-apply` 会改写会话与工作区文件，半套实现会丢数据；
`chat:insert` 的「可插入回合」判定与定时任务/压缩/回滚互相影响，需要统一状态机。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `chat:insert` | 建立回合内插入队列 `pendingInserts` + `insertableTurns` 判定 | 流式过程中插入一条消息，回合结束后按序发出；定时任务/压缩/回滚期间插入被拒并有明确文案 |
| `chat:withdraw-inserts` | 撤回同一队列里未发出的插入 | 插入后撤回，队列为空，模型未收到该条 |
| `chat:resolve-proposal` | 提案边车 `session.proposals` + `card_resolved` 事件 | 界面点「接受/拒绝」后边车落盘、事件广播、重开进程仍在 |
| `chat:resolve-autotask` | 自动任务边车 `session.autotasks` + 状态落盘 | 卡片状态变化落盘并可重读 |
| `chat:remove-member` | 群成员会话（`parentId` 链路）与成员注册表 | 移除成员后该成员不再出现在回复者列表，历史保留 |
| `chat:stop-subagent` | 按 `toolUseId` 停止后台子智能体 | 后台子智能体运行中停止，主会话收到停止结果而非正常结论 |
| `chat:rewind-list` | 生成回滚点（checkpoints）并列出 | 每轮对话产生一个回滚点，列表非空且有序 |
| `chat:rewind-preview` | checkpoint 快照与工作区差异比较 | 预览显示相对当前工作区的文件差异，且不改动文件 |
| `chat:rewind-apply` | 应用回滚（会话 + 工作区） | 回滚后会话与文件均回到该点；有备份可再前滚 |
| `chat:rewind-undo` | 回滚前快照与撤销 | 撤销后状态与回滚前逐字节一致 |
| `chat:ask-response` | 交互请求注册表 + `ask_user` 工具接线 | 模型调 `ask_user`，界面出现提问，回答回灌后模型继续 |
| `chat:plan-response` | 计划审批边车与「先到者生效」语义 | 两次回复并发时只有第一个生效，界面显示正确状态 |
| `chat:mount-response` | 挂载卡（依赖 R6） | 未挂载时模型请求路径，界面出现挂载卡，批准后该路径可用 |

### R11　`git:` 域 24 条

**目标**：新建 git 服务层，把 24 条通道一次性接通（原版 `git.ts` 约 1000 行）。
**前置依赖**：无（可用系统 `git` 子进程，不必引库）。
**预估规模**：L（写操作多，且每条都有失败分类要求）。
**风险**：`git:discard` / `git:merge` / `git:delete-branch --force` 会丢改动或丢提交，
不能做半套；`git:generate-commit-message` 依赖模型流式生成（与 R3 联动）。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `git:available` | 检测 `git` 可执行文件与版本 | 无 git 时返回不可用而非抛异常 |
| `git:status` | porcelain 解析与三栏分组 | 改动/暂存/未跟踪三类分别正确，路径含空格与中文不串行 |
| `git:diff` | 单文件 diff（含 staged 变体） | diff 文本与 `git diff` 输出一致 |
| `git:stage` | 按路径 add | 暂存后 `status` 反映到暂存栏 |
| `git:unstage` | reset HEAD 语义 | 暂存栏对应条目消失，工作区改动保留 |
| `git:discard` | 丢弃改动 | 只在用户显式确认后执行；丢弃后文件回到 HEAD 状态 |
| `git:commit` | 提交并返回 oid | 提交后 oid 与 `git log -1` 一致 |
| `git:set-config` | 写 `user.name` / `user.email` | 写入后 `git config --get` 读到新值 |
| `git:branches` | 本地 / 远端分支列举 | 与 `git branch -a` 一致 |
| `git:checkout` | 切换分支与失败分类 | 有未提交改动时按 git 语义拒绝并给出分类错误 |
| `git:create-branch` | 建分支并可选中切换 | 新分支存在且 HEAD 指向它 |
| `git:checkout-remote` | 检出远端并建跟踪分支 | 上游关系正确（`git rev-parse --abbrev-ref @{u}`） |
| `git:merge` | 合并并返回冲突分类 | 冲突时返回冲突文件列表而非通用失败 |
| `git:merge-abort` | 中止合并 | 中止后回到合并前状态 |
| `git:delete-branch` | 删分支（含 force） | 未合并分支不加 force 时拒绝 |
| `git:rename-branch` | 重命名分支 | 旧名消失、新名存在 |
| `git:delete-remote-branch` | 删远端分支 + `safeRef` 校验 | 非法 ref 被拒，合法时远端分支消失 |
| `git:log` | 提交列表，depth 1..500 | depth 越界被截断或拒绝，返回字段完整 |
| `git:init` | 初始化仓库 | 空目录可 init，重复 init 有明确返回 |
| `git:fetch` | `fetch --prune` | 远端已删分支的本地跟踪引用被清理 |
| `git:pull` | pull | 快进与冲突两种情形分别返回正确结果 |
| `git:push` | push / push -u | 新分支自动设置上游 |
| `git:generate-commit-message` | diff 摘要 + 模型流式生成 + 中断 | 生成过程中可中断，中断后不留半截提交信息 |
| `git:cancel-commit-message` | 进行中生成请求注册表 | 取消后生成请求终止，界面状态回到空闲 |

### R12　`browser:` 域 13 条

**目标**：内置浏览器面板（独立视图、标签注册表、导航、缩略图）。
**前置依赖**：R4（需要真显示环境验证）、R1（渲染层契约比对）。
**预估规模**：XL（原版依赖 Electron `BrowserView` 与 `capturePage`，QtWebEngine 无对位接口，
`live-start` / `live-stop` / `thumbnail` 三条需要另找帧源方案）。
**风险**：`browser:live-start` 走 Electron 定时器推流，QtWebEngine 无等价接口；
若改用 `QWebEngineView.grab()` 会带来明显 CPU 开销，需要先测；
`browser:handoff` 要求双向通道，语义复杂。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `browser:open` | 独立视图 + 浏览器面板 UI | 打开后出现浏览器面板，聊天页不被替换 |
| `browser:dock` | 停靠 / 浮动布局切换 | 两种布局各截图，几何符合契约 |
| `browser:close-session` | 按会话关闭标签 | 关闭后该会话标签清空，其他会话不受影响 |
| `browser:live-start` | 实时帧推流的帧源 | 帧率与 CPU 占用实测记录；不可行则明确记为已知差异 |
| `browser:live-stop` | 停止推流 | 停止后不再产生帧，CPU 回落 |
| `browser:pin` | 钉住窗口（alwaysOnTop 子窗口） | 钉住后浮在聊天窗之上 |
| `browser:activate` | 标签注册表与视图切换 | 激活指定标签后当前页变化 |
| `browser:close-tab` | 关闭标签并广播状态 | 事件推送到渲染层，标签栏同步 |
| `browser:nav` | 前进/后退/刷新/停止 | 四种动作各生效，历史栈正确 |
| `browser:menu` | 浏览器视图上的原生右键菜单 | 菜单项与实际动作对应 |
| `browser:thumbnail` | 标签缩略图 | 缩略图非空且随页面变化 |
| `browser:handoff` | 控制权交还代理的双向通道 | 交接后代理能继续操作同一页面 |
| `browser:stop` | 按会话停止浏览器操作（运行期注册表） | 停止后该会话的进行中操作终止 |

### R13　`tasks:` 域 8 条

**目标**：定时任务调度器（`tasks.json` + cron 解析 + nextRun 计算）。
**前置依赖**：无。
**预估规模**：M（原版 `tasks.ts` 约 500 行 + 类型定义）。
**风险**：时区与 DST 处理是主要坑；`tasks:run-now` 与正在运行的实例并发必须显式回报「已在运行」。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `tasks:list` | 读取任务清单 | 与 `tasks.json` 内容一致，含 nextRun |
| `tasks:get` | 单条读取 | 不存在的 id 返回明确空值 |
| `tasks:create` | 校验 tz/cron/once 并计算 nextRun | 非法 cron 被拒，合法 cron 的 nextRun 可复算 |
| `tasks:update` | 局部更新，非法 schedule 静默忽略 | 只更新给定字段，非法 schedule 不破坏原值 |
| `tasks:delete` | 删任务并清理其会话 | 任务与会话同时消失 |
| `tasks:set-status` | active 时清零错误计数并重算 nextRun | 状态切换后 nextRun 与计数符合预期 |
| `tasks:preview` | cron 描述生成与下次运行时间预览 | 常见 cron 的中文描述正确（含 `*/5`、`0 9 * * 1`） |
| `tasks:run-now` | 立即运行并回报「已在运行」 | 并发触发第二次时返回已在运行而非重复执行 |

### R14　`mcp:` 域 9 条

**目标**：MCP 配置读写 + 运行期连接状态 + 密钥命名空间。
**前置依赖**：无（`SecretsVault` 已可用）。
**预估规模**：M（原版 `mcp-config.ts` + `mcp.ts` 约 1000 行）。
**风险**：密钥键空间 `mcp:<id>:<field>` 与现有密钥库的键规则要统一，
否则会出现「有密钥但查不到」；`mcp:remove` 必须同时清运行态、配置与密钥，缺一即残留。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `mcp:list` | 读取 `mcp.json` + 运行期连接状态 | 列表含 enabled/connected 两列真实状态 |
| `mcp:get` | 单条配置读取 | 不存在时返回明确空值 |
| `mcp:upsert` | 名称去空白、slug 生成唯一 id | 同名重复 upsert 复用同一 id |
| `mcp:remove` | 撤运行态 + 删配置 + 清 `mcp:<id>:` 前缀密钥 | 三步都完成后无残留（配置/进程/密钥各查一次） |
| `mcp:set-roles` | 角色白名单写入 | 非白名单角色调用被拒 |
| `mcp:set-enabled` | 启停写入并触发 reconcile | 关闭后服务不再拉起 |
| `mcp:retry` | 重连并回最新视图 | 失败后重试成功，状态同步 |
| `mcp:set-secret` | 写 `mcp:<id>:<field>` | 写入后 `has-secret` 为真，明文不落盘 |
| `mcp:has-secret` | 存在性查询 | 只回布尔，不回密钥内容 |

### R15　`remote:` 域 9 条

**目标**：远端机器人（飞书 / Telegram）配对、启停、作用域与授权用户管理。
**前置依赖**：无工程内依赖，但需要真实机器人凭据才能端到端验证。
**预估规模**：L（原版 `remote/` 共约 3400 行）。
**风险**：涉及外部平台协议与账号，无法离线验证；删除机器人 / 移除用户属于不可逆操作，
必须二次确认；配对码有效期与并发配对要明确。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `remote:scan-start` | 局域网扫码配对（二维码 + 等待态） | 扫码后出现等待态，超时可取消 |
| `remote:scan-cancel` | 取消配对扫描 | 取消后不残留监听 |
| `remote:set-enabled` | 启停并注册/注销 hub | 关闭后不再接收消息 |
| `remote:set-reply-mode` | stream / final 回复模式 | 两种模式下外部端收到的消息形态不同 |
| `remote:set-scope` | 全部 / 按角色 / 按会话 | 作用域外消息不被处理 |
| `remote:delete-bot` | 删除机器人与其状态 | 删除后列表不再出现，外部连接断开 |
| `remote:pair-code` | 配对码生成 | 配对码唯一、有有效期 |
| `remote:pair-cancel` | 取消配对 | 取消后配对码失效 |
| `remote:remove-user` | 移除已授权用户 | 移除后该用户消息被拒 |

### R16　`terminal:` 域 5 条

**目标**：终端面板（xterm.js + pty）。
**前置依赖**：无。
**预估规模**：M（原版 `terminal.ts` 约 110 行，但 pty 与前端渲染是主要工作量）。
**风险**：pty 生命周期与进程回收容易泄漏；`terminal:input` 是单向 `ipcMain.on` 通道，
桥层目前只有 invoke 语义，需要单独注册单向通道；Windows 只有 ConPTY，行为与 Unix 不同。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `terminal:list-shells` | 平台 shell 清单 | 与系统实际可用 shell 一致（Windows 含 pwsh/cmd） |
| `terminal:create` | 建 pty 与会话 id 注册表 | 创建后可读写，进程存活 |
| `terminal:input` | 单向写入（`on` 通道） | 输入回显正确，非 UTF-8 字节不破坏流 |
| `terminal:resize` | TIOCSWINSZ / ConPTY resize | 改尺寸后 `stty size` 与界面一致 |
| `terminal:dispose` | 关闭 pty 并清理注册表 | 关闭后进程退出，无僵尸 |

### R17　`memory:` 域 4 条

**目标**：记忆文件（全局 / 项目作用域）读写服务。
**前置依赖**：无。
**预估规模**：S（原版 `memory.ts` 约 360 行）。
**风险**：去重与字数上限、总量预算要一次定清楚，否则记忆会无限膨胀；
项目作用域与全局作用域的路径判定必须复用同一条规则。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `memory:list` | 列出两个作用域的记忆 | 作用域隔离正确 |
| `memory:write` | 去重、字数上限、总量预算 | 重复内容去重，超限被拒并说明 |
| `memory:delete` | 按 id 删除 | 删除后不可读，其他条目不受影响 |
| `memory:clear` | 清空指定作用域 | 只清该作用域 |

### R18　`deliverables:` 域 4 条

**目标**：交付物清单（`toolUseId` → 产出文件的映射）与打开/定位。
**前置依赖**：R10（需要回合产出的 toolUseId 映射表）。
**预估规模**：S（原版 `deliverables.ts` 约 130 行）。
**风险**：`deliverables:open` 用系统默认程序打开任意路径，必须限制在受信根内，
否则成为任意文件执行入口。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `deliverables:inspect` | 清单与 toolUseId 映射 | 一次回合产出的文件全部出现 |
| `deliverables:thumbnail` | 缩略图生成与缓存 | 图片有缩略图，非图片有类型图标，缓存命中 |
| `deliverables:open` | `QDesktopServices` 打开（限受信根） | 受信根外路径被拒 |
| `deliverables:reveal` | 文件管理器中定位 | 打开所在目录并选中文件 |

### R19　`update:` 域 3 条

**目标**：检查更新、下载、安装并重启。
**前置依赖**：R2（要先有跨平台发布产物）。
**预估规模**：M（原版 `updater.ts` 约 270 行，但需要发布源与签名）。
**风险**：自动更新涉及签名校验与回滚，做错会造成无法启动的安装；
在没有正式发布源与签名之前应保持未实现，而不是做半套。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `update:check` | 查询发布源版本 | 有新版/无新版两种返回正确 |
| `update:download` | 下载并校验 | 校验失败不落盘为可用包 |
| `update:install` | 安装并重启 | 重启后版本号变化，失败可回滚 |

### R20　`skills:` 域 1 条

**目标**：从文件/目录导入 `SKILL.md` 并解析 frontmatter。
**前置依赖**：无（`frontmatter` 解析与技能存储已存在）。
**预估规模**：S。
**风险**：导入的目录可能包含任意文件，必须只取 `SKILL.md` 与其声明资源，
不能整目录复制。

| 通道 | 要做的事 | 可核查验收 |
|---|---|---|
| `skills:import` | 导入 + frontmatter 校验 | 合法技能导入后出现在列表；缺 `name`/`description` 时被拒并说明 |

---

## 交付顺序建议

1. **先做 R1、R3**：都不大，却能立刻改善「结论可信度」与「能否自称可用」。
2. **再做 R2**：把已验证平台从 1 个扩到 5 个。
3. **R6 → R7 → R10** 是一条依赖链，做完才算「对话域完整」。
4. **R11 / R13 / R17 / R20** 互相独立、规模可控，可并行插空做。
5. **R12（浏览器）规模最大且依赖真显示环境，放最后**；`live-start` /
   `live-stop` / `thumbnail` 三条若 QtWebEngine 无法给出可用帧源，
   以「已记录差异」结案，不做假实现。
6. **R19 保持未实现**，直到有跨平台发布产物与签名方案。
