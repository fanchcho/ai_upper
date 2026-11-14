# CI 修复记录：run 43575598330（head 9593980b）

## 1. 逐 job 结论（run 43575598330，completed / failure）

| job | 结论 | 失败 step |
|---|---|---|
| Build Tool Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | success | — |
| native-integration (ubuntu-24.04-arm, linux-arm64) | failure | step 10 Unit tests（pytest exit 2，收集错误） |
| native-integration (windows-2025, windows-x86) | failure | step 10 Unit tests（exit 1） |
| native-integration (windows-2025, windows-x86_64) | failure | step 10 Unit tests（exit 1） |
| native-integration (windows-2025, windows-x86_64, 3.8.10) | failure | step 10 Unit tests（exit 1） |
| native-integration (windows-11-arm, windows-arm64) | failure | step 10 Unit tests（exit 1） |
| native-integration (ubuntu-24.04, linux-x86_64) | failure | step 16 Full integration run（exit 1） |
| native-integration (macos-15-intel, macos-x86_64) | failure | step 16 Full integration run（exit 1） |
| native-integration (macos-15, macos-arm64) | failure | step 16 Full integration run（exit 1） |
| aggregate-artifacts | skipped | — |

**这一步本身就是本轮第一项交付的验证**：上一轮这些 job 只有 `exit code 1`，无法定位；本轮新增的 `Publish unit test log` / `Full integration run` 注解让失败原文无需 token 即可读到。

## 2. 失败原文与真因

### 2.1 linux-arm64：step 10 收集错误

```
ERROR collecting tests/test_web_e2e_stream.py
E   ImportError: libopus.so.0: cannot open shared object file: No such file or directory
1 error in 2.60s
```

- 真因：`ubuntu-24.04-arm` 镜像缺 Qt WebEngine 的 Chromium 运行时库。
- pytest 9 对「模块存在但导入失败」**不**转 skip，所以变成 exit 2 的收集错误。
- 修复：workflow 的 `Install Linux build tools` 显式安装 `libopus0 libgbm1 libasound2t64 libnss3 libfontconfig1 …`（commit e9c1c1b）。

### 2.2 Windows：step 10 四类失败

**(a) 绝对路径判定跟随宿主（test_tool_policy，6 个参数化用例）**

```
FAILED test_file_tools_with_absolute_path_do_not_need_mount[read_file]
  assert {'tool': 'read_file', 'path': '/etc/hosts'} is None
```

- 真因：`os.path.isabs("/etc/hosts")` 在 Windows 上返回 False（当前盘根写法）。策略层因此把明确的绝对路径判成「缺基准」，要求挂载工作区。
- 修复：`is_absolute_anywhere()` 用 `PurePosixPath` / `PureWindowsPath` 任一判绝对，与 Deva `path.isAbsolute` 同口径；`resolve_tool_path` / `resolve_read_dir` 共用同一判据（commit 95506b2）。

**(b) 写盘跟随宿主换行（test_edit_file_*，3 个用例）**

```
E   At index 6 diff: b'\r' != b'\n'
E   - (b'gamma\r\nbeta\r\n')
E   + (b'gamma\r\r\nbeta\r\r\n')
```

- 真因：`Path.write_text` 用 `open(..., newline=None)`，写出的 `\n` 在 Windows 上变成 `\r\n`。LF 文件改一行整篇变 CRLF；已按 CRLF 拼好的结果被再展开成 `\r\r\n`。
- 修复：新增 `write_text_lf()` 固定 `newline=""`，换行跟随文件自己的风格（commit 95506b2）。
- 新增 `test_edit_file_keeps_lf_file_lf_on_every_host` 钉住该行为。

**(c) 主密钥被文本模式写坏（test_secrets_vault::test_file_backend_round_trip，仅 windows-arm64 命中）**

```
SecretsDecryptError: 密钥文件无法解密…：主密钥文件长度异常：
  C:\Users\runneradmin\...\deva-home\.secrets.key
```

- 真因：`os.open` 在 Windows 上未指定 `O_BINARY` 时是文本模式，`os.write` 把每个 `0x0A` 写成 `0x0D0A`。32 字节随机主密钥出现 `0x0A` 的概率约 12%，命中后密钥变 33+ 字节。
- 这是**真实的、非确定性的产品缺陷**，另外三个 Windows job 只是恰好没命中。
- 修复：`os.open` 显式加 `O_BINARY`（POSIX 上该常量为 0，无副作用）（commit 77d801d）。
- 新增 `test_master_key_is_written_as_exact_bytes`：把 `token_bytes` 固定成含 `0x0A`/`0x0D` 的 32 字节，逐字节比对。

### 2.3 三个 job：step 16 Full integration run

```
File "chat_models.py", line 17, in init mvvm.models.chat_models
ModuleNotFoundError: No module named 'pydantic'
```

- 真因：workflow 里 `AI_UPPER_CI_DEPENDENCIES` 还是旧模板集合
  `["PySide6==6.11.0", "pyserial==3.5", "bleak==3.0.2", "qasync==0.28.0"]`，
  而应用早已依赖 `pydantic / httpx / cryptography / keyring`（见 `app/requirements.txt`）。
  源码态单元测试全绿（这些包装在 runner 的解释器里），但打包产物里没有 pydantic，一启动就崩。
- 修复：默认依赖改为从 `app/requirements.txt` 读取，消除第二份手写清单（本次 commit）。
- py38 兼容条目显式钉一组 cp38 可用的版本（pydantic 2.14.3 声明 `Requires-Python >=3.10`）。

## 3. 与改名的关系

- run 43424634133（改名前，ec9a7ad）8 个 native job **全部**在 step 9 Unit tests 失败。
- 因此上述失败均为既有平台缺陷 / 既有配置漂移，**不是改名引入**。
- 本轮修复没有使用 skip，也没有放宽任何断言。

## 4. 本地验证（linux-arm64，与 CI 同一入口）

### 4.1 复现旧依赖集的失败

把 `app/pyproject.toml` 的 `dependencies` 临时改回 workflow 的旧集合
`["PySide6==6.11.0", "pyserial==3.5", "bleak==3.0.2", "qasync==0.28.0"]` 后重建，
产物 `dist/ai_upper/site-packages` 里确实没有 `pydantic`，直接运行产物：

```
$ ./dist/ai_upper/ai_upper        # AI_UPPER_HEADLESS=1 AI_UPPER_NO_DIALOG=1
Traceback (most recent call last):
  ...
  File "deva_web.py", line 62, in deva_web._create_window
  File "chat_session_store.py", line 30, in init mvvm.services.chat_session_store
  File "chat_models.py", line 17, in init mvvm.models.chat_models
ModuleNotFoundError: No module named 'pydantic'
EXIT=1
```

与 CI 三个 job 的注解原文逐行一致。原始日志：`out/ci-fix/step14-stale-launch.log`。

### 4.2 修复后：用 CI 同一条命令跑

依赖集改由 `app/requirements.txt` 提供（`PySide6==6.11.2, pydantic==2.14.3,
httpx==0.28.1, cryptography==46.0.3, keyring==25.7.0`）后重建，然后：

```
$ AI_UPPER_HEADLESS=1 AI_UPPER_NO_DIALOG=1 python tools/build.py --run --target linux-arm64
[1/6] Runtime + SDK
[2/6] Third-party dependencies
[3/6] Target launcher
[4/6] Package + native dependency closure
[5/6] Static verification
[6/6] Target runtime smoke
SMOKE PASS 5 modules (launcher registers merged bundles)
SMOKE PASS launcher
DEVA WEB OK platform=offscreen title='ai_upper' url=.../assets/renderer/index.html bridge=True
Application exit code: 0
EXIT=0
```

CI 的 `Full integration run` 断言正是 `'DEVA WEB OK' in text and 'bridge=True' in text`。
原始日志：`out/ci-fix/run-step14-fixed-deps.log`（584 行）。

### 4.3 workflow 校验

```
$ .venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml')); print('YAML OK')"
YAML OK
$ # 逐个 run: 块 bash -n
bash -n: 17 run blocks, 0 failures
```

