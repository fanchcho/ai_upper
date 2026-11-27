# Typeahead、密钥成功分支与残差复核

## 基线与范围

起始 develop HEAD/ls-remote 均 a80f43a2bd7ffd706a3c7e666ee0a98602bfe552，status 空。没有回退已推送提交。deva 仅只读源码；既有测试、SettingsModal 导航/路由、Theme/SoftShadow 与正文实现未修改。所有应用/测试 AI_UPPER_HOME 显式 /tmp。生产只修改 ExtensionDetail.qml。

## Typeahead 原版规则与验证

原版 apps/desktop/src/renderer/src/components/Select.tsx:77 为 600ms；:195–223 为完整键规则。不是搜索过滤器，没有搜索输入框/清空按钮：所有项始终显示。只在菜单打开态处理单字符，排除 Ctrl/Meta/Alt；大小写折叠，600ms内累积前缀，从第0项找首个 startsWith。无匹配保留活动行；连续 ww 不轮转；Backspace 不处理；停顿>=600ms后的新字符重置前缀。方向键不清空缓冲；Enter/Space沿用选择；关闭/重开不主动清缓冲（与原版ref一致）。

改前完全没有 typeahead；改后保持原列表，只更新 activeRow。Qt event.text 的 Backspace 是单个控制字符，因此必须排除小于32及127，避免误当DOM单字符键。首次探针失败暴露这一差异，已修。另一次探针鼠标停在菜单首行触发hover干扰，最终真实QTest先把指针移到菜单外再输入；未以直接设置活动行替代按键。

暗亮最终日志一致：WR -> buffer wr / activeRow6(writer)；z -> wrz / 6；Backspace忽略；等待650ms，re -> row4(reviewer)；Enter将reviewer从真实config.json移除；等待650ms t ->5；Ctrl+A不改行；等待650ms w ->6；紧接w ->ww/6；所有五个fixture角色仍在菜单中。截图 typeahead-prefix、typeahead-selected、typeahead-full-list。日志 dark.log/light.log。

## OS 与替身严格区分

原版 main/services/secrets.ts:81–90 依赖 Electron safeStorage.isEncryptionAvailable；SettingsPane.tsx:852–869 显示 Saved/Configured。

本机检查（原始输出 out/extensions-typeahead/os-credentials.log）：
```
busctl --user list
# /bin/bash: busctl: command not found
# type -a 检查 dbus-send / gnome-keyring-daemon / kwalletd6，均不可用
AI_UPPER_HOME=/tmp/ai-upper-typeahead-os PYTHONPATH=app/src .venv/bin/python ...
keyring: keyring.backends.fail.Keyring (priority: 0)
backend: none available: False
save: {'ok': False, 'available': False}
```
原版当前CDP读取尝试 `node scripts/parity/extensions_reference_cdp.mjs 'window.deva.secrets.available()'` 返回 ECONNREFUSED 127.0.0.1:9344（deva-credentials.log）。因此本轮没有新的Electron live成功态证明；沿用extensions-calibration.md的真实 `{ok:false,available:false}`。真实OS成功态仍未验证：需要可用会话D-Bus/Secret Service及Electron safeStorage支持，不能把Python文件加密回退当OS成功。

新增独立可重复测试 scripts/parity/extensions_secret_double.py，只替换vault的keyring接口为内存字典，产品代码的vault/service/bridge/QML路径不变。QTest输入测试值、600ms timer自动保存，断言字典收到值、Saved可见；重新进入详情断言Configured和占位提示可见。暗亮通过。这是替身分支验证，不是OS成功或原版同状态截图；测试值不写真实用户目录。

发现并修复真实样式缺口：原版 SettingsPane.tsx:858/863 使用ShieldCheck size12，app.css:3465–3472为gap4/font11/weight600/success；:5184–5199为状态行gap3和左边距34%+8。此前移植只有灰色普通字且无图标。现补同Lucide路径12px，间距4px，11px半粗，dark #51cf66/light #2f9e44（tokens.css:64/:132）。替身真实截图Configured text bbox两主题均 x663.68,y548,w68,h13，实体字色分别RGB(81,207,102)/(47,158,68)，详见status-measurements.json。不得称原版OS成功态像素已验证。

## 四类残差逐项复核

|项|原版依据|当前移植|结论|
|圆底|styles/tokens.css:47/:115，light rgba(91,91,214,.12)，dark rgba(124,124,240,.2)|Theme.qml:21/:37相同，20px圆底不变|暗色旧实测原版#3b3b55/Qt#3b3b54，未归零|
|外环|tokens.css:59/:127，light .1/dark .16；Select打开态外环|ExtensionDetail相同rgba、外扩3px不变|旧矩阵dark #37374e/#37374d、light #eeeefb/#eeeefa，未归零|
|阴影|tokens.css:82/:149，light 0 6px 24px black12%，dark 0 8px 30px black50%|SoftShadow同blur/offset/alpha不变|浅色尾部原版#fcfcfc/Qt#fbfbfb，未归零|
|正文|既有六块同token同坐标相位实验|正文和文档格式文件零改动|+1/+1/0/+1/+1/0px，未归零|

本轮只复核源码/token与现有证据，不重跑已验收实验，不声称新测量：docs/audit/extensions-rounding.md；out/extensions-rounding/measurements.json、composite-matrix.json与compare-dark/light-*图片。0.5px同位移令六块差值全0而1px又恢复；阴影同位移0/.5/1导致浅色差-1/0/-1，支持栅格化/合成解释。本轮四类没有发现新的可证实token差，不修改token凑像素。

## 可重复命令

在仓库根目录执行，使用新临时home避免fixture重复：
```
AI_UPPER_HOME=/tmp/ai-upper-typeahead-dark5 XDG_DATA_HOME=$PWD/.tmp/extensions-typeahead/data LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python scripts/parity/extensions_typeahead_evidence.py dark
AI_UPPER_HOME=/tmp/ai-upper-typeahead-light XDG_DATA_HOME=$PWD/.tmp/extensions-typeahead/data LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python scripts/parity/extensions_typeahead_evidence.py light
AI_UPPER_HOME=/tmp/ai-upper-secret-dark4 XDG_DATA_HOME=$PWD/.tmp/extensions-typeahead/data LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python scripts/parity/extensions_secret_double.py dark
AI_UPPER_HOME=/tmp/ai-upper-secret-light XDG_DATA_HOME=$PWD/.tmp/extensions-typeahead/data LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python scripts/parity/extensions_secret_double.py light
AI_UPPER_HOME=/tmp/ai-upper-typeahead-tests LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-typeahead-tests/tests
```
首次pytest因basetemp父目录未建立发生664 passed/6 skipped/768 setup errors，FileNotFoundError；原始pytest-setup-error.log保留。创建.tmp/extensions-typeahead/test-home并以/tmp/ai-upper-typeahead-tests软链指向后重跑，未改测试。

最终全量：1429 passed, 9 skipped in 365.14s (0:06:05)，0 failed。git diff --check通过，既有测试零改动。暗亮typeahead与密钥替身独立验证均通过（verification.json）。正常提交/push后HEAD与ls-remote原始行见out/extensions-typeahead/git-final.log。
