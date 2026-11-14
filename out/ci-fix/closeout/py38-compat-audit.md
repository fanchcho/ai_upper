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

未改动但已确认安全的条目：2–8、11–15、17–20（见上表判定列）。