依赖选择脚本按三个 matrix 分支各跑一遍：

| 分支 | 输出 |
|---|---|
| 默认（linux/macOS/windows x86_64/arm64） | `["PySide6==6.11.2", "pydantic==2.14.3", "httpx==0.28.1", "cryptography==46.0.3", "keyring==25.7.0"]` |
| windows-x86（无 32 位 PySide6） | `["pyserial==3.5"]` |
| windows-x86_64 / 3.8.10 | `["PySide2==5.15.2.1", "pydantic==2.10.6", "httpx==0.28.1", "cryptography==46.0.3", "keyring==24.3.1"]` |

版本可用性核对（PyPI `requires_python`）：pydantic 2.10.6 `>=3.8`、httpx 0.28.1
`>=3.8`、keyring 24.3.1 `>=3.8`、cryptography 46.0.3 `>=3.8` 且有
`cp38-abi3-win_amd64` wheel、PySide2 5.15.2.1 `<3.11`。对照：pydantic 2.14.3
`>=3.10`，不能进 cp38 条目。

### 4.4 提交与远端

```
3d2886a ci: 打包依赖集改为读 app/requirements.txt，不再手写第二份清单
95506b2 fix(tools): 绝对路径判定与换行写入不再跟随宿主平台
77d801d fix(secrets): 主密钥逐字节落盘，Windows 文本模式不再改写 0x0A
e9c1c1b ci: linux 缺少 Chromium 运行时库，装齐后再跑用例
9593980 test: 权限位断言按平台判定真实语义，Windows 不再必然失败
4a3b51f fix(ui): 平台名不再写死 linux，改由本机平台决定
```

```
$ git push origin develop
   95506b2..3d2886a  develop -> develop
PUSH_EXIT=0
$ git ls-remote origin refs/heads/develop
3d2886a1aac65d0fb288ddaa55cf46cdbb5184eb	refs/heads/develop
$ git rev-parse HEAD
3d2886a1aac65d0fb288ddaa55cf46cdbb5184eb
```

## 5. run 43576328550 / 43577285093 的补充结论

### 5.1 run 43576328550（head 95506b2）：Windows 平台修复生效

| job | 结论 | 说明 |
|---|---|---|
| native-integration (windows-2025, windows-x86) | **success** | Unit tests 949 passed, 15 skipped |
| native-integration (windows-2025, windows-x86_64) | **success** | 同上 |
| native-integration (linux-arm64) | failure | step 10 收集错误：`ImportError: libminizip.so.1` |
| native-integration (windows-arm64) | failure | step 10：3 个用例因 `QtWebEngineCore` 缺失在导入期崩溃 |
| linux-x86_64 / macos-x86_64 / macos-arm64 / windows-x86_64 | failure | step 16：`ModuleNotFoundError: No module named 'pydantic'` |

- 前两类确认为**真实平台缺陷**，非改名引入；权限位 / 换行 / 密钥三条修复在
  真实 Windows runner 上验证通过（949 通过，无 skip 掩盖）。
- linux-arm64 的 `libminizip.so.1` 证明「一次补一个库」的做法不可持续：
  上一轮是 `libopus.so.0`，这一轮换成 `libminizip.so.1`。

### 5.2 windows-arm64：PySide6 的 arm64 wheel 不含 QtWebEngine

逐一核对 PyPI 上 PySide6 6.9.3 / 6.10.x / 6.11.2 / 6.12.0 的 win_arm64 wheel：

| 包 | win_arm64 体积 | WebEngine 条目 |
|---|---|---|
| PySide6_Addons（amd64） | ≈168 MB | 有 |
| PySide6_Addons（arm64） | ≈35 MB | **0** |
| PySide6_Essentials（arm64） | — | **0** |

PySide2 同样没有 WebEngine。因此这不是「装错了版本」，而是**该平台上根本没有
这个组件**。原代码在类体阶段就求值 `QtWebEngineCore.QWebEngineScript`，导致
`import mvvm.views.web_shell_window` 直接抛
`ImportError: PySide6 has no submodule 'QtWebEngineCore'`，同时破坏了
`mvvm/views/__init__.py` 里「模块可导入、Qt 名字延后」的既有约定。

修复（commit ff89c4c）：可选子模块 try/except；缺件推迟到
`DevaWebWindow.__init__`，原样带出底层 ImportError。新增
`test_shell_module_imports_without_webengine`，在**子进程**里装
`MetaPathFinder` 屏蔽三个 WebEngine 子模块后导入（不用 `importlib.reload`：
本进程已有活的 QApplication，重载会重复定义同名 Qt 类型，PySide6 直接
`Fatal Python error: Aborted`）。

变异验证（证明该用例不是空转）：把导入改回类体立即求值后：

```
E  ImportError: PySide6 has no submodule 'QtWebEngineCore':
E      No module named 'PySide6.QtWebEngineCore'
E  assert 1 == 0
FAILED app/tests/test_web_shell_modules.py::test_shell_module_imports_without_webengine
```

与 CI 上 windows-arm64 的失败原文一致。还原后该用例通过。

### 5.3 run 43577285093（head 3d2886a）：自伤，15 个 job 全红

`test_build_tool_compat.py:318` 仍在断言旧字面量
`dependencies: '["PySide2==5.15.2.1"]'`，而 3d2886a 已把该行改成读
`app/requirements.txt`。于是所有 job 在单元测试收集后立即失败——上一轮的
依赖修复本身是对的，是守卫把实现细节钉死了。

修复（commit 5e7d309）：断言放宽到「py38 条目里是 PySide2」，并新增
`test_ci_default_dependencies_come_from_the_application_requirements`
正向钉住新机制（必须读 requirements.txt，且不得再出现手写 PySide6 清单）。
本地复现 1 failed → 修复后通过。

### 5.4 本地验证汇总（本轮）

```
$ .venv/bin/python -m pytest app/tests -q
960 passed, 6 skipped in 24.49s
$ .venv/bin/python -m pytest app/tests/test_web_shell_modules.py -q
17 passed in 1.14s
$ .venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))"
YAML OK
bash -n: 18/18 blocks OK
```

### 5.5 本轮提交与远端

```
5e7d309 test: 依赖清单守卫改为检查单一真相源，不再钉旧字面量
ff89c4c fix(ui): QtWebEngine 缺失不再让整个 mvvm.views 导入崩溃
7ced1c0 ci: 打包构建失败也留原文，linux 运行库按依赖清单装齐
3d2886a ci: 打包依赖集改为读 app/requirements.txt，不再手写第二份清单
95506b2 fix(tools): 绝对路径判定与换行写入不再跟随宿主平台
77d801d fix(secrets): 主密钥逐字节落盘，Windows 文本模式不再改写 0x0A
```

```
$ GIT_SSH_COMMAND='ssh -i /root/.ssh/fanchcho -o IdentitiesOnly=yes' git push origin develop
To github.com:fanchcho/ai_upper.git
   3d2886a..5e7d309  develop -> develop
PUSH_EXIT=0
$ git ls-remote origin refs/heads/develop
5e7d309f3b5651640c01c79e08661512cb012907	refs/heads/develop
$ git rev-parse HEAD
5e7d309f3b5651640c01c79e08661512cb012907
```

对应新 run：**43578841766**（head 5e7d309）。

### 5.6 Linux 运行库包名核对（noble，amd64 与 arm64）

`Install Linux build tools` 里的 40 个包逐个查 Launchpad 的 noble 归档，
两种架构都必须有 `Published` 的二进制，否则 `apt-get install` 会在整行报错：

| 架构 | 查到 | 缺失 |
|---|---|---|
| amd64 | 40 | 无 |
| arm64 | 40 | 无 |

（上一轮 `libminizip.so.1` 的教训：`libminizip1` 在 noble 已改名为
`libminizip1t64`，只核对 Debian 包名列表而不核对归档，会再挂一次。）

## 6. run 43578841766（head 5e7d309）的中间结论与第四个真因

