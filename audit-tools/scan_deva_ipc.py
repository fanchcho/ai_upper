"""Scan Deva main-process IPC registrations (read-only) into /tmp/deva_ipc.json.

Usage: python3 audit-tools/scan_deva_ipc.py [deva_root]
Prints: entries / unique / handle / on, and per-domain counts.
"""
import json
import pathlib
import re
import sys

DEVA = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/home/agent/shared_workspace/deva")
BASE = DEVA / "apps/desktop/src"
MAIN = BASE / "main"
OUT = pathlib.Path("/tmp/deva_ipc.json")

PATTERN = re.compile(r"ipcMain\s*\.\s*(handle|on)\s*\(\s*(['\"])([^'\"]+)\2", re.S)


def scan() -> list[dict]:
    rows = []
    for path in sorted(MAIN.rglob("*.ts")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in PATTERN.finditer(text):
            rows.append({
                "file": str(path.relative_to(BASE)),
                "line": text.count("\n", 0, match.start()) + 1,
                "kind": match.group(1),
                "channel": match.group(3),
            })
    rows.sort(key=lambda row: (row["file"], row["line"]))
    return rows


def main() -> int:
    rows = scan()
    unique = {row["channel"] for row in rows}
    handles = sum(1 for row in rows if row["kind"] == "handle")
    ons = sum(1 for row in rows if row["kind"] == "on")
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"entries {len(rows)} / unique {len(unique)} / handle {handles} / on {ons} -> {OUT}")
    domains = {}
    for row in rows:
        domain = row["channel"].split(":")[0]
        domains[domain] = domains.get(domain, 0) + 1
    for domain in sorted(domains, key=lambda key: (-domains[key], key)):
        print(f"  {domain}: {domains[domain]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
