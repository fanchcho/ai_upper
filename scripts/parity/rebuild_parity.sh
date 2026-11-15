#!/usr/bin/env bash
# 一次跑完「数据 → 原版截图 → QML 截图 → 逐页像素比对」。
#
# 为什么必须整套重跑：会话列表显示的是相对时间（21 hr ago），夹具时间戳相对生成时刻算，
# 所以原版截图与 QML 截图必须在同一批数据上、前后脚拍，隔天复用旧图会出现
# 「原版 21 hr ago / QML yesterday」这种假差异。
#
# 用法: scripts/parity/rebuild_parity.sh [--skip-deva]
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
PY="$ROOT/.venv/bin/python"

rm -rf /tmp/fx-pages /tmp/fx-page-home /tmp/fx-qml-home /tmp/qml-pages-out
mkdir -p /tmp/fx-page-home out/qml-shell/pages/deva

echo "== 1/5 夹具（120 会话，相对时间）"
"$PY" scripts/parity/make_pages_fixture.py /tmp/fx-pages || exit 2
"$PY" scripts/parity/make_pages_config.py /tmp/fx-page-home --model || exit 2

if [ "${1:-}" != "--skip-deva" ]; then
  echo "== 2/5 原版 Deva 19 页实拍（Electron + Xvfb）"
  bash scripts/parity/deva_pages_all.sh out/qml-shell/pages/deva || exit 3
else
  echo "== 2/5 跳过原版实拍（复用 out/qml-shell/pages/deva）"
fi

echo "== 3/5 QML 数据目录"
"$PY" scripts/parity/make_qml_home.py /tmp/fx-qml-home /tmp/fx-pages/data/chats /tmp/fx-page-home || exit 4

echo "== 4/5 QML 19 页实拍（offscreen + 软件光栅）"
bash scripts/parity/qml_pages_all.sh /tmp/qml-pages-out /tmp/fx-qml-home || exit 5

echo "== 5/5 逐页比对"
bash scripts/parity/parity_run.sh || exit 6
echo "== done: out/qml-shell/parity/numbers.tsv"
