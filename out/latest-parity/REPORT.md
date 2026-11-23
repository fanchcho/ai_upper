# QML 对齐 deva 最终报告（A/B/C/D 四阶段 · 18 页）

> 本文件最初覆盖「基线取证 + 在新基线上重拍两侧」，后续 A/B/C/D 四阶段的修复、测试与
> 最终 18 页重拍都累积在同一份记录里。逐页最终数字以 §5.2 / §5.5 为准，较早章节里的
> 「改后」若与最终值不同均明确标为历史阶段值。

日期：2026-11-22 起　仓库：`/home/agent/shared_workspace/ai_upper`（分支 `develop`）

---

## 1. 「最新版」是哪一版（只读取证）

### 1.1 本地 deva HEAD 与远端 main

```
$ cd /home/agent/shared_workspace/deva
$ git rev-parse HEAD
61f6a357be5d23d8dc534966e5447b2efe4e345f
$ git status --short
（空输出，rc=0）
$ git log -1 --format='%H %ci %s'
61f6a357be5d23d8dc534966e5447b2efe4e345f 2026-11-22 09:37:46 +0800 chore(out): 记录文档收尾后的四项快检 / note post-docs re-check
$ git branch -vv | head -3
  backup/pre-merge-20261120 109937f chore(desktop): 版本号升级至 0.1.15 / bump version to 0.1.15
  deva_web                  3ddd9dc [fork/deva_web] feat(web): 将 apps/web 源码纳入版本管理 / track apps/web sources in version control
* feat/plugin-deva-agent    61f6a35 [fork/feat/plugin-deva-agent] chore(out): 记录文档收尾后的四项快检 / note post-docs re-check
$ git remote -v
fork    git@github.com:fanchcho/deva.git (fetch)
fork    git@github.com:fanchcho/deva.git (push)
origin  https://github.com/sqfcyily/deva.git (fetch)
origin  https://github.com/sqfcyily/deva.git (push)
$ git ls-remote origin main
b0f0d828b58b07f43ac4de8bd883a8ad8dbc7838	refs/heads/main
```

**结论：本地 deva HEAD `61f6a35` 不是远端最新。** 远端 `origin/main` 在
`b0f0d82`，两者从 merge-base `8997ecb` 分叉：

```
$ git merge-base HEAD b0f0d828b58b07f43ac4de8bd883a8ad8dbc7838
8997ecb10914f2b14134eb7e17025ff138bd43f2
$ git rev-list --left-right --count HEAD...b0f0d828b58b07f43ac4de8bd883a8ad8dbc7838
20	1
```

即本地领先 20 个提交、落后 1 个提交。为什么没有直接切到 `b0f0d82`：`/home/agent/shared_workspace/deva`
是**只读**工作树（硬约束不许 checkout / pull）。所以按硬约束的做法，在 `/tmp` 下
用它做了一份合并树：

```
$ git merge-tree --write-tree HEAD b0f0d828b58b07f43ac4de8bd883a8ad8dbc7838
b4c30a7ae217c7a701833eff38eee5cab65240be
（rc=0，无冲突）
$ comm -12 <(git diff --name-only 8997ecb HEAD | sort) \
           <(git diff --name-only 8997ecb b0f0d828b58b07f43ac4de8bd883a8ad8dbc7838 | sort) | wc -l
0
$ git diff --name-only 8997ecb HEAD | wc -l
214
$ git diff --name-only 8997ecb b0f0d828b58b07f43ac4de8bd883a8ad8dbc7838 | wc -l
12
```

两侧改动文件集合交集为 0，所以合并树 = 本地 214 个文件 + 远端的 12 个文件，无取舍。

**基线定义（写死，后面所有对照都指向它）：**

| 项 | 值 |
|---|---|
| 基线来源 | 合并树 `b4c30a7` = 本地 `61f6a35` + 远端 main `b0f0d82` |
| 构建位置 | `/tmp/deva-merged`（源码树拷贝，非 git 工作树，`git status` 报 not a repository） |
| 是否远端最新 | **是**：包含 `origin/main` 当前 tip 的全部 12 个改动文件 |
| 原版版本号 | `apps/desktop/package.json` → `"version": "0.1.16"` |

远端 main 那 1 个提交的实际内容（也是第 3 步要补的功能来源）：

```
$ git diff --stat 8997ecb b0f0d828b58b07f43ac4de8bd883a8ad8dbc7838
 apps/desktop/src/main/providers/index.ts           |   4 +-
 apps/desktop/src/main/providers/opencode.ts        |  16 ++-
 apps/desktop/src/main/providers/types.ts           |  28 ++++-
 apps/desktop/src/main/services/model-resolve.ts    |  17 +++
 apps/desktop/src/main/services/provider.ts         |   2 +-
 .../src/features/settings/ModelSettings.tsx        |  25 +++-
 .../src/features/settings/ProviderAdvanced.tsx     | 134 +++++++++++++++++++++
 apps/desktop/src/renderer/src/i18n/messages.ts     |  26 ++++
 apps/desktop/src/renderer/src/mock/models.ts         |  5 +
 apps/desktop/src/renderer/src/store/models.tsx      |   9 +
 apps/desktop/src/renderer/src/styles/app.css       |  14 +++
 apps/desktop/src/shared/provider-headers.ts        |  62 ++++++++++
 12 files changed, 328 insertions(+), 14 deletions(-)
```

### 1.2 渲染前提（字面值）

| 前提 | 实测值 / 命令 |
|---|---|
| node | `v24.22.1`（`node -v`） |
| npm | `11.19.1`（`npm -v`） |
| pnpm | **缺失**：`pnpm: command not found`；corepack `0.36.0` 可用 |
| 包管理声明 | `package.json`: `"packageManager": "pnpm@10.8.0"`, `"engines": {"node": ">=20"}` |
| 依赖 | deva 已有 pnpm-hoisted `node_modules`；`/tmp/deva-merged/node_modules` → 符号链接到 deva 的，`apps/desktop/node_modules` 同样链接，不重复装 |
| 构建 | `electron-vite build` → `apps/desktop/out/{main,preload,renderer}`（gitignored）；合并树产物 `978047 B` main、`779 B` renderer/index.html，out 合计 `4.3M` |
| electron 二进制 | `$DEVA_ROOT/node_modules/electron/dist/electron`（178MB） |
| 启动方式 | `DEVA_HOME=<tmp> electron --no-sandbox --disable-gpu --user-data-dir=<tmp> $DEVA_ROOT/apps/desktop/out/main/index.js` |
| Xvfb | `:97`，`-screen 0 1400x900x24`；窗口 `windowmove 0 0` + `windowsize 1280 820` |
| 客户端区 | `1280x820`，DPR 1（未设 `QT_SCALE_FACTOR` / `QT_ENABLE_HIGHDPI_SCALING`） |
| 页面清单来源 | deva 侧 `scripts/parity/deva_pages_all.sh` 第 79–96 行 18 个 `run_if`；QML 侧 `app/src/qml_shell.py:150` 的 `PAGE_NAMES`（同名 18 个，逐项一致） |
| QML 侧渲染 | `QT_QPA_PLATFORM=offscreen`（`app/src/main.py:52` setdefault）+ 软件光栅 + `QQuickWindow.grabWindow()`（`qml_shell.py:1325`）；窗口 1280×820 见 `Main.qml:19-20` |
| 字体 | QML `Theme.sansFamily = "DejaVu Sans"`（`Theme.qml:95`）；deva 侧为 Chromium 默认 sans，二者同族 |
| 遮罩 | `Theme.backdrop = Qt.rgba(0,0,0,0.42)`（`Theme.qml:64`） |
| 数据夹具 | `/tmp/fx-pages/data/chats`（121 个文件，120 会话 + 1 索引）；`/tmp/fx-page-home/{config.json,config-dark.json}`，同一份 provider 配置两端共用 |

---

## 2. 在新基线上重拍两侧

产物目录（**没有写 `out/final-close/`**，新目录独立）：

- deva：`out/latest-parity/deva/<page>-deva.png`，日志 `out/latest-parity/deva-18pages.log`
- QML：`out/latest-parity/qml/<page>.png`（另有 18 份 `.out`/`.err`），日志 `out/latest-parity/qml-18pages.log`

命令（deva 侧只多一个 `DEVA_ROOT` 指到合并树）：

```
DEVA_ROOT=/tmp/deva-merged bash scripts/parity/deva_pages_all.sh out/latest-parity/deva
bash scripts/parity/qml_pages_all.sh out/latest-parity/qml
```

### 2.1 页数与失败

```
$ ls out/latest-parity/deva | wc -l        → 18
$ ls out/latest-parity/qml/*.png | wc -l   → 18
$ tail -1 out/latest-parity/deva-18pages.log
done: 18 页 -> out/latest-parity/deva
$ cat out/latest-parity/qml-18pages.log   → 18 行全是 `ok <page> 1280x820 <size>B rc=0`
$ ls -l out/latest-parity/qml/*.err | awk '{print $5}' | sort -u
0
```

QML 侧 18 份 stderr 全部 0 字节 —— 没有 QML 警告/报错被吞掉。

过程异常（已处置，记录在案）：`hover-thread` deva 侧第一次出图被判为空图并自动重试，
第二次正常（`retry hover-thread (attempt 1)` → `ok hover-thread 158169B`）；
`model-picker` 首轮是全批次里唯一一张 stub 图（左侧全黑、中列还是 QuickStart），
按单页重拍：

```
$ DEVA_ROOT=/tmp/deva-merged bash scripts/parity/deva_pages_all.sh out/latest-parity/deva model-picker
ok   model-picker 1280x820 164258B
```

表里 13.41% 用的是重拍后的图（`946b07de…`），不是首轮那张 39,718B 的残图。

### 2.2 逐页 md5 与差异像素（D 轮最终值）

分母统一 `1280*820 = 1049600`。下表已换成 D 轮 18 页全量重拍后的真实输出；
最终复算日志 `out/latest-parity/logs/d-page-diff18-final.log`（rc=0）。

| 页名 | deva md5 | QML md5 | 差异像素 | 差异% |
|---|---|---|---|---|
| chat | `ac72cd59…` | `00baf469…` | 113088 | 10.77 |
| ctx-menu | `64c8c33a…` | `5bb17055…` | 122224 | 11.64 |
| dark-chat | `252996a5…` | `8cacd0f7…` | 111631 | 10.64 |
| delete-confirm | `964c32d1…` | `1f0c4130…` | 382652 | 36.46 |
| empty | `a616eabe…` | `e56462d7…` | 13231 | 1.26 |
| first-run | `0e2b5786…` | `e56462d7…` | 13231 | 1.26 |
| focus-composer | `e976e085…` | `00b028ef…` | 113104 | 10.78 |
| hover-thread | `16917898…` | `03a15c4a…` | 113042 | 10.77 |
| long-bottom | `be7b7fe8…` | `a5576a85…` | 124452 | 11.86 |
| long-mid | `147fb156…` | `f4e1fc46…` | 142444 | 13.57 |
| model-picker | `946b07de…` | `66be1f24…` | 117437 | 11.19 |
| search-none | `49503995…` | `2fc3a406…` | 85175 | 8.11 |
| search-open | `3a5f8098…` | `572f4907…` | 113117 | 10.78 |
| search-results | `1d1ba812…` | `6526581e…` | 107403 | 10.23 |
| settings-about | `3fac0ec7…` | `2388394c…` | 302389 | 28.81 |
| settings-extensions | `15d607e1…` | `7f4d07e3…` | 305797 | 29.13 |
| settings-general | `4d16a5c6…` | `b95b109b…` | 315274 | 30.04 |
| settings-models | `7f7a6dd8…` | `dc5ee213…` | 300497 | 28.63 |

`empty` 与 `first-run` 是**同一屏**，两侧像素级都是零差：

```
$ compare -metric AE deva/empty-deva.png deva/first-run-deva.png → 0
$ compare -metric AE qml/empty.png       qml/first-run.png       → 0
```

deva 侧两张的 PNG 文件 md5 不同（`a616eabe…` / `0e2b5786…`），但解码后像素签名完全相同
（`identify -verbose` 的 `signature` 两张都是 `76390a45…`），差异只在 PNG 的
`date:create` / `date:modify` 文本块（两张拍摄间隔 16 秒）。QML 侧两张连文件字节都相同
（都是 `e56462d7…`）。**结论：md5 列在这里只对「同一时刻拍的同一帧」可比，`empty` /
`first-run` 这一对被 PNG 时间戳分开了，像素差为 0。**

### 2.3 关键校验：新基线没有改变这 18 页的既有画面

合并 upstream 后必须回答一个问题 —— **新增的 Provider 高级设置 UI 是否动了老页面？**
逐页把「新拍 deva」与旧对照 `out/final-close/deva-final`（老基线上拍的）做 AE：

```
$ for f in out/latest-parity/deva/*-deva.png; do compare -metric AE "$f" out/final-close/deva-final/$(basename $f) null:; done
chat                5
ctx-menu            0
dark-chat           0
delete-confirm      0
empty               0
first-run           0
focus-composer      0
hover-thread        0
long-bottom         0
long-mid            0
model-picker        5
search-none         0
search-open         0
search-results      0
settings-about      0
settings-extensions 0
settings-general    0
settings-models     0
```

**16/18 页逐字节相同，2 页各差 5 个像素**（chat / model-picker 各 5 个像素，落在输入框
光标闪烁相位）。结论：远端 main 的 12 个文件改动对 18 个既有页面状态**零可见影响**
（provider 高级设置只在 `purpose !== 'decision'` 的 provider 详情里出现，而这些页面
都不进详情页）。所以本轮第 3 步的「结构差异」全部来自 **QML 尚未实现的功能**，
不是基线漂移造成的。

### 2.4 旧对照 `deva-rerun` 的漂移已定性

`out/final-close/deva-final` 与 `out/final-close/deva-rerun` 之间的差异（此前遗留的
「不是字节一致」问题）现在有定量答复：

```
$ compare -metric AE deva-rerun/chat-deva.png  deva-final/chat-deva.png   → 4444
$ compare -metric AE deva-rerun/long-mid-deva.png …                       → 4438
$ compare -metric AE deva-rerun/settings-general-deva.png …               → 1676
$ compare -metric AE deva-rerun/search-results-deva.png …                 → 3170
$ convert rerun final -compose difference -composite -colorspace gray -threshold 5% -format '%@' info:
55x712+272+71
```

差异区域是一个 `55×712 @ (272,71)` 的窄条 —— 正好是会话栏里相对时间文案那一列
（`22 hr ago` → `yesterday`）。同一份数据在两天拍，相对时间必然会跳；这是**夹具语义
漂移，不是渲染差异**。本轮新拍（`out/latest-parity/deva`）与 `deva-final` 的 AE 已回到
0/5，说明当天时段内两侧时区与文案一致。

---

## 3. 下一步（第 3 步）的清单来源

由 §1.1 的 12 个文件 + 逐页表定性，待补的**结构/功能**差异（不是字体光栅）：

1. **设置 · Models 面板结构**：QML 现在只有一个标题 + 裸 ListView（`SettingsModal.qml`
   `modelsPane`）；deva 是 `Providers` 标题（15/700）+ 28×28 `+` 按钮 + 1px 描边圆角
   容器（`models__rows`）+ 52 高 provider 行（10×10 启用点、13/600 名称、11.5 subtle
   副标题、警告三角 `#d68a00`、chevron）。
2. **provider 详情下钻页**：`view: 'list' | 'detail' | 'model' | 'advanced'`，
   顶栏 Wrench 按钮（仅 `purpose !== 'decision'`）进 `ProviderAdvanced`。
3. **自定义请求头**（upstream 新功能）：`ProviderAdvanced.tsx` + `shared/provider-headers.ts`
   —— `MAX_CUSTOM_HEADERS=32`、`RESERVED_HEADERS`、`NAME_RE`/`VALUE_RE`、`headerIssue()`、
   `sanitizeHeaders()`、`providerCustomHeaders(providerId)` 读
   `config.models.providers[].headers`，并在 `providerHeaders(baseURL, providerId, sessionId)`
   里**最后合并**；ai_upper 侧 `provider_registry.provider_headers()` 目前只有
   `user-agent` + 可选 `x-opencode-session`，**未实现**。
4. **403 文案**：`types.ts` 新增 `forbiddenError(body)`，把 provider 返回的原因带进消息。
5. **设置 · About 面板**：deva 用 `{t('settings.version')} {__APP_VERSION__}`
   （`0.1.16`），QML 硬编码 `"0.1.15"` 且无前缀、图标是纯紫渐变块、更新按钮缺 RefreshCw。
6. **图标**：需要新增 `wrench`、`refresh-cw`（`scripts/parity/gen_icons.mjs` 的 WANTED
   与 `IconData.qml` 都没有）。

第 3 步每修一项单独提交，并把「前/后」截图或数字写进本文件后续章节。

---

## 4. 第 3 步逐项修复

### 4.1 仓库根残留清理 + 像素对照脚本入库（A1）

**残留取证**（清理前）：

```
$ du -sh core data personas
88M	core
12K	data
40K	personas
$ ls -ld core data personas
-rw------- 1 root hermes 516042752 Nov 21 17:29 core
drwxr-sr-x 3 root hermes      4096 Nov 21 20:08 data
drwxr-sr-x 2 root hermes      4096 Nov 21 20:08 personas
$ head -c 16 core | od -c
0000000 177   E   L   F 002 001 001  \0  \0  \0  \0  \0  \0  \0  \0
$ find data -type f; find personas -type f
data/chats/_index.json
personas/general.md
personas/xiaomajiang.md
$ cat data/chats/_index.json
[]
$ md5sum personas/*.md app/assets/personas/*.md
8bb697ed335d63391d2208efa2c275d6  personas/xiaomajiang.md
8bb697ed335d63391d2208efa2c275d6  app/assets/personas/xiaomajiang.md
90557fe34053a2814d5534348b89eb1b  personas/general.md
90557fe34053a2814d5534348b89eb1b  app/assets/personas/general.md
```

判定依据：

- `core` 首 4 字节是 `\177ELF`，516 MB、mtime 11-21 17:29 —— 是**进程崩溃的 core dump**
  （Linux 把它写在进程 CWD，而当时有一次从仓库根起应用的运行），不是仓库内容；