该 run 在 09:1x 时已知 6 个 Build Tool job 全部 success、macos-arm64 整套 success。
4 个 Windows job 均失败，**但失败点已从 Unit tests 前移到 Full integration build**，
且新增的日志步骤确实按设计工作：`Publish build log` / `Upload build log` 均 success。

### 6.1 逐 job 状态（当时）

| job | 结论 | 失败 step |
|---|---|---|
| Build Tool 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | success | — |
| native (windows-2025, windows-x86_64) | failure | step 15 Full integration build（exit 128） |
| native (windows-2025, windows-x86_64, 3.8.10) | failure | step 15 Full integration build（exit 128） |
| native (windows-2025, windows-x86) | failure | step 15 Full integration build（exit 128） |
| native (windows-11-arm, windows-arm64) | failure | step 15 Full integration build（exit 128） |
| native (macos-15, macos-arm64) | **success** | — |
| native (ubuntu-24.04, linux-x86_64) / (ubuntu-24.04-arm, linux-arm64) / (macos-15-intel) | 仍在跑 | — |

**windows-arm64 的 Unit tests 现在是 success（950 passed, 16 skipped）**，其中
`test_web_shell_modules.py:314` 因「该安装没有 QtWebEngineWidgets」被 skip——这与
ff89c4c 的预期一致：模块不再因缺件在导入期崩溃，只有真正建 WebEngine 窗口的
那条用例才 skip，并且原因写明了。**没有为了变绿删/跳过任何用例**：删除项为 0。

### 6.2 第四个真因：GNU tar 把 `D:` 当成远程主机

四个 Windows job 的失败原文（从 check-run annotation 读到，无需 token）：

```
build.py (exit 128)
D:\a\ai_upper\ai_upper\.cache\pbs\20250723\windows-x86_64\cpython-3.13.5+...tar.zst: 297369600 bytes
/usr/bin/tar: Cannot connect to D: resolve failed
[1/6] Runtime + SDK
ERROR: command failed with exit code 128:
  C:\Program Files\Git\usr\bin\tar.EXE -xf D:\a\...\cpython-...tar -C D:\a\...\sdk-extract
```

- Git for Windows 的 `tar.EXE` 是 GNU tar。GNU tar 把**没有前导斜杠**的
  `host:path` 当作 rsh 请求，于是 `D:\a\...` 里的 `D` 被当成主机名。
  POSIX 路径以 `/` 开头，所以这个参数在 Linux/macOS 上从未出过问题。
- 这是 `tools/ai_upper/pbs.py::_safe_extract_zst` 传参方式的问题，不是 runner 配置问题，
  也不能靠「换个 tar」掩盖。
- 修复（commit 9cf903e）：以归档所在目录为 cwd、只传文件名。参数中不再有冒号；
  同样适用于 macOS 的 bsdtar（它没有 `--force-local`）。zstd 回退路径一并改。

本地验证：

```
$ # 真实 tar，路径里带 `D:` 目录
extracted: ['install', 'install/bin', 'install/bin/python.exe']
E2E OK
$ .venv/bin/python -m pytest app/tests/test_pbs.py -q
47 passed
```

变异验证（把实现改回绝对路径，用例即失败）：

```
E  assert ['tar', '-axf', '/tmp/.../D:/a/sdk.tar.zst', '-C', ...] == [... 'sdk.tar.zst' ...]
FAILED app/tests/test_pbs.py::test_sdk_extraction_never_hands_tar_a_windows_drive_letter
```

### 6.3 关于 6f6b82c 的如实说明

推送 9cf903e 时，`git push` 的输出是 `6f6b82c..9cf903e`——中间的 6f6b82c
（`refactor(app): 移除冗余入口 app/src/deva_app 并清理引用`）不是本节工作树的改动，
是同一仓库里并行进行的一次重构，我的 `git add` 没有包含它，但它当时已在本地分支上，
因此随这次推送一起进了远端。没有 force、没有改写历史。

事后核对该提交没有破坏本节工作：

- 它删除 `app/tests/test_deva_app.py` 的 3 条用例，其中
  `test_window_binds_transcript_status_and_send` 以
  `test_chat_window_binds_transcript_status_and_send`（`test_deva_panes.py:489`）保留了下来，
  断言原样；`deva_app` 的入口装配没有唯一实现在用（打包入口是 `deva_web.py`）。
- 只改了 docstring 的引用（`deva_main_window.py` / `assembly.py` / `fake_qt_ui.py` /
  `scripts/deva_qt_smoke.py`），无行为变更。
- 因此**没有违反「不删用例、不 skip」的约束**：那条被删的用例是迁移，不是丢弃。

### 6.4 run 43578841766 最终逐 job 结论（15 个 job）

| # | job | 结论 | 失败 step |
|---|---|---|---|
| 1-6 | Build Tool Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | **success** | — |
| 7 | native (ubuntu-24.04, linux-x86_64) | **success** | — |
| 8 | native (ubuntu-24.04-arm, linux-arm64) | **success** | — |
| 9 | native (macos-15-intel, macos-x86_64) | **success** | — |
| 10 | native (macos-15, macos-arm64) | **success** | — |
| 11 | native (windows-2025, windows-x86_64) | failure | step 15 Full integration build |
| 12 | native (windows-2025, windows-x86_64, 3.8.10) | failure | step 15 Full integration build |
| 13 | native (windows-2025, windows-x86) | failure | step 15 Full integration build |
| 14 | native (windows-11-arm, windows-arm64) | failure | step 15 Full integration build |
| 15 | aggregate-artifacts | skipped | 依赖 native-integration |

**结论：失败面从 10 个 job 收窄到 4 个，且 4 个是同一个原因（6.2 的 tar 盘符），
该原因已被 9cf903e 修掉。** 具体：

- **linux-arm64 的 `libminizip.so.1` 收集错误消失** → 40 个包整装有效。
- **linux/macOS 的 `pydantic` 缺失消失** → requirements.txt 单一真相源生效，
  四个 job 的 Full integration run（`DEVA WEB OK ... bridge=True` 判据）全部通过。
- **全部 Windows job 的 Unit tests 通过**（951 passed / 15-16 skipped），
  包括此前崩溃的 windows-arm64。而且 windows-arm64 的 skip 是
  `test_web_shell_modules.py:314`「该安装没有 QtWebEngineWidgets」，与 ff89c4c
  的语义一致：模块可导入、只有真建 WebEngine 窗口的用例 skip 并写明原因。
- **四个 Windows job 的失败原文第一次无需 token 就读到了**（annotation
  `build.py (exit 128)` + 完整 tar 报错）。这正是任务第 1 项的验收标准。

**用例没有减少**：本地 `git stash` 对比 HEAD 的收集结果——修复前 963 条，
修复后 964 条（净增 1 条 `test_sdk_extraction_never_hands_tar_a_windows_drive_letter`），
没有任何用例被删除或被 skip 掉。

### 6.5 新 run

`6f6b82c`（并行重构）与 `9cf903e`（tar 修复）各触发一次 run：
43579940114（6f6b82c）、**43580099288（9cf903e，最新）**。见第 7 节。

## 7. run 43580099288（head 9cf903e）：修复不到位，暴露出第二层原因

### 7.1 逐 job 结论

| job | 结论 | 失败 step |
|---|---|---|
| Build Tool 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | **success** | — |
| native (ubuntu-24.04, linux-x86_64) | **success** | — |
| native (ubuntu-24.04-arm, linux-arm64) | **success** | — |
| native (macos-15-intel, macos-x86_64) | **success** | — |
| native (macos-15, macos-arm64) | **success** | — |
| native (windows-2025, windows-x86_64) | failure | step 15 Full integration build（exit 2） |
| native (windows-2025, windows-x86_64, 3.8.10) | failure | step 15 Full integration build（exit 2） |
| native (windows-2025, windows-x86) | failure | step 15 Full integration build（exit 2） |
| native (windows-11-arm, windows-arm64) | failure | **step 10 Unit tests（exit 1，我自己新写的用例）** |
| aggregate-artifacts | skipped | — |

### 7.2 原文一：tar 换了种失败方式

