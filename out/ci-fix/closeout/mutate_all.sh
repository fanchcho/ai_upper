#!/bin/bash
# Regenerate the five py38 mutation records: guard result (CPython 3.13) + real
# result (CPython 3.8.20 venv with pydantic 2.10.6 / typing_extensions 4.13.2).
#
# Each mutation is applied in place to the tracked source with an exact-anchor
# replacement, exercised, and then restored from a pristine copy. Nothing is
# left mutated: the restore step is itself checked at the end.
set -u
ROOT=/home/agent/shared_workspace/py_upper
OUT=$ROOT/out/ci-fix/closeout
PY313=$ROOT/.venv/bin/python-real
PY38=/tmp/venv38/bin/python

CM=$ROOT/app/src/mvvm/models/chat_models.py
EF=$ROOT/app/src/mvvm/services/effort.py
PG=$ROOT/app/src/mvvm/services/provider_gateway.py
TP=$ROOT/tools/ai_upper/third_party.py

backup() { cp -p "$1" "$1.mutbak"; }
restore() { mv -f "$1.mutbak" "$1"; }

run_guard() { # "$1" = log path
  cd "$ROOT" && $PY313 -m pytest app/tests/test_py38_compat.py -q >>"$1" 2>&1
  echo "GUARD_EXIT=$?" >>"$1"
}

run_import38() { # "$1" = log path, "$2" = module
  cd "$ROOT"
  PYTHONPATH=$ROOT/app/src:$ROOT/tools $PY38 -c "import $2" >>"$1" 2>&1
  echo "IMPORT38_EXIT=$?" >>"$1"
}

mutate() { # "$1" = file, "$2" = old, "$3" = new
  $PY313 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(path, encoding="utf-8").read()
assert s.count(old) == 1, f"anchor not unique in {path}: {old!r}"
open(path, "w", encoding="utf-8").write(s.replace(old, new))
PY
}

header() { # "$1" = file, "$2" = title
  cat >"$1" <<EOF
### $2
# 守卫：pytest app/tests/test_py38_compat.py（CPython $($PY313 -V 2>&1 | cut -d' ' -f2)）
# 真 3.8：$PY38（$($PY38 -V 2>&1 | cut -d' ' -f2)；pydantic / typing_extensions 版本见 py38-mutation-env.log）
# 生成：out/ci-fix/closeout/mutate_all.sh
# ----------------------------------------------------------------
EOF
}

# Environment statement shared by every record.
$PY38 -c "import sys, pydantic, typing_extensions, importlib.metadata as m; print('3.8 interpreter:', sys.version.split()[0], '| pydantic', pydantic.VERSION, '| typing_extensions', m.version('typing_extensions'), '|', typing_extensions.__file__)" \
  >"$OUT/py38-mutation-env.log" 2>&1
cd "$ROOT"
PYTHONPATH=$ROOT/app/src:$ROOT/tools $PY38 -c "import mvvm.models.chat_models, mvvm.services.effort, mvvm.services.provider_gateway; import ai_upper.third_party; print('baseline ok')" \
  >>"$OUT/py38-mutation-env.log" 2>&1
echo "BASELINE_EXIT=$?" >>"$OUT/py38-mutation-env.log"

# ---------- mutation 0: unmutated tree (control) ----------
header "$OUT/py38-mutation-0-baseline.log" "变异 0：未改动的树（对照）"
run_guard "$OUT/py38-mutation-0-baseline.log"
PYTHONPATH=$ROOT/app/src:$ROOT/tools $PY38 -c "import mvvm.models.chat_models, mvvm.services.effort, mvvm.services.provider_gateway; import ai_upper.third_party" \
  >>"$OUT/py38-mutation-0-baseline.log" 2>&1
echo "IMPORT38_EXIT=$?" >>"$OUT/py38-mutation-0-baseline.log"
# 与变异 4 用同一个调用做对照：未变异的切片实现在 3.8 上必须成功。
PYTHONPATH=$ROOT/app/src:$ROOT/tools $PY38 - >>"$OUT/py38-mutation-0-baseline.log" 2>&1 <<'EOF38'
import tempfile
from pathlib import Path

import ai_upper.third_party as tp

with tempfile.TemporaryDirectory() as d:
    dist_info = Path(d) / "Some.Dist-1.2.3.dist-info"
    dist_info.mkdir()
    print("baseline _dist_name ->", tp._dist_name(dist_info))
EOF38
echo "BASELINE_CALL_EXIT=$?" >>"$OUT/py38-mutation-0-baseline.log"

# ---------- mutation 1: bare `from typing import Annotated` ----------
backup "$CM"
mutate "$CM" "$(printf '%s\n' \
  'if sys.version_info >= (3, 9):' \
  '    from typing import Annotated' \
  'else:  # 3.8：Annotated 由 typing_extensions 提供（已列入 app/requirements.txt）' \
  '    from typing_extensions import Annotated')" "from typing import Annotated"