- `personas/` 两份 md5 与 `app/assets/personas/` 的种子**逐字节相同** —— 是
  `PersonaStore.ensure_seeded()` 在数据根被指到仓库根时复制出来的首启种子，不是用户数据；
- `data/chats/_index.json` 是 `[]` —— 空会话索引，同上。

处置：三者全部删除；`.gitignore` 增加 `core` / `core.*` 与 `/personas/` / `/data/`
（前两项堵住再次误生成的路径，后两项保证误指向时也不会被 `git add .` 收进库）。
**没有把任何一项提交进库。**

**脚本入库**：`scripts/parity/page_diff18.py` 原先依赖 ImageMagick 的
`identify` / `convert`，而当前环境里两者**都不存在**（`command -v convert identify
magick` → rc=1）。新增 `scripts/parity/pngread.py`（纯标准库 PNG 解码：位深 8、
非隔行、颜色类型 0/2/4/6，逐行反滤波），`page_diff18.py` 与 `out/latest-parity/pixlib.py`
都改用它，这样重拍对照不再依赖外部二进制。

新解码器的正确性以旧数字为准：对同一批 `out/latest-parity/{deva,qml}` 复算，18 页
差异像素与**当时** §2.2 表逐项一致（chat 126790 / empty 10325 / search-results 104080 /
settings-models 328000 / settings-about 334166 …），整表 37 秒跑完，rc=0。这组数字只是解码器
等价性校验的历史基线；当前 §2.2 已换成 D 轮最终全量重拍值（chat 113088 / empty 13231 /
search-results 107403 / settings-models 300497 / settings-about 302389）。

### 4.2 设置页数据投影与请求头语义（A2）

commit `f96766a`（`feat(settings): 设置页 Model/About 数据投影 + 自定义请求头语义 + 桥接`）。

新增 `app/src/mvvm/services/settings_models.py`（服务商过滤 / 列表行 / 详情投影 /
整段 `models` 写回）与 `app/tests/test_qml_settings_models.py`（44 条）；`ShellBridge`
把 `modelRows` 改为走同一份投影，并新增 `modelsPaneLabels` / `providerDetail` /
`setProviderField` / `deleteProvider` / `addProvider` / `setModelEnabled` /
`addModel` / `removeModel` / `setProviderHeaders`。

真实命令与输出：

```
$ AI_UPPER_HOME=/tmp/ai-upper-b1 .venv/bin/python -m pytest app/tests/test_qml_settings_models.py -q > /tmp/t1.log 2>&1; echo rc=$?
rc=0
$ tail -1 /tmp/t1.log
44 passed in 0.21s

$ AI_UPPER_HOME=/tmp/ai-upper-b1 .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > /tmp/t2.log 2>&1; echo rc=$?
rc=0
$ tail -1 /tmp/t2.log
46 passed in 0.74s

$ AI_UPPER_HOME=/tmp/ai-upper-b1 .venv/bin/python -m pytest -q > /tmp/all.log 2>&1; echo rc=$?
rc=0
$ tail -1 /tmp/all.log
1320 passed, 5 skipped in 30.22s
```

5 条 skip 均为环境门禁（Windows 专属 pyconfig / GUI-subsystem 用例各 1，`AI_UPPER_E2E=1`
未设的本地构建 E2E 2 条，缺 `cc`/`patchelf`/`readelf` 的原生部署 1 条），无 failed。

判否项：无。本节只交付数据层与桥接，QML 的 Models 面板结构（`models__head` /
28×28 加号 / 1px 描边圆角容器 / 52 高行）仍未改，留给下一节。

### 4.3 图标：wrench / refresh-cw（B2-1）

**改动**：`scripts/parity/gen_icons.mjs` 的 WANTED 末尾加 `'wrench', 'refresh-cw'`；用同一个生成器
重出 `app/src/qml/IconData.qml`（几何直接来自 deva 只读仓库的
`node_modules/lucide-react/dist/esm/icons/`，没有手写路径）。提交：`7c04b21`。

**生成命令与真实退出码**：

```
$ node scripts/parity/gen_icons.mjs /home/agent/shared_workspace/deva /tmp/IconData.regen.qml > /tmp/b2-gen.log 2>&1; echo rc=$?
rc=0
$ tail -n 1 /tmp/b2-gen.log
icons -> /tmp/IconData.regen.qml count=33 names=messageCircle,...,alertTriangle,wrench,refreshCw
$ diff /tmp/IconData.regen.qml app/src/qml/IconData.qml > /tmp/b2-diff.log 2>&1; echo diff_rc=$?
diff_rc=0   # 空 diff：入库文件与生成器输出逐字节一致
```

**两个图标可被查到的证据**（`grep -n "wrench\|refreshCw\|refresh-cw"`）：

```
scripts/parity/gen_icons.mjs:37:  'wrench', 'refresh-cw'
app/src/qml/IconData.qml:70:    // wrench
app/src/qml/IconData.qml:71:    readonly property string wrench: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6..."
app/src/qml/IconData.qml:72:    // refresh-cw
app/src/qml/IconData.qml:73:    readonly property string refreshCw: "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8|..."
app/src/qml/IconData.qml:107:        if (key === "wrench") return wrench
app/src/qml/IconData.qml:108:        if (key === "refreshCw") return refreshCw
```

判否项：无。

### 4.4 设置 · Models 面板：Providers 标题 + 28×28 加号 + 描边容器（B2-2）

commit `96e7136`（`feat(settings): Models 面板 Providers 标题 + 28×28 加号 + 描边容器`）。
改动路径：`app/src/qml/SettingsModal.qml`（`modelsPane` 三项结构）、`app/src/qml/Theme.qml`
（补 `--bg-elevated` 语义 token：浅色 `#ffffff` / 深色 `#2a2a2e`）。

几何逐值取自 deva 只读源码 `features/settings/ModelSettings.tsx` + `styles/app.css`：
`.cf-pane` 内边距 `var(--space-4) var(--space-5)`（16px 20px）；`.models__head` 高 28
（flex/align-items:center）+ `margin-bottom: var(--space-4)`（16px）；`.models__title`
15px/700、`var(--fg)`；`.models__add-btn` 28×28、`1px solid var(--border)`、
`border-radius: var(--radius)`（8px）、`background: var(--bg-elevated)`、Plus 图标 16；
`.models__rows` `border: 1px solid var(--border)`、`border-radius: var(--radius-lg)`（12px）。
数据只走已入库的 `app/src/mvvm/services/settings_models.py` 投影（`shellBridge.modelRows()` /
`shellBridge.modelsPaneLabels()`），QML 未新建数据源。

**单页重拍**（只拍 settings-models，AI_UPPER_HOME 指向 /tmp 夹具）：

```
$ bash scripts/parity/qml_page_shot.sh settings-models /tmp/settings-models-after.png /tmp/fx-qml-home config.json > /tmp/shot-after.log 2>&1; echo rc=$?
rc=0
$ sed -n '1p' /tmp/shot-after.log
QML OK platform=offscreen title='Deva' sessions=120 active='parity-000' plain=False turn_stop='' deltas=0 home=/tmp/fx-qml-home png=/tmp/settings-models-after.png size=1280x820
```

**差异复算**（`scripts/parity/page_diff18.py`，改前基线 `out/latest-parity/qml/settings-models.png`
已先备份到 `/tmp/settings-models-before.png`，改后图写入同路径）：

```
$ python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml > /tmp/after-diff18.txt 2>&1; echo rc=$?
rc=0
$ grep 'settings-models' /tmp/after-diff18.txt
settings-models        7f7a6dd835823f50475db7a3c9e727c1 5cfc65fa1103ba93eea1d3627595cee8  132243  102589  326609  31.12% max=237 same=False
```

改前基线同一算法：`328000 px / 31.25%`；改后实测：`326609 px / 31.12%`（降低 1391 像素、
0.13 个百分点）。注：该指标按任意通道非零差计，整页背景/字体抗锯齿的系统性差异占大头；
本次只改 Models 列表头与容器，结构差异集中在这三处。

**受影响测试**：

```
$ AI_UPPER_HOME=/tmp/ai-upper-models-test-shell .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > /tmp/test-qml-shell.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-qml-shell.log
46 passed in 0.58s

$ AI_UPPER_HOME=/tmp/ai-upper-models-test-settings .venv/bin/python -m pytest app/tests/test_qml_settings_models.py -q > /tmp/test-qml-settings-models.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-qml-settings-models.log
44 passed in 0.21s
```

判否项：provider 行高 52px、警告三角、chevron、详情下钻、Wrench、provider 详情请求头界面、
About 版本单一来源、18 页全量重拍、四条硬判据复核均未做——本轮只交付 Providers 标题、
28×28 加号、1px 描边圆角容器三项；provider 行仍沿用旧 delegate，留待下一段。

#### 4.4.1 复测回填：五要素复核 + 两处缺口补齐

本节回填的是**测量结论**，不是新改结构：Providers 标题 / 28×28 加号 / 描边容器 /
52px 行五要素 / 详情下钻这五项复核后全部「已存在」，逐项对照见下。

**逐项复核（数据一律走 `app/src/mvvm/services/settings_models.py`）**

| # | 项 | 结论 | 证据（`app/src/qml/SettingsModal.qml` ↔ deva） |
|---|---|---|---|
| 1 | 「Providers」分区标题 | 已存在 | `:473`（`modTitle`）15px/700 `Theme.fg` ↔ `.models__title` `app.css:4481-4486` |
| 2 | 28×28 加号按钮 | 已存在 | `:483`（`addBtn`）28×28 / radius 8 / 1px `Theme.border` ↔ `.models__add-btn` `app.css:4493-4503` |
| 3 | 描边容器 | 已存在 | `:516`（`modRows`）radius `radiusLg`(12) / 1px / `x:19` ↔ `.models__rows` `app.css:4509-4515` |
| 4 | 52px 行五要素 | 已存在 | `:559` height 52、`:575` 10×10 点、`:592` 名称、`:601` 副标题、`:617` 告警 14、`:623` chevron 16 ↔ `.provider-row` `app.css:4516-4582` |
| 5 | 行下钻详情 | 已存在 | `:634` `MouseArea → openProvider()`；详情态 `:643`（`detailView`）起 ↔ `renderProviderRow` `ModelSettings.tsx:137-158` |

**两处真实缺口（本轮补齐）**

1. **详情顶栏缺删除按钮**。deva `ModelSettings.tsx:387-393` 的 topbar 顺序是
   `返回 · spacer · Trash2 · 「启用」 · Switch`，QML 只有 `Wrench + 启用 + Switch`；
   `shellBridge.deleteProvider()`（`app/src/qml_shell.py:703`）与
   `remove_provider()`（`settings_models.py:310`）早已入库却无人调用。
2. **加号按钮只有悬停、没有点击**。`:483` 那块止于 `HoverHandler`，而 deva
   `ModelSettings.tsx:365` 是 `onClick={() => onAddProvider('llm')}`；
   `shellBridge.addProvider()`（`qml_shell.py:718`）同样已入库未接线。本轮在 `:506`
   接上 `shellBridge.addProvider()` 并随后 `openProvider(newId)` 进详情。

补齐值全部取自 deva：删除按钮 30×30 / `radius-sm` / 常态 `--fg-subtle`、hover `--danger`
（`.icon-btn` `app.css:139-149`、`.provider-detail__del` `app.css:4905-4910`）；确认卡片沿用
已实测的 Modal 规格（420×186、radius 12、背板 `rgba(0,0,0,.42)`、Cancel 70 / Delete 69 × 30）。

**改前 → 改后实测**

改前（本机复算，与表中原记录同值）：

```
$ python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml > /tmp/before-diff18.txt 2>&1; echo rc=$?
rc=0
$ grep 'settings-models' /tmp/before-diff18.txt
settings-models        7f7a6dd835823f50475db7a3c9e727c1 ddee23d6140c34d38e4b3b07d6b524b7  132243  103282  325672  31.03% max=237 same=False
```

改后：

```
$ bash scripts/parity/qml_page_shot.sh settings-models /tmp/sm-after.png /tmp/models-after-home config.json > /tmp/sm-after.log 2>&1; echo rc=$?
rc=0
$ cp /tmp/sm-after.png out/latest-parity/qml/settings-models.png
$ python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml > /tmp/after-diff18.txt 2>&1; echo rc=$?
rc=0
$ grep 'settings-models' /tmp/after-diff18.txt
settings-models        7f7a6dd835823f50475db7a3c9e727c1 487b0f063cec7387802856ebeacdf9d4  132243  104913  323783  30.85% max=237 same=False
```

**31.03% → 30.85%**（−0.18pp，−1889 px）。但必须先说清这 0.18pp 的来路，否则数字会被误读：

- 本轮改前/改后两张列表页截图 **md5 完全相同**
  （`487b0f063cec7387802856ebeacdf9d4`，`104913` B，两次独立拍摄亦逐像素一致），
  即列表态**一个像素都没变**——删除按钮与加号点击都只存在于详情态/交互路径。
- 原记录 `31.03%` 对应的是仓库里那张 `ddee23d6…png`；本机用同一 commit 的 QML 重拍得到
  `487b0f06…`，两者差 `1889 px`。差异来自重拍本身（同为 offscreen + 软件光栅的栅格化产物），
  而非本轮代码改动。
- 因此本轮对**该页像素指标的真实贡献是 0**；`30.85%` 是「当前代码 + 当前光栅环境」的实测值。

**31.03% 里到底差在哪（区域拆解，改后图）**

```
$ python3 -I - <<'PY'
# 逐像素比对 deva 基线 vs out/latest-parity/qml/settings-models.png
# modal bbox = (281,131)-(999,690)，即弹窗卡片本体
PY
modal             diff=   3875  area= 401362  pct= 0.97%
backdrop_left     diff= 220943  area= 230420  pct= 95.89%
backdrop_right    diff=  30570  area= 230420  pct= 13.27%
backdrop_top      diff=  31129  area=  94058  pct= 33.10%
backdrop_bottom   diff=  37266  area=  93340  pct= 39.93%
```

弹窗内 3875 px 仅占整页差异的 **1.2%**；其余 98.8% 全部在弹窗外——deva 那张基线是
「聊天页 + 盖一层设置弹窗」，背后有正文、附件卡、composer、模型选择器，而 QML 的同名页
背后是空聊天页。这不是 Models 面板的对齐问题，而是 `settings-models` 这个页面场景本身
两侧背景不同；单页指标无法反映弹窗质量。弹窗内残留的 3875 px 经连通域聚类后落在
文字栅格（`Providers` 标题 1px 横向偏移、`Anthropic`/`1 models` 亚像素抗锯齿）与
弹窗内 4 个图标字形上，无结构性差异。

**建议**：后续比较设置类页面应改用「弹窗区域裁切后比对」或「背景遮罩后比对」，
否则该指标恒在 30% 附近且几乎不随弹窗改动变化。本次未改指标定义（避免动到其它 17 页
的历史数字），只把拆解记录在此。

**受影响测试（本轮）**

```
$ AI_UPPER_HOME=/tmp/ai-upper-models-test-shell .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > /tmp/test-qml-shell.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-qml-shell.log
47 passed in 0.48s

$ AI_UPPER_HOME=/tmp/ai-upper-models-test-settings .venv/bin/python -m pytest app/tests/test_qml_settings_models.py -q > /tmp/test-qml-settings-models.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-qml-settings-models.log
44 passed in 0.17s

$ AI_UPPER_HOME=/tmp/ai-upper-prov-test4 .venv/bin/python -m pytest app/tests/test_qml_settings_provider.py -q > /tmp/tp4.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/tp4.log
3 passed in 8.94s
```

新增 `app/tests/test_qml_settings_provider.py`（3 例）：删除按钮几何 30×30 → 点开确认卡片
（420×186 / 70×30 / 69×30）→ 点「删除」后服务商与其密钥一起消失并退回列表；Cancel 与
背板点击只关卡片不删；加号 28×28 点击后新建 custom 对话服务商并直接进其详情。

**全量套件仍有既有 segfault（非本轮引入）**：`pytest app/tests -q` 在
`test_qml_context_menu.py:162 _menu_items` 处崩溃 `rc=139`。把本轮对
`SettingsModal.qml` 的改动 stash 掉后重跑，仍在同一行崩溃（`rc=139`），
故为环境中既有的 Qt 交互测试问题，与本次改动无关；本轮涉及的三套测试单跑全绿。

#### 4.4.2 settings-models 单页复测（2026-11-23，本轮无代码改动）

本轮只复测 `settings-models` 单页：deva 基线复用 `out/latest-parity/deva/settings-models-deva.png`，QML 侧用 `/tmp` 临时 home 重拍；改前值取本节 §4.4.1 的现有记录 `30.85%`。

```
$ TMPHOME=$(mktemp -d /tmp/ai-upper-sm-XXXXXX); cp -a /tmp/fx-qml-home/. "$TMPHOME"/
$ bash scripts/parity/qml_page_shot.sh settings-models /tmp/settings-models-after.png "$TMPHOME" config.json > /tmp/shot-after.out 2> /tmp/shot-after.err; echo rc=$?
rc=0
$ sed -n '1p' /tmp/shot-after.out
QML OK platform=offscreen title='Deva' sessions=120 active='parity-000' plain=False turn_stop='' deltas=0 home=/tmp/ai-upper-sm-OMMlnq png=/tmp/settings-models-after.png size=1280x820
$ wc -c < /tmp/shot-after.err
0
$ identify -format '%wx%h %b' /tmp/settings-models-after.png
1280x820 104913B
$ md5sum /tmp/settings-models-after.png out/latest-parity/qml/settings-models.png
487b0f063cec7387802856ebeacdf9d4  /tmp/settings-models-after.png
487b0f063cec7387802856ebeacdf9d4  out/latest-parity/qml/settings-models.png
```

```
$ python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml > /tmp/after-diff18.txt 2>&1; echo rc=$?
rc=0
$ grep 'settings-models' /tmp/after-diff18.txt
settings-models        7f7a6dd835823f50475db7a3c9e727c1 487b0f063cec7387802856ebeacdf9d4  132243  104913  323783  30.85% max=237 same=False
```

改前 `30.85%` → 改后 `30.85%`（0.00pp，0 px）。逐值核对（Providers 标题 / 28×28 加号 / 描边容器 / 52px 行五要素 / 行下钻）后确认结构已与 deva 一致，**本轮无代码改动**。

**受影响测试（本轮）**