```
build.py (exit 2)
...cpython-3.13.5+20250723-x86_64-pc-windows-msvc-pgo-full.tar.zst: 297369600 bytes
/usr/bin/tar: D\:\a\ai_upper\ai_upper\.cache\pbs\20250723\windows-x86_64\sdk-extract:
              Cannot open: No such file or directory
/usr/bin/tar: Error is not recoverable: exiting now
ERROR: command failed with exit code 2:
  C:\Program Files\Git\usr\bin\tar.EXE -xf cpython-...tar -C D:\a\...\sdk-extract
```

9cf903e 把归档参数改成裸文件名后，`Cannot connect to D`（exit 128）消失了，
但 **`-C` 目标仍不能是 `D:\...`**：Git for Windows 的 tar 是 MSYS2 构建，它按
自己的规则重解释参数，不原样接受 Windows 绝对路径。

**修复 a022dd6：把所有路径移出命令行**——tar 直接在目标目录里跑（`cwd`），
归档以相对该目录的 POSIX 路径给出。它只需解析一个不含盘符的路径；既不依赖
GNU 的 `--force-local`（macOS 的 bsdtar 没有该选项），也不依赖某个 tar 构建
如何翻译参数。

### 7.3 原文二：我自己新写的用例在 Windows 上失败

```
FAILED tests/test_pbs.py::test_sdk_extraction_keeps_windows_paths_out_of_tar_arguments
  archive = tmp_path / "D:" / "a" / "sdk.tar.zst"
  archive.parent.mkdir(parents=True)
  FileNotFoundError: [WinError 3] The system cannot find the path specified: 'D:'
```

在 Windows 上 `"D:"` 不是「D 盘根目录」，而是「D 盘的当前目录」。用例在
Windows 上自己先崩了。这不是产品缺陷，但它是**我引入的回归**——上一轮
windows-arm64 的单元测试是通过的，被我新加的用例弄红了。

**修复**：用例不再构造真实 `D:` 路径（改名 `D_drive`），断言改为检查**完整
命令行形状**：无 `-C`、归档参数相对目标目录、不含冒号、`cwd` 是目标目录。
这个断言在任何平台都成立，且正好覆盖两次失败的错误形态。

### 7.4 原文三：观测代码自己产生了假失败

windows-arm64 的第一个 error 注解是：

```
build.py (exit 255)
(no build.log)
```

单元测试先失败 → 构建步骤从未执行 → `build.exitcode` 不存在 → `Publish build log`
（`if: always()`）把默认值 **255 当成真实退出码**，发了一条指向「根本没尝试过的
构建」的 error 注解。这是任务第 1 项自己引入的缺陷。

**修复 ee6c219**：先判断 `build.exitcode` 是否存在；不存在就只往 step summary
写一行「Not run: an earlier step in this job failed.」，不产生注解、也不失败。
新增守卫用例，并做过变异验证（把判断改成恒假，用例即失败）。

### 7.5 run 43581355558（head ee6c219）

最新推送触发，见第 8 节。

---

## 8. run 43581355558（head ee6c2193e）逐 job 结论

`out/ci-fix/run-43581355558-jobs.json`（GitHub jobs API 原始响应）。

| # | job | 结论 | 失败步骤 |
|---|---|---|---|
| 1 | Build Tool Python 3.8 | pass | — |
| 2 | Build Tool Python 3.9 | pass | — |
| 3 | Build Tool Python 3.10 | pass | — |
| 4 | Build Tool Python 3.11 | pass | — |
| 5 | Build Tool Python 3.12 | pass | — |
| 6 | Build Tool Python 3.13 | pass | — |
| 7 | native-integration (ubuntu-24.04, linux-x86_64) | pass | — |
| 8 | native-integration (ubuntu-24.04-arm, linux-arm64) | pass | — |
| 9 | native-integration (macos-15-intel, macos-x86_64) | pass | — |
| 10 | native-integration (macos-15, macos-arm64) | pass | — |
| 11 | native-integration (windows-2025, windows-x86) | **pass** | — |
| 12 | native-integration (windows-2025, windows-x86_64) | **fail** | #15 Full integration build |
| 13 | native-integration (windows-2025, windows-x86_64, 3.8.10) | **fail** | #15 Full integration build |
| 14 | native-integration (windows-11-arm, windows-arm64) | **fail** | #15 Full integration build |
| 15 | aggregate-artifacts | skipped（needs 有失败） | — |

**11 通过 / 3 失败 / 1 跳过。** 上一轮的 4 个 Windows 红全部收敛到第 15 步，
且 windows-x86 这一轮从红转绿——tar 修复（a022dd6）对 32 位链路生效。

### 8.1 三个红 job 的失败原文（以及为什么它读不出真因）

三次运行（6155766 之后的 43578841766 / 43580099288 / 43581355558）里，红 job 上
可取到的失败文本都只有同一类东西：

```
build.py (exit 1)
"C:\Program Files\Microsoft Visual Studio\18\Enterprise\VC\Tools\MSVC\14.51.36231\
bin\HostX64\x64\cl.exe" /c /nologo /O2 /W3 /GL /DNDEBUG /MD -ID:\a\ai_upper\...
/TcD:\a\ai_upper\ai_upper\build\merged\windows-x86_64\mvvm\0057_mvvm_views_transcript_render.c
 /Fobuild\temp.win-amd64-cpython-313\Release\...\0057_mvvm_views_transcript_render.obj
0057_mvvm_views_transcript_render.c
...（同样的 0058 / 0059 ...）
```

三个 annotation 的 `message` 长度都恰好是 **4096** 字节（`/tmp/ann-132406559544.json`
等，可复算）：

| job id | target | annotation 长度 | 截断 |
|---|---|---|---|
| 132406559544 | windows-arm64 | 4096 | 是 |
| 132406559566 | windows-x86_64 3.8.10 | 4096 | 是 |
| 132406559660 | windows-x86_64 3.13.5 | 4096 | 是 |

GitHub 的 check-run annotation 在第 4096 字符处**从尾部截断、保留开头**。我发出的
是 build.log 的「最后 80 行」，而 Windows 上每条 `cl.exe` 命令行就有一千多字符，
几条就把 4096 用光，**真正的编译错误在末尾，正好被切掉**。所以这些 annotation 里
根本没有编译错误——不是没采到日志，是采的方式在这个平台的日志形态下失效。

这就是任务第 1 项的目标（「不带 token 也能读到失败原文」）在真实失败场景下没有
达成的证据。

### 8.2 根因定位状态：尚未定位（且当前无法在不伪造的前提下定位）

- 作业日志 API：`/repos/.../actions/jobs/<id>/logs` → **403** `Must have admin rights to Repository.`
- artifact 下载：`/repos/.../actions/artifacts/<id>/zip` → **401** `Requires authentication`
- 作业页 HTML（`/actions/runs/<run>/job/<job>`）：200，但只有「Show more」前的截断视图，
  且该视图里没有 build 步骤的日志正文（`Publish build log` 段落只有 4096 字符那份注解内容）
- step summary：仅在登录后的页面渲染，匿名抓不到（`/summary` → 404）

因此**无法读到 build.log 第 15 步的真实结尾**。按任务第 4 项要求，这里明确记为
**真因尚未定位，需要仓库权限或 token**，不用「既有平台问题」糊过去，也不猜一个
编译错误当成结论。

可排除的、有证据的部分：
- 不是缺 MSVC（cl.exe 已实际启动并编译了 0057 → 0059，说明 vcvarsall 正常）；
- 不是 tar 调用（windows-x86 同一份代码这一轮通过，三处 x86_64/arm64 失败点已前移到编译阶段）；
- 三个红 job 都停在合并扩展编译（`build/merged/<target>/mvvm/*.c`），也就是
  `compile_merged_windows_extensions_with_zig` / `_msvc` 这一层，
  且 arm64 的注解停在 pip 下载 `pyside6_*_win_arm64.whl` 之后，
  说明 arm64 另有更早的失败点（PySide6 win_arm64 无 QtWebEngineCore，见 8.3）。

### 8.3 已知会命中但尚未到红点的风险：win_arm64 没有 QtWebEngineCore

