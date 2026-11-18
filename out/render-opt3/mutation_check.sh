#!/usr/bin/env bash
# 变异验证：把实现逐条改坏，确认新增用例会红（而不是「改坏了也照绿」）。
set -u
cd /home/agent/shared_workspace/ai_upper
PY="LD_LIBRARY_PATH=/tmp/qtlibs QT_QPA_PLATFORM=offscreen env -u AI_UPPER_HOME HOME=$(mktemp -d) .venv/bin/python -m pytest"
SRC=app/src/markdown/document.py
TESTS="app/tests/test_markdown_chunked.py app/tests/test_markdown_document.py"

run_case() {
  local name="$1"; shift
  local backup; backup=$(mktemp)
  cp "$SRC" "$backup"
  "$@"
  local out; out=$(eval "$PY $TESTS -q 2>&1 | tail -2")
  cp "$backup" "$SRC"; rm -f "$backup"
  echo "MUTANT $name => $out"
}

mutate_py() {  # $1=python 替换脚本
  .venv/bin/python - "$1" <<'PY'
import sys
path = "app/src/markdown/document.py"
src = open(path).read()
old, new = sys.argv[1].split("|||")
assert old in src, "mutation target not found: %r" % old[:60]
open(path, "w").write(src.replace(old, new, 1))
PY
}

# 1. 去掉密度门槛：稀疏结构文档会被误判成分块
run_case "density_floor=0" mutate_py '_CHUNK_DENSITY_FLOOR = 0.15|||_CHUNK_DENSITY_FLOOR = 0.0'

# 2. 去掉规模门槛：小文档会被误判成分块
run_case "pressure=0" mutate_py '_CHUNK_PRESSURE = 45000|||_CHUNK_PRESSURE = 0'

# 3. 高密度仍用 50：小组优化丢失
run_case "dense_group=50" mutate_py '_CHUNK_DENSE_GROUP = 32|||_CHUNK_DENSE_GROUP = 50'

# 3b. 高密度门槛退回 0.30：密度 0.31 的文档会被推给小分组
run_case "dense_density=0.30" mutate_py '_CHUNK_DENSE_DENSITY = 0.40|||_CHUNK_DENSE_DENSITY = 0.30'

# 4. 引用不递归计数：嵌套引用漏算
run_case "no_recursive_quote" mutate_py 'total += _structural_load(block.get("children") or [])|||pass'

# 5. h2 不计数
run_case "no_h2_weight" mutate_py 'total += _STRUCTURAL_WEIGHTS["heading2"]|||pass'

# 6. 颜色缓存把结果写错：一条解析用例必须红
run_case "color_cache_wrong" mutate_py '    return color


@lru_cache(maxsize=512)|||    return QColor("#010203")


@lru_cache(maxsize=512)'

# 7. 字体缓存键丢了 bold：粗体与常规会撞车
run_case "font_key_drops_bold" mutate_py 'max(1, int(round(px))), bool(bold), bool(italic))|||max(1, int(round(px))), False, bool(italic))'

# 8. 行高缓存键丢了字号
run_case "line_height_key_drops_px" mutate_py 'spacing = _line_spacing(tuple(self.style.sans), max(1, int(round(px))))|||spacing = _line_spacing(tuple(self.style.sans), 14)'

# 9. 分组计划忽略 group 参数：分块永远用 50
run_case "ignore_group_arg" mutate_py 'size = group or _CHUNK_BLOCKS|||size = _CHUNK_BLOCKS'

# 10. 单元格格式缓存不分表头/斑马行：偶数行底色会串到奇数行
run_case "cell_key_drops_parity" mutate_py 'cell_key = (header_row, row_index % 2 == 0)|||cell_key = (header_row, True)'

# 11. 块格式缓存忽略对齐：三列不同对齐会塌成同一档
run_case "cell_block_key_drops_alignment" mutate_py 'block_fmt = self._cell_block_formats.get(alignment)|||block_fmt = self._cell_block_formats.get("left")'

# 12. 字符格式缓存不分表头：正文会继承粗体
run_case "cell_char_key_drops_bold" mutate_py 'char_fmt = self._cell_char_formats.get(header_row)|||char_fmt = self._cell_char_formats.get(True)'