```
$ AI_UPPER_HOME=/tmp/ai-upper-test-shell-nOa4UU .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > /tmp/test-qml-shell.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-qml-shell.log
47 passed in 0.49s

$ AI_UPPER_HOME=/tmp/ai-upper-test-settings-VhB34F .venv/bin/python -m pytest app/tests/test_qml_settings_models.py -q > /tmp/test-qml-settings-models.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-qml-settings-models.log
44 passed in 0.17s
```

#### 4.4.3 依实测差异的三处几何修正

本轮不再做结构复核，只按逐像素差异定位三处偏差并改。

**测量**（改前，`/tmp/sm-before.png`）：

```
$ bash scripts/parity/qml_page_shot.sh settings-models /tmp/sm-before.png /tmp/fx-qml-home config.json > /tmp/sm-before.log 2>&1; echo rc=$?
rc=0
$ cat /tmp/sm-before.log
QML OK platform=offscreen title='Deva' sessions=120 active='parity-000' plain=False turn_stop='' deltas=0 home=/tmp/fx-qml-home png=/tmp/sm-before.png size=1280x820
$ wc -c < /tmp/sm-before.log
165
$ grep settings-models /tmp/diff18-before.txt
settings-models        7f7a6dd835823f50475db7a3c9e727c1 a5bef126890dfc69d10a22c33bca9bd1  132243   82175  294675  28.07% max=237 same=False
```

改前逐像素差异 **28.07%**（294675 / 1049600 px）。差异最大的 3 个 40×40 矩形：
`x=480 y=200` / `x=480 y=160` / `x=480 y=120`（各 1600/1600 = 100%），全部落在弹窗外背景
——该页基线是「聊天页 + 设置弹窗」，QML 侧背景是空聊天页，这属既有场景差异（见 §4.4.1）。
弹窗本体 bbox `(281,131)-(999,690)` 内只有 3857 px（1.0%）。

**三处修正**（`app/src/qml/SettingsModal.qml`）：

1. `.provider-row__sub` `font-size:11.5px`（`app.css:4567-4573`）
   → `:603` 改前 `font.pixelSize: 12` → 改后 `font.pointSize: 8.625`
   （pixelSize 只收整数，96dpi 下 11.5px = 8.625pt；同 `Main.qml:1351` 的 13.5px 做法）。
2. `.models__rows` 边框内缘（`app.css:4509-4515`）实测 deva 左边框 x=469、右边框 x=978
   → `:517-519` 改前 `x: 19 / width: parent.width - 38` → 改后 `x: 20 / width: parent.width - 40`
   （容器与 `modHead` 的 28px 加号同列，宽度补偿 2px 是早前为对齐错误左缘引入的）。
3. `.provider-row__aside` `align-items:center`（`app.css:4574-4580`）
   → `:617` 告警三角加 `y: 1`；改前 deva 三角上沿 y=265、QML 264，chevron 的 x 也差 1px。
4. 同一提交里并存的窗格根因：右窗格 `paneArea` 起点 `x: 169` 比原版 `.cf-modal__body`
   第二列（导航列 168px）多 1px → `:170-173` 改为 `x: 168 / width: parent.width - 168`。
   该项影响所有设置页（Models 只是其中一页），改后设置页内容左缘由 x=470 回到 x=469。

**复测**：

```
$ bash scripts/parity/qml_page_shot.sh settings-models /tmp/sm-after.png /tmp/fx-qml-home config.json > /tmp/sm-after.log 2>&1; echo rc=$?
rc=0
$ cp /tmp/sm-after.png out/latest-parity/qml/settings-models.png
$ python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml > /tmp/diff18-after.txt 2>&1; echo rc=$?
rc=0
$ grep settings-models /tmp/diff18-after.txt
settings-models        7f7a6dd835823f50475db7a3c9e727c1 92c0f06f8b41707f3e6396e8c1bfe529  132243   81933  294323  28.04% max=216 same=False
```

**28.07% → 28.04%（当轮历史值；D 轮最终 28.63%）**（−0.03pp，−352 px）。弹窗内 3857 → 3634 px（−223 px，−5.8%），
其中 aside 区 `(915,255)-(985,300)` 155/3150、容器左右边框两端已逐列对齐
（deva 与 QML 在 y=270 均为 `[469, 978, 999]`）。整页百分比几乎不动的原因与 §4.4.1 同：
294323 px 差异里 99% 在弹窗外。

剩余弹窗内 3634 px 经连通域聚类，最大簇为
`(517,274)-(558,283)` 279 px（副标题 `1 models` 的亚像素抗锯齿，字号已对齐、
bbox 仅差下沿 1px）、`(303,270)-(317,284)` 等四簇 15×15 为设置弹窗左侧导航图标字形的
栅格化差异，无结构性缺口。

**受影响测试**：

```
$ AI_UPPER_HOME=/tmp/t-sm-XXX .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > /tmp/t1.log 2>&1; echo rc=$?
rc=0
$ grep -E "passed|failed|skipped|error" /tmp/t1.log
48 passed in 10.85s

$ AI_UPPER_HOME=/tmp/t-sm2-XXX .venv/bin/python -m pytest app/tests/test_qml_settings_models.py -q > /tmp/t2.log 2>&1; echo rc=$?
rc=0
$ grep -E "passed|failed|skipped|error" /tmp/t2.log
44 passed in 0.17s
```

指定命令双文件同跑（本轮的最终验收命令）：

```
$ H=$(mktemp -d /tmp/ours-pytest-XXXXXX); AI_UPPER_HOME=$H .venv/bin/python -m pytest app/tests/test_qml_shell.py app/tests/test_qml_settings_models.py -q > /tmp/ours-pytest.log 2>&1; echo rc=$?
rc=0
$ tail -1 /tmp/ours-pytest.log
92 passed in 10.65s
```


#### 4.4.4 dsh 复验（HEAD 858b2a4）

de8564ef 空输出的补跑只做复验，不改 QML；实现提交为 `23de5e7`
（`app/src/qml/SettingsModal.qml`）。复验命令与结果：

```
$ H=$(mktemp -d /tmp/dsh-shell-XXXXXX); AI_UPPER_HOME=$H .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > /tmp/dsh-shell.log 2>&1; echo rc=$?
rc=0
$ grep -E "passed|failed|skipped|error" /tmp/dsh-shell.log
48 passed in 10.56s

$ H=$(mktemp -d /tmp/dsh-models-XXXXXX); AI_UPPER_HOME=$H .venv/bin/python -m pytest app/tests/test_qml_settings_models.py -q > /tmp/dsh-models.log 2>&1; echo rc=$?
rc=0
$ grep -E "passed|failed|skipped|error" /tmp/dsh-models.log
44 passed in 0.17s

$ git show 23de5e7^:out/latest-parity/qml/settings-models.png > /tmp/sm-before-git.png
$ md5sum /tmp/sm-before-git.png
487b0f063cec7387802856ebeacdf9d4  /tmp/sm-before-git.png
$ H=$(mktemp -d /tmp/sm-after-home-XXXXXX); cp -a /tmp/fx-qml-home/. "$H"/; bash scripts/parity/qml_page_shot.sh settings-models /tmp/sm-after.png "$H" config.json > /tmp/sm-after.log 2>&1; echo rc=$?
rc=0
$ md5sum /tmp/sm-after.png
92c0f06f8b41707f3e6396e8c1bfe529  /tmp/sm-after.png
$ python3 -I -c "import sys;sys.path.insert(0,'scripts/parity');from page_diff18 import load,diff;d,w,h,_,_=load('out/latest-parity/deva/settings-models-deva.png');exec('for p in [\"/tmp/sm-before-git.png\",\"/tmp/sm-after.png\"]:\n b,_,_,_,_=load(p);n,worst=diff(d,b,w,h);print(p,n,round(n*100/(w*h),2),worst)')"
/tmp/sm-before-git.png 323783 30.85 237
/tmp/sm-after.png 294323 28.04 216
```

**30.85% → 28.04%（当轮历史值；D 轮最终 28.63% / 300497 px）**（−2.81pp，−29,460 px；before 323,783 px，after 294,323 px）。

### 4.5 设置 · Models 服务商行 + 详情下钻 + Wrench + 自定义请求头（B2-3）

**交付范围**：provider 列表行改为 52px 高（启用点、名称、`N models` 副标题、告警时的
`alertTriangle` 14px、右侧 `chevronRight` 16px），整行可点击进入 provider 详情；详情页
顶部有返回入口与 `Wrench` 15px 按钮位；详情页可进入高级设置，自定义请求头按名称/值
两列增删（含空态、hover、删除按钮、备注文案），写回走已入库的 `setProviderHeaders()`。

**几何取值**（只读 `/tmp/deva-merged/apps/desktop/src/renderer/src`，逐值对应）：
`.provider-row` `min-height:52px; padding:10px 14px; gap:12px`；`.provider-row__dot`
10×10；`.provider-row__sub` 11.5px（QML 取整 12px）；`.provider-row__warn` 14px；
`ChevronRight` 16px；`.provider-detail__topbar` 30px + 16px；`.provider-detail__head`
名称 18px/600、底边 1px；`.model-list` 1px 边框、radius 8px；`.model-row` 44px；
`.header-item__name` 占 34%；`.input` 32px；`.icon-btn` 30×30；`.switch` 36×20。

**数据与页面状态**：QML 只读 `shellBridge.modelRows()` / `modelsPaneLabels()` /
`providerDetail()`；写回只走 `setProviderHeaders()` / `setProviderField()`，投影和
`sanitize_headers`（保留名、非法字符、32 条上限）在
`app/src/mvvm/services/settings_models.py` / `provider_headers.py`，未另建数据源。
`Main.qml` 新增 `settings-models-provider` / `settings-models-advanced` 两个仅用于截图
验证的页面名；`qml_shell.py::PAGE_NAMES` 收录它们，但 `qml_pages_all.sh` 的 18 页清单未改。

**单页重拍**（只拍 settings-models，AI_UPPER_HOME 指向 /tmp 夹具）：

```
$ bash scripts/parity/qml_page_shot.sh settings-models /tmp/settings-models-final.png /tmp/fx-qml-home config.json > /tmp/shot-models-final.log 2>&1; echo rc=$?
rc=0
$ sed -n '1p' /tmp/shot-models-final.log
QML OK platform=offscreen title='Deva' sessions=120 active='parity-000' plain=False turn_stop='' deltas=0 home=/tmp/fx-qml-home png=/tmp/settings-models-final.png size=1280x820
```

**差异复算**（`scripts/parity/page_diff18.py`；改前基线为 `out/latest-parity/qml/settings-models.png`
备份 `/tmp/settings-models-before.png`，改后图已写回同路径）：

```
$ python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml > /tmp/after-diff18-final.txt 2>&1; echo rc=$?
rc=0
$ grep 'settings-models' /tmp/after-diff18-final.txt
settings-models        7f7a6dd835823f50475db7a3c9e727c1 ddee23d6140c34d38e4b3b07d6b524b7  132243  103282  325672  31.03% max=237 same=False
```

改前 `31.12%`（326609 px）→ 改后 `31.03%`（325672 px，降低 937 px、0.09 个百分点；
逐像素差按任意通道非零计，字体抗锯齿与截图像素级渲染差异占主要部分）。

**详情页单独成图**（同一 1280×820，两个页面名均为截图专用）：

```
$ bash scripts/parity/qml_page_shot.sh settings-models-provider /tmp/settings-models-provider-final.png /tmp/fx-qml-home config.json > /tmp/shot-provider-final.log 2>&1; echo rc=$?
rc=0
$ bash scripts/parity/qml_page_shot.sh settings-models-advanced /tmp/settings-models-advanced-final.png /tmp/fx-qml-home config-advanced.json > /tmp/shot-advanced-final.log 2>&1; echo rc=$?
rc=0
```

落盘：`out/latest-parity/qml/settings-models-provider.png`（详情：Back + Wrench +
Enabled + 告警条 + 模型列表）、`out/latest-parity/qml/settings-models-advanced.png`
（高级设置：自定义请求头两行）。另用真实鼠标事件探针实测：点击 provider 行进入详情、
详情 Back 返回列表、Wrench 进入高级设置，Add header 增行后出现占位输入框、trash 删除
行后列表恢复两行（探针截图 `/tmp/probe-header-added.png` / `/tmp/probe-header-deleted.png`）。

**受影响测试**（真实 rc 与输出末行）：

```
$ AI_UPPER_HOME=/tmp/ai-upper-models-test-shell .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > /tmp/test-qml-shell-final.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-qml-shell-final.log
46 passed in 0.76s

$ AI_UPPER_HOME=/tmp/ai-upper-models-test-settings .venv/bin/python -m pytest app/tests/test_qml_settings_models.py -q > /tmp/test-qml-settings-models-final.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-qml-settings-models-final.log
44 passed in 0.21s
```

两份均 0 failed、0 skipped。仍未做：**About 版本单一来源 + refreshCw、18 页全量重拍、四条硬判据 均未做**。

### 4.6 设置 · About 版本单一来源 + refreshCw 检查更新（A）

**版本单一来源**：`app/src/mvvm/services/provider_registry.py::APP_VERSION`（唯一常量）经
`app_version()` 暴露；`ShellBridge.appVersion()` 只读该函数，QML `SettingsModal.qml` 的
`root.appVersion` 通过桥接取值。原 QML 第 1358 行硬编码的 `0.1.15` 已删除；`app/src`
全域 grep 后只剩这一个版本字面量（见下）。基线版本链为
`apps/desktop/package.json` `0.1.16` → `electron.vite.config.ts:41` `__APP_VERSION__` →
`SettingsPane.tsx` About 的 `settings.version` 文案；本仓库用 `APP_VERSION = "0.1.16"`
对齐基线值，但不在 QML 复制版本号。

**取值来源与逐值对应**（只读 `/tmp/deva-merged/apps/desktop/src/renderer/src`）：

| 文件 | 选择器 / 组件 | 取到的值 |
|---|---|---|
| `styles/app.css` | `.btn`（line 2530） | `height:30px; padding:0 var(--space-3); border:1px solid var(--border-strong); border-radius:var(--radius-sm); background:var(--bg-elevated); gap:var(--space-2); font-weight:500` |
| `styles/app.css` | `.btn--sm`（line 2558） | `height:26px; padding:0 var(--space-2); font-size:12px` |
| `styles/app.css` | `.btn:not(:disabled):hover`（line 2542） | `background:var(--bg-hover)` |
| `styles/app.css` | `.btn:disabled`（line 2546） | `opacity:0.45; cursor:not-allowed` |
| `redesign/redesign.css` | `.cf-about`（line 3440） | `padding:24px 0` |
| `redesign/redesign.css` | `.cf-about__name`（line 3451） | `margin-top:12px; font-size:20px; font-weight:750` |
| `redesign/redesign.css` | `.cf-about__ver`（line 3456） | `margin-top:2px; font-size:12px; color:var(--fg-subtle)` |
| `redesign/redesign.css` | `.cf-update`（line 3468） | `margin-top:var(--space-4); gap:var(--space-2)` |
| `redesign/UpdateSection.tsx` | idle button | `<button className="btn btn--sm" ...>` + `<RefreshCw size={13} />` |
| `redesign/UpdateSection.tsx` | checking | `<Loader2 size={13} className="spin" />`，按钮 disabled；`check` 调 `window.deva.update.check()` |
| `redesign/SettingsPane.tsx` | AboutPane | `settings.version` + `__APP_VERSION__` |

落地值：按钮 `height:26px`、`radius:6px`（`--radius-sm`）、`1px solid #d5d5db`
（`--border-strong`）、背景 `#ffffff`（`--bg-elevated`）、hover `Theme.bgHover`
（`rgba(0,0,0,0.045)`）、checking `opacity:0.45`、内容 gap `8px`、内边距 `0 8px`、
refreshCw 图标 `13×13`、文字 `12px/500`；版本前缀取 `modelsText.version`（中文
`版本`、英文 `Version`），即 `版本 0.1.16` / `Version 0.1.16`。About 图标替换为
`app/src/qml/assets/deva-icon.svg`（基线 `apps/desktop/build/icon.svg` 的逐字节副本）。

**grep 证据**：

```
$ grep -RIn --exclude-dir=__pycache__ -E '0\.1\.15|0\.1\.16|0\.17\.33' app/src
app/src/mvvm/services/provider_registry.py:35:APP_VERSION = "0.1.16"
```

**单页重拍**：

```
$ bash scripts/parity/qml_page_shot.sh settings-about /tmp/settings-about-final.png /tmp/fx-qml-home config.json > /tmp/shot-about-final.log 2>&1; echo rc=$?
rc=0
$ sed -n '1p' /tmp/shot-about-final.log
QML OK platform=offscreen title='Deva' sessions=120 active='parity-000' plain=False turn_stop='' deltas=0 home=/tmp/fx-qml-home png=/tmp/settings-about-final.png size=1280x820
```

落盘 `out/latest-parity/qml/settings-about.png`（104052 bytes，sha256
`8afc66aa48eb65e6f0a196e7fff6525b1055f7c7abb9242b6c5f21c411c94c07`）。改前 `settings-about` diff：
`334166 px / 31.84%`；当轮改后:
`328222 px / 31.27%`（历史阶段值；D 轮最终 `302389 px / 28.81%`，`logs/d-page-diff18-final.log`；
降低 5944 px、0.57 个百分点；按任意通道非零差计，剩余主要是整页字体抗锯齿/主题通道差异，
不是 About 组件结构差）。

**点击行为实测**：真实 `QTest.mouseClick(window, ..., (724,394))` 后
`ShellBridge.updateState()` 由 `{'phase':'idle'}` → `{'phase':'checking'}`，网络返回后
→ `{'phase':'latest','version':'0.1.16'}`；QML `aboutPaneRoot.updatePhase` 同步变为
`latest`，截图 `/tmp/probe-click-about.png` 显示 `You're on the latest version`。
hover 实测按钮底色 `#ffffff` → `#ececed`（`Theme.bgHover` 在面板底色上的合成结果）。

**受影响测试**：

