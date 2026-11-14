#!/usr/bin/env python3
"""生成 `docs/audit/IPC-158-LEDGER.md`：158 条 IPC 通道逐条结论表。

事实来源（全部机器读取，不手抄）：
- 通道全集：`/tmp/deva_ipc.json`（对 deva 源码 grep `ipcMain.handle/on` 的产物；只读）
- 入参/出参：`docs/audit/contracts-*.md` 的 `### <通道>` 小节
- 判定：`audit-tools/ipc_status_table.py`
- 「是否真的注册在桥里」：真实构造 `DevaBridge`（Qt offscreen）后读 `channels()`，与判定表
  交叉校验——判定说实现了但桥里没有，或桥里有却没判定，脚本都直接报错。

用法：`cd <repo> && .venv/bin/python audit-tools/make_ipc_ledger.py`
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ipc_status_table import EVENT_ROWS, STATUS  # noqa: E402

AUDIT = REPO / "docs" / "audit"
IPC_JSON = Path(os.environ.get("DEVA_IPC_JSON", "/tmp/deva_ipc.json"))
BRIDGE_PY = REPO / "app" / "src" / "mvvm" / "webui" / "bridge.py"
OUT = AUDIT / "IPC-158-LEDGER.md"
EXPECTED_TOTAL = 158
EXPECTED_HANDLE = 154
EXPECTED_ON = 4

REGISTER_CALL = re.compile(r'self\.register(?:_deferred)?\(\s*"([^"]+)"')
# 循环注册：`for channel, method in (("chat:send", "send"), …): self.register(channel, ...)`
LOOP_REGISTER = re.compile(r"self\.register\(\s*channel\s*,\s*self\._host_method\(")
LOOP_ENTRY = re.compile(r'\(\s*"([a-z][a-z0-9:-]*)",\s*"\w+"\s*\)')


def bridge_register_lines() -> dict[str, int]:
    """通道 → bridge.py 里注册该通道的行号（现查，不手写）。

    两种注册形态都要认得：字面量 `self.register("x", …)` / `register_deferred`，以及
    写通道批量循环 `for channel, method in ((...)): self.register(channel, …)`。只认字面量
    会让 14 条写通通在台账里显示「—（未注册）」，而桥明明注册了——那种台账比没有更坏。
    """
    out: dict[str, int] = {}
    lines = BRIDGE_PY.read_text(encoding="utf-8").splitlines()
    loop_line: int | None = None
    for number, line in enumerate(lines, 1):
        for match in REGISTER_CALL.finditer(line):
            out.setdefault(match.group(1), number)
        if LOOP_REGISTER.search(line):
            loop_line = number
    if loop_line is not None:
        # 循环体在同一语句块里：从注册行往前找成对的 `(`，把其中的 (通道, 方法) 全收进来。
        start = loop_line - 1
        while start > 0 and "for channel, method in (" not in lines[start - 1]:
            start -= 1
        for line in lines[start:loop_line]:
            for match in LOOP_ENTRY.finditer(line):
                out.setdefault(match.group(1), loop_line)
    return out


def parse_contracts() -> dict[str, dict[str, str]]:
    """`### channel` → {入参, 出参, 原版位置}（契约文件原文，表格里截断到 240 字）。"""
    out: dict[str, dict[str, str]] = {}
    heading = re.compile(r"^### (\S+)\s*$")
    for path in sorted(AUDIT.glob("contracts-*.md")):
        current = None
        for line in path.read_text(encoding="utf-8").splitlines():
            match = heading.match(line)
            if match:
                current = match.group(1)
                out[current] = {"file": path.name}
                continue
            if current is None or not line.startswith("- "):
                continue
            for key, prefix in (("入参", "- 入参:"), ("出参", "- 出参:"), ("原版位置", "- 原版位置:")):
                if line.startswith(prefix):
                    out[current][key] = line[len(prefix):].strip()
    return out


def read_bridge_channels() -> set[str]:
    """真实构造桥，读已注册通道名。必须用真实 Qt（offscreen），失败就报错不糊弄。"""
    script = r"""
import json, sys, tempfile, pathlib
sys.path.insert(0, "app/src")
from utils.qt_compat import QtWidgets
app = QtWidgets.QApplication([])
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.persona_store import PersonaStore
from mvvm.services.settings_service import SettingsService
from mvvm.webui.bridge import DevaBridge
home = pathlib.Path(tempfile.mkdtemp())
b = DevaBridge(settings=SettingsService(home), personas=PersonaStore(home),
               store=ChatSessionStore(home), home=home)
