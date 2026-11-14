# windows-x86_64 3.8.10 收尾报告

HEAD: `bccaee8`（develop），远端 `refs/heads/develop` 已确认一致。

## 一句话结论

**是**：3.8.10 这条 leg 的四处运行期兼容缺陷已在真实 CPython 3.8.20 + pydantic 2.10.6
上逐一复现、修好、并用守卫用例锁死；本地打包与产物启动均通过。CI 最终结论见文末
「逐 job 结论表」——以远端 run 的终态为准。

## 1. 改动范围自检

`git diff --stat bb6e9ac..bccaee8`（提交前为工作区）：

| 文件 | 增删 | 主题 |
|---|---|---|
| `app/src/mvvm/models/chat_models.py` | +26/−18 | fix(py38) |
| `app/src/mvvm/services/effort.py` | +5/−2 | fix(py38) |
| `app/src/mvvm/services/provider_gateway.py` | +7/−2 | fix(py38) |
| `tools/ai_upper/third_party.py` | +5/−1 | fix(py38) |
| `app/requirements.txt` | +6/−0 | build(py38) |
| `.github/workflows/validate.yml` | +10/−1 | build(py38) |
| `app/tests/test_py38_compat.py` | +363（新文件） | test(py38) |

`out/ci-fix/closeout/*` 为取证文件（chore(evidence) / docs(py38)）。

**范围核对**：只有上述 7 个代码/配置文件 + 取证文件；`app/requirements.txt` 的
keyring 两处注释完好（全文 18 行 `#`，第 15 行含 "Secret Service"）。
每个改动到清查条目的映射见 `py38-compat-audit.md` 第二节。

## 2. 依赖闭环

- 3.8：`pydantic==2.10.6` 要求 `typing-extensions>=4.12.2`；`typing_extensions==4.13.2`
  同时装于 `/tmp/venv38`，`pip install --dry-run` 报 "Requirement already satisfied"。
- 3.9+：环境标记不生效，打包实测 pip 输出
  `Ignoring typing_extensions: markers 'python_version < "3.9"' don't match your environment`，
  随后由 pydantic 2.14.3 拉 `typing_extensions-4.16.0`。
- 证据：`py38-dependency-closure-final.log`、`py38fix-build3.log`。

## 3. 真 3.8 全量 import

- `app/src` 78 个模块 → **INCOMPATIBLE 0**；MISSING-DEP 5（全部是
  "No Qt binding found"，本机没装 PySide2 的 cp38 linux-aarch64 轮子，不计为兼容性失败）。
- `tools` 30 个模块 → INCOMPATIBLE 0、MISSING-DEP 0。
- 证据：`py38-import-sweep-final.log`、`py38-import-sweep-tools.log`。

## 4. 全量 pytest

| 组 | 结果 | 退出码 |
|---|---|---|
| 带 patchelf | **985 passed, 5 skipped** | 0 |
| 无 patchelf | **984 passed, 6 skipped** | 0 |
| CI 同款调用（`cd app && pytest tests`） | 985 passed, 5 skipped | 0 |

skip 明细见 `-rs`（`py38fix-final-pytest-*.log`）。无用例被删除或新增 skip。

**关于基线的说明（必须澄清）**：任务给的基线是 939/5 与 938/6，这两组数字来自
`out/baseline-pytest-app.log`（939/5）和 `out/packaging/pytest-full.log`（938/6）——
它们生成于改名提交 `8baf77d` 之前，skip 文案里还写着旧名 `PY_UPPER_E2E`。
改名之后 `8baf77d..591c7e3` 之间新增了 41 个 test def（`test_ci_tail.py`、
`test_app_home.py`、`test_qt_prune.py` 等），所以同一套代码的收集数变成 980/979。
本次再 +5（新增守卫用例）→ 985/984。三个数字的对应关系：939+41=980，980+5=985；
938+41=979，979+5=984。**skip 数没有变化（5 与 6）**，差的 1 条是
`test_native_deployment.py:177 requires cc, patchelf and readelf`，只在无 patchelf 组出现。

## 5. 打包与启动

```
BUILD_EXIT=0
READY: /home/agent/shared_workspace/py_upper/dist/ai_upper
SMOKE PASS 6 modules (launcher registers merged bundles)
SMOKE PASS launcher
```

产物：`dist/ai_upper/ai_upper`（499 MB 目录）。实跑（xvfb + `AI_UPPER_HEADLESS=1`）：

```
DEVA WEB OK platform=offscreen title='ai_upper' url=.../dist/ai_upper/assets/renderer/index.html bridge=True
LAUNCH_EXIT=0
```

证据：`py38fix-build3.log`、`py38fix-launch.log`。

本机环境注意（与仓库改动无关）：`.venv/bin/python` 是指向 `/usr/bin/python3.13`
的软链、后者没有 pip，所以打包要用 `.venv/bin/python-real`；`cmake -G Ninja`
需要 `.venv/bin` 在 PATH 里。

## 6. 提交

```
db2b416 fix(py38): 让运行期类型表达式在 Python 3.8 上可求值
069e31f build(py38): 声明 typing_extensions 并只钉在 3.8
cc3a0d5 test(py38): 按求值时机钉住 3.8 兼容性守卫
769e071 chore(evidence): 3.8 兼容修复的清查、实测与变异记录
bccaee8 docs(py38): 清查表补「改动 → 条目」对照
```

`git push origin develop`：`769e071..bccaee8`，无 `--force`。
远端 `refs/heads/develop` = `bccaee8`（`git ls-remote` 实测）。

## 7. 变异记录

五条变异（`py38-mutation-{0..5}*.log`）都包含「守卫结果 + 真 3.8 结果」：

| 变异 | 守卫 | 真 3.8 |
|---|---|---|
| 0 基线 | 5 passed | import ok |
| 1 裸 `from typing import Annotated` | 2 failed | `ImportError: cannot import name 'Annotated'` |
| 2 `LevelMap = dict[str, str]` | 1 failed | `TypeError: 'type' object is not subscriptable` |
| 3 `StreamEvent = A \| B` | 1 failed | `TypeError: unsupported operand type(s) for \|` |
| 4 `str.removesuffix` | 1 failed | `AttributeError: 'str' object has no attribute 'removesuffix'` |
| 5 pydantic 字段 `list[ImagePart]` | 1 failed | pydantic `Unable to evaluate type annotation` |

第一次生成时变异 3/5 的真 3.8 记录用的是没有第三方包的裸解释器，因此误报为
`ModuleNotFoundError: typing_extensions`；已改用 `/tmp/venv38`（3.8.20 + pydantic
2.10.6 + typing_extensions 4.13.2）重跑，现记录的是真实缺陷。文件头已注明来源。

## 8. CI 逐 job 结论

见文末追加。