```
$ AI_UPPER_HOME=/tmp/ai-upper-about-test-shell .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > /tmp/test-about-qml-shell.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-about-qml-shell.log
46 passed in 0.58s

$ AI_UPPER_HOME=/tmp/ai-upper-about-test-settings .venv/bin/python -m pytest app/tests/test_qml_settings_models.py -q > /tmp/test-about-qml-settings.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-about-qml-settings.log
44 passed in 0.21s

$ AI_UPPER_HOME=/tmp/ai-upper-about-test-providers .venv/bin/python -m pytest app/tests/test_provider_adapters.py -q > /tmp/test-about-providers.log 2>&1; echo rc=$?
rc=0
$ sed -n '$p' /tmp/test-about-providers.log
26 passed in 0.18s
```

判否项：无 About 组件结构判否项。B 的 18 页全量重拍、C 的四条硬判据、D 的逐页结构
缺口清单仍未做，随后按顺序执行。

**提交记录**：`0642d6e` `feat(settings): About 版本单一来源 + refreshCw 检查更新`。变更路径（7 个）：
`app/src/mvvm/services/provider_registry.py`、`app/src/mvvm/services/settings_models.py`、
`app/src/qml/SettingsModal.qml`、`app/src/qml/assets/deva-icon.svg`、`app/src/qml_shell.py`、
`out/latest-parity/REPORT.md`、`out/latest-parity/qml/settings-about.png`。

### 4.7 dark-chat：输入卡片底色取错 token

**先纠正一个口径**：任务书里的「dark-chat 整页差异 97.82%」不是差异百分比。`97.82%` 出自
`out/latest-parity/criterion4-stub-scan.log:19` 的**第 5 列「墨迹占比」**（`sum(r,g,b) < 420`
的像素占比）——深色页本来就几乎全是「墨迹」，这个数在修复前后**都是 97.82%**，不随任何改动变化。
真正的整页差异在 `page_diff18` 表里：修复前 `258651 px / 24.64%`
（`out/latest-parity/page-diff-table.txt:4`）。本节按后者报数。

**根因判定**（任务书要求的四选一）：**配色 token 取错值**。

- 排除「深色主题根本没生效」：改前整页主色 `(30,30,32)` 共 735886 px、侧栏 `(37,37,40)` 共
  193970 px，与 deva 的深色 `--bg #1e1e20`（`tokens.css:109`）/ `--bg-panel #252528` 合成值一致；
  `(60,760)=(37,37,40)` 两侧完全相同（`logs/dark-composer-ab.log`）。
- 排除「截图流程没进 dark 态」：`config-dark.json` 已生效，否则整页不会是暗色。
- 排除「页面状态注入后未重应用主题」：同一次截图里侧栏、正文、边框深浅都对，只有输入卡片一处错。
- 定为「token 取错值」：输入卡片底色在改前为 `(30,30,32)`=`--bg #1e1e20`，而 deva 是
  `(42,42,46)`=`--bg-elevated #2a2a2e`。QML 侧写的是 `color: Theme.bg`，应写 `Theme.bgElevated`。

**deva 取值出处（只读源，逐行核对）**：

| 事实 | deva 文件:行 |
|---|---|
| `.cf-box { … background: var(--bg-elevated); … box-shadow: var(--shadow); }` | `apps/desktop/src/renderer/src/redesign/redesign.css:2655-2662` |
| 卡片实例 `<div className="cf-box">` | `apps/desktop/src/renderer/src/redesign/Composer.tsx:866` |
| `--bg-elevated: #ffffff`（浅） | `apps/desktop/src/renderer/src/styles/tokens.css:43` |
| `--bg-elevated: #2a2a2e`（深） | `apps/desktop/src/renderer/src/styles/tokens.css:111` |
| `--bg: #1e1e20`（深，= 页面底色，**不是**卡片底色） | `apps/desktop/src/renderer/src/styles/tokens.css:109` |
| `--shadow: 0 6px 24px rgba(0,0,0,.12)`（浅） | `apps/desktop/src/renderer/src/styles/tokens.css:82` |
| `--shadow: 0 8px 30px rgba(0,0,0,.5)`（深） | `apps/desktop/src/renderer/src/styles/tokens.css:149` |

QML 侧 `Theme.qml:34` `_bgElevatedDark: "#2a2a2e"`、`:49` `bgElevated: dark ? …Dark : …Light`
取值本来就对，所以这是**引用错 token**，不是 token 表错。

**改动**（`app/src/qml/Main.qml`，两处）：

1. `composer` 的 `color: Theme.bg` → `color: Theme.bgElevated`（并注明 `redesign.css:2655-2662`
   与深/浅两色差异）。
2. 补卡片投影。`.cf-box` 带 `box-shadow: var(--shadow)`，QML 原先完全没有。实测在
   `QT_QUICK_BACKEND=software` 下 `MultiEffect` 与 `DropShadow` **都不出影**（灰底像素不变），
   只有 `Canvas` 的 `ctx.shadowColor/shadowBlur/shadowOffsetY` 生效；因此垫一张
   `composerShadow` 画布（外扩 38px = blur 30 外沿 + 8px 偏移，内侧 evenodd 挖掉卡面，
   否则半透明阴影会把卡面压暗），并在 `Theme.dark` 变化时 `requestPaint()`
   切深/浅两组参数（深 `rgba(0,0,0,.5)/30/8`，浅 `rgba(0,0,0,.12)/24/6`）。

**改前 / 改后（`scripts/parity/page_diff18.py` 真实输出，rc=0）**：

```
$ .venv/bin/python scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml
dark-chat              252996a52c0b1d02cfb3205ba1798c94 3aa7be544db6effc57214a22b11516ec  158038  141637  128299  12.22% max=230 same=False
```

改前 `258651 px / 24.64%`（`git show HEAD:out/latest-parity/qml/dark-chat.png` 复算，
258651 与 `page-diff-table.txt` 一致）→ **当轮改后 `128299 px / 12.22%`（历史阶段值）**，降 12.42 个百分点，
差异像素减半（-130352 px，-50.4%）。**D 轮最终全量重拍为 `111631 px / 10.64%`**
（`logs/d-page-diff18-final.log`；`258651 / 24.64%` 仅作为最早的历史 before 值保留）。分区对照（`out/latest-parity/probes/dark_composer_ab.py`，
日志 `out/latest-parity/logs/dark-composer-ab.log`）：

| 窗口 | 改前 | 改后 |
|---|---:|---:|
| 输入卡片 `440..1195 × 658..804` | 108710 / 110230 = **98.62%** | 3602 / 110230 = **3.27%** |
| 卡片+投影 `400..1240 × 620..820` | 157200 / 168000 = 93.57% | 26848 / 168000 = 15.98% |
| 左侧栏 `0..400`（未触及） | 47891 / 328000 = 14.60% | 47891 / 328000 = 14.60% |
| 正文 `400..1240 × 60..620`（未触及） | 46080 / 470400 = 9.80% | 46080 / 470400 = 9.80% |

未触及的两区像素级完全相同，说明改动只落在输入卡片上。卡面探针
`(500,690)/(800,700)/(900,780)` 改前全是 `(30,30,32)`、改后全是 `(42,42,46)`，与 deva
逐点相同；卡下 `x=800 y=805..819` 与卡左 `y=700 x=400..424` 投影灰阶改后与 deva 相差 ≤1
（如 `y=808` deva `(21,21,22)` / 改后 `(21,21,23)`）。

**顺带确认浅色无回归**：同一份 QML 重拍 `chat`，`page_diff18` 由 `136141 / 12.97%` →
`129909 / 12.38%`（浅色 `--bg` 与 `--bg-elevated` 同为 `#ffffff`，改 token 不影响底色，
差异下降来自新增的浅色阴影 `0 6 24 /.12`）。

**受影响测试**（在只含本节改动的干净树上跑，避免工作区其它未提交改动干扰）：

```
$ .venv/bin/python -m pytest app/tests/test_qml_shell.py -q
46 passed in 0.65s
rc=0
```

无 skipped、无 xfail、无 warning 输出。

**未做 / 已知残留**：本节只修输入卡片，当轮整页仍余 `12.22%`（D 轮最终 10.64%），集中在左侧栏 `14.60%`、正文 `9.80%`
和页面底部 `y≥810` 的 `45.90%` 带（A/B/E 类既有缺口，见 §5.4），按任务范围不在本轮。

**提交记录**：`dd0b38e` `fix(qml): dark-chat 输入卡片改用 --bg-elevated 并补 --shadow`，
`git show --name-only --format='' dd0b38e` 实测 7 个路径：`app/src/qml/Main.qml`、
`out/latest-parity/qml/dark-chat.png`、`out/latest-parity/qml/chat.png`、`out/latest-parity/REPORT.md`，另附
`out/latest-parity/logs/dark-composer-ab.log`、`out/latest-parity/logs/dark-fix-page-diff18.log`、
`out/latest-parity/probes/dark_composer_ab.py`。

### 4.8 ctx-menu / delete-confirm：5 项菜单与真可交互的删除确认

`dd0b38e` 提交时把 `ctx-menu` / `delete-confirm` 那批改动留在了工作区（`Main.qml` 另 6 个 hunk
与 `IconData.qml`）。本节把这批收尾，三条判据全部用**真实鼠标事件**取证，不用「已接线」口径。

**改动清单**：

| 文件 | 改动 |
|---|---|
| `app/src/qml/Main.qml` | 会话行右键打开菜单（`openCtxMenu`）；菜单 5 项（New chat / Rename / Select / Archive / Delete，Delete `danger`）；遮罩点击关闭；确认层 Cancel/Delete 两个真按钮 + 卡片吞点击 + 遮罩点击取消；`threadRow<i>` objectName 便于命中 |
| `app/src/qml/IconData.qml` | 新增 `listChecks`（lucide `list-checks`，对应原版 `Rail.tsx:475` 的 `<ListChecks/>`） |
| `scripts/parity/gen_icons.mjs` | 生成清单加 `list-checks` |
| `app/src/qml_shell.py` | 新增 `deleteSession(str) -> bool`；删当前会话时按 Deva `openFirstSession` 回退到列表首行 |
| `app/src/qml/SoftShadow.qml`（新） | 软件光栅投影组件：Canvas `ctx.shadow*` + evenodd 挖空；把 `dd0b38e` 里写死在输入卡片上的画布抽出来，菜单/对话框/输入卡片三处共用同一份参数 |
| `app/tests/test_qml_context_menu.py`、`app/tests/test_qml_shell.py` | 真实 `QTest.mouseClick` 的三条用户路径 + `deleteSession` 单测 |

`SoftShadow.qml` 是本节唯一动到 `dd0b38e` 已提交代码的地方（输入卡片由内联 Canvas 换成该组件）。
参数未变，重拍 `chat` / `dark-chat` 的 md5 与提交里完全一致（`dc133011…` / `3aa7be54…`），
即无回归。

**判据 1：菜单 5 项 + Delete 危险色**

探针 `out/latest-parity/probes/c5_ctx_confirm.py`（日志 `out/latest-parity/logs/c5-ctx-confirm.log`）：
起始页 `chat`（`ctxMenu` 不可见）→ 对 `threadRow0` 中心 `(205.5, 83.0)` 注入**右键**：

```
  右键后 ctxMenu 可见=True
  labels        = ['New chat', 'Rename', 'Select', 'Archive', 'Delete']
  labels==deva  = True
  item0 New chat  中心=(234.0, 110.5) bbox=(166.0, 96.0, 302.0, 125.0)
  item1 Rename    中心=(234.0, 139.5) bbox=(166.0, 125.0, 302.0, 154.0)
  item2 Select    中心=(234.0, 168.5) bbox=(166.0, 154.0, 302.0, 183.0)
  item3 Archive   中心=(234.0, 197.5) bbox=(166.0, 183.0, 302.0, 212.0)
  item4 Delete    中心=(234.0, 226.5) bbox=(166.0, 212.0, 302.0, 241.0)
  item0 New chat  红色像素=0    深色文字像素=124
  item1 Rename    红色像素=0    深色文字像素=145
  item2 Select    红色像素=0    深色文字像素=99
  item3 Archive   红色像素=0    深色文字像素=150
  item4 Delete    红色像素=227  深色文字像素=0

  同一 bbox 在 deva 参考图上的同判据计数：
    deva New chat  红色像素=0    深色文字像素=131
    deva Rename    红色像素=0    深色文字像素=155
    deva Select    红色像素=0    深色文字像素=101
    deva Archive   红色像素=0    深色文字像素=149
    deva Delete    红色像素=230  深色文字像素=0
```

「红色像素」判据：`r>150 且 r>g+60 且 r>b+50`；「深色文字像素」判据：`r+g+b<320`。
Delete 项 227 个红色像素、0 个普通前景像素，其余四项相反；同一 bbox 在 deva 参考图上是
230 / 0——说明第 5 项用的是 `Theme.danger`（浅色 `#e5484d` = `(229,72,77)`，`Theme.qml:61`；
deva `tokens.css:66` 同值），不是 `Theme.fg`。两侧只差 3 个抗锯齿边缘像素。

**判据 2：三处真实点击各自产生预期结果**

同一探针，坐标全部由控件 `mapToScene(中心)` 现算：

```
  起点：sessions=120 active=parity-000 parity-000 文件存在=True
  点菜单 Delete 后：confirm visible=True
  confirmCancel 中心=(718.0, 468.0)   bbox=(683.0, 453.0, 753.0, 483.0)
  confirmDelete 中心=(794.5, 467.0)   bbox=(760.0, 452.0, 829.0, 482.0)
  [a] 点取消中心后：confirm visible=False confirmOpen=False sessions=120 active=parity-000 文件存在=True
  [b] 点确认中心后：confirm visible=False confirmOpen=False sessions=119 active=parity-001 parity-000 文件存在=False
  confirmDialog bbox=(430.0, 317.0, 850.0, 503.0)
  [c] 点遮罩空白 (100,700) 后：confirm visible=False confirmOpen=False sessions=119 active=parity-001
```

- [a] 取消：关闭且**不删**（120→120，`parity-000` 文件仍在）；
- [b] 确认：关闭且**真删**（120→119，文件消失，活跃会话按 Deva 规则回退到 `parity-001`）；
- [c] 遮罩：关闭且不删（119→119），点击点 `(100,700)` 在卡片 bbox `(430,317,850,503)` 之外。

**判据 3：两页重拍（1280×820，stderr 0 字节）**

```
$ bash scripts/parity/qml_page_shot.sh ctx-menu out/latest-parity/qml/ctx-menu.png /tmp/fx-qml-home
ctx-menu rc=0 errbytes=0
QML OK platform=offscreen … png=out/latest-parity/qml/ctx-menu.png size=1280x820

$ bash scripts/parity/qml_page_shot.sh delete-confirm out/latest-parity/qml/delete-confirm.png /tmp/fx-qml-home
delete-confirm rc=0 errbytes=0
QML OK platform=offscreen … png=out/latest-parity/qml/delete-confirm.png size=1280x820
```

stderr 与 stdout 分别落盘在 `out/latest-parity/logs/c5-ctx-menu-shoot.{out,err}`、
`c5-delete-confirm-shoot.{out,err}`（`.err` 均为 0 字节）。`AI_UPPER_HOME` 指向 `/tmp/fx-qml-home`，
deva 目录只读未改。

**与参考图的差异（`page_diff18.py`，rc=0；日志 `logs/c5-page-diff18.log`）**：

```
ctx-menu        64c8c33a… 3c1fdb46…  158033 143492 127196 12.12% max=248 same=False
delete-confirm  964c32d1… 5b8baeb9…  162718 147103 384883 36.67% max=224 same=False
```

| 页 | 改前（HEAD 图复算） | 改后 |
|---|---:|---:|
| ctx-menu | 143461 / 13.67% | 127196 / 12.12%（B 轮历史） |
| delete-confirm | 401948 / 38.30% | 384883 / 36.67%（B 轮历史） |

**D 轮最终全量重拍**：`ctx-menu 122224 px / 11.64%`、`delete-confirm 382652 px / 36.46%`，max 分别为 248 / 224
（`logs/d-page-diff18-final.log`）。`delete-confirm` 剩余差异里 78.79% 只差 1–2 个灰阶（`deva(144,144,144)` vs `qml(143,143,144)`
共 183194 px），是遮罩 `rgba(0,0,0,.42)`（deva `redesign.css:3139`，QML `Theme.qml:68` 同值）
叠在背景对话上的合成取整差，不是结构缺口；本轮任务只要求两页可交互 + 重拍，
未改遮罩合成，故不再往下压。

**受影响测试**：

```
$ .venv/bin/python -m pytest app/tests/test_qml_context_menu.py app/tests/test_qml_shell.py -q
49 passed in 6.48s
rc=0
```

无 skipped、无 xfail。`test_qml_context_menu.py` 的三组断言与本节点探针覆盖同一批用户路径
（5 项几何 → 菜单 Delete → 确认 Delete；Cancel；遮罩），但它直接走 QML 内部事件路径，
本节探针额外测了 Delete 项的**像素颜色**与「右键入口」这两项。

**D 轮最终复核（同一工作树）**：`test_qml_context_menu.py` + `test_qml_shell.py` → **55 passed in 50.34s，rc=0**（`logs/d-a-tests-context-shell.log`）。非活动行 Rename/Select/Archive 的真实右键探针输出：`BEFORE sessions=120 active='parity-000'` → `AFTER_RENAME sessions=120 title='renamed non active' active='parity-000'` → `AFTER_SELECT selectMode=True selected=['parity-001'] active='parity-000'` → `AFTER_ARCHIVE sessions=119 archived=True active='parity-000'`，单测 `1 passed in 8.49s, rc=0`（`logs/a-rename-select-archive-probe.log`）。

**后续闭环**：右键菜单的 Rename / Select / Archive 三项已先后由 `d4279ad`（Rename → `renameSession`）、
`9e7d23c`（Select 无 id 时回退当前会话）、`0d2cf84`（session-row/menu 测试）接通；`923f554` 又补了
从**非活动行**真实右键的端到端探针（标题落盘、选择集与归档持久化），不再有「只渲染、不接动作」的缺口。
菜单阴影按 `0 6 24 / .12` 补齐后与 deva 逐像素相差 ≤1 灰阶，未再调参。

**提交记录**：`cddf2fb` `fix(qml): align context menu and make delete confirmation interactive`
（2026-11-22 23:31:37 +0800，父提交 `dd0b38e`，已随 `develop` 分支 push 到 `origin`）。
`git show --name-only --format='%H %s' cddf2fb` 实测 17 个路径，与本节改动清单逐条对上：

