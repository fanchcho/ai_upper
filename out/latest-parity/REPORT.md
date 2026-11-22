# 对齐基线更新到 deva 最新代码 · 第 1–2 步报告

> 本文件只覆盖「基线取证 + 在新基线上重拍两侧」。第 3 步（逐页补齐）另起章节，
> 每条修复单独提交并把 commit 记进来。

日期：2026-11-22　仓库：`/home/agent/shared_workspace/ai_upper`（分支 `develop`）

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

### 2.2 逐页 md5 与差异像素

分母统一 `1280*820 = 1049600`。表格原文另存 `out/latest-parity/page-diff-table.txt`
（md5 `2b453517e89610258fbe53efe0663361`）。

| 页名 | deva md5 | QML md5 | 差异像素 | 差异% |
|---|---|---|---|---|
| chat | `ac72cd59…` | `e36d9edb…` | 126790 | 12.08 |
| ctx-menu | `64c8c33a…` | `8ff33025…` | 133997 | 12.77 |
| dark-chat | `252996a5…` | `cc067223…` | 249359 | 23.76 |
| delete-confirm | `964c32d1…` | `55a629b9…` | 396118 | 37.74 |
| empty | `a616eabe…` | `3b1ddb91…` | 10325 | 0.98 |
| first-run | `0e2b5786…` | `3b1ddb91…` | 10325 | 0.98 |
| focus-composer | `e976e085…` | `3c8b55f5…` | 126806 | 12.08 |
| hover-thread | `16917898…` | `96a86cfd…` | 127197 | 12.12 |
| long-bottom | `be7b7fe8…` | `8d291d66…` | 125692 | 11.98 |
| long-mid | `147fb156…` | `6bea500d…` | 132329 | 12.61 |
| model-picker | `946b07de…` | `ff84da6c…` | 140783 | 13.41 |
| search-none | `49503995…` | `db2e09d1…` | 82432 | 7.85 |
| search-open | `3a5f8098…` | `be846a41…` | 126819 | 12.08 |
| search-results | `1d1ba812…` | `8ad4403a…` | 104080 | 9.92 |
| settings-about | `3fac0ec7…` | `96154d72…` | 334166 | 31.84 |
| settings-extensions | `15d607e1…` | `72ee5888…` | 329666 | 31.41 |
| settings-general | `4d16a5c6…` | `9858fecd…` | 340234 | 32.42 |
| settings-models | `7f7a6dd8…` | `6319db2e…` | 328000 | 31.25 |

`empty` 与 `first-run` 是**同一屏**，两侧像素级都是零差：

```
$ compare -metric AE deva/empty-deva.png deva/first-run-deva.png → 0
$ compare -metric AE qml/empty.png       qml/first-run.png       → 0
```

deva 侧两张的 PNG 文件 md5 不同（`a616eabe…` / `0e2b5786…`），但解码后像素签名完全相同
（`identify -verbose` 的 `signature` 两张都是 `76390a45…`），差异只在 PNG 的
`date:create` / `date:modify` 文本块（两张拍摄间隔 16 秒）。QML 侧两张连文件字节都相同
（都是 `3b1ddb91…`）。**结论：md5 列在这里只对「同一时刻拍的同一帧」可比，`empty` /
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
差异像素与 §2.2 表**逐项一致**（chat 126790 / empty 10325 / search-results 104080 /
settings-models 328000 / settings-about 334166 …），整表 37 秒跑完，rc=0。

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
