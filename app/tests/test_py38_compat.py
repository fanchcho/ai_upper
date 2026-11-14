"""守卫：应用与构建工具必须能在 Python 3.8 上 import 成功。

背景：`windows-x86_64 3.8.10` 这条 CI leg 在第 18 步启动时红，最内层帧是
`mvvm/models/chat_models.py` 的 `from typing import Annotated`。修掉那一行后
还有三处会依次打回来（`LevelMap = dict[str, str]`、`StreamEvent = A | B`、
`str.removesuffix`），所以这里按**求值时机**而不是按文件把规则钉住。

关键事实（决定了本文件的判定口径）：`from __future__ import annotations` 只把
函数/变量**注解**变成字符串，不会推迟下面几类求值——

1. 模块级/类体**赋值右侧**的类型表达式（`X = dict[str, str]`、`A = B | C`）；
2. **基类**表达式与类关键字参数；
3. ``@dataclass`` 字段注解——`get_type_hints` 会解析；
4. **pydantic** 模型字段注解——pydantic 在建类时就解析（实测 3.8 + pydantic
   2.10.6 报 `Unable to evaluate type annotation 'Optional[list[ImagePart]]'`）。

所以本文件检查的是「会被运行期求值的位置」，而不是「所有出现过的写法」：
函数签名里的 `list[str]` 有 future import 保护，不算违规。

变异检验（见 out/ci-fix/closeout/py38-mutation-*.log）：把任一修复退回旧写法，
本文件立即变红。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

# 3.8 的 typing 里没有这些名字。typing_extensions 也不能替代其中每一个
# （例如 TypeGuard 在 3.8 的 typing_extensions 4.13 里有，但本工程不需要），
# 因此这里只要求「不能从 typing 导入」——用不用 typing_extensions 由调用点决定。
MISSING_FROM_38_TYPING = {
    "Annotated",
    "Concatenate",
    "ParamSpec",
    "Self",
    "TypeAlias",
    "TypeAliasType",
    "TypeGuard",
    "Unpack",
}

# 3.9+ 才能下标的内置类型（PEP 585）。
BUILTIN_GENERICS = {"list", "dict", "tuple", "set", "frozenset", "type"}

# 3.9+ 才有的运行期 API。
MISSING_API_CALLS = {"removesuffix", "removeprefix"}

# 3.9+/3.10+ 才有的模块。
MISSING_MODULES = {"zoneinfo", "graphlib"}


def _project_roots():
    """`app/src` and the repository's `tools` directory."""
    app = Path(__file__).resolve().parents[1]
    return [app / "src", app.parent / "tools"]


def _sources():
    for root in _project_roots():
        for path in sorted(root.rglob("*.py")):
            if "_vendor" in path.parts or "__pycache__" in path.parts:
                continue
            yield path


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _annotation_offenders(node):
    """PEP 585 / PEP 604 constructs in an annotation expression."""
    found = []
    for child in ast.walk(node):
        if isinstance(child, ast.Subscript) and isinstance(child.value, ast.Name):
            if child.value.id in BUILTIN_GENERICS:
                found.append((child.lineno, "%s[...]" % child.value.id))
        elif isinstance(child, ast.BinOp) and isinstance(child.op, ast.BitOr):
            found.append((child.lineno, "A | B"))
    return found


def _value_offenders(node):
    """Same, for expressions evaluated at import time.

    ``A | B`` on plain integers (``stat.S_IXUSR | stat.S_IXGRP``) is not a type
    union, so a union operand has to look like a type: a locally defined class
    name or any capitalised name. That keeps the rule precise instead of
    flagging every bitwise or.
    """
    found = []
    for child in ast.walk(node):
        if isinstance(child, ast.Subscript) and isinstance(child.value, ast.Name):
            if child.value.id in BUILTIN_GENERICS:
                found.append((child.lineno, "%s[...]" % child.value.id))
        elif isinstance(child, ast.BinOp) and isinstance(child.op, ast.BitOr):
            operands = _flatten_union(child)
            names = [o for o in operands if isinstance(o, ast.Name)]
            if any(name.id[:1].isupper() for name in names):
                found.append((child.lineno, "A | B"))
    return found