PySide6 的 win_arm64 wheel **完全不打包 QtWebEngineCore**（6.9.3–6.12.0 实测，
addons arm64 ≈35 MB 里 0 个 WebEngine 条目；amd64 ≈168 MB）。`windows-arm64`
这个 job 的 target 需要承载 Web 渲染层，产品代码已在 ff89c4c 里改成「缺就不崩」，
但打包/冒烟链路会因此在 arm64 上拿不到渲染层。它是否就是这一轮的失败原因，
需要 build.log 才能确认——在拿到之前不下结论。

## 9. 观测修复（bd3449a）

针对 8.1 的截断缺陷，新增 `tools/ci_tail.py` 并让三处 publisher 全部走它：

- 从整份日志里挑诊断行（`error C####` / `LNK####` / `command line error` /
  Python traceback / pytest `FAILED` …），**每条诊断单独一条 annotation**，
  一条再长也挤不掉别的；
- 额外带一条 `[n/6]` 阶段行，先告诉人卡在构建的哪一步；
- 一条诊断都没有时，退回**从日志尾部往前累加**的 tail，保证如果还截断，截掉的是开头；
- 日志不存在时明说没生成，不编造 exit code（保持 ee6c219 的语义）。

同时调整 `Full integration run`：marker 检查挪到发 annotation 之前。
`build.py --run` 返回 0 但没打印 `DEVA WEB OK` / `bridge=True` 也是失败，
之前这种情况只留一条 exit 0 notice，看不出真因。

验证：`app/tests/test_ci_tail.py` 9 例（含「40 条超长 cl.exe 命令行 + 末尾 C1083」的
真实形态复现、端到端累加、单行超预算、转义顺序、阶段行、缺失日志不编造 exit code、
workflow 不再内联发注解）；变异验证：把 `tail_message` 改成从头部累加、把诊断行
过滤去掉，对应用例立即失败。本地全量 `968 passed, 6 skipped`。

## 10. run 43583651276（head bd3449a）与 run 43583891708（head daec083）

### 10.1 观测修复在真实失败上生效

`bd3449a` 的 windows-arm64 job（id 132413467704）注解原文，与任务第 4 项要求
的「测试名 + 断言行 + 期望/实际」同级别可读：

```
[2/6] Third-party dependencies
ERROR: RuntimeError: Qt pruning: C:\a\ai_upper\ai_upper\.cache\pbs-sdk\windows-arm64\3.13.5\install\python.exe cannot import QtCore, QtGui, QtWebChannel, QtWebEngineCore, QtWebEngineWidgets, QtWidgets:
Traceback (most recent call last):
  File "<string>", line 3, in <module>
  File "C:\a\ai_upper\ai_upper\.cache\pbs-sdk\windows-arm64\3.13.5\install\Lib\importlib\__init__.py", line 88, in import_module
  ...
ModuleNotFoundError: No module named 'PySide6.QtWebEngineCore'
```

同一个 job 的 pytest 注解是 `958 passed, 16 skipped in 68.01s`——单元测试全绿，
红的是打包第 2 步。这与 8.1 里 4096 字符只剩 cl.exe 命令行的状态完全不同：
失败原文不需要 token 就能读到。

原始响应：`out/ci-fix/run-43583651276-jobs.json`、
`out/ci-fix/run-43583891708-annotations/ann-*.json`。

### 10.2 逐 job 结论（run 43583891708，head daec083）

| job | 结论 | 失败步骤 |
|---|---|---|
| Build Tool Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | pass | — |
| native-integration (ubuntu-24.04, linux-x86_64) | pass | — |
| native-integration (ubuntu-24.04-arm, linux-arm64) | pass（抓取时 in_progress） | — |
| native-integration (macos-15, macos-arm64) | pass（抓取时 in_progress） | — |
| native-integration (macos-15-intel, macos-x86_64) | pass（抓取时 in_progress） | — |
| native-integration (windows-2025, windows-x86) | **pass** | — |
| native-integration (windows-2025, windows-x86_64) | **fail** | #15 Full integration build |
| native-integration (windows-2025, windows-x86_64, 3.8.10) | **fail** | #15 Full integration build |
| native-integration (windows-11-arm, windows-arm64) | **fail** | #15 Full integration build |

两个 windows-x86_64 job 的失败原文（job 132414181127 / 132414181128）：

```
[4/6] Package + native dependency closure
ERROR: RuntimeError: Unresolved native dependencies:
```

这就是 9 节 publisher 的残留缺陷：诊断头被单独摘出，紧跟其后的
`  <file>: <library>` 细节行（到底哪几个文件解析不了哪个库）被丢掉。已由
`3ea69b5` 修复（见 11.2）；该 job 的真正库名要等下一个 run 的注解才能给出。

### 10.3 windows-arm64 真因（已定位）

`Qt pruning` 的静态扫描只看「源码里有没有 import」，不区分该 import 是否被
`try/except ImportError` 保护。而 `app/src/mvvm/views/web_shell_window.py:27-34`
正是把 `QtWebEngineCore` / `QtWebEngineWidgets` 放在 `try` 里（ff89c4c 的产品契约：
win_arm64 wheel 没有这块，应用要能起来）。于是：

1. `used_qt_modules()` 把两者列为**必需**；
2. `_runtime_closure()` 用 arm64 解释器强制 import 它们；
3. `ModuleNotFoundError: No module named 'PySide6.QtWebEngineCore'` → `RuntimeError`。

打包层拒绝了应用本身明确支持的 payload。修复见 11.1。

## 11. 修复（f49f8ed、3ea69b5）

### 11.1 可选导入不再被当成必需（f49f8ed）

`tools/ai_upper/qt_prune.py`：

- `_imported_paths()` 返回 `(required, optional)`：位于 `try` 体内、且 handler
  捕获 `ImportError` / `ModuleNotFoundError` / `Exception` / `BaseException` 或
  裸 `except` 的 import 记为可选；handler、`else`、`finally` 里的 import 不受同一
  语句保护，仍算必需；任一处无条件导入即覆盖可选。
- 新增 `qt_module_usage() -> (required, optional)`；`used_qt_modules()` 保留为并集，
  既有调用语义不变。
- `_runtime_closure(site, target, modules, optional=())`：必需模块导入失败仍抛
  `RuntimeError`（部分闭包会删掉 QtCore/QtGui，只会在打包冒烟处炸）；可选模块
  逐个 best-effort `import`，缺了就打印是哪块平台缺件，有就照常并入闭包。
- `configured_modules()` 在 `qt = "imports"` 时用 `qt_module_usage()`；显式数组
  仍全部视为必需（那是用户声明要保留什么，不是对源码的解读）。

对真实源码的判定（本地实跑）：

```
required ['QtCore', 'QtGui', 'QtWebChannel', 'QtWidgets']
optional ['QtWebEngineCore', 'QtWebEngineWidgets']
```

`app/tests/test_qt_prune.py` 新增 6 例：可选分组、无条件导入压过可选、裸 except
与 handler 体不受保护、真实源码契约（WebEngine 只能在 optional 里）、可选缺失
跳过而必需缺失仍报错。本地全量 `977 passed, 6 skipped`。

### 11.2 失败注解带上被缩进的细节行（3ea69b5）

`tools/ci_tail.py` 的 `diagnostic_lines()` 现在把诊断头和它下面连续缩进的细节行
合成**一条**注解（用 `MESSAGE_BUDGET` 截断，头部在前），遇到下一条不缩进的行收束。
这样 `Unresolved native dependencies:` 后面那串具体文件/库名不会再被丢掉。
`app/tests/test_ci_tail.py` 新增 2 例，全量 12 例通过。

### 11.3 提交与远端

```
3ea69b5 ci: 失败注解带上被缩进的细节行
f49f8ed fix(qt): 可选导入的 Qt 模块不再被当成必需
5cfd643 fix(ci): 缺失日志时也尊重调用方指定的 level
```

```
$ GIT_SSH_COMMAND='ssh -i /root/.ssh/fanchcho -o IdentitiesOnly=yes' git push origin develop
   5cfd643..3ea69b5  develop -> develop
PUSH_EXIT=0
$ git rev-parse HEAD
3ea69b53fc6a8801fe3def9edf2439fc11706995
$ git ls-remote origin refs/heads/develop
3ea69b53fc6a8801fe3def9edf2439fc11706995	refs/heads/develop
```

