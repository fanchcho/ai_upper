# 第五阶段收口报告：界面与原版逐页一致

- 日期：2026-11-14
- 分支：`develop`（`origin/develop` 快进关系，本地 ahead 18，未 force push）
- 配套台账：`docs/BUILD-PROGRESS.md`（§0 对账、§1.11 逐页判定、§2/§3 两档）
- 口径：只写**实际跑出来的**结果。「已一致」的判定是**实测截图比对**，
  不是主观描述；残余差异逐像素列出，**不含「零差异」这种说法**。

---

## 一、已实现并验证

### 1. 界面载体：QtWebEngine 承载原版渲染层

| 项 | 证据 |
|---|---|
| 原版渲染层只读复用（`app/assets/renderer`） | `deva` 工程全程未写入任何文件 |
| Python 侧实现 `window.deva`，替代 Electron preload | `app/src/mvvm/webui/bridge.py`（QWebChannel） |
| 窗口几何与原版一致：1280×820，最小 940×600，无边框 | `app/src/mvvm/views/web_shell_window.py` |
| 自绘 `titleBarOverlay`：右上角 96×40 实色，三个 32×40 按钮 | `app/src/mvvm/views/title_bar_overlay.py` |
| 未实现的通道在桥边界**显式 reject**，不返回假成功 | `test_bridge_unknown_channel_is_explicit_not_silent` |
| 单元测试（真实 Qt binding） | `pytest tests/test_web_shell_modules.py -q` → **12 passed in 0.40s** |

### 2. 技能服务（设置 › 扩展页的数据源）

| 项 | 证据 |
|---|---|
| 内置三个元技能，正文与原版常量**逐字一致** | `app/src/mvvm/services/skill_store.py` |
| 自定义目录 + frontmatter 四类条目解析 | 同上（`parse_frontmatter` / `parse_skill`） |
| 启用态 `skills.enabled[id]`「缺省即启用」、角色 `skills.roles[id]`「缺省即全部」 | 同上 |
| 单元测试 | `pytest tests/test_skill_store.py -q` → **19 passed in 0.18s** |

### 3. 全量测试

```text
$ cd app && ../.venv/bin/python -m pytest -q
........................................................................ [  8%]
..........ss............................................................ [ 16%]
........................................................................ [ 25%]
...........................ss........................................... [ 33%]
........................................................................ [ 42%]
.s...................................................................... [ 50%]
........................................................................ [ 59%]
........................................................................ [ 67%]
........................................................................ [ 76%]
........................................................................ [ 84%]
........................................................................ [ 93%]
..........................................................               [100%]
845 passed, 5 skipped in 21.51s
```

5 条 skip 的原文原因（`-q -rs`）：

```text
SKIPPED [1] tests/test_build_tool_compat.py:1615: the auto-link pragma belongs to the Windows pyconfig.h
SKIPPED [1] tests/test_build_tool_compat.py:1669: handle inheritance for GUI-subsystem children belongs to Windows
SKIPPED [1] tests/test_e2e_local.py:432: set PY_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_e2e_local.py:470: set PY_UPPER_E2E=1 to run the full local build E2E
SKIPPED [1] tests/test_native_deployment.py:177: requires cc, patchelf and readelf
```

全部是环境型跳过。**没有**用跳过 / 注释 / 抑制把红灯做绿。

### 4. 本轮唯一的红灯与修复（如实记录）

`test_every_mvvm_module_imports` 曾红：`ImportError: PySide6.QtCore has no 'QPoint'`。
原因是承载层三个模块在**类体求值**时就要 Qt（继承 `QWidget`/`QMainWindow`/`QObject`，
类体里调 `Signal(...)`），懒导入推迟不到类体。修复方式**不是跳过**，而是：

1. 把三者列入显式豁免名单，并断言名单内文件真实存在（防重命名后豁免悄悄失效）；
2. 新增 `tests/test_web_shell_modules.py` 用**真实 binding** 补上被豁免的覆盖。

全量结果由 `1 failed, 832 passed, 5 skipped` 变为 `845 passed, 5 skipped`。

---

## 二、页面一致性判定（第五阶段核心）

### 2.1 判定口径

- 截图：Xvfb `1400x900x24`，窗口 `windowmove 0 0` + `windowsize 1280 820`，`import -window root`。
- 原版 `:95`（Electron 33.4.11）、移植版 `:96`（PySide6 6.11.2 + QtWebEngine），**点击坐标完全相同**。
- `raw` = `compare -metric AE`（无容差）；`fuzz3` = 容差 3% 的 AE；
  `maxd` = 差值图 **RGB 三通道**最大差（0..255）。