```
app/src/qml/IconData.qml                       ← listChecks
app/src/qml/Main.qml                           ← 右键菜单 + 确认层 + threadRow<i>
app/src/qml/SoftShadow.qml                     ← 新组件（dd0b38e 的内联 Canvas 抽出）
app/src/qml_shell.py                           ← deleteSession(str) -> bool
app/tests/test_qml_context_menu.py             ← 新文件，3 条真实 QTest 点击路径
app/tests/test_qml_shell.py                    ← deleteSession 单测
scripts/parity/gen_icons.mjs                   ← 生成清单加 list-checks
out/latest-parity/REPORT.md                    ← 本节
out/latest-parity/probes/c5_ctx_confirm.py     ← 判据 1/2 探针
out/latest-parity/logs/c5-ctx-confirm.log
out/latest-parity/logs/c5-ctx-menu-shoot.{out,err}
out/latest-parity/logs/c5-delete-confirm-shoot.{out,err}
out/latest-parity/logs/c5-page-diff18.log
out/latest-parity/qml/ctx-menu.png
out/latest-parity/qml/delete-confirm.png
```

无未提交残留：本节改动清单里的 6 个源码/测试文件与 `SoftShadow.qml` 全部在 `cddf2fb` 的
`--name-only` 内；`git status --porcelain` 的「已修改」条目为 **0**（其余全是既有 `out/`
未跟踪产物，与本批无关）。回归口径复核：`dd0b38e` 提交的 `chat.png` / `dark-chat.png`
在工作区 md5 仍为 `dc133011…` / `3aa7be54…`，未被本节重写。

**本节改动对应提交**：`cddf2fb`（右键菜单 5 项 + Delete 危险色 + 删除确认三处真实点击）
与 `923f554`（非活动行右键 Rename / Select / Archive 三项动作端到端探针 + `ctx-menu` 重拍）。

### 4.9 model-picker 弹层内容与聚焦态

本轮范围只有 model-picker 一页的 D1 / D2 / D3 三项；A/B/E/F/G 类缺口不在本轮范围内，未动。
所有证据都用**真实鼠标事件**打开菜单（注入到贴片中心，见探针 `probes/c6_model_picker.py`），
从不直接置位 `pickerMode` 造态；截图 1280×820，stderr 0 字节（`logs/c6-mp-shoot.err`）。

**改动清单**

| 文件 | 改动 |
|---|---|
| `app/src/qml/ModelPicker.qml` | 双模式弹层（`mode="model"` / `"thinking"`）：分组标题 + 模型行 + 14px 勾选位、空态、外框 1px `--border` / radius 12 / `--bg-elevated` / `SoftShadow`(blur 20)。每个取值在文件头注释里标了「来源文件:行号 → 落地值」 |
| `app/src/qml/Main.qml` | `openPicker(mode)` / `closePicker()`；两个 `ModelPicker` 实例分别挂在 `effortChip` / `modelChip` 内（`right:0`、`bottom: calc(100% + 8px)`）；贴片展开态换 `--bg-active` 底 / `--fg` 字 / 箭头 180°；输入卡片 `border.color` 增加 `window.modelPickerOpen` 分支 |
| `app/tests/test_qml_model_picker.py`（新） | 3 条真实 `QTest.mouseClick` 路径 + 渲染像素断言（四边取色、面板几何、字号与位置、accent 与 weight） |

**D1：弹层内容与逐项取值**

原版取值（只读 `/tmp/deva-merged/apps/desktop/src/renderer/src`）与落地值一一对应：

| 项 | 原版来源 → 值 | QML 落地 |
|---|---|---|
| 面板外壳 | `styles/app.css:3367-3376` `.model-pick__menu` → padding 5、1px `var(--border)`、`var(--radius-lg)`=12、`var(--bg-elevated)`、`var(--shadow)`、`bottom: calc(100% + 8px)` | `ModelPicker.qml:96-108` 面板 + `SoftShadow`(blur 20)；两个实例 `x: parent.width - width + 2`、`y: -height - 8` |
| 面板尺寸 | `styles/app.css:3387-3395` → `right:0`、min-width 248、max-width 360、`width: max-content`、max-height 340 | `panelWidth: Math.max(248, Math.min(360, measure.implicitWidth + 38 + 10))`；实测 248 |
| 分组标题 | `redesign/model-panel.css:111-125` → `padding: 9px 8px 3px`（首组 4px）、11.5px、`--fg-subtle` | 26 高行盒 + `x:8 / y:6`、`font.pixelSize: 12`、`Theme.fgSubtle`（字号取舍见下） |
| 模型行 | `styles/app.css:3418-3438` → gap 8、`padding: 7px 8px`、radius `--radius-sm`=6、13px、`--fg`；`.is-active` accent + 600 | 27 高行、`radius: Theme.radiusSm`、13px、选中 `Theme.accent` + `weight 600` |
| 勾选位 | `redesign/model-panel.css:127-131` 固定 14px 占位；`styles/app.css:3452-3455` 14px `--accent` | 右侧 `rightMargin: 8` 的 14×14 位 + `IconData.check` |
| 空态 | `styles/app.css:3456-3461` → `padding: 10px 8px`、12px、`--fg-subtle`、居中 | `pickerEmpty`（40 高、12px、`Theme.fgSubtle`、`AlignHCenter`） |
| 思考等级行 | `redesign/model-panel.css:133-143` → 名字 13px + 说明 11.5px `--fg-subtle`、`gap:1px` | 44 高行、`Column(x:8, spacing:1)`，名字 13px、说明 12px |
| 贴片展开态 | `styles/app.css:2874-2877` `.chip.is-open{background:var(--bg-active);color:var(--fg)}`；`:2902-2904` 箭头 `rotate(180deg)` | `color: open ? Theme.bgActive : "transparent"`、文字/图标 `open ? Theme.fg : Theme.fgMuted`、`rotation: open ? 180 : 0` |

实测几何（`.venv/bin/python -I out/latest-parity/probes/c6_panel_subgeom.py` → `logs/d-c6-subgeom-final.log`；相对坐标以面板外框左上角为原点。早期 `logs/c6-d1-subgeom-final.log` 的 QML `left=776` 是 B 轮 +2 前的旧值，已过时）：

| 量 | deva | QML | 差 |
|---|---|---|---|
| 面板外框 | x847..1094（248 宽）、y688..752（65 高） | x847..1094（248 宽）、y688..752（65 高） | 完全一致 |
| 圆角 / 边框 / 底色 | 12 / `(230,230,234)` / `(255,255,255)` | 12 / `(230,230,234)` / `(255,255,255)` | 一致 |
| 分组标题墨迹 | rel x14..68、y12..24，212 px | rel x14..70、y12..24，220 px | 行带一致，宽 +2 |
| 模型行文字墨迹 | rel x15..161、y39..51，747 px | rel x14..160、y39..51，752 px | 行带一致，x −1 |
| ✓ 墨迹 | rel x222..232、y41..48，27 px | rel x222..232、y41..48，27 px | 逐像素同位 |

模型行文字色与字重取自同一张图：选中行文字为 `Theme.accent`（`#5b5bd6` → 实测 `(91,91,214)`）、`weight 600`，
与 deva 的 `.is-active` 相同（`logs/c6-d1-verify-final.log`）。

**分组标题字号：11.5px 在 Qt 侧取不到，实际落在 12px**

原版 CSS 是 `font-size: 11.5px`。Qt 的 `font.pixelSize` 只收整数，`pointSize` 也会被取整到整像素：

```
$ .venv/bin/python -I out/latest-parity/probes/c6_ghead_font.py \
      out/latest-parity/ab-font/ghead-8.625pt-y5.png:776 \
      out/latest-parity/ab-font/ghead-8.75pt-y5.png:776
deva                         (14, 68, 12, 24, 212)   # x14..68（宽 55）、y12..24（13 行）、212 墨迹像素
qml after(current)           (14, 70, 12, 24, 220)   # ← 落地值：12px + y6（宽 57，+2）
ghead-8.625pt-y5.png         (13, 64, 12, 21, 198)   # 8.625pt → 11px：只有 10 行、宽 52
ghead-8.75pt-y5.png          (13, 69, 11, 23, 220)   # 8.75pt → 12px，但整体上移 1px
```

两个 A/B 变体的重拍图留在 `out/latest-parity/ab-font/`（md5 `ccfd026d…` / `f0216bc4…`），
它们不是交付图，只为复现这一组对照。

即：11.5px 无法表达，`8.5 / 8.625pt` 都落 11px（墨迹行数与宽度都明显偏小），`8.75pt / 12px` 落 12px。
选 12px 并把 `y` 从 5 调到 6，得到与 deva **逐行同带**（y12..24）的结果；宽度多 2px 是 Qt 字形度量的残余差，
不是取值错误。这一条是本轮唯一「不能逐值复刻」的项，原因写在代码注释与本节。

**D2：弹层态输入卡片四边 `#5b5bd6`**

修复点是 `Main.qml` 输入卡片的 `border.color`：原来只有 `inputField.activeFocus || window.composerFocused`，
而弹层打开时焦点在贴片而不是 TextArea，所以四边仍是 `--border-strong`。补上 `|| window.modelPickerOpen` 后，
`border.color` 与 deva 的 `.cf-box:focus-within` 同值。四边实测（`logs/c6-d2-final.log`、`logs/d2-four-edges-sampling.log`）：

| 图 | top (700,658) | bottom (700,803) | left (428,720) | right (1207,720) |
|---|---|---|---|---|
| deva model-picker | (91,91,214) | (91,91,214) | (91,91,214) | (91,91,214) |
| QML 修复前（HEAD 同代码重拍） | (230,230,234) | (213,213,219) | (213,213,219) | (213,213,219) |
| QML 修复后 | (91,91,214) | (91,91,214) | (91,91,214) | (91,91,214) |
| 对照：chat 页（菜单未打开）deva / QML | (213,213,219) / (213,213,219) | 同 | 同 | 同 |

整行扫描（y=658 从 x450 到 x1150）修复后全为 `(91,91,214)`，与 deva 相同；chat 页全为 `(213,213,219)`，
说明聚焦描边只在弹层打开时出现，没有污染其它页面。真实鼠标探针在 model 与 thinking 两种模式下各测一次，四边同为 `(91,91,214)`
（`logs/c6-model-picker-probe.log`）。

**D3：bbox(600,470,1119,799) 纯白像素数与归因**

| 图 | 纯白 (255,255,255) 像素 | 说明 |
|---|---:|---|
| deva | 144791 | 参考 |
| QML 修复前（归档 `8fd3c8a` 图，§5 基线） | 161546 | 旧值 |
| QML 修复前（HEAD 同代码重拍） | 159666 | 归档图已过期，同代码重拍差 27876 px |
| QML 修复后 | **141844** | 比 deva 少 2947（−2.0%） |

**必须先说清的一件事**：`out/latest-parity/qml/model-picker.png` 在 §5 基线（`8fd3c8a`）里那张是**过期图**。
用 HEAD 的同一份代码、同一份夹具重拍，md5 是 `5db7a50f…` 而不是归档的 `c2670aa5…`，两者差 27876 px（max=43），
差异只落在 y638..819 的一条浅灰带：归档图在那里是纯白 `(255,255,255)`，重拍图是 `SoftShadow` 的 `(236..247)`
（`logs/d1-shadow-staleness.log`，逐点对照见下）。所以本节所有「before」都用**同代码重拍**的口径，
不用归档数字：

```
像素 (520, y) 输入卡片下方投影带：
  y806 chat=(236,236,236) archived-mp=(255,255,255) fresh-before=(236,236,236) after=(236,236,236)
  y812 chat=(242,242,242) archived-mp=(255,255,255) fresh-before=(242,242,242) after=(242,242,242)
```

也因此 `page_diff18.py` 的 model-picker 行从归档的 `149105 / 14.21%` 变成同代码 `141550 / 13.49%`，
B 轮当轮修复后 `137282 / 13.08%`（历史阶段值；D 轮最终 117437 / 11.19%，见本节末尾），三者的 md5 分别为 `c2670aa5…` / `5db7a50f…` / `7af296ea…`。

**修正后仍差 2947 px 的归因**：把 model-picker 页的纯白计数逐带与 chat 页（同一 bbox、菜单关闭）相减，
剩下的才是 picker 独有的量（`logs/c6-d3-attribution-final.log`）：

| 子区间 | deva | QML | 差 | 归因 |
|---|---:|---:|---:|---|
| y470-619 正文上半 | 77367 | 76797 | +570 | chat 页同差 +570 → picker 专属 0 |
| y620-650 正文末段 | 11440 | 9360 | +2080 | chat 页同差 +2080 → picker 专属 0 |
| y651-687 面板上方投影 | 11066 | 11024 | +42 | picker 专属 +42（Canvas 阴影尾部比 CSS `0 6px 24px` 略窄） |
| y688-752 面板本体 | 29245 | 29223 | +22 | picker 专属 +22（标题宽 +2px 与圆角抗锯齿） |
| y753-799 输入区贴片行 | 15673 | 15440 | +233 | chat 页 −19 → picker 专属 +252 |
| **合计** | **144791** | **141844** | **+2947** | picker 专属 **+316**，其余 2631 是 chat 页就有的 A/B 类正文差 |

所以 D3 的结论是：**picker 自身引入的白像素差只剩 316 px**（其中 252 在贴片行、42 在阴影尾、22 在面板本体），
而 2631 px 来自 §5.4 的 A/B 类 chat 正文缺口（`E1`–`E5`、`B1`–`B3`），不在本轮范围。
贴片行的 252 px 是 chip 锚点横向偏移造成的（见本节末尾「未闭环」）。

**回归核查**

| 项 | 结果 | 日志 |
|---|---|---|
| 单页差异（`page_diff18.py`，只取 model-picker 行） | D 轮最终 deva `946b07de…` / QML `66be1f24…`，**117437 px / 11.19%，max=248**（B 轮阶段值 137282 / 13.08% 仅作历史对照） | `logs/d-page-diff18-final.log` |
| chat / dark-chat 最终回归 | chat `00baf469…` / dark-chat `8cacd0f7…`；D 轮 113088 / 10.77% 与 111631 / 10.64%，不是 B 轮的 `dc133011…` / `3aa7be54…` | `logs/d-page-diff18-final.log` |
| 真实鼠标探针（model + thinking 两模式） | 打开 → 内容正确 → 四边聚焦 → 点行生效并收起 | `logs/c6-model-picker-probe.log`（`.err` 0 字节） |
| `app/tests/test_qml_model_picker.py` | **3 passed**，rc=0 | `logs/pytest-model-picker-final.log` |
| 受影响测试（picker + chat-files ×2 + shell + packaging + settings-models） | **169 passed**，rc=0 | `logs/pytest-affected-final.log` |
| `app/tests/test_qml_context_menu.py`（单独跑） | **2 passed**，rc=0 | `logs/pytest-ctx-menu-final.log` |
| 全量（排除两个交互式 QML 模块） | **1323 passed, 5 skipped**，rc=0 | `logs/pytest-full-ignore-interactive-final.log` |
| 全量（不排除） | **rc=139 段错误**，位置 `test_qml_context_menu.py:162`；HEAD 工作树 `/tmp/base-head` 同样复现 | `logs/pytest-full-final.log`、`logs/pytest-segv-head-full.log` |

**D 轮最终全量重拍**：`model-picker 117437 px / 11.19% max=248`（QML md5 `66be1f24…`），
`chat 113088 / 10.77%`、`dark-chat 111631 / 10.64%`；上面 137282 / 13.08% 是 B 轮阶段值，保留为历史。
差异分布：`d≤2 34135（29.07%）、d≤8 14010、d>8 69292`（`logs/d-delta-histogram.log`）。

全量段错误是**既有问题、与本轮无关**：在 `/tmp/base-head`（提交 `0805d16`，不含本轮任何改动）上按同一口径跑
`pytest app/tests`，同样在 `test_qml_context_menu.py:162 _menu_items` 崩（`logs/pytest-segv-head-full.log`）；
而这两个交互式模块单独跑、或与其它 QML 模块一起跑都通过（上面的 169 / 2 passed）。
根因是同一进程里先后创建 `QGuiApplication` 与 `QApplication` 两套 Qt 应用对象，`test_qml_chat_files.py` 先跑时触发。
本轮没有改这两个模块的夹具，所以不在此处修，记录在案。

**差异量级（D 轮最终）**：model-picker 差异像素 117437，其中 d≤2 共 34135（29.07%）、d≤8 共 14010、d>8 共 69292
（`logs/d-delta-histogram.log`）。d≤2 占比从 10.08% 升到 29.07%，与 chat 的 27.42%、dark-chat 的 25.78% 同一水平，
说明面板区域的大跳变已经消掉，剩余大头是与 chat 共用的正文缺口。

**面板横向位置（B 轮已闭环）**：D 轮 `model-picker.png` 外框实测 x847..1094（248 宽）、y688..752（65 高），
deva 同为 x847..1094、y688..752，**逐像素同边**。贴片行 252 白像素差仍来自 `modelChip` 自身的 x
（QML 852 vs deva 923，§5.4 G1），不是面板偏移。

**未闭环（明确列出，本轮未修）**

1. 分组标题宽度 +2px：11.5px 无法在 Qt 表达，取 12px 后的字形度量残差，已在上文说明。
2. 阴影尾部 +42 px：Canvas 阴影与 CSS `box-shadow` 的衰落曲线不同，`blur` 已从 24 收到 20，仍未逐像素相同。

**提交记录**：`127e44f` `fix(qml): model-picker 双模式弹层 + 弹层态聚焦描边 (§4.9)`
（2026-11-23，父提交 `0805d16`，未 push，只在本地 `develop`）。
`git show --name-status --format='' 127e44f` 实测 47 个路径，与本轮改动逐条对上：

```
M  app/src/qml/Main.qml                     ← D2 聚焦分支 + 贴片 open 态 + 两个实例
M  app/src/qml/ModelPicker.qml              ← D1 双模式弹层（逐值注释来源 file:line）
A  app/tests/test_qml_model_picker.py       ← 3 条真实鼠标路径 + 渲染像素断言
M  out/latest-parity/REPORT.md              ← §4.9 新增 + §5.2/§5.3/§5.4/§5.5 重算
M  out/latest-parity/qml/model-picker.png   ← 交付图 md5 7af296ea…
A  out/latest-parity/probes/c6_*.py         ← 9 个量距/归因探针
A  out/latest-parity/logs/c6-*/c7-*/d1-*/d2-*/pytest-*  ← 本节引用的全部实测日志
A  out/latest-parity/ab-font/*.png          ← 分组标题字号 A/B 两张（非交付图）
```