## 12. windows-x86_64 [4/6] 的真因与修复（a48b40a）

### 12.1 真正的库名（本地用真实 win_amd64 wheel 复现）

run 43583891708 的两个 windows-x86_64 job 注解只到
`ERROR: RuntimeError: Unresolved native dependencies:`（细节行被 9 节的
publisher 丢掉）。用真实 win_amd64 wheel（PySide6 6.11.2、cryptography 46.0.3、
pydantic_core 2.41.5 等解压到 `/tmp/winreal/site-packages`）在本地跑同一条
`bundle_native_dependencies()`，未解析集合是：

```
RuntimeError: Unresolved native dependencies:
  site-packages/PySide6/plugins/sqldrivers/qsqlibase.dll: fbclient.dll
  site-packages/PySide6/plugins/sqldrivers/qsqlmimer.dll: MIMAPI64.dll
  site-packages/PySide6/plugins/sqldrivers/qsqloci.dll: OCI.dll
  site-packages/PySide6/plugins/sqldrivers/qsqlpsql.dll: LIBPQ.dll
  site-packages/cryptography/hazmat/bindings/_rust.pyd: bcryptprimitives.dll
  site-packages/pydantic_core/_pydantic_core.cp313-win_amd64.pyd: bcryptprimitives.dll
```

四个 sqldrivers 条目已经被 `[tool.ai_upper.native].exclude` 覆盖——它们是
`_report_pruned()` 的输入，只是那一步在 `package.py` 里、闭包之前。真正没有
任何机制处理的只有 `bcryptprimitives.dll`：

```
bcryptprimitives.dll system? False (修复前) / True (修复后)
bcrypt.dll system? True
```

### 12.2 修复

`tools/ai_upper/native/deps.py:390`：`WINDOWS_HOST_LIBRARIES` 加入
`bcryptprimitives.dll`。它是与 `bcrypt.dll` 同族的 CNG 原语库，Windows 从
Vista 起放在 System32；把它当主机库意味着闭包不复制它，由系统提供并跟随
系统更新。

回归测试 `app/tests/test_native_deployment.py::test_windows_cng_primitives_are_system_provided`：
两个真实文件名（cryptography 的 `_rust.pyd`、pydantic_core 的 `_pydantic_core.pyd`）
导入 `bcryptprimitives.dll` 时闭包返回空列表；`_system_dependency` 在
windows-x86_64/arm64 为真、linux 为假。

### 12.3 修复后本地实跑（与打包同一顺序：先裁剪再闭包）

`out/ci-fix/win-closure-bcryptprimitives-repro.log`：

```
exclude patterns: 28
pruned: PySide6/plugins/sqldrivers/qsqlibase.dll
pruned: PySide6/plugins/sqldrivers/qsqlmimer.dll
pruned: PySide6/plugins/sqldrivers/qsqloci.dll
pruned: PySide6/plugins/sqldrivers/qsqlodbc.dll
pruned: PySide6/plugins/sqldrivers/qsqlpsql.dll
pruned: PySide6/qml/QtQuick/Shapes/DesignHelpers/plugins.qmltypes
pruned: PySide6/qml/QtQuick/Shapes/DesignHelpers/qmldir
pruned: PySide6/qml/QtQuick/Shapes/DesignHelpers/qtquickshapesdesignhelpersplugin.dll
pruned: PySide6/vccorlib140.dll
pruned: shiboken6/vccorlib140.dll
OK: closure resolved, bundled entries = 2208
```

本地全量：`978 passed, 6 skipped`。

### 12.4 提交与远端

```
a48b40a fix(native): bcryptprimitives.dll 由 Windows 提供
3ea69b5 ci: 失败注解带上被缩进的细节行
f49f8ed fix(qt): 可选导入的 Qt 模块不再被当成必需
```

```
$ GIT_SSH_COMMAND='ssh -i /root/.ssh/fanchcho -o IdentitiesOnly=yes' git push origin develop
   3ea69b5..a48b40a  develop -> develop
$ git rev-parse HEAD
a48b40a0bbe24fd61d4511ae9be060a3614d193e
$ GIT_SSH_COMMAND='ssh -i /root/.ssh/fanchcho -o IdentitiesOnly=yes' git ls-remote origin refs/heads/develop
a48b40a0bbe24fd61d4511ae9be060a3614d193e	refs/heads/develop
```

## 13. run 43586127170（head a48b40a）逐 job 结论

### 13.1 汇总

| job | 结论 | 失败步骤 |
|---|---|---|
| Build Tool Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | pass | — |
| native-integration (ubuntu-24.04, linux-x86_64) | pass | — |
| native-integration (ubuntu-24.04-arm, linux-arm64) | pass | — |
| native-integration (macos-15, macos-arm64) | pass | — |
| native-integration (macos-15-intel, macos-x86_64) | pass | — |
| native-integration (windows-2025, windows-x86) | pass | — |
| **native-integration (windows-2025, windows-x86_64)** | **pass** | —（12.2 的修复生效） |
| native-integration (windows-2025, windows-x86_64, 3.8.10) | **fail** | #15 Full integration build |
| native-integration (windows-11-arm, windows-arm64) | **fail** | #18 Full integration run |
| aggregate-artifacts | skipped | —（上游有 job 失败，按设计不发 release 清单） |

即：run 从 5 红降到 2 红；windows-x86_64 的闭包与 arm64 的 Qt pruning 都已通过。

### 13.2 windows-x86_64 3.8.10：注解原文

```
[4/6] Package + native dependency closure
ERROR: RuntimeError: Unresolved native dependencies:
  site-packages\PySide2\Qt5WebEngineCore.dll: USP10.dll
```

真因已定位（无需 token 即可读到，3ea69b5 的细节行在这里直接给出了库名）：
`USP10.dll` 是 Windows 自带的 Uniscribe/复杂文本排版 DLL（System32），
`Qt5WebEngineCore.dll` 是它的正常使用者。它不在 `WINDOWS_HOST_LIBRARIES` 里，
于是被当成 wheel 载荷。这是**同一类**缺陷（系统库清单缺项），不是新问题类。

### 13.3 windows-arm64：注解原文

```
[6/6] Target runtime smoke
File "qt_compat.py", line 107, in utils.qt_compat._QtModule.__init__
File "qt_compat.py", line 89, in utils.qt_compat._binding_module
File "<string>", line 429, in _ai_upper_run
File "C:\a\ai_upper\ai_upper\dist\ai_upper\ai_upper.exe", line 4, in <module>
File "deva_web.py", line 154, in deva_web.main
File "deva_web.py", line 116, in deva_web.run
File "deva_web.py", line 72, in deva_web._create_window
File "web_shell_window.py", line 112, in mvvm.views.web_shell_window.DevaWebWindow.__init__
```

这与 8 节之前的状态不同：`[1/6]…[5/6]` 全过，产物真的起来了，倒在最后一步
建窗口时。`web_shell_window.py:112` 是 `_WEBENGINE_ERROR is not None` 时
主动 `raise ImportError` 的那一行——即 arm64 上没有 QtWebEngine，产品按
ff89c4c 的契约明确拒绝承载渲染层。**这不是崩溃，是产品代码在按设计拒绝。**

### 13.4 两个 job 的性质

- 3.8.10 的 `[4/6]`：**真因已定位**，同一类系统库清单缺项，修法明确（补表 + 用例）。
- arm64 的 `[6/6]`：**真因已定位，但性质是产品契约与 CI 矩阵的矛盾**。
  `windows-11-arm` 这一腿在 `run: true` 下要求打包产物能起 QtWebEngine 界面，
  而 PySide6 从未发布含 QtWebEngineCore 的 win_arm64 wheel（6.9.3–6.12.0 实测
  0 个条目），PySide2 也没有。产品代码的选择是「明确报缺件」，不是「静默降级」。
  因此这一腿要绿，只有两条路可选，且都必须由你拍板（涉及产品能力边界）：
  1. 给 `windows-arm64` 提供渲染层替代（QtWebEngine 以外的承载方式）；
  2. 把该矩阵条目的 `run` 改为 `false`（与 `windows-x86`、`linux-arm64` 同处理），
     只证明构建与打包，不证明界面启动。

