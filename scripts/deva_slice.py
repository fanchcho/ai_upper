"""纵向切片真机脚本：发送一条消息 → 假 provider 回复 → 工具允许/拒绝 → 落盘 → 重启读回。

不依赖 pytest，跑法和应用入口一样：`PYTHONPATH=app/src .venv/bin/python scripts/deva_slice.py`。
只用临时目录（`tempfile.mkdtemp`），不碰 `~/.deva`，退出时清理；
`--keep` 保留目录供人工翻看。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.fake_provider import FakeProvider
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import DENIED, WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel


def build_vm(home: Path, workspace: Path, provider: FakeProvider) -> ChatViewModel:
    guard = WorkspaceGuard([workspace])
    return ChatViewModel(ChatSessionStore(home), provider, ToolRuntime(guard, workspace))


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="保留临时目录")
    args = parser.parse_args()

    base = Path(tempfile.mkdtemp(prefix="deva-slice-"))
    home = base / "deva-home"
    workspace = base / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "notes.txt").write_text("会议纪要：上线时间定在周五\n", encoding="utf-8")
    outside = base / "outside-secret.txt"
    outside.write_text("机密\n", encoding="utf-8")
    try:
        section("1. 允许：read_file 在受信根内")
        vm = build_vm(home, workspace, FakeProvider(tool_path="notes.txt"))
        vm.open_session("slice-allowed")
        vm.input_text_property.set_value("看一下 notes.txt")
        vm.send()
        print("status:", vm.status)
        print("error:", repr(vm.error))
        print("tool_results:", [(r.is_error, r.summary) for r in vm.tool_results])
        print("transcript roles:", [e["role"] for e in vm.transcript])
        print("assistant:", vm.transcript[-1]["text"])

        section("2. 拒绝：read_file 指向受信根之外")
        denied_vm = build_vm(home, workspace, FakeProvider(tool_path=str(outside)))
        denied_vm.open_session("slice-denied")
        denied_vm.input_text_property.set_value("读一下根外的文件")
        denied_vm.send()
        result = denied_vm.tool_results[0]
        print("tool denied:", result.is_error, "| content == DENIED:", result.content == DENIED)
        print("assistant:", denied_vm.transcript[-1]["text"])

        section("3. 落盘：data/chats 下的文件")
        chats = ChatSessionStore(home).chats_dir
        for path in sorted(chats.iterdir()):
            print(f"  {path.name}  {path.stat().st_size} bytes")
        raw = json.loads((chats / "slice-allowed.json").read_text(encoding="utf-8"))
        print("messages in slice-allowed.json:", len(raw["messages"]))
        print("content part types:", [p["type"] for p in raw["messages"][1]["content"]])

        section("4. 重启：全新 Store + 全新 ViewModel 只从磁盘读回")
        restarted = build_vm(home, workspace, FakeProvider())
        restarted.open_session("slice-allowed")
        print("title:", restarted.title)
        print("transcript roles:", [e["role"] for e in restarted.transcript])
        print("last assistant:", restarted.transcript[-1]["text"])
        ok = "会议纪要" in restarted.transcript[-1]["text"]

        section("5. 索引自愈：删掉 _index.json 后重建")
        (chats / "_index.json").unlink()
        rebuilt = ChatSessionStore(home)
        print("sessions after rebuild:", sorted(m.id for m in rebuilt.list_sessions()))

        print("\nSLICE PASS" if ok else "\nSLICE FAIL")
        return 0 if ok else 1
    finally:
        if args.keep:
            print("\n临时目录（保留）:", base)
        else:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