print(json.dumps(sorted(b.channels())))
"""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=REPO, env=env,
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        raise SystemExit(f"桥自检失败：\n{proc.stderr[-3000:]}")
    return set(json.loads(proc.stdout.strip().splitlines()[-1]))


def clip(text: str, limit: int = 240) -> str:
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= limit else text[:limit] + "…"


def resolve_impl(impl: str, channel: str, lines: dict[str, int]) -> str:
    if impl == "{bridge}":
        line = lines.get(channel)
        return f"app/src/mvvm/webui/bridge.py:{line}" if line else "—（未注册）"
    return impl


def main() -> None:
    ipc = json.loads(IPC_JSON.read_text())
    contracts = parse_contracts()
    registered = read_bridge_channels()
    lines = bridge_register_lines()

    # ── 交叉校验：台账不许自说自话 ─────────────────────────────────────────
    problems: list[str] = []
    for item in ipc:
        channel = item["channel"]
        if channel not in STATUS:
            problems.append(f"{channel}: 判定表里缺这一条")
            continue
        impl, _test, result = STATUS[channel]
        claims_impl = impl != "—"
        # 只对「声称在桥里实现」的条目做交叉校验；shim 侧实现（config:get-sync 是 sendSync
        # 的同步取配置，没有跨进程往返）本来就不该出现在桥里。
        if impl == "{bridge}" and channel not in registered:
            problems.append(f"{channel}: 判定声称已实现（{impl}），桥里却没有注册")
        if not claims_impl and channel in registered:
            problems.append(f"{channel}: 判定写未实现，但桥里已经注册了")
        if not result.startswith(("通过", "已知差异", "不适用", "未实现")):
            problems.append(f"{channel}: 实测结果必须以前缀 通过/已知差异/不适用/未实现 开头：{result!r}")
        contract = contracts.get(channel)
        if contract is None or "入参" not in contract or "出参" not in contract:
            problems.append(f"{channel}: 契约文件里缺入参/出参")
    unknown = [c for c in registered if c not in {i["channel"] for i in ipc}]
    if unknown:
        problems.append(f"桥里注册了 158 条之外的通道：{unknown}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        raise SystemExit(1)

    # ── 统计与总数校验 ────────────────────────────────────────────────────
    tally = Counter(STATUS[item["channel"]][2].split()[0] for item in ipc)
    handles = sum(1 for item in ipc if item["kind"] == "handle")
    ons = sum(1 for item in ipc if item["kind"] == "on")
    assert len(ipc) == EXPECTED_TOTAL, len(ipc)
    assert handles == EXPECTED_HANDLE and ons == EXPECTED_ON, (handles, ons)

    out: list[str] = []
    add = out.append
    add("# IPC 158 条通道逐条结论表（移植版）")
    add("")
    add("> 本文件由 `audit-tools/make_ipc_ledger.py` 生成，**不要手改**；改判定请改")
    add("> `audit-tools/ipc_status_table.py` 后重新生成。通道全集来自对 deva 源码")
    add("> `ipcMain.handle` / `ipcMain.on` 的 grep 产物（deva 工程只读，未改动），")
    add("> 入参/出参抄自 `docs/audit/contracts-*.md`（超 240 字截断，全文见同名小节）。")
    add("")
    add("**总数校验：158 条 = 154 条 `ipcMain.handle` + 4 条 `ipcMain.on`**")
    add("（4 条 `on` 为 `config:get-sync`、`terminal:input`、`terminal:resize`、`terminal:dispose`）。")
    add("另有 2 条主进程 → 渲染层推送事件（`chat:event`、`chat:sessions-changed`），")
    add("不在 158 条 invoke 通道内，单列在末尾。")
    add("")
    add("**移植版实现位置**里的行号是生成时从 `bridge.py` 现查的 `self.register(...)` 行；")
    add("`—` 表示桥里没有这条通道，原因写在「实测结果」列。")
    add("")
    add("## 汇总")
    add("")
    add("| 判定 | 条数 |")
    add("|---|---|")
    for word in ("通过", "已知差异", "不适用", "未实现"):
        add(f"| {word} | {tally.get(word, 0)} |")
    add(f"| **合计** | **{sum(tally.values())}** |")
    add("")
    # 自洽校验的第二半：声称有实现的位置（impl != '—'）必须能和「桥内注册 + shim 实现」
    # 对上账。对不上说明台账在虚标——宁可这里报错，也不要把矛盾数字写进文档。
    claims = [c for c in STATUS if STATUS[c][0] != "—"]
    shim_only = [c for c in claims if c not in registered]
    assert len(claims) - len(shim_only) == len(registered), (
        len(claims), len(shim_only), len(registered)
    )
    add(f"生成时桥内已注册通道数：**{len(registered)}**；"
        f"判定有实现位置的条目 **{len(claims)}** 条，其中 "
        f"{len(shim_only)} 条在渲染层 shim 里实现（{', '.join(f'`{c}`' for c in shim_only) or '无'}），"
        f"其余 {len(claims) - len(shim_only)} 条与桥内注册逐条对应。"
        "桥里没有的通道在「实测结果」列写明阻塞原因。")
    add("")
    add("## 逐条结论")
    add("")
    add("| # | 通道 | 入参 | 出参 | 原版位置 | 移植版实现位置 | 测试方式 | 实测结果 |")
    add("|---|---|---|---|---|---|---|---|")
    for index, item in enumerate(ipc, 1):
        channel = item["channel"]
        contract = contracts[channel]
        impl, test, result = STATUS[channel]
        add(
            "| {i} | `{ch}` | {inp} | {out} | {src} | {impl} | {test} | {res} |".format(
                i=index,
                ch=channel,
                inp=clip(contract["入参"]),
                out=clip(contract["出参"]),
                src=clip(f"{item['file']}:{item['line']}（{item['kind']}）", 120),
                impl=clip(resolve_impl(impl, channel, lines), 120),
                test=clip(test, 160),
                res=result,
            )
        )
    add("")
    add("## 附加：主进程 → 渲染层推送事件（不计入 158 条）")
    add("")
    add("| 事件 | 形状 | 移植版实现位置 | 实测结果 |")
    add("|---|---|---|---|")
    for channel, shape, impl, result in EVENT_ROWS:
        add(f"| `{channel}` | {clip(shape, 200)} | {impl} | {result} |")
    add("")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} rows={len(ipc)} registered={len(registered)} tally={dict(tally)}")


if __name__ == "__main__":
    main()