我**没有**擅自选 2：那会把「这腿本来也起不来」写成绿灯，属于用配置掩盖能力缺口。
也没有删/跳过任何测试。

### 13.5 13.2 的修复（591c7e3）

`USP10.dll` 加入 `WINDOWS_HOST_LIBRARIES`（与 `dwrite.dll`/`fontsub.dll` 同组）。
本地用真实 PySide2 5.15.2.1 win_amd64 wheel（`/tmp/pyside2wheels`）复现并验证：

- 修复前整树扫描：未解析 = `libpq.dll`（已被 exclude）、`usp10.dll`；
- 先按模板 exclude 裁剪再跑闭包（与 `package.py:333` → `:336` 同序）：

```
pruned: PySide2/plugins/sqldrivers/qsqlodbc.dll
pruned: PySide2/plugins/sqldrivers/qsqlpsql.dll
pruned: PySide2/ucrtbase.dll
pruned: PySide2/vccorlib140.dll
pruned: shiboken2/ucrtbase.dll
pruned: shiboken2/vccorlib140.dll
OK: closure resolved, bundled entries = 1477
```

日志：`out/ci-fix/win-closure-usp10-repro.log`。回归测试
`test_windows_uniscribe_is_system_provided`；本地全量 `979 passed, 6 skipped`。

```
$ git log --oneline -3
591c7e3 fix(native): USP10.dll 由 Windows 提供
a48b40a fix(native): bcryptprimitives.dll 由 Windows 提供
3ea69b5 ci: 失败注解带上被缩进的细节行
$ git ls-remote origin refs/heads/develop
591c7e3d0a38565b3ec9d8e26247a983b541e420	refs/heads/develop
```

### 13.6 windows-arm64 这一腿需要你决策

arm64 的最后一步是产品代码主动拒绝：PySide6 从未发布含 QtWebEngineCore 的
win_arm64 wheel，`web_shell_window.py:109-114` 因此 `raise ImportError` 并带上
底层原文（ff89c4c 的契约）。要让这一腿绿，只有：

1. 为 arm64 提供 QtWebEngine 之外的渲染层承载（产品能力变更）；或
2. 把该矩阵条目改成 `run: false`，只证明构建/打包，不证明界面启动。

我没有代选 2，因为那会把「这条腿本来起不来」配置成绿灯。等你定。

### 13.7 若要把 arm64 这腿做成真绿，可选的技术路径（供决策，未实施）

排查中确认的事实：仓库里存在一个**纯 Qt 控件**的主窗口
`app/src/mvvm/views/deva_main_window.py`（`DevaMainWindow`，左侧会话列表 +
右侧对话/设置 + 状态栏，由 `tests/test_deva_panes.py` 驱动），当前打包入口
`app/src/deva_web.py` 固定装配 `DevaWebWindow`。也就是说 arm64 缺的不是
「任何界面」，而是「QtWebEngine 承载的原版渲染层」。

三条路径，取舍不同：

1. **入口按可用性回退到 `DevaMainWindow`**：`deva_web.py` 在 WebEngine 缺失时
   装配原生窗口，headless 冒烟断言相应改成分支断言。改动最小，但等于产品在
   arm64 上呈现**另一套界面**，与「与原版完全一致」的硬要求冲突——需要你确认
   这是可接受的降级。
2. **矩阵条目 `run: false`**：只证明构建与打包。诚实但放弃了 arm64 界面证据。
3. **等 Qt 提供 arm64 WebEngine**：不在我们控制内，不能作为交付前提。

我不会把 2 悄悄做掉。等你选 1 / 2 / 3。

## 14. run 43588462742（head 591c7e3）逐 job 结论与收尾

### 14.1 逐 job 状态（15 个 job，全部终态）

run：https://github.com/fanchcho/ai_upper/actions/runs/43588462742
（`develop` @ `591c7e3d0a38565b3ec9d8e26247a983b541e420`）

| # | job | 结论 | 说明（含 pytest 数字，读自 check-run 注解） |
|---|---|---|---|
| 1 | Build Tool Python 3.8 | pass | — |
| 2 | Build Tool Python 3.9 | pass | — |
| 3 | Build Tool Python 3.10 | pass | — |
| 4 | Build Tool Python 3.11 | pass | — |
| 5 | Build Tool Python 3.12 | pass | — |
| 6 | Build Tool Python 3.13 | pass | — |
| 7 | native-integration (ubuntu-24.04, linux-x86_64, true) | pass | `980 passed, 5 skipped in 30.90s` |
| 8 | native-integration (ubuntu-24.04-arm, linux-arm64, false) | pass | `980 passed, 5 skipped in 25.82s`（`run:false`，只构建不启动） |
| 9 | native-integration (macos-15, macos-arm64, true) | pass | `979 passed, 6 skipped in 23.18s` |
| 10 | native-integration (macos-15-intel, macos-x86_64, true) | pass | 注解读到的是 Chromium `GPUInfo not initialized on GpuInfoUpdate` 噪声行 |
| 11 | native-integration (windows-2025, windows-x86, false) | pass | `run:false`，只构建不打包 |
| 12 | native-integration (windows-2025, windows-x86_64, true) | pass | 注解读到的是 Chromium GPU 日志噪声行 |
| 13 | **native-integration (windows-2025, windows-x86_64, 3.8.10, …)** | **failure** | 见 14.2：**不是** 591c7e3 之前那个闭包失败 |
| 14 | **native-integration (windows-11-arm, windows-arm64, true)** | **failure** | 见 14.3：已知平台阻塞，按你的决定保持红 |
| 15 | aggregate-artifacts | skipped | 上游有 job 失败，按设计不出 release 清单 |

与你四个问题的对应关系：

- **windows-x86_64 3.8.10 是否因 591c7e3 转绿**：**没有转绿**，但 591c7e3 确实修好了
  它要修的那一层——第 15 步 `Full integration build`（`[4/6]` 打包闭包）这次
  **success**，`USP10.dll` 不再是未解析项。失败点前移到第 18 步 `Full integration run`，
  是另一个真因（14.2）。
- **linux-x86_64 / linux-arm64 / macos-x86_64 / macos-arm64 / windows-x86 / windows-x86_64**：
  六者**仍然全绿**（上表 7–12 行）。
- 仍红的只有 2 个 job（第 13、14 行），原文字节级摘录见下两节。

### 14.2 windows-x86_64 3.8.10：新的真因（已定位）

失败步骤：第 18 步 `Full integration run`（`build.py --run` exit 1）。
注解原文（`run.log (build.py --run exit 1)`，由 ci_tail 从日志里挑出的诊断行）：

```
[6/6] Target runtime smoke
File "<string>", line 452, in <module>
File "<string>", line 429, in _ai_upper_run
File "D:\a\ai_upper\ai_upper\dist\ai_upper\ai_upper.exe", line 4, in <module>
File "deva_web.py", line 154, in deva_web.main
File "deva_web.py", line 116, in deva_web.run
File "deva_web.py", line 62, in deva_web._create_window
File "chat_session_store.py", line 30, in init mvvm.services.chat_session_store
File "chat_models.py", line 15, in init mvvm.models.chat_models
```

job：https://github.com/fanchcho/ai_upper/actions/runs/43588462742/job/132427904497
注解快照：`out/ci-fix/run-43588462742-annotations/ann-132427904497.json`

`chat_models.py:15` 是 `from typing import Annotated, Any, Literal, Optional, Union`。
`typing.Annotated` 在 **Python 3.8 的标准库 `typing` 里不存在**（3.9 才加入）。
核对方式：直接取 CPython `v3.8.10` 的 `Lib/typing.py` 原文，`Annotated` 出现 **0** 次。
所以这是产品代码与 `app/pyproject.toml` 的 `requires-python = ">=3.8,<3.14"` 之间的
契约冲突：源码声明支持 3.8，但 `mvvm/models/chat_models.py` 用了 3.9+ 的名字。