- 判定：**`fuzz3 ≤ 1` 且 `maxd ≤ 10` → 已一致**。

### 2.2 两轮截图安排（原因）

| 轮次 | 数据 | 能拍到 | 为什么必须这样 |
|---|---|---|---|
| 第一轮 | 空 `DEVA_HOME` | 首启页 + 设置四个子页 + 关闭后的主界面 | 有会话时首屏直接进对话页，拍不到首启页 |
| 第二轮 | 预置一个会话（fixture） | 对话页 | 空库时进不了对话页 |

两轮都有同一前置：**截图前指针移到中立位置**（`xdotool mousemove 200 700`）。
Xvfb 指针默认停在屏幕中心，正好压在首启页的「智谱 · GLM」卡片上，原版会画 `:hover` 强调边框；
指针不一致时首启页永远比不平（曾实测 `fuzz3 = 11948`，全部来自这一处）。

### 2.3 逐页结论（七页全部已一致，差异非零）

| 页面 | 原版截图（绝对路径） | 移植版截图（绝对路径） | raw | fuzz3 | maxd | 判定 |
|---|---|---|---|---|---|---|
| 01 首启页（未配置提供方） | `/home/agent/shared_workspace/py_upper/out/parity/deva/01-first-run.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/01-first-run.png` | 409 | 1 | 9 | 已一致 |
| 02 设置 › 通用 | `/home/agent/shared_workspace/py_upper/out/parity/deva/02-settings-general.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/02-settings-general.png` | 241599 | 1 | 9 | 已一致 |
| 03 设置 › 模型 | `/home/agent/shared_workspace/py_upper/out/parity/deva/03-settings-models.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/03-settings-models.png` | 241446 | 1 | 9 | 已一致 |
| 04 设置 › 扩展 | `/home/agent/shared_workspace/py_upper/out/parity/deva/04-settings-extensions.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/04-settings-extensions.png` | 241527 | 1 | 9 | 已一致 |
| 05 设置 › 关于 | `/home/agent/shared_workspace/py_upper/out/parity/deva/05-settings-about.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/05-settings-about.png` | 241398 | 1 | 9 | 已一致 |
| 06 关闭设置后的主界面 | `/home/agent/shared_workspace/py_upper/out/parity/deva/06-after-settings.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/06-after-settings.png` | 409 | 1 | 9 | 已一致 |
| 07 对话页（带 fixture） | `/home/agent/shared_workspace/py_upper/out/parity/deva/07-chat.png` | `/home/agent/shared_workspace/py_upper/out/parity/py/07-chat.png` | 14033 | 1 | 9 | 已一致 |

并排图（原版 / 移植版，同一台 Xvfb、同一窗口几何）：

| 页面 | 原版 | 移植版 |
|---|---|---|
| 01 首启页 | ![01 原版](/home/agent/shared_workspace/py_upper/out/parity/deva/01-first-run.png) | ![01 移植版](/home/agent/shared_workspace/py_upper/out/parity/py/01-first-run.png) |
| 02 设置 › 通用 | ![02 原版](/home/agent/shared_workspace/py_upper/out/parity/deva/02-settings-general.png) | ![02 移植版](/home/agent/shared_workspace/py_upper/out/parity/py/02-settings-general.png) |
| 03 设置 › 模型 | ![03 原版](/home/agent/shared_workspace/py_upper/out/parity/deva/03-settings-models.png) | ![03 移植版](/home/agent/shared_workspace/py_upper/out/parity/py/03-settings-models.png) |
| 04 设置 › 扩展 | ![04 原版](/home/agent/shared_workspace/py_upper/out/parity/deva/04-settings-extensions.png) | ![04 移植版](/home/agent/shared_workspace/py_upper/out/parity/py/04-settings-extensions.png) |
| 05 设置 › 关于 | ![05 原版](/home/agent/shared_workspace/py_upper/out/parity/deva/05-settings-about.png) | ![05 移植版](/home/agent/shared_workspace/py_upper/out/parity/py/05-settings-about.png) |
| 06 主界面 | ![06 原版](/home/agent/shared_workspace/py_upper/out/parity/deva/06-after-settings.png) | ![06 移植版](/home/agent/shared_workspace/py_upper/out/parity/py/06-after-settings.png) |
| 07 对话页 | ![07 原版](/home/agent/shared_workspace/py_upper/out/parity/deva/07-chat.png) | ![07 移植版](/home/agent/shared_workspace/py_upper/out/parity/py/07-chat.png) |