header "$OUT/py38-mutation-1-annotated.log" "变异 1：把版本分支退化成裸 \`from typing import Annotated\`"
run_guard "$OUT/py38-mutation-1-annotated.log"
header "$OUT/py38-mutation-1-real38.log" "变异 1（真 3.8）：裸 \`from typing import Annotated\` 在 3.8 上 ImportError"
run_import38 "$OUT/py38-mutation-1-real38.log" mvvm.models.chat_models
restore "$CM"

# ---------- mutation 2: LevelMap = dict[str, str] ----------
backup "$EF"
mutate "$EF" "LevelMap = Dict[str, str]" "LevelMap = dict[str, str]"
header "$OUT/py38-mutation-2-levelmap.log" "变异 2：模块级赋值改回 \`LevelMap = dict[str, str]\`（PEP 585）"
run_guard "$OUT/py38-mutation-2-levelmap.log"
header "$OUT/py38-mutation-2-real38.log" "变异 2（真 3.8）：模块级 \`dict[str, str]\` 赋值运行期求值即 TypeError"
run_import38 "$OUT/py38-mutation-2-real38.log" mvvm.services.effort
restore "$EF"

# ---------- mutation 3: StreamEvent = A | B | ... ----------
backup "$PG"
mutate "$PG" "$(printf '%s\n' \
  'StreamEvent = Union[' \
  '    TextDelta, ThinkingDelta, ToolCall, ToolCallTruncated, Usage, StreamError, Done' \
  ']')" "StreamEvent = TextDelta | ThinkingDelta | ToolCall | ToolCallTruncated | Usage | StreamError | Done"
header "$OUT/py38-mutation-3-streamevent.log" "变异 3：模块级 \`A | B\` 联合（PEP 604）"
run_guard "$OUT/py38-mutation-3-streamevent.log"
header "$OUT/py38-mutation-3-real38.log" "变异 3（真 3.8）：模块级 \`A | B\` 求值即 TypeError"
run_import38 "$OUT/py38-mutation-3-real38.log" mvvm.services.provider_gateway
restore "$PG"

# ---------- mutation 4: str.removesuffix in the build tool ----------
backup "$TP"
mutate "$TP" '    stem = name[:-len(suffix)] if name.endswith(suffix) else name' '    stem = name.removesuffix(suffix)'
header "$OUT/py38-mutation-4-removesuffix.log" "变异 4：构建工具改回 \`str.removesuffix\`（3.9+ 运行期 API）"
run_guard "$OUT/py38-mutation-4-removesuffix.log"
header "$OUT/py38-mutation-4-real38.log" "变异 4（真 3.8）：\`str.removesuffix\` 在 3.8 上 AttributeError（导入不触发，须真调一次）"
# 该 API 位于函数体内，import 不会执行到它；缺陷是运行期调用，所以按真调用取证。
# 不写 METADATA：`_dist_name` 有 METADATA 时会提前 return，走不到被变异的行。
PYTHONPATH=$ROOT/app/src:$ROOT/tools $PY38 - >>"$OUT/py38-mutation-4-real38.log" 2>&1 <<'EOF38'
import tempfile
from pathlib import Path

import ai_upper.third_party as tp

with tempfile.TemporaryDirectory() as d:
    dist_info = Path(d) / "Some.Dist-1.2.3.dist-info"
    dist_info.mkdir()
    print("_dist_name ->", tp._dist_name(dist_info))
EOF38
echo "CALL_EXIT=$?" >>"$OUT/py38-mutation-4-real38.log"
restore "$TP"

# ---------- mutation 5: pydantic field annotation uses list[...] ----------
backup "$CM"
mutate "$CM" "    images: Optional[List[ImagePart]] = None" "    images: Optional[list[ImagePart]] = None"
header "$OUT/py38-mutation-5-pydantic-field.log" "变异 5：pydantic 字段注解改回 \`Optional[list[ImagePart]]\`"
run_guard "$OUT/py38-mutation-5-pydantic-field.log"
header "$OUT/py38-mutation-5-real38.log" "变异 5（真 3.8）：pydantic 解析字段注解时 TypeError"
run_import38 "$OUT/py38-mutation-5-real38.log" mvvm.models.chat_models
restore "$CM"

# ---------- restore proof ----------
cd "$ROOT"
git --no-pager diff --stat -- "$CM" "$EF" "$PG" "$TP" >"$OUT/py38-mutation-restore-check.log" 2>&1
echo "--- tracked files touched by mutations (must be empty above) ---" >>"$OUT/py38-mutation-restore-check.log"
git --no-pager status --porcelain -- "$CM" "$EF" "$PG" "$TP" >>"$OUT/py38-mutation-restore-check.log" 2>&1
echo "RESTORE_CHECK_EXIT=$?" >>"$OUT/py38-mutation-restore-check.log"