def _flatten_union(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flatten_union(node.left) + _flatten_union(node.right)
    return [node]


def _class_scope_offenders(cls, pydantic_models=()):
    """Class-body assignments, plus field annotations only for pydantic models.

    The distinction is measured, not assumed. On 3.8 a ``@dataclass`` with a
    future import stores the *string* in ``__annotations__`` and never
    evaluates it -- a dataclass declaring ``x: dict[str, int]`` loads fine
    (verified on CPython 3.8.20). pydantic 2.x is different: it calls
    ``get_type_hints`` while creating the class, so
    ``images: Optional[list[ImagePart]]`` fails on 3.8 with
    ``Unable to evaluate type annotation`` regardless of the future import.

    So field annotations are only a hazard for classes derived from
    ``BaseModel``; everywhere else the annotation position is lazy and the
    module-level assignments below are the real risk.

    ``pydantic_models`` carries the module's own inheritance chain: the models
    here derive from a shared ``_Model(BaseModel)`` base rather than naming
    ``BaseModel`` directly, and missing that indirection is exactly the gap
    that let a ``dict[str, int]`` field slip past this check during mutation
    testing (the real 3.8 interpreter failed to import the module while the
    guard stayed green).
    """
    found = []
    pydantic_model = any(
        (isinstance(base, ast.Name) and (base.id == "BaseModel" or base.id in pydantic_models))
        or (isinstance(base, ast.Attribute) and base.attr == "BaseModel")
        for base in cls.bases
    )
    for statement in cls.body:
        if isinstance(statement, ast.AnnAssign):
            if pydantic_model:
                found.extend(_annotation_offenders(statement.annotation))
            if statement.value is not None:
                found.extend(_value_offenders(statement.value))
        elif isinstance(statement, ast.Assign):
            found.extend(_value_offenders(statement.value))
        elif isinstance(statement, ast.ClassDef):
            found.extend(_class_scope_offenders(statement, pydantic_models))
    return found


def _pydantic_model_names(tree):
    """Names of classes in one module that pydantic will resolve at class creation.

    Resolved to a fixed point so a chain such as ``_Model(BaseModel)`` ->
    ``TextPart(_Model)`` is covered. Only same-module bases are considered;
    a cross-module base would need import resolution, and the models that
    matter all live in one module.
    """
    known = set()
    changed = True
    while changed:
        changed = False
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name in known:
                continue
            for base in node.bases:
                name = None
                if isinstance(base, ast.Name):
                    name = base.id
                elif isinstance(base, ast.Attribute):
                    name = base.attr
                if name == "BaseModel" or name in known:
                    known.add(node.name)
                    changed = True
                    break
    return known


def _import_time_offenders(tree):
    """Everything the module evaluates while it is being imported."""
    models = _pydantic_model_names(tree)
    found = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            found.extend(_value_offenders(statement.value))
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            found.extend(_value_offenders(statement.value))
        elif isinstance(statement, ast.ClassDef):
            for base in statement.bases:
                found.extend(_value_offenders(base))
            for keyword in statement.keywords:
                found.extend(_value_offenders(keyword.value))
            found.extend(_class_scope_offenders(statement, models))
    return found


def test_import_time_type_expressions_are_python38_safe():
    """No PEP 585/604 construct in a position the interpreter evaluates on import.

    These are exactly the sites that the future import cannot rescue. A
    regression here is invisible on 3.9+ and kills the 3.8 leg on startup.
    """
    problems = []
    for path in _sources():
        tree = _parse(path)
        for line, what in _import_time_offenders(tree):
            problems.append("%s:%d: %s evaluated at import time" % (path, line, what))
    assert not problems, (
        "PEP 585/604 constructs that Python 3.8 evaluates at import time "
        "(use typing.List / typing.Dict / typing.Union instead):\n" + "\n".join(problems)
    )


def test_no_python39_typing_names_imported_from_typing():
    """`typing.Annotated` does not exist on 3.8.

    A bare ``from typing import Annotated`` is the original red: it fails at
    import on 3.8 with ``ImportError: cannot import name 'Annotated'``. The
    only allowed form is inside a branch that cannot be taken on 3.8, i.e.
    guarded by ``sys.version_info >= (3, 9)`` -- which is what the test below
    pins down for chat_models.py.
    """
    problems = []
    for path in _sources():
        tree = _parse(path)
        guarded = _version_guarded_lines(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "typing":
                for alias in node.names:
                    if alias.name in MISSING_FROM_38_TYPING and node.lineno not in guarded:
                        problems.append(
                            "%s:%d: from typing import %s" % (path, node.lineno, alias.name)
                        )
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "typing" and node.attr in MISSING_FROM_38_TYPING:
                    problems.append("%s:%d: typing.%s" % (path, node.lineno, node.attr))
    assert not problems, (
        "names that do not exist in Python 3.8's typing module outside a "
        "version guard:\n" + "\n".join(problems)
    )


def _version_guarded_lines(tree):
    """Line numbers that sit under an ``if sys.version_info >= (3, 9)`` branch."""
    guarded = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare):
            continue
        left = test.left
        if not (isinstance(left, ast.Attribute) and left.attr == "version_info"
                and isinstance(left.value, ast.Name) and left.value.id == "sys"):
            continue
        if not isinstance(test.ops[0], (ast.GtE, ast.Gt)):
            continue
        comparator = test.comparators[0]
        if isinstance(comparator, ast.Tuple):
            guarded.update(statement.lineno for statement in node.body)
    return guarded


def test_no_python39_only_runtime_apis():
    """`str.removesuffix` / `zoneinfo` / `graphlib` are 3.9+.

    The build tool itself runs on 3.8 in the `build-tool-compat` job, so a 3.9+
    call there fails a job that has nothing to do with the application.
    """
    problems = []
    for path in _sources():
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Attribute) and node.attr in MISSING_API_CALLS:
                problems.append("%s:%d: .%s(" % (path, node.lineno, node.attr))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in MISSING_MODULES:
                        problems.append("%s:%d: import %s" % (path, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in MISSING_MODULES:
                    problems.append("%s:%d: from %s import" % (path, node.lineno, node.module))
    assert not problems, (
        "APIs and modules that only exist from Python 3.9:\n" + "\n".join(problems)
    )


def test_chat_models_selects_annotated_by_version_not_by_exception():
    """The 3.8 fallback must be an explicit version check.

    ``try: from typing import Annotated / except ImportError: from
    typing_extensions import ...`` would also mask a missing typing_extensions
    install: the app would then fail on the next name instead of at the import
    that says what is wrong. The version check is also what the CI pin list is
    derived from, so it has to be readable statically.
    """
    path = Path(__file__).resolve().parents[1] / "src" / "mvvm" / "models" / "chat_models.py"
    tree = _parse(path)

    guarded = False
    for node in tree.body:
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        left = node.test.left
        if not (isinstance(left, ast.Attribute) and left.attr == "version_info"
                and isinstance(left.value, ast.Name) and left.value.id == "sys"):
            continue
        for comparator in node.test.comparators:
            if isinstance(comparator, ast.Tuple) and len(comparator.elts) == 2:
                if all(isinstance(e, ast.Constant) for e in comparator.elts):
                    if tuple(e.value for e in comparator.elts) == (3, 9):
                        guarded = True
    assert guarded, "chat_models.py must branch on `sys.version_info >= (3, 9)`"

    # 3.8 分支里必须真的导入 typing_extensions。
    else_imports = set()
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            for branch in node.orelse:
                if isinstance(branch, ast.ImportFrom) and branch.module == "typing_extensions":
                    else_imports.update(alias.name for alias in branch.names)
    assert "Annotated" in else_imports, (
        "the else branch of the version check must import Annotated from typing_extensions"
    )

    # 不许用 try/except ImportError 把缺依赖吞掉。
    for node in tree.body:
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                names = []
                if isinstance(handler.type, ast.Name):
                    names = [handler.type.id]
                elif isinstance(handler.type, ast.Tuple):
                    names = [e.id for e in handler.type.elts if isinstance(e, ast.Name)]
                assert "ImportError" not in names, (
                    "the Annotated fallback must not swallow ImportError; "
                    "a missing typing_extensions has to fail loudly"
                )


def test_typing_extensions_is_a_declared_runtime_dependency():
    """3.8 gets `Annotated` from typing_extensions, so it has to be bundled.

    Cython compiles the app's own modules and the bundler installs exactly
    ``app/requirements.txt``; a name imported but not declared is absent from
    the packaged runtime, and the failure only shows up when the artifact
    starts on 3.8.
    """
    app = Path(__file__).resolve().parents[1]
    declared = []
    for line in (app / "requirements.txt").read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry and not entry.startswith("-"):
            declared.append(entry)
    matching = [entry for entry in declared if entry.lower().startswith("typing_extensions")]
    assert matching, "app/requirements.txt must declare typing_extensions for the 3.8 bundle"
    entry = matching[0]
    # 4.14.0 起 Requires-Python >=3.9，装不上 3.8；用环境标记把它限定在 3.8，
    # 因为 pydantic 2.14.3 要求 typing-extensions>=4.16.0。
    assert 'python_version < "3.9"' in entry, (
        "typing_extensions must be pinned to 3.8 only: pydantic 2.14.3 requires >=4.16.0"
    )
    assert "4.13.2" in entry, "4.13.2 is the last typing_extensions release supporting 3.8"