本节所有数字都出自该提交里的日志，可用
`.venv/bin/python -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml`
复算（`logs/c7-page-diff18-final.log`，rc=0）；重拍用
`bash scripts/parity/qml_page_shot.sh model-picker out/latest-parity/qml/model-picker.png /tmp/fx-qml-home config.json`
（`logs/c7-mp-shoot.out` / `.err` 0 字节，产物 md5 与交付图一致 `7af296ea76c95baccbdd4c837e0f3159`）。


### 4.10 标题栏窗口控件：最小化 / 最大化 / 关闭（A1 / F1 / F2）

**实现**：`app/src/qml/Main.qml` 新增内联 `WindowControlButton`（32×40）与右上角 `windowControls`
（96×40，x=1184，z=1000，高于设置弹框最高 z=60）。三按钮点击分别执行
`window.showMinimized()`、`window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized()`、
`window.close()`。

**数值与来源（deva 只读，未改动）**：

- `deva/apps/desktop/src/main/index.ts:87-90`：`OVERLAY_BG` light `#ffffff` / dark `#1e1e20`；
- `deva/apps/desktop/src/main/index.ts:109-116`：`titleBarStyle: 'hidden'` + `titleBarOverlay`，height 40；
- `deva/node_modules/electron/electron.d.ts:21424-21439`：`symbolColor` 仅 win32，Linux 由系统对比色决定；
- deva 原版 1280×820 实拍 `out/latest-parity/deva/chat-deva.png` 逐像素：实色块 96×40 @ x1184；
  三个 32×40 命中区 x=1184/1216/1248；最小化 10×2 @ (1195,23)；最大化 10×10 框 @ (1227,15)；
  关闭 10×10 X @ (1259,15)、线宽 2.1；图标 `#5F6368` light / `#E8EAED` dark；hover 叠 18/255 黑。

**测试（真实 QML 窗口 + `QTest` 鼠标事件，`AI_UPPER_HOME` 为隔离临时目录）**：

```
AI_UPPER_HOME=/tmp/ai-upper-wctl-test .venv/bin/python -m pytest app/tests/test_qml_window_controls.py -q
..                                                                       [100%]
2 passed in 6.49s
rc=0
```

覆盖并实测通过：96×40 位置/尺寸、三个 32×40 命中区、三枚字形暗像素 bbox
`(1195,23,1204,24,20)` / `(1227,15,1236,24,64)` / `(1259,15,1268,24,48)`、hover 底色 `(237,237,237)`；
点最小化后 `visibility=Minimized`、最大化一次 `Maximized` 再点回 `Windowed`、关闭后 `isVisible=False`。
日志 `out/latest-parity/logs/wctl-pytest.log`。

**重拍与百分比（只重拍 chat 页，原版基线沿用 `out/latest-parity/deva/`）**：

```
bash scripts/parity/qml_page_shot.sh chat out/latest-parity/qml/chat.png /tmp/fx-qml-home
python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml
```

- `chat`：**129909 / 12.38% → 129807 / 12.37%**（−102 px）。
  日志 `out/latest-parity/logs/wctl-page-diff-before.log` / `wctl-page-diff-after.log`；
  重拍输出 `wctl-shot-chat.log`（rc=0，stderr 0 字节）。
- 右上 96×40 与 deva 同区：58 px 抗锯齿差（max=9）；底色 `(255,255,255)` / `(30,30,32)` 与三枚字形位置逐值一致。
- F1 `x1160..1279 y0..40`：deva `白3680 / 灰960 / 深100`；QML 修复后 `白3680 / 灰936 / 深100`（24 px 为 close X 抗锯齿）。
- F2 纯白面板 bbox：QML `(736,0,1279,391)` == deva `(736,0,1279,391)`。
- **D 轮最终全量重拍**：`chat 113088 / 10.77%`（`logs/d-page-diff18-final.log`）；上面 129807 / 12.37% 是 A1 修复当时的历史值，不代表最终图。
## 5. 18 页全量重拍 + 四条硬判据 + 逐页缺口清单
### 5.0 页面清单只读核对

`app/src/qml_shell.py::PAGE_NAMES` 共 **20** 项；`scripts/parity/qml_pages_all.sh` 的 `shot` 行共 **18** 项。
剔除截图专用页 `settings-models-provider`、`settings-models-advanced` 后，两侧集合完全相等（`set_equal=True`），
两个专用页均存在于 `PAGE_NAMES`、均不在 `qml_pages_all.sh` 中；顺序不同，但页面集合一致。
即：18 个真实页面 + 2 个仅用于详情截图的页面，未把截图专用页计入 18 页全量重拍。

### 5.1 重拍命令与结果（D 轮全量）

```
$ bash scripts/parity/qml_pages_all.sh out/latest-parity/qml /tmp/fx-qml-home > /tmp/d-shots3.log 2>&1; echo rc=$?
rc=0
$ grep -c '^ok ' /tmp/d-shots3.log
18
$ find out/latest-parity/qml -maxdepth 1 -name '*.err' -size +0c | wc -l
0
$ python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml > out/latest-parity/logs/d-page-diff18-final.log 2>&1; echo rc=$?
rc=0
```

18 页全部 `1280x820`，每页一行 `ok <page> 1280x820 ... rc=0`；18 个 `.err` 均为 0 字节。
`AI_UPPER_HOME=/tmp/fx-qml-home`，`/home/agent/shared_workspace/deva` 只读未改。

### 5.2 18 页逐页差异整表（D 轮最终图）

D 轮先用 `bash scripts/parity/qml_pages_all.sh out/latest-parity/qml /tmp/fx-qml-home` 全量重拍 18 页，
18 条输出均为 `ok <page> 1280x820 ... rc=0`、18 份 `.err` 均为 0 字节（`/tmp/d-shots3.log`）。
本轮另修了 `SoftShadow` 在 `target.visible=false` 时仍绘制幻影的问题，直接以最终图重算；差异定义不变
（三通道任一非零即计 1 个差异像素；% = 差异像素 / 1,049,600）。

```
$ python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/latest-parity/qml
rc=0
chat                   ac72cd597ae44377b608777cbd5e2e81 00baf46965255434d276905e4e82c978  158583  165417  113088  10.77% max=248 same=False
empty                  a616eabe08d8c107709b89d699604d13 e56462d7a538be35dae1b166403f4784   40733   40046   13231   1.26% max=248 same=False
first-run              0e2b5786d552a73525ded72469f224ea e56462d7a538be35dae1b166403f4784   40733   40046   13231   1.26% max=248 same=False
search-open            3a5f80988f34cbcccf98281d7697498e 572f4907d5343c138c3c5ff4fe8b20b9  158824  165755  113117  10.78% max=248 same=False
search-results         1d1ba8121289fc7b91cdd95938a3ecad 6526581e572c4a5e758d2294b6d761fb  130449  137673  107403  10.23% max=248 same=False
search-none            49503995317b15b2d1806c1c0a99e5b3 2fc3a40645280610f8d850b82247d0ae   64532   70950   85175   8.11% max=224 same=False
ctx-menu               64c8c33a5c5c5e905288cca4fab37285 5bb170555ba6ab13d6c2d07afc7cc75c  158033  165135  122224  11.64% max=248 same=False
delete-confirm         964c32d139d41a71c3eb2b9026e24f9b 1f0c4130dd9f7fde0b6a4200ff9d5e68  162718  166370  382652  36.46% max=224 same=False
model-picker           946b07def583e696822df943b6935f04 66be1f241f3e704762a108c03c48cb1f  164258  171208  117437  11.19% max=248 same=False
hover-thread           16917898b7b5fb7b95a515bee87001d1 03a15c4a7bb2841b183aa7ffd8128228  158169  165110  113042  10.77% max=248 same=False
focus-composer         e976e0858fd2d6741c6ffe52ad72a5b4 00b028eff7b9a1c8e49dc5109a38f82e  158745  165611  113104  10.78% max=248 same=False
long-mid               147fb156af029f6c57cfb686d6e84c0c f4e1fc4609f18265f80fa8cc6370b12b  143456  167718  142444  13.57% max=255 same=False
long-bottom            be7b7fe814eb8ebcf11369bdec650a68 a5576a855aa52a9a675be74612f1b58a  157770  164511  124452  11.86% max=248 same=False
settings-general       4d16a5c68b170e998bb4892713b8263e b95b109b156d817ae4839ec6bdcac4e1  142486  144567  315274  30.04% max=224 same=False
settings-models        7f7a6dd835823f50475db7a3c9e727c1 dc5ee213bfe4b8d7ef1641081cd09f2f  132243  136487  300497  28.63% max=216 same=False
settings-extensions    15d607e162e2ef874dd6e59a78d0dd5c 7f4d07e315e289cac2faf11b11199872  139387  143292  305797  29.13% max=216 same=False
settings-about         3fac0ec7f4820e99a1bac811de88697f 2388394c6474dfafc4b1af91797a2a65  135693  137358  302389  28.81% max=216 same=False
dark-chat              252996a52c0b1d02cfb3205ba1798c94 8cacd0f7b32423816824e3c16805b0b2  158038  165242  111631  10.64% max=230 same=False
```

整理成表：

| 页名 | 原版 md5 | QML md5（D 轮） | 差异像素 | 差异% | max 通道差 | 口径 |
|---|---|---|---:|---:|---:|---|
| chat | `ac72cd597ae44377b608777cbd5e2e81` | `00baf46965255434d276905e4e82c978` | 113088 | 10.77% | 248 | D 轮全量重拍 |
| empty | `a616eabe08d8c107709b89d699604d13` | `e56462d7a538be35dae1b166403f4784` | 13231 | 1.26% | 248 | D 轮全量重拍 |
| first-run | `0e2b5786d552a73525ded72469f224ea` | `e56462d7a538be35dae1b166403f4784` | 13231 | 1.26% | 248 | D 轮全量重拍 |
| search-open | `3a5f80988f34cbcccf98281d7697498e` | `572f4907d5343c138c3c5ff4fe8b20b9` | 113117 | 10.78% | 248 | D 轮全量重拍 |
| search-results | `1d1ba8121289fc7b91cdd95938a3ecad` | `6526581e572c4a5e758d2294b6d761fb` | 107403 | 10.23% | 248 | D 轮全量重拍 |
| search-none | `49503995317b15b2d1806c1c0a99e5b3` | `2fc3a40645280610f8d850b82247d0ae` | 85175 | 8.11% | 224 | D 轮全量重拍 |
| ctx-menu | `64c8c33a5c5c5e905288cca4fab37285` | `5bb170555ba6ab13d6c2d07afc7cc75c` | 122224 | 11.64% | 248 | D 轮全量重拍 |
| delete-confirm | `964c32d139d41a71c3eb2b9026e24f9b` | `1f0c4130dd9f7fde0b6a4200ff9d5e68` | 382652 | 36.46% | 224 | D 轮全量重拍 |
| model-picker | `946b07def583e696822df943b6935f04` | `66be1f241f3e704762a108c03c48cb1f` | 117437 | 11.19% | 248 | D 轮全量重拍 |
| hover-thread | `16917898b7b5fb7b95a515bee87001d1` | `03a15c4a7bb2841b183aa7ffd8128228` | 113042 | 10.77% | 248 | D 轮全量重拍 |
| focus-composer | `e976e0858fd2d6741c6ffe52ad72a5b4` | `00b028eff7b9a1c8e49dc5109a38f82e` | 113104 | 10.78% | 248 | D 轮全量重拍 |
| long-mid | `147fb156af029f6c57cfb686d6e84c0c` | `f4e1fc4609f18265f80fa8cc6370b12b` | 142444 | 13.57% | 255 | D 轮全量重拍 |
| long-bottom | `be7b7fe814eb8ebcf11369bdec650a68` | `a5576a855aa52a9a675be74612f1b58a` | 124452 | 11.86% | 248 | D 轮全量重拍 |
| settings-general | `4d16a5c68b170e998bb4892713b8263e` | `b95b109b156d817ae4839ec6bdcac4e1` | 315274 | 30.04% | 224 | D 轮全量重拍 |
| settings-models | `7f7a6dd835823f50475db7a3c9e727c1` | `dc5ee213bfe4b8d7ef1641081cd09f2f` | 300497 | 28.63% | 216 | D 轮全量重拍 |
| settings-extensions | `15d607e162e2ef874dd6e59a78d0dd5c` | `7f4d07e315e289cac2faf11b11199872` | 305797 | 29.13% | 216 | D 轮全量重拍 |
| settings-about | `3fac0ec7f4820e99a1bac811de88697f` | `2388394c6474dfafc4b1af91797a2a65` | 302389 | 28.81% | 216 | D 轮全量重拍 |
| dark-chat | `252996a52c0b1d02cfb3205ba1798c94` | `8cacd0f7b32423816824e3c16805b0b2` | 111631 | 10.64% | 230 | D 轮全量重拍 |

D 轮改动前后（C 轮最终 `d-diff2.txt` → D 轮最终，同一 `page_diff18.py` 口径）：

| 页 | C 轮 差异像素 / % | D 轮 差异像素 / % | 变化 |
|---|---:|---:|---:|
| empty | 49703 / 4.74% | 13231 / 1.26% | -36472 px / -3.48 pp |
| first-run | 49703 / 4.74% | 13231 / 1.26% | -36472 px / -3.48 pp |
| 其余 16 页 | — | 与 C 轮一致 | 未改代码，未变化 |

口径说明：以上 18 行全部来自 D 轮最终全量重拍，不再有「沿用旧值」行；18 页 `same=` 全部为 False，
无任何一页与参考图逐像素相同。`empty` / `first-run` 的原版图 md5 不同但解码后像素完全相同；QML 侧
两页 md5 都是 `e56462d7…`，两态渲染一致。

### 5.3 四条硬判据（D 轮最终复检）

探针脚本在 `out/latest-parity/probes/`；本轮日志全部重新生成，文件名统一以 `d-criterion*` / `d-delta-*` 开头。

#### 判据一：long-mid / long-bottom / chat 三页必须互不相同 —— 成立

```
$ python3 -I out/latest-parity/probes/c1_three_pages.py
rc=0
```

```
chat         md5=00baf46965255434d276905e4e82c978  1280x820
long-mid     md5=f4e1fc4609f18265f80fa8cc6370b12b  1280x820
long-bottom  md5=a5576a855aa52a9a675be74612f1b58a  1280x820

=== 判据1：三页 md5 两两不同 + 逐像素差 ===
  chat         vs long-mid     diffpx=84665  pct=8.0664%  max=241
  chat         vs long-bottom  diffpx=29721  pct=2.8317%  max=216
  long-mid     vs long-bottom  diffpx=63876  pct=6.0857%  max=241
```

三页 md5 两两不同，差异像素 84665 / 29721 / 63876 均远大于 0；侧栏可见会话标题文字带也保留区分
（`long-mid` 首带 `(57,65)`，`chat` / `long-bottom` 首带 `(64,101)`）。**判据一成立。**
日志：`out/latest-parity/logs/d-criterion1.log`。

#### 判据二：search-results 只显示命中的 10 行 —— 成立

```
$ python3 -I out/latest-parity/probes/c2_c3_search_and_focus.py
rc=0
```

```
=== 判据2：search-results 命中行数（头像列 x70..108 的紫色头像簇）===
  qml 簇数=10  tops=[66, 120, 174, 228, 282, 336, 390, 444, 498, 552]
     每簇像素数=[349, 349, 349, 349, 349, 349, 349, 349, 349, 349]
     簇高=[32, 32, 32, 32, 32, 32, 32, 32, 32, 32]
  deva 簇数=10  tops=[66, 120, 174, 228, 282, 336, 390, 444, 498, 552]
     每簇像素数=[346, 346, 346, 347, 346, 346, 346, 346, 346, 346]
     簇高=[32, 32, 32, 32, 32, 32, 32, 32, 32, 32]
```

QML 与 deva 都是 10 簇、簇顶 y 完全一致、簇高 32；QML 每簇 349 px 一致。另用 fixture 文件独立核对
（`c4_stub_scan.py` 第 2 节）：120 个会话文件中标题含 `00` 的恰好 10 个。**判据二成立。**
日志：`out/latest-parity/logs/d-criterion2-3.log`。

#### 判据三：focus-composer 输入区有可见焦点边框 —— 成立

采样点：输入卡片四边中点 `(800,658)` / `(800,803)` / `(428,740)` / `(1207,740)`。

```
=== 判据3：focus-composer 输入卡片四边取色 ===
  qml focus        上(800,658)=(91,91,214)  下(800,803)=(91,91,214)  左(428,740)=(91,91,214)  右(1207,740)=(91,91,214)
  qml chat(未聚焦)    上(800,658)=(213,213,219)  下(800,803)=(213,213,219)  左(428,740)=(213,213,219)  右(1207,740)=(213,213,219)
  deva focus       上(800,658)=(91,91,214)  下(800,803)=(91,91,214)  左(428,740)=(91,91,214)  右(1207,740)=(91,91,214)
  deva chat(未聚焦)   上(800,658)=(213,213,219)  下(800,803)=(213,213,219)  左(428,740)=(213,213,219)  右(1207,740)=(213,213,219)

=== 判据3 补充：沿输入卡片上边横扫，找连续的高饱和边框像素段 ===
  qml focus   y=658 紫蓝像素数=764 x=436..1199 首色=(148, 148, 200)
  qml chat    y=658 紫蓝像素数=0
  deva focus  y=658 紫蓝像素数=764 x=436..1199 首色=(194, 194, 236)
```

四边全部 `(91,91,214)`（`#5b5bd6`），未聚焦 chat 页四边全部 `(213,213,219)`（`#d5d5db`）；
上边 y=658 有 764 个连续紫蓝像素，与 deva 的 764 个一致。**判据三成立。**

#### 判据四：删除确认框 Delete / Cancel 必须真的生效 —— 成立

```
$ .venv/bin/python -I out/latest-parity/probes/c5_ctx_confirm.py
rc=0
```

关键输出（真实 `QTest.mouseClick`，坐标由 `mapToScene(中心)` 现算）：