### 2.4 残余差异（**不是零像素差**）

七页没有一页 `raw = 0`。差异只有两个来源：

**（a）关闭按钮 ✕ 的字形抗锯齿 —— 每页都是同一处、58 个像素**

| 灰度级 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 9 |
|---|---|---|---|---|---|---|---|---|
| 像素数 | 17 | 8 | 7 | 7 | 9 | 6 | 3 | 1 |

- 位置 `10x10+1259+15`，七页完全一致。
- 最大 **9/255**：原版 `(122,125,129)` vs 移植版 `(113,118,121)`，全图唯一 ≥8 级差异点，
  因此七页 `maxd` 都是 9。
- Electron 用位图字形、Qt 用 `QPainter` 画线，覆盖度采样不同。控件本身已核对：
  离屏渲染的 96×40 区域对原版实拍 `>8` 级差异像素为 **0**，几何/线宽/颜色逐值相同。

**（b）页面正文 —— 绝大多数差 1 级，极少数 2～3 级**

| 页面 | 正文差异像素 | 1 级 | ≥2 级 | 正文最大级差 |
|---|---|---|---|---|
| 01 首启页 | 351 | 343 | 8 | 3 |
| 02 设置 › 通用 | 241541 | 241507 | 34 | 2 |
| 03 设置 › 模型 | 241388 | 241363 | 25 | 2 |
| 04 设置 › 扩展 | 241469 | 241447 | 22 | 2 |
| 05 设置 › 关于 | 241340 | 241320 | 20 | 2 |
| 06 主界面 | 351 | 343 | 8 | 3 |
| 07 对话页 | 13975 | 13965 | 10 | 3 |

- 设置四页的十万级数字来自**整片半透明遮罩的 1 级取整差**：
  原版 `(144,144,144)` / 移植版 `(143,143,144)` 占 178498 像素（73.9%），
  `(140,140,141)` / `(139,139,140)` 占 41753 像素（17.3%）。肉眼不可分辨。
- 对话页同理：用户气泡底 `(228,228,244)` → `(228,228,243)`，12564 像素。
- **布局、比例、内边距、字号/行高、颜色、圆角/描边/阴影、图标、控件形态、滚动条、
  空态/错态**均无差异；`≥2` 级的像素全部落在文字与图标的抗锯齿边缘，最大 3 级。

### 2.5 本阶段修掉的两个真实差异

1. **设置页叠加层被遮罩压暗**（差异块 `96x40+1184+0`）：原版 Linux 的 `titleBarOverlay`
   是**实色**矩形，画在网页之上，遮罩压不暗它。端口原用半透明叠加层，被 dim 成 `#949494`；
   改为不透明并按 96×40 摆放后差异消失。
2. **设置 › 扩展页显示 `No extensions`**：`skills:list` 未接入。新增 `skill_store.py`
   （内置三技能 + 自定义目录 + frontmatter + 启用/角色语义），内置技能正文与原版**逐字一致**。

---

## 三、可复现命令（全部实跑过）

```bash
cd /home/agent/shared_workspace/py_upper

# 原版：启动 + 截图（第一轮空库 / 第二轮带 fixture）
bash scripts/parity/deva_original_shots.sh /tmp/deva-shots      /tmp/deva-home
bash scripts/parity/deva_original_shots.sh /tmp/deva-shots-chat /tmp/deva-home-chat /tmp/parity-fixture

# 移植版：同样的两轮
bash scripts/parity/port_shots.sh /tmp/py-shots      /tmp/py-home
bash scripts/parity/port_shots.sh /tmp/py-shots-chat /tmp/py-home-chat /tmp/parity-fixture

# 对齐判定（输出见下）
bash scripts/parity/compare.sh /tmp/deva-shots /tmp/py-shots

# 差异拆解（把 raw 拆成「✕ 字形块 / 正文」并给逐级灰度）
.venv/bin/python scripts/parity/measure_diff.py /tmp/deva-shots /tmp/py-shots

# 只启动移植版窗口（人工观察）
DISPLAY=:96 DEVA_HOME=/tmp/py-home QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu" \
  .venv/bin/python scripts/parity/port_run.py

# 单测
cd app
../.venv/bin/python -m pytest tests/test_skill_store.py -q      # 19 passed in 0.18s
../.venv/bin/python -m pytest tests/test_web_shell_modules.py -q # 12 passed in 0.40s
../.venv/bin/python -m pytest -q                                # 845 passed, 5 skipped in 21.51s
```