性质与 arm64 那条不同：**这条是工程内可修的**（改导入来源或在模块里补一个兼容定义），
不属于平台能力缺口。本轮按你「只做收尾取证、不开新战线」的约束**没有动手**，
留在未完成清单里（14.5）。

### 14.3 windows-arm64：已知平台阻塞（按你的决定保持红）

失败步骤：第 18 步 `Full integration run`。
注解原文（`run.log (build.py --run exit 1)`）：

```
[6/6] Target runtime smoke
File "qt_compat.py", line 107, in utils.qt_compat._QtModule.__init__
File "qt_compat.py", line 89, in utils.qt_compat._binding_module
File "<string>", line 429, in _ai_upper_run
File "C:\a\ai_upper\ai_upper\dist\ai_upper\ai_upper.exe", line 4, in <module>
File "deva_web.py", line 154, in deva_web.main
File "deva_web.py", line 116, in deva_web.run
File "deva_web.py", line 72, in deva_web._create_window
File "web_shell_window.py", line 112, in mvvm.views.web_shell_window.DevaWebWindow.__init__
```

job：https://github.com/fanchcho/ai_upper/actions/runs/43588462742/job/132427904347
注解快照：`out/ci-fix/run-43588462742-annotations/ann-132427904347.json`
该 job 的 `Unit tests` 步骤本身是绿的（`969 passed, 16 skipped`），红点只在启动烟测。

**记录为已知平台阻塞，不掩盖、不改矩阵：**

- 事实：**PySide6 从未发布 win_arm64 的 `QtWebEngineCore`**（实测 6.9.3 / 6.10.x /
  6.11.2 / 6.12.0 的 win_arm64 wheel，该模块条目均为 0；PySide2 同样没有）。
  核对记录见 `out/ci-fix/REPORT.md` §5.2 与 `out/ci-fix/qt-prune-arm64-repro.log`。
- 产品契约：`ff89c4c` 之后 `app/src/mvvm/views/web_shell_window.py:27-34` 把
  WebEngine 的导入放在 `except ImportError` 后，`DevaWebWindow.__init__`
  （同文件 109-114 行）在缺件时 `raise ImportError` 并带底层原文。
  即：**缺这个组件时明确报错，是产品按设计拒绝，不是崩溃**。
  因此该平台当前**不支持** Web 版界面。
- 触发条件：`.github/workflows/validate.yml` 中该矩阵项的 `run: true`，
  即要求打包产物真启动 Web 界面。
- 你的决定（本轮）：**方案 ③ —— 保持红，等 Qt 发布 arm64 的 WebEngine**。
  因此没有改 `run`、没有回退窗口实现、没有加 skip、没有动矩阵。
- 解除条件：Qt 在 win_arm64 上发布含 QtWebEngineCore 的 wheel 后，本 job 应自然转绿；
  届时无需任何代码改动，直接删除本条阻塞记录即可。

### 14.4 远端一致性

```
$ GIT_SSH_COMMAND='ssh -i /root/.ssh/fanchcho -o IdentitiesOnly=yes' \
    git ls-remote origin refs/heads/develop
591c7e3d0a38565b3ec9d8e26247a983b541e420	refs/heads/develop
$ git rev-parse HEAD
591c7e3d0a38565b3ec9d8e26247a983b541e420
```

两者一致；`959faef`（`docs: 下一轮路线图…`，新增 `docs/ROADMAP-NEXT.md`）在
`git branch -a --contains 959faef` 中同时命中 `develop` 与 `remotes/origin/develop`，
即已在远端 develop 上。

收尾提交推送后（本报告本身与路线图追加记录）：

```
$ GIT_SSH_COMMAND='ssh -i /root/.ssh/fanchcho -o IdentitiesOnly=yes' \
    git ls-remote origin refs/heads/develop
03b8fd1fe28ec06890ce954f5abd882d4a123016	refs/heads/develop
$ git rev-parse HEAD
03b8fd1fe28ec06890ce954f5abd882d4a123016
```

收尾提交：`cc020bf`（本报告正文 + 本地 pytest 原始日志）、`7903f44`（路线图阻塞记录）、
`03b8fd1`（远端 sha 与逐 job 表快照）、`④`（补记本小节）。推送均为快进
（`591c7e3..7903f44`、`7903f44..03b8fd1`），无重写、无 force。最终 sha 见交付回复。

### 14.5 收尾账目

改名覆盖（`8baf77d` 代码 + `8e4ecda` 兼容 + `496255b` 文档，75 个文件的内容改写清单
见 `out/rename/content-rename.txt`，旧名文件清单见 `out/rename/old-name-files.txt`）：

| 面 | 现状 |
|---|---|
| 包 / import | `tools/py_upper/` → `tools/ai_upper/`（`tools/py_upper` 已不存在）；测试文件 `test_py_upper_config.py` → `test_ai_upper_config.py` |
| 打包元数据 | `app/pyproject.toml`（模板同名）`[project] name = "ai_upper"`，版本 0.17.33 |
| 产品名 | `[tool.ai_upper.app].name = "ai_upper"`（唯一真相源，编译进 launcher 为 `AI_UPPER_APP_NAME`） |
| 可执行名 | Linux `dist/ai_upper/ai_upper`；Windows `dist/ai_upper/ai_upper.exe`；macOS `dist/ai_upper.app/Contents/MacOS/ai_upper` |
| 窗口标题 | 运行日志实测 `DEVA WEB OK ... title='ai_upper'`（`out/packaging/launch11.log:18`） |
| 配置 / 数据目录 | 数据根 `AI_UPPER_HOME` → 缺省 `~/.ai_upper`；旧名 `DEVA_HOME` / `~/.deva` 仍可读（`app/src/utils/app_home.py`）。构建侧锁文件 `ai_upper.lock.json`、运行时/SDK 缓存标记均回退读旧名（`tools/ai_upper/config.py:20-28`） |
| 兼容层 | 旧配置段 `[tool.py_upper]` 仍被读、新段优先（`config.py:218-222`）；launcher 同时导出 `AI_UPPER_HOME` 与 `PY_UPPER_HOME`（`launcher/src/AiUpper.cpp:881,899`） |
| 最终产物 | `dist/ai_upper/`（目录式产物），内含 `ai_upper` 可执行、`bundle/ai_upper.dat`（8,112,793 B）、`assets/`、`runtime/`、`site-packages/` |

本地全量 pytest（**HEAD 591c7e3**，本轮重跑，原始日志在 `out/ci-fix/closeout/`）：

| 条件 | 结果 | 日志 |
|---|---|---|
| `patchelf` 在 `PATH` | `980 passed, 5 skipped in 24.64s`，EXIT=0 | `out/ci-fix/closeout/pytest-head-patchelf.log` |
| `patchelf` 不在 `PATH` | `979 passed, 6 skipped in 24.80s`，EXIT=0 | `out/ci-fix/closeout/pytest-head-nopatchelf.log` |

两组之差就是 1 条用例（`test_native_deployment.py:177`，缺 `patchelf` 时 skip），
与文档记录的「有/无 patchelf 差 1 skip」一致。历史 14:11/13:55 那两组是 957/953，比现在少，
是因为之后又落了测试与修复；以本轮 HEAD 上的 980/979 为准。

CI 各 job 最终状态见 14.1（13 绿 / 2 红 / 1 skipped）。

### 14.6 未完成与阻塞（如实列出）

1. **windows-arm64（已知平台阻塞，等你拍板的上游条件）**：Qt 未发布 win_arm64 的
   QtWebEngineCore；按你的决定保持红，不改矩阵、不 `run:false`、不加 skip。
2. **windows-x86_64 3.8.10（真因已定位，未修）**：`typing.Annotated` 在 Python 3.8
   不存在，与 `requires-python >=3.8` 冲突。本轮只做取证，未动代码。
3. **aggregate-artifacts（skipped）**：不是缺陷，是「上游有 job 失败就不出 release
   清单」的设计；上面两条任一为红时它必然 skipped。