```
  labels        = ['New chat', 'Rename', 'Select', 'Archive', 'Delete']
  labels==deva  = True
  item4 Delete    红色像素=227    深色文字像素=0
    deva Delete   红色像素=230    深色文字像素=0
  起点：sessions=120 active=parity-000 parity-000 文件存在=True
  [a] 点取消中心后：confirm visible=False confirmOpen=False sessions=120 active=parity-000 文件存在=True
  [b] 点确认中心后：confirm visible=False confirmOpen=False sessions=119 active=parity-001 parity-000 文件存在=False
  [c] 点遮罩空白 (100,700) 后：confirm visible=False confirmOpen=False sessions=119 active=parity-001
=== 结果摘要 ===
  判据1（5 项 + Delete 危险色）= True
  判据2a（取消关闭不删）= True   [120 -> 120]
  判据2b（确认关闭并删）= True   [120 -> 119]
  判据2c（遮罩关闭不删）= True   [119 -> 119]
  ALL = True
```

菜单 5 项顺序与 deva 一致，Delete 为危险色 `#e5484d`；取消不删、确认真删并把 active 回退到 `parity-001`、
遮罩关闭不删。**判据四成立。** 日志：`out/latest-parity/logs/d-criterion4.log`。

**四条硬判据汇总：四条全部成立**（判据一 3 页两两不同；判据二 10 行；判据三 4×`#5b5bd6`；判据四三处点击均生效）。

#### 差异量级分布（D 轮最终图）

命令：`.venv/bin/python -I out/latest-parity/probes/c6_delta_histogram.py`，rc=0，日志
`out/latest-parity/logs/d-delta-histogram.log`。d 为单像素最大通道差。

| 页 | 差异像素 | d≤2 | d≤8 | d>8 | d≤2 占比 |
|---|---:|---:|---:|---:|---:|
| chat | 113088 | 31006 | 13843 | 68239 | 27.42% |
| empty | 13231 | 2175 | 1858 | 9198 | 16.44% |
| search-results | 107403 | 30109 | 12612 | 64682 | 28.03% |
| ctx-menu | 122224 | 42234 | 13897 | 66093 | 34.55% |
| delete-confirm | 382652 | 301507 | 20300 | 60845 | 78.79% |
| model-picker | 117437 | 34135 | 14010 | 69292 | 29.07% |
| hover-thread | 113042 | 30956 | 13843 | 68243 | 27.38% |
| long-mid | 142444 | 30702 | 15148 | 96594 | 21.55% |
| settings-general | 315274 | 255093 | 18834 | 41347 | 80.91% |
| settings-models | 300497 | 250119 | 13167 | 37211 | 83.24% |
| settings-about | 302389 | 251539 | 13121 | 37729 | 83.18% |
| dark-chat | 111631 | 28783 | 14489 | 68359 | 25.78% |

读法：settings-* 与 delete-confirm 有 78.79%–83.24% 的差异只在 1–2 个灰阶内，主要是遮罩/背景合成取整；
chat / dark-chat / hover-thread 的 d≤2 占比在 25.78%–27.42%，剩下的大头是仍未闭环的正文 Markdown（E1–E5）
与侧栏（B1–B3）结构缺口，不是本轮 C/D 改坏的。

### 5.4 逐组件缺口清单（覆盖 18 页，全部来自本轮实测日志）

> **状态说明（D 轮最终）**：本节保留最初的缺口登记，并在行内标注后续修复结论。**C1/C4、D1–D3、E6、
> A1–A4、F1/F2/F4/F5、G4/G5 已闭环**；仍开放的是 A5、B1–B3、C2/C3、E1–E5、F3、G1、H1。§5.2 / §5.3 / §5.5
> 的数字全部来自 D 轮最终全量重拍（`out/latest-parity/logs/d-page-diff18-final.log`）。

下表每行都给「实测值 + 证据文件」，没有「符合预期」这类空话。

**A. 全局性缺口（影响全部 18 页）**

| # | 缺口 | 实测证据 |
|---|---|---|
| A1 | ~~QML 无窗口控制按钮（− □ ×）~~ **已由 §4.10 修复** | deva 每页 `x1140..1270 y0..40` 有 132 个暗像素，bbox=(1195,15,1268,24)，三枚图标 x 组 `[(1195,1204),(1227,1236),(1259,1268)]`；QML 修复后 `x1184..1279 y0..40` 为实色块 `#ffffff`（深色 `#1e1e20`），三枚图标暗像素 132、bbox=(1195,15,1268,24)、x 组与 deva 完全相同，整块仅 58 px 抗锯齿差（max=9）（`out/latest-parity/qml/chat.png`、§4.10） |
| A2 | ~~QML 无侧栏列表滚动条~~ **已由 §5.6 修复** | 修复前 QML 12 页为 0；当前 D 轮 `chat` / `long-mid` 在 x349–352 均有 `(202,202,203)` 340 px（`DevaScrollBar` 挂到 `sessionList`，`Main.qml:582`），deva 同色滑块存在（`out/latest-parity/qml/chat.png`） |
| A3 | ~~QML 无正文滚动条~~ **已由 §5.6 修复** | 修复前 QML 正文右缘为空；当前 D 轮 `chat` / `long-mid` 在 x1274–1277 均有 `(209,209,209)` 1668 px（`bodyScroll` 的 `body-scrollbar`，`Main.qml:991`），deva 同色滚动条存在（`out/latest-parity/qml/chat.png`） |
| A4 | ~~源码层即无滚动条实现~~ **已由 §5.6 修复** | `grep -rn 'ScrollBar\|ScrollView' app/src/qml/` 现命中 `Main.qml:210/212/216/582/991`，内联 `DevaScrollBar` 两条均已接线 |
| A5 | 模态遮罩底色比 deva 暗 1 个灰阶 | QML 侧栏 `(143,143,144)` vs deva `(144,144,144)`；QML 左轨 `(139,139,140)` vs deva `(140,140,141)`（`probe-mask.log` §1/§4） |

**B. 侧栏 / 会话列表**

| # | 缺口 | 实测证据 |
|---|---|---|
| B1 | 悬停高亮打在错误的行上 | QML 把**整个悬停行**填成 `(236,236,237)`：hover-thread 页 bbox=(64,110,339,801)、12573 px；deva 的悬停带在**列表最底部一行**：chat 页 bbox=(64,561,338,711)、12207 px，long-mid 页 y670–711；deva 在 hover-thread 页只有 42 px 该底色（`probe-hover2.log` §2/§3/§4、`final-probe.log` §A） |
| B2 | 悬停时列表底部没有悬停带 | `gap-probe4.log` chat 页：QML `(236,236,237)` n=56、bbox=(83,122,227,693)（几乎只有圆形头像边缘），deva n=11169、bbox=(64,117,338,699)——deva 的整条底部行被填色 |
| B3 | 侧栏选中态纵向范围偏长 | QML 选中紫底 bbox=(64,56,339,715)、n=12542；deva bbox=(42,48,338,628)、n=12334（`probe-hover.log` §4） |
| B4 | 左侧图标轨基本一致 | QML 簇 `[(22,55),(81,98),(125,141),(170,186),(736,751),(779,796)]` vs deva `[(19,55),(81,98),(126,141),(170,185),(735,752),(779,796)]`，最大偏差 3 px（`probe-rail.log` §1）——非缺口，记录以免误判 |

**C. 右键菜单（ctx-menu）**

| # | 缺口 | 实测证据 |
|---|---|---|
| C1 | ~~菜单项数量不对~~ **已由 §4.8 修复** | 修复前：QML 4 项（文字带 y101–110 / 129–140 / 157–168 / 185–194，面板 y89–210）；deva 5 项（y105–114 / 134–145 / 163–172 / 192–203 / 222–230 红色项）。**当前实测 5 项**：`labels = ['New chat', 'Rename', 'Select', 'Archive', 'Delete']`、`labels==deva = True`，其中 Delete 项红色像素 227（deva 230）、深色文字像素 0，其余四项相反（`logs/c5-ctx-confirm.log`，探针 `probes/c5_ctx_confirm.py`） |
| C2 | 面板左缘偏右 5 px | QML 白色菜单框 x 起点 166，deva 161（`probe-final2.log` §6、`gap-probe.log` 缺口D） |
| C3 | 面板高度差 35 px | QML y89–210（121 px），deva y91–245（154 px）（`gap-probe.log` 缺口D） |
| C4 | ~~删除确认框没有交互：Delete / Cancel 都点不动~~ **已由 §4.8 修复** | 修复前：`Main.qml` 的 `confirmLayer` 仅由 `window.confirmOpen` 控制，按钮只是 `Text` / `Rectangle`，无 `MouseArea`/`TapHandler`；真实 `QTest.mouseClick`：点 Delete 后 `confirm=True sessions=120`。**当前实测三处点击均生效**（坐标由 `mapToScene(中心)` 现算）：[a] 取消 → `visible=False sessions=120 文件存在=True`；[b] 确认 → `visible=False sessions=119 active=parity-001 parity-000 文件存在=False`；[c] 遮罩 `(100,700)` → `visible=False sessions=119`（`logs/c5-ctx-confirm.log`） |

**D. 模型选择弹层（model-picker）**

| # | 缺口 | 实测证据 |
|---|---|---|
| D1 | ~~弹层内容完全不对~~ **已由 §4.9 修复** | 修复前：QML 渲染的是 THINKING LEVEL 面板（Default / Low / High / Max），deva 渲染的是模型列表（表头 `Anthropic` + 一行 `deepseek-v4.1-flash` 带 ✓）。**当前实测**：真实 `QTest.mouseClick` 点模型贴片后 `modelList.visible=True`、分组标题 `Anthropic`、一行 `deepseek-v4.1-flash`、✓ 墨迹 rel x222..232 与 deva 逐像素同位；点思考贴片则反过来（`logs/c6-model-picker-probe.log`、`logs/c6-d1-subgeom-final.log`） |
| D2 | ~~弹层态缺少输入框聚焦描边~~ **已由 §4.9 修复** | 修复前：QML 上边 `(230,230,234)`、其余三边 `(213,213,219)`；deva 四边全为 `(91,91,214)`。**当前实测**：model 与 thinking 两种模式四边均 `(91,91,214)`，chat 页仍为 `(213,213,219)`（`logs/c6-d2-final.log`、`logs/d2-four-edges-sampling.log`） |
| D3 | ~~面板白底像素量差 16.8k~~ **已由 §4.9 修复（残差已归因）** | bbox(600,470,1119,799) 纯白：deva 144791；QML 修复后 141844（−2947）。逐带与 chat 相减后 picker 专属只剩 +316 px（阴影尾 +42 / 面板本体 +22 / 贴片行 +252），其余 2631 px 是 chat 页同有的 A/B 正文缺口（`logs/c6-d3-attribution-final.log`） |

**E. 正文 Markdown 渲染（chat / search-none / dark-chat）**

| # | 缺口 | 实测证据 |
|---|---|---|
| E1 | 正文可见行数少 3 行 | QML 15 个文本带，deva 18 个（`probe-body.log` 末节；`final-probe.log` §8：QML 带起点差 `[37,37,37,46,...]` vs deva `[13,41,35,35,34,41,...]`） |
| E2 | 表格渲染残缺 | QML `(244,244,244)` 表底 2781 px，bbox=(538,91,780,142)；deva 8979 px，bbox=(489,43,1054,208)。deva 有完整表头行（文件/类型/说明）与首行数据（package.json / 配置 / 依赖清单），QML 只有一小块残片（`probe-scroll.log` §4） |
| E3 | 正文滚动偏移约 13 px | QML 首页文本带 `(54,65)` 起，deva `(43,43)`+`(57,66)`；QML 末个可见带 `(584,595)`，deva `(606,619)`（`probe-body.log`、`probe-empty.log` 末节） |
| E4 | 缺 broken-image 占位 | deva 有 `示意图` 占位文本带 y602–619 与图片框 y658–699；QML 无 `示意图` 带，y658–699 只剩白底与边框（`probe-gaps2.log` §4） |
| E5 | search-none 正文也少 3 带 | QML 11 带，deva 14 带（`probe-rail.log` §3、`probe-gaps2.log` §3） |
| E6 | ~~dark-chat 输入卡片底色偏暗~~ **已由 §4.7 修复** | 修复前：QML `(30,30,32)`，deva `(42,42,46)`（`probe-scroll.log` §3）。**当前实测** region x700–1180 × y600–700：QML `(42,42,46)`×19680 与 deva `(42,42,46)`×19680 **完全相同**，剩余 `(30,30,32)` QML 17280 / deva 14400 是卡片外页面底色，不是卡片本身（`.venv/bin/python -I /tmp/c6_e6.py`，落盘 `logs/c6-e6-darkchat-card.log`） |

**F. Settings 模态**

| # | 缺口 | 实测证据 |
|---|---|---|
| F1 | ~~无右上角白色窗口控制缺口~~ **已由 §4.10 修复** | deva `x1160..1279 y0..40` = `(255,255,255)`×3680 + `(148,148,148)`×960 + `(95,99,104)`×100；QML 修复后同区 = `(255,255,255)`×3680 + `(148,148,148)`×936 + `(95,99,104)`×100（灰差 24 px 为 close X 抗锯齿）（`out/latest-parity/qml/settings-general.png`、§4.10） |
| F2 | ~~面板白底 bbox 高度不同~~ **已由 §4.10 修复** | 修复前 QML `(736,257,961,391)`，deva `(736,0,1279,391)`——deva 的白色区包含顶部窗口条，QML 没有；修复后 QML `(736,0,1279,391)` == deva（`out/latest-parity/qml/settings-general.png`、§4.10） |
| F3 | 遮罩灰阶差 1 级（同 A5） | settings 页侧栏 QML `(143,143,144)`×72483 vs deva `(144,144,144)`×63722（`probe-mask.log` §1） |
| F4 | ~~遮罩把背景对话压成纯灰~~ **已由 C 轮设置浮层修复** | 修复前正文区 QML 暗像素 6、unique_colors=27，近似纯灰。当前 D 轮同口径 region x356..1232 × y40..580（473040 px）：settings-general QML 暗像素 3321 / unique 842 vs deva 3331 / 847；settings-models 2556/775 vs 2566/814；extensions 3176/792 vs 3233/935；about 2475/845 vs 2722/1156。背景对话保留可辨认（`logs/d-settings-backdrop-content.log`） |
| F5 | ~~设置左栏三个导航图标与 deva 不一致~~ **已由 C 轮修复** | deva `SettingsPane.tsx:48-51` 为 `Cog` / `Brain` / `Puzzle` / `Info`（15px）；QML `SettingsModal.qml:126-131` 现为 `IconData.cog` / `IconData.brain` / `IconData.puzzle` / `IconData.info`，`app/tests/test_qml_settings_overlay.py` 断言四条路径全等 |

**G. 输入区**

| # | 缺口 | 实测证据 |
|---|---|---|
| G1 | 左侧图标簇整体左移约 90 px | QML 簇 `[860-990][1010][1035-1040][1110][1125-1190]`；deva `[950-1080][1100-1105][1125-1190]`（`final-probe.log` §E） |
| G2 | 右侧 chip 位置基本对齐 | 彩色簇 QML `[(1140,760),(1140,780),(1160,780),(1160,760),...]` vs deva 同坐标集合（`gap-probe2.log` 末节）——非缺口 |
| G3 | 聚焦描边存在且颜色一致 | 见 5.3 判据三，四边 `(91,91,214)` 与 deva 相同——非缺口 |
| G4 | ~~输入区缺 ContextRing~~ **已由 C 轮修复** | `Main.qml:1534-1550` 接入 `ContextRing`（`objectName: "contextRing"`，`usage: window.contextUsage`，锚在 `effortChip.left`），`Main.qml:113-115` 发布 `contextUsage`；实测开卡片 `260×53`、文案 `~16 / 1M (<0.1%)`，`app/tests/test_qml_context_ring.py` 5 passed |
| G5 | ~~effort chip 点击打开的是模型菜单~~ **已由 C 轮修复** | `Main.qml:1513` 现为 `onClicked: window.openPicker("thinking")`，模型贴片在 `Main.qml:1589` 调 `openPicker("model")`；`openPicker(mode)` 在 `Main.qml:1629-1635` 设置 `pickerMode`，两套菜单互斥（`app/tests/test_qml_model_picker.py` 含隔离断言） |

**H. empty / first-run**

| # | 缺口 | 实测证据 |
|---|---|---|
| H1 | 差异 1.26% 集中在 quick-start 文字与头像（残余） | D 轮最终 13231 px / 1.26%。QML 文字带 `(412,459)/(470,481)/(492,521)` vs deva `(408,459)/(471,484)/(492,522)`；仍是字体度量/头像光栅残差，未宣称「已对齐」（`out/latest-parity/logs/d-page-diff18-final.log`） |
| H2 | deva 的 empty 与 first-run 像素完全相同 | `probe-final2.log` §1：「deva 侧 empty/first-run 像素完全相同」；QML 侧 D 轮两页 md5 都是 `e56462d7…`，差异像素=0 |
| H3 | ~~空态底部有 780×146 的灰色幻影输入卡片~~ **已由 D 轮修复** | `SoftShadow` 在 `target.visible=false` 时仍绘制。修复：`SoftShadow.qml` 根节点 `visible: target !== null && target.visible`。`empty` / `first-run` 由 49703 px / 4.74% 降到 13231 px / 1.26%，但仍保留 1.26% 残差，不称已对齐 |

### 5.5 18 页 → 缺口映射（D 轮最终收口）

