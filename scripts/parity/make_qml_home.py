"""从原版那份固定数据生成 QML 壳的数据目录（同一份 chats + 同一份 config）。

两侧必须读**同一份** chats 与**同一份** config，逐页像素对比才有意义：QML 不接受
`DEVA_HOME`，它只认 `AI_UPPER_HOME`，所以这里把 deva 侧的 `data/chats` 原样复制过去。

用法: .venv/bin/python scripts/parity/make_qml_home.py <qml home> <deva fixture chats> <deva home>
  第 2 个参数是原版的 `data/chats` 目录（make_pages_fixture.py 的产物），
  第 3 个参数是放了 config.json / config-dark.json 的原版 home（deva_pages_all.sh 会写）。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main(argv: list) -> None:
    home = Path(argv[1])
    chats = Path(argv[2])
    deva_home = Path(argv[3])

    if home.exists():
        shutil.rmtree(home)
    (home / "data" / "chats").mkdir(parents=True, exist_ok=True)
    for item in chats.iterdir():
        if item.is_file():
            shutil.copy2(item, home / "data" / "chats" / item.name)

    for name in ("config.json", "config-dark.json"):
        src = deva_home / name
        if src.is_file():
            shutil.copy2(src, home / name)
    print("qml home ok at %s (chats=%d)" % (home, len(list((home / 'data' / 'chats').glob('*.json')))))


if __name__ == "__main__":
    main(sys.argv)
