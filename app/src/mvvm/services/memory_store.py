"""角色记忆 v2：`<AI_UPPER_HOME>/deva/personas/memory/<persona>.json`（deva memory.ts）。"""
from __future__ import annotations
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Optional

TITLE_MAX = 60
BODY_MAX = 1500
MAX_ENTRIES = 100
BUDGET = 4000


def _home() -> Path:
    from mvvm.services.plugin_identity import shared_store
    return shared_store().home


def _path(persona_id: str) -> Path:
    return _home() / "personas" / "memory" / (str(persona_id) + ".json")


def _read(persona_id: str) -> dict[str, Any]:
    try:
        parsed = json.loads(_path(persona_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"entries": []}
    entries = parsed.get("entries") if isinstance(parsed, dict) else None
    return {"entries": [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []}


def _write(persona_id: str, entries: list[dict[str, Any]]) -> None:
    path = _path(persona_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def list_memories(persona_id: str) -> list[dict[str, Any]]:
    return sorted(_read(persona_id)["entries"], key=lambda e: int(e.get("updatedAt") or 0), reverse=True)


def save_memory(persona_id: str, payload: Any) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    title = " ".join(str(data.get("title") or "").split())[:TITLE_MAX]
    if not title:
        return {"ok": False, "error": "title is empty"}
    body = str(data.get("body") or "")[:BODY_MAX]
    kind = str(data.get("type") or "reference")
    if kind not in ("user", "feedback", "project", "reference"):
        kind = "reference"
    entries = _read(persona_id)["entries"]
    now = int(time.time() * 1000)
    existing = str(data.get("id") or "")
    for entry in entries:
        if entry.get("id") == existing:
            entry.update({"type": kind, "title": title, "body": body, "updatedAt": now})
            _write(persona_id, entries)
            return {"ok": True, "entry": entry}
    if len(entries) >= MAX_ENTRIES:
        return {"ok": False, "error": "memory limit reached"}
    entry = {"id": "r_" + secrets.token_hex(4), "type": kind, "title": title, "body": body,
             "createdAt": now, "updatedAt": now}
    entries.append(entry)
    _write(persona_id, entries)
    return {"ok": True, "entry": entry}


def delete_memory(persona_id: str, entry_id: str) -> dict[str, Any]:
    entries = _read(persona_id)["entries"]
    kept = [e for e in entries if e.get("id") != str(entry_id)]
    if len(kept) == len(entries):
        return {"ok": False, "error": "not found"}
    _write(persona_id, kept)
    return {"ok": True}


def clear_memories(persona_id: str) -> dict[str, Any]:
    _write(persona_id, [])
    return {"ok": True}


__all__ = ["clear_memories", "delete_memory", "list_memories", "save_memory"]
