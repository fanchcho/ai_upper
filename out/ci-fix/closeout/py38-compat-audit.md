# Python 3.8 运行期兼容性清查（ai_upper @ 591c7e3）

目的：`windows-x86_64 3.8.10` 这一腿在 CI 第 18 步启动时红，最内层帧是
`app/src/mvvm/models/chat_models.py:15` 的 `from typing import Annotated`。
一次只修这一处会随后被下一处打回，所以先把**全部** 3.9+/3.10+ 特性按
「运行期 / 仅注解期」逐条判定。

判定口径（重要）：`from __future__ import annotations` 只把 **函数/变量注解**
变成字符串，**不会**推迟下面几类求值：

1. 模块级**赋值**里对类型的下标/并集运算（`X = dict[str, str]`、`A = B | C`）；
2. **基类**表达式（`class C(Generic[T])`、`class C(Protocol[...])`）；
3. `@dataclass` 的**字段注解**——dataclasses 会 `get_type_hints` 解析它们；
4. **pydantic** 模型字段注解——pydantic 在类创建时就解析（3.8 由
   `typing_extensions` 提供 `Annotated`，但名字必须先能**导入**）；
5. 类型别名被当作**值**传给 `Annotated[...]` 之外的运行期 API。

扫描方法：`ast` 遍历全部 `app/src`、`tools`、`app/tests`（排除 `_vendor`），
识别「不在注解位置」的 `list/dict/tuple/set/type` 下标与 `|` 运算；再用
`ast.parse(..., feature_version=(3, 8))` 校验 3.8 语法。

## 一、逐条判定

| # | 特性 | 3.8 是否可用 | 判定 | 命中位置 |
|---|---|---|---|---|
| 1 | `typing.Annotated` | 否（3.9+；3.8 只有 `typing_extensions.Annotated`） | **运行期**——被 `Annotated[...]` 与 `Field(...)` 在模块顶层求值 | `app/src/mvvm/models/chat_models.py:15, 106` |
| 2 | `typing.ParamSpec` | 否（3.10+） | 未使用 | — |
| 3 | `typing.TypeAlias` | 否（3.10+） | 未使用 | — |
| 4 | `typing.Concatenate` | 否（3.10+） | 未使用 | — |
| 5 | `typing.TypeGuard` | 否（3.10+） | 未使用 | — |
| 6 | `typing.Self` | 否（3.11+） | 未使用（`Self` 只出现在 pydantic 自己内部） | — |
| 7 | `typing.Unpack` | 否（3.11+） | 未使用 | — |
| 8 | 内置泛型 `list[str]` 等**在注解里** | 否（3.9+），但 63/78 个 `app/src` 模块有 `from __future__ import annotations` | 仅注解期（字符串化），**安全**；但见第 9 条的两个例外 | 见下 |
| 9 | 内置泛型**在运行期值位置** | 否（3.9+） | **运行期**——两处需要修 | `app/src/mvvm/services/effort.py:51`（`LevelMap = dict[str, str]`，模块级赋值，3.8 抛 `TypeError: 'type' object is not subscriptable`）；`app/src/mvvm/models/chat_models.py` 的 pydantic 字段 `Optional[list[ImagePart]]` 等（pydantic 运行期解析） |
| 10 | `str.removeprefix` / `removesuffix` | 否（3.9+） | **运行期**——构建工具里 | `tools/ai_upper/third_party.py:166`（`dist_info.name.removesuffix(".dist-info")`） |
| 11 | `functools.cache` | 否（3.9+） | 未使用 | — |
| 12 | `zoneinfo` | 否（3.9+） | 未使用 | — |
| 13 | `graphlib` | 否（3.9+） | 未使用 | — |
| 14 | `math.lcm` | 否（3.9+） | 未使用 | — |
| 15 | `dict |` 合并运算（PEP 584） | 否（3.9+） | 未使用（`{**a, **b}` 拼字典，3.5+ 可用） | `app/src/mvvm/services/effort.py:54-58` 用的是 `{**LMH, ...}`，安全 |
| 16 | 类型**并集** `A | B`（PEP 604）在值位置 | 否（3.10+） | **运行期**——需要修 | `app/src/mvvm/services/provider_gateway.py:306`（`StreamEvent = TextDelta | ... | Done`，模块级赋值） |
| 17 | `A | B` 出现在**注解**里 | 否（3.10+），被 future import 字符串化 | 仅注解期，安全 | 多处，如 `app/src/utils/paths.py:42`、`app/src/mvvm/services/workspace_guard.py:61` |
| 18 | `sys.stdlib_module_names` | 否（3.10+） | 仅测试代码，且只在 3.13 的解释器上跑 | `app/tests/test_app.py:165` |
| 19 | `tomllib` | 否（3.11+） | 已由 `tools/ai_upper/compat.py` 回退到 vendored `tomli` | `tools/ai_upper/config.py:11` |
| 20 | 3.10 `match` 语句 / 3.9 括号化 `with` / 3.11 `except*` | — | 未使用；`ast.parse(feature_version=(3,8))` 对全部源码 0 失败 | — |

## 二、改动 → 清查条目对照（提交 db2b416 / 069e31f）