`compare.sh` 真实输出：

```text
$ bash scripts/parity/compare.sh out/parity/deva out/parity/py
PAGE                          raw    fuzz3   maxd  VERDICT
01-first-run                  409        1      9  已一致
02-settings-general        241599        1      9  已一致
03-settings-models         241446        1      9  已一致
04-settings-extensions     241527        1      9  已一致
05-settings-about          241398        1      9  已一致
06-after-settings             409        1      9  已一致
07-chat                     14033        1      9  已一致
```

> 注：`maxd` 早期实现先转灰度再取最大值，会把三通道的差平均掉（灰度法得 7，真实单通道差 9）。
> `compare.sh` 已改为在 RGB 上取 `maxima`，上表是修正后的口径。

依赖：`xvfb`、`xdotool`、`imagemagick`；原版另需 Electron 运行库与 `fonts-noto-cjk`。

---

## 四、已实现未验证

| 项 | 现状 | 缺什么 |
|---|---|---|
| 真实网络调用（Anthropic / OpenAI / Responses） | 适配器与装配线完整，事件流解析有离线测试 | 无可密钥；不保证出网 |
| `web_fetch` 真实抓网页 | 非 http 拒绝、缺 url、HTML→文本已测 | 同上 |
| 真桌面（真显卡 / HiDPI / Wayland）下的观感 | 已在 Xvfb 软渲染下逐页比对 | 结论只对 `1400x900x24 + 软渲染` 成立 |
| `titleBarOverlay` 按钮**点击生效** | 画得一致、几何有测试 | Xvfb 无窗口管理器，最小化/最大化需真桌面验 |
| 深色主题七页对比 | 叠加层深色切换有单测 | 只实拍了浅色七页 |
| 打包产物起 Web 承载窗口 | 裁剪已保留 `QtWebEngineCore`/`QtWebChannel` | 入口尚未切到 Web 窗口，产物起的仍是原生窗口 |
| 自定义技能的**非 ASCII 名**排序 | `casefold()` 与原版 `localeCompare` 对 ASCII 等价 | 中文名在 ICU 默认排序下可能不同，未实拍 |

## 五、未实现及阻塞

| 项 | 原因 | 影响 |
|---|---|---|
| **新界面的写路径**（`chat:send` 等） | 本轮只做到七页渲染正确 | **最大功能缺口**：新界面能看不能发消息 |
| 158 通道逐条结论表 | 本轮时间用尽 | 契约闭环缺一张表；未实现的通道在桥边界显式 reject，但不假成功 |
| 打包入口指向 Web 窗口并真实构建 | 同上 | 打包产物未被证明能起新界面 |
| 工作区挂载交互轮 | py_upper 改为启动时 `DEVA_APP_WORKSPACE` | 运行中不能换工作区 |
| 子智能体 / `task` 类工具（19 里的 9 个） | 依赖挂载与多轮编排 | 模型工具面变窄 |
| 真机人工验收（焦点、IME、拖拽） | 容器无显示服务器 | 只能由人验 |

---

## 六、本轮新增 commit

```text
e289b45 fix(webui): 窗口控制与剪贴板改为真实实现，不再返回假成功
188cfed docs: 第五阶段收口（逐页一致性判定 + 三档报告 + 差异量化）
64a8402 chore(assets): 补齐首启种子角色文件
06841f9 test(webui): 修好全量测试的红灯，豁免项补真实 binding 覆盖
f5e987b feat(ui): QtWebEngine 承载原版渲染层 + Python 桥接 + 逐页截图流水线
4f53a1e feat(ext): 技能服务（内置元技能 + 自定义目录 + frontmatter 解析）
c08da9d feat(tools): 工具权限判定层（交互轮放行/密封轮拒绝/挂载判据）接入执行入口
```

其中 `188cfed` 是本报告与台账自身的 docs commit；`e289b45` 是收口后复核频道表时
发现的「静默假成功」修复（窗口控制与剪贴板），单测从 10 条增至 12 条。

远端只做快进：全程 `git commit`，未 force push、未覆盖远端提交。
`deva` 工程（`/home/agent/shared_workspace/deva`）全程只读，未写入任何文件。