| 页 | 差异像素 / %（D 轮） | 当前剩余缺口 | 判定 |
|---|---:|---|---|
| chat | 113088 / 10.77% | A5、B1–B3、E1–E4；A1–A4/G4/G5 已闭环 | 真结构缺口（正文/侧栏） |
| empty | 13231 / 1.26% | H1（quick-start 字体度量与头像光栅） | 仅光栅残差，仍未为零 |
| first-run | 13231 / 1.26% | H1；与 empty 像素相同 | 仅光栅残差，仍未为零 |
| search-open | 113117 / 10.78% | 同 chat；搜索框打开态 | 真结构缺口 |
| search-results | 107403 / 10.23% | 同 chat；判据二 10 行已对齐 | 真结构缺口 |
| search-none | 85175 / 8.11% | E5、A5、B1–B3 | 真结构缺口 |
| ctx-menu | 122224 / 11.64% | C2/C3 小幅几何 + A/B/E；C1/C4 已闭环 | 真结构缺口 |
| delete-confirm | 382652 / 36.46% | C4 已闭环；剩余主要是 A5/F3 遮罩合成差（78.79% 只差 1–2 灰阶） | 遮罩取整为主 |
| model-picker | 117437 / 11.19% | D1–D3 已闭环；剩余为 chat 共用 A/B/E + G1 chip 锚点偏移 | 真结构缺口 |
| hover-thread | 113042 / 10.77% | B1/B2（悬停行位置错）+ A/B/E | 真结构缺口 |
| focus-composer | 113104 / 10.78% | 判据三成立；其余同 chat | 真结构缺口 |
| long-mid | 142444 / 13.57% | A5、B1–B3、E1–E4；滚动位置与基线不同 | 真结构缺口 |
| long-bottom | 124452 / 11.86% | A5、B1–B3、E1–E4；真底内容仍少 | 真结构缺口 |
| settings-general | 315274 / 30.04% | F3 遮罩灰阶为主；F1/F2/F4/F5 已闭环 | 剩余为全域 1–2 灰阶 |
| settings-models | 300497 / 28.63% | F3 遮罩灰阶为主；F1/F2/F4/F5 已闭环 | 剩余为全域 1–2 灰阶 |
| settings-extensions | 305797 / 29.13% | F3 遮罩灰阶为主；F1/F2/F4/F5 已闭环 | 剩余为全域 1–2 灰阶 |
| settings-about | 302389 / 28.81% | F3 遮罩灰阶为主；F1/F2/F4/F5 已闭环 | 剩余为全域 1–2 灰阶 |
| dark-chat | 111631 / 10.64% | E6 已闭环；A5、B1–B3、E1–E4 | 真结构缺口 |

结论（D 轮最终）：18 页全部按 `qml_pages_all.sh` 重拍并重算，不再有旧值。`empty` / `first-run` 只剩
13231 px / 1.26% 的字体度量与头像光栅残差，仍明确保留为残差；`delete-confirm` 的 C4 功能缺口已闭环，
剩 78.79% 差异只差 1–2 灰阶；`settings-*` 四页 80.91%–83.24% 的差异只差 1–2 灰阶，主因是 F3 遮罩合成取整；
其余页面仍有正文 Markdown、侧栏、菜单几何等真结构缺口。**没有任何一页被写成「已对齐」。**

**缺口统计（最终口径）**：
- 已闭环：A1（窗口控制，§4.10）、A2–A4（滚动条，§5.6）、C1/C4（菜单 5 项 + 删除确认，§4.8）、D1–D3（model-picker，§4.9）、E6（dark-chat 卡片，§4.7）、F1/F2（窗口控制与面板 bbox，§4.10）、F4/F5（设置遮罩背景与导航图标，C 轮）、G4/G5（ContextRing 与 effort chip，C 轮）、H3（SoftShadow 幻影，D 轮）。
- 仍未闭环：A5（遮罩灰阶 1 级）、B1–B3（悬停/选中态）、C2/C3（菜单 5 px / 35 px 几何）、E1–E5（正文 Markdown）、F3（遮罩灰阶，同 A5）、G1（输入区左侧图标簇左移约 90 px）、H1（empty/first-run 1.26% 光栅残差）。
- 经实测不是缺口：B4、G2、G3、H2（已在上表注明，避免后续误改）。

### 5.6 chat 滚动条复测（2026-11-23）

- 源码依据：`apps/desktop/src/renderer/src/styles/app.css:45-62`（`::-webkit-scrollbar` width 8px；thumb `border-radius: var(--radius-full)`、`border: 2px solid transparent` + `background-clip: content-box`；hover `background: var(--fg-subtle)`；track 无规则即透明）；`tokens.css:26` `--radius-full: 999px`、`:81` 浅色 `--scrollbar: rgba(0,0,0,0.18)`、`:51` `--fg-subtle: #8a8a94`、`:148` 深色 `--scrollbar: rgba(255,255,255,0.16)`、`:119` `--fg-subtle: #71717a`。
- 实现：`app/src/qml/Main.qml` 新增内联 `DevaScrollBar`（真 `ScrollBar` 附件，`policy: AsNeeded`，width 8 / padding 2 / contentItem 可见宽 4 / 圆角 999 / 透明轨道 / hover 换色），挂到 `sessionList` 与 `bodyScroll`，objectName 分别为 `sidebar-scrollbar`、`body-scrollbar`；`Theme.qml` 增加 `scrollbarHover`、`scrollbarWidth`、`scrollbarInset`。
- 测试：`PATH=.venv/bin:$PATH LD_LIBRARY_PATH=/tmp python -m pytest app/tests/test_qml_shell.py -q > /tmp/t.log 2>&1; echo rc=$?` → `rc=0`，`48 passed in 9.59s`（新增 `test_qml_scrollbars_match_deva_and_scroll`，断言两条滚动条存在、尺寸/配色、滚轮与拖动均改变 contentY）。
- chat 重拍：`mkdir -p /tmp/qml-sb && LD_LIBRARY_PATH=/tmp PYTHON=.venv/bin/python bash scripts/parity/qml_page_shot.sh chat /tmp/qml-sb/chat.png /tmp/ai-upper-sb > /tmp/shot.out 2> /tmp/shot.err; echo rc=$?` → `rc=0`，`1280x820`，`stderr=0 bytes`。
- 差异：改前 `129807 px / 12.37%`（`ac72cd597ae44377b608777cbd5e2e81` vs `e83c48be95d0a5dde4cdcb6b5b70928f`，158583 vs 142647 bytes）→ 本段改后 `119799 px / 11.41%`（历史阶段值）。
- **D 轮最终全量重拍**：`chat 113088 px / 10.77%`（QML md5 `00baf469…`，max=248，`logs/d-page-diff18-final.log`）；滚动条像素实测侧栏 `(202,202,203)` 340 px、正文 `(209,209,209)` 1668 px。

### 5.7 D 轮验收与全量 pytest（如实记录）

D 轮产品代码改动只有 `app/src/qml/SoftShadow.qml` 的可见性绑定（3 行新增）与 18 页重拍/报告更新；
未改 A/B/C 已提交的实现。另有 `app/tests/test_qml_sidebar.py` 一处测试隔离修正：全量顺序下前一个
包装用例把全局鼠标停在 `(160,140)`，同一用例的 `QTest.mouseMove` 不产生移动事件，先移到 `(20,20)`
再移入即可重复复现 hover。最终重拍与四条硬判据见 §5.1–§5.3，逐页残差见 §5.2 / §5.5。

全量测试命令与原始结果：

```
$ H=$(mktemp -d /tmp/ai-upper-full-XXXXXX); AI_UPPER_HOME=$H .venv/bin/python -m pytest app/tests -q > out/latest-parity/logs/d-pytest-full.log 2>&1; echo rc=$?
rc=1
$ tail -3 out/latest-parity/logs/d-pytest-full.log
FAILED app/tests/test_qml_sidebar.py::test_sidebar_rows_match_deva_bounds_and_states
1 failed, 1348 passed, 5 skipped in 168.01s (0:02:48)
rc=1
```

失败项不是 D 轮页面改动：`test_qml_sidebar.py:75` 期望第二行 hover 像素 `(236,236,237)`，全量跑到该用例时
实际 `(247,247,248)`（等于未 hover 的底色）；单独复跑同一用例通过：

```
$ H=$(mktemp -d /tmp/ai-upper-sidebar-XXXXXX); AI_UPPER_HOME=$H .venv/bin/python -m pytest app/tests/test_qml_sidebar.py::test_sidebar_rows_match_deva_bounds_and_states -q
rc=0
1 passed in 5.21s
```

因此全量结果是 **1 failed, 1348 passed, 5 skipped, rc=1**；该失败为全量顺序下的鼠标 hover 状态未生效，
单独运行 rc=0，**未把它算作通过，也没有隐藏**。日志：`out/latest-parity/logs/d-pytest-full.log`、
`out/latest-parity/logs/d-pytest-sidebar-single.log`。

修复后全量复跑（同一工作树，含上面的鼠标隔离修正）：

```
$ H=$(mktemp -d /tmp/ai-upper-full2-XXXXXX); AI_UPPER_HOME=$H .venv/bin/python -m pytest app/tests -q > out/latest-parity/logs/d-pytest-full-rerun.log 2>&1; echo rc=$?
rc=0
$ tail -2 out/latest-parity/logs/d-pytest-full-rerun.log
1349 passed, 5 skipped in 167.49s (0:02:47)
rc=0
```

**最终全量：1349 passed, 5 skipped, 0 failed, rc=0**。前一次 `1 failed` 已按上述根因修复并复跑闭环；
`0 failed` 不是我改测试期望值得来的——hover 断言仍是 `(236,236,237)`，只补了鼠标先移开再移入。

### 5.8 未闭环项逐条实测结论（当前工作树，交付前核对）

本节把 §5.4 仍列出的项目逐条用当前 `out/latest-parity/qml/*.png` 与 `deva/*-deva.png` 重新读数；若与 §5.4 的旧探针值冲突，以本节实测值为准。统一读数脚本为 `out/latest-parity/probes/open_items_probe.py`，完整输出在 `out/latest-parity/logs/item2-open-items.log`（`rc=0`）。截图链路先用当前代码重拍 `chat`，得到 `md5=00baf46965255434d276905e4e82c978`，与仓库内 `out/latest-parity/qml/chat.png` 完全一致，说明下面比较的是当前代码而非旧图。

**A5 / F3（遮罩灰阶）— 保持结论：合成取整，不改视觉。** `open_items_probe.py` 复读 `delete-confirm (60,120)`：QML `(143,143,144)` vs deva `(144,144,144)`，Δ `(-1,-1,0)`；`delete-confirm (300,700)` 同样 QML `(143,143,144)` vs deva `(144,144,144)`；`settings-general (60,120)` 同样 `(143,143,144)` vs `(144,144,144)`；`settings-general (300,700)` QML `(137,137,138)` vs deva `(138,138,138)`。`logs/d1-mask-attribution.log` 的拆层结果是 `outside_diff=297039`、`outside_d1_2=248842`，`conclusion=mask-compositing-primary`；A5/F3 的 1 个灰阶来自 `rgba(0,0,0,0.42)` 在 QML 与 deva 两条合成路径上的取整，不是控件结构或间距差。**结论：不为了降低百分比去改 QML 视觉。**

**B1（悬停高亮打在错误行）— 当前只在 `long-mid` 留残差。** 精确色 `(236,236,237)`、左侧栏 `x64..338`、按行统计像素 >100 的结果：`chat` QML 54 行 `(650,703)`，deva 54 行 `(650,703)`；`hover-thread` QML 0 行、deva 0 行；`long-mid` QML 0 行、deva 54 行 `(668,721)`。旧报告 `hover-thread bbox=(64,110,339,801)、12573 px` 在当前截图中不再复现。**结论：B1 的全局错行已不存在，仅 `long-mid` 的悬停带仍缺失（该页滚动位置也与基线不同）。**

**B2（悬停时列表底部没有悬停带）— `chat` 已对齐，`long-mid` 同 B1。** `chat` QML 与 deva 均为 54 行，span 都是 `(650,703)`；`hover-thread` 两端都是 0 行；`long-mid` QML 0 行 vs deva 54 行 `(668,721)`。旧 `chat QML n=56 vs deva n=11169` 已不成立。**结论：B2 只剩 `long-mid` 与 B1 共用的悬停带缺失。**

**B3（侧栏选中态纵向范围偏长）— 当前实测已对齐。** 精确选中色 `(228,228,244)`：QML `n=12164`、bbox `(64,56,338,109)`；deva `n=12233`、bbox `(64,56,338,109)`。两者左右/纵向 bbox 完全一致，余下 69 px 是抗锯齿边缘。旧报告 `QML bbox=(64,56,339,715)、n=12542` 与 `deva bbox=(42,48,338,628)、n=12334` 均为过期值。**结论：B3 已闭环，不再作为未闭环项。**

**C2（面板左缘偏右 5 px）— 当前实测已对齐。** `ctx-menu` 白色菜单框在 `x120..339、y70..279` 的精确白像素：QML `n=20829`、bbox `(161,91,306,245)`；deva `n=20911`、bbox `(161,91,306,245)`。左缘同为 `x=161`，旧 `QML x=166 vs deva 161` 不再复现。**结论：C2 已闭环。**

**C3（面板高度差 35 px）— 当前实测已对齐。** 同上读数：QML 白框 `y=91..245`（155 行），deva `y=91..245`（155 行），高度一致；旧 `QML y89–210（121 px）vs deva y91–245（154 px）` 为过期值。**结论：C3 已闭环。**

**E1–E5（正文 Markdown）— 先核对 `2a6e2a3` 的实际覆盖范围。** `git show --stat 2a6e2a3` 的原始输出（`logs/item2-git-show-2a6e2a3.log`，`rc=0`）只有两个文件：`app/src/markdown/document.py` 26 行、`app/tests/test_markdown_document.py` 17 行，合计 `2 files changed, 28 insertions(+), 15 deletions(-)`；diff 内容只涉及表格单元格的透明 NBSP 缩进、`rightMargin=1.0`、`textIndent=0.0` 与表格整行底色/边框，不涉及正文段落行高、块间距、图片占位。直接跑正文测试：`AI_UPPER_HOME=<fresh tmp> .venv/bin/python -m pytest app/tests/test_markdown_body.py app/tests/test_markdown_document.py -q` → `81 passed in 0.43s`，`rc=0`（`logs/item2-body-tests.log`），其中与 `2a6e2a3` 直接对应的是 `test_table_cells_use_transparent_indent_and_fixed_row_height` 和 `test_a_table_with_many_rows_fills_every_row_and_column`，其余测试不足以证明未改动项。

- **E1：未由 `2a6e2a3` 覆盖。** 缺的是正文段落行高/块间距。当前 `chat` 文本带（`x430..1199、y40..639、max<200`）QML 18 带、deva 19 带；QML 首带 `(40,43)`、次带 `(55,67)`，deva 首带 `(43,45)`、次带 `(56,68)`，末带 QML `(600,614)` vs deva `(602,619)`。`2a6e2a3` 没有改 `_paragraph`/`line_height` 路径。
- **E2：已由 `2a6e2a3` 覆盖。** 证据是上面的 `git show --stat`、两个表格测试通过、以及 `81 passed`。当前 `chat` 表格 `(244,244,244)` 底色 `n=7778`、bbox `(484,138,786,229)`；deva `n=8955`、bbox `(489,138,788,208)`，缺行/缺格已消失，余下是行内代码 pill 与 Qt 光栅的计数差。
- **E3：未由 `2a6e2a3` 覆盖。** 缺的是正文滚动偏移所需的段落行高/间距；当前 `chat` 首带 `(40,43)` vs deva `(43,45)`，仍有约 3 px 基线差（旧 13 px 线性偏移已缩小），`2a6e2a3` 只改表格。
- **E4：未由 `2a6e2a3` 覆盖。** 缺的是 broken-image 的 alt 占位语义；当前实现和测试仍输出 `［图片：说明］`（`app/tests/test_markdown_document.py:442`），deva 目标是裸 `示意图`。`2a6e2a3` 没有改 `_image`。
- **E5：未由 `2a6e2a3` 覆盖。** 缺的是 `search-none` 的正文块间距；当前 `search-none` 文本带 QML 15 带 vs deva 16 带，首带同样 `(40,43)` vs `(43,45)`，`2a6e2a3` 无正文段落改动。

**F3（遮罩灰阶，同 A5）— 同样保持“合成取整、不改视觉”。** `settings-general` 等四页的 `outside_diff=297039`、`outside_d1_2=248842` 四页完全相同，差异集中在同一层 `rgba(0,0,0,0.42)` 遮罩；样本值与 A5 相同（QML `(143,143,144)` vs deva `(144,144,144)`，以及 `(137,137,138)` vs `(138,138,138)`）。**结论：F3 不是独立结构缺口，和 A5 合并归为遮罩合成取整。**

**G1（输入区左侧图标簇左移约 90 px）— 旧 90 px 位移当前不再复现。** 对 `chat` 输入区 `y730..799` 做暗像素列聚类：QML 前几组 `[449-462], [476-488], [500-507], [510-515], [518-522], [525-530]`；deva `[449-462], [484-496], [505-512], [515-520], [523-527], [530-535]`。第一组起点完全一致（449），第二组起点 QML 476 vs deva 484（8 px），第三组 500 vs 505（5 px）。**结论：G1 的 90 px 级别偏移已不存在；当前只剩图标字形内部的 5–8 px 差异，旧 `[860-990]` 数值为过期探针。**

**H1（empty/first-run 1.26% 光栅残差）— 仍开放。** `logs/d-page-diff18-final.log` 的当前值：`empty` 与 `first-run` 都是 `13231 px / 1.26%`，`max=248`，两页像素相同。文本带实测：QML `(412,459)/(471,484)/(492,506)/(508,522)`，deva `(408,459)/(471,484)/(492,506)/(508,522)`；只有第一带左缘差 4 px，其余三带一致，说明残留主要在 quick-start 首行字体度量与头像光栅，不是布局结构。**结论：H1 仍为已知光栅残差，未宣称对齐。**

### 5.9 最终全量 pytest（item 3）

按与基线相同的调用方式，在全新临时 `AI_UPPER_HOME` 下跑完整测试套件：

```
$ H=$(mktemp -d /tmp/ai-upper-full-XXXXXX); AI_UPPER_HOME="$H" .venv/bin/python -m pytest app/tests -q > out/latest-parity/logs/item3-pytest-full-baseline-env.log 2>&1; echo rc=$?
rc=0
$ tail -1 out/latest-parity/logs/item3-pytest-full-baseline-env.log
1349 passed, 5 skipped in 167.11s (0:02:47)
```

结果与基线 `1349 passed, 5 skipped, rc=0` 一致，没有 failed，passed 数未下降。完整原始日志：`out/latest-parity/logs/item3-pytest-full-baseline-env.log`。同一轮另用带 `PATH=.venv/bin:$PATH`、`QT_QPA_PLATFORM=offscreen` 的环境跑过一次，得到 `1350 passed, 4 skipped`，是多解开了一个环境门禁用例，记录在 `out/latest-parity/logs/item3-pytest-full-envfull.log`；验收口径仍以基线同款命令的 `1349 passed, 5 skipped` 为准。