| 改动文件 | 改了什么 | 对应条目 | 为什么必须改 |
|---|---|---|---|
| `app/src/mvvm/models/chat_models.py` | `Annotated` 按 `sys.version_info >= (3, 9)` 分支，3.8 从 `typing_extensions` 导入 | 第 1 条 | 3.8 的 `typing` 没有这个名字，裸导入即 `ImportError`（红 job 的最内层帧） |
| `app/src/mvvm/models/chat_models.py` | pydantic 字段 `list[...]`/`dict[...]` → `typing.List`/`typing.Dict` | 第 9 条 | pydantic 2.x 建类时调 `get_type_hints`，future import 不生效；实测 3.8 报 `Unable to evaluate type annotation` |
| `app/src/mvvm/services/effort.py` | `LevelMap = dict[str, str]` → `typing.Dict[str, str]` | 第 9 条 | 模块级赋值是运行期求值，3.8 抛 `TypeError: 'type' object is not subscriptable` |
| `app/src/mvvm/services/provider_gateway.py` | `StreamEvent = A \| B \| ...` → `typing.Union[...]` | 第 16 条 | PEP 604 的 `type.__or__` 3.10 才有，3.8/3.9 抛 `TypeError: unsupported operand type(s) for \|` |
| `tools/ai_upper/third_party.py` | `str.removesuffix` → 切片 | 第 10 条 | `removesuffix` 是 3.9+；构建工具要在 3.8 上跑 |
| `app/requirements.txt` | `typing_extensions==4.13.2; python_version < "3.9"` | 第 1 条（依赖侧） | 3.8 分支直接导入它，必须显式声明且只钉 3.8 |
| `.github/workflows/validate.yml` | py38 matrix 依赖清单加 `typing_extensions==4.13.2` | 第 1 条（依赖侧） | 该 leg 不复用 `app/requirements.txt`，清单是手写的 |
| `app/tests/test_py38_compat.py`（新增） | 5 条守卫用例 | 1 / 9 / 10 / 16 | 防止同类回归；条目 9 的 pydantic 子类需要追本地继承链 |

## 三、第二轮追加（提交 158a36c / c49161b / 28aeec5）

第二轮红点不在语言特性层，而在 Qt binding 能力层——第一轮修完「能导入」之后，
打包产物冒烟（`[6/6] Target runtime smoke`）才把它暴露出来。

| 改动文件 | 改了什么 | 对应条目 | 为什么必须改 |
|---|---|---|---|
| `app/src/mvvm/views/web_shell_window.py` | 类体按名探测 `QWebEngineScript`/`QWebEngineSettings`/`QWebEngineView`，替代写死 `QtWebEngineCore.*` | 第 21 条（binding 类布局差异） | Qt6 把 Script/Settings 放 `QtWebEngineCore`，Qt5 的 PySide2 全放 `QtWebEngineWidgets`；写死一边必炸 |
| `app/src/deva_web.py` | readiness 探测改为 JS `String(...)` 回报、Python 侧比 `"true"` | 第 22 条（`runJavaScript` 布尔转换差异） | PySide6 6.6 把 JS bool 转成空串，6.11 才转 bool；按真假判断在 6.6 上永远读不到就绪 |
| `.github/workflows/validate.yml` | 3.8.10 leg 的 `PySide2==5.15.2.1` → `PySide6==6.6.3` | 第 23 条（Qt 自带 Chromium 版本） | PySide2 5.15 是 Chromium 83，渲染产物无保护使用 `Object.hasOwn`（Chromium 93+）；不改会得到「冒烟 OK、渲染链接时抛错」的假绿 |
| `app/tests/test_web_shell_modules.py` | 新增 3 条守卫 | 21 / 22 | 两种子模块布局各测一遍；都缺时抛 ImportError；探测格式与判定表达式钉死 |
| `app/tests/test_build_tool_compat.py` | 断言改为 PySide6 6.6.3，并遮罩矩阵覆盖行再查默认依赖来源 | 23 + 依赖侧 | 原来断言 PySide2，是上一轮的错误决定 |

第 21–23 条是新判定的类别，不在第一轮条目表（1–20）里：那一轮只按「语言特性 →
运行期/注解期」判定，没有覆盖「同一个类名在不同 Qt binding 的不同子模块」与
「同一调用在不同 binding 版本的返回值转换」。这两类只会在打包产物真正跑起来时显形。


## 四、第三轮追加（原生依赖闭包，非语言特性）

第三轮的红点在**打包流水线的原生依赖闭包**，既不是语言特性也不是 Qt binding API：
它只在目标机（Windows）跑 `[4/6]` 时才显形，本机 Linux 无法复现出同一条错误。

| 改动文件 | 改了什么 | 为什么必须改 |
|---|---|---|
| `tools/ai_upper/native/deps.py` | `WINDOWS_HOST_LIBRARIES` 增加 `bluetoothapis.dll` | PySide6 6.6.3（最后一个 cp38 版本）的 `Qt6WebEngineCore.dll` 在载入期导入 System32 的 `BluetoothApis.dll`；不在宿主库清单里就被判为 wheel 负载，整个 3.8.10 leg 在 `[4/6]` 失败。6.11.2 已不再导入它，所以只有 3.8.10 这条 leg 会撞上 |
| `app/tests/test_native_deployment.py` | 新增 `test_windows_web_bluetooth_is_system_provided` | 把「Windows 为真、Linux/macOS 为假、闭包为空」钉住，与已有的 `bcryptprimitives`/`usp10`/`msi` 同型 |

证据：`out/ci-fix/verify-round3/bluetoothapis-closure.log`（直接读 6.6.3 与 6.11.2
四个 win_amd64 wheel 的 PE 导入表做对比）。

这一条不属于第 1–23 条的任何一类：前 23 条都是「Python 代码/绑定 API 在 3.8 上行为
不同」，而这条是「目标平台本来就提供的系统 DLL 没被登记为宿主库」。同类缺口在历史
上出现过两次（`bcryptprimitives.dll`、`usp10.dll`），都是补清单而不是改代码。
