"""为 QML 附件贴片 / 交付卡的实跑截图造夹具（临时 HOME，不碰真实 ~/.ai_upper）。

产物（全部真实落盘，体积可被 `ls -l` 核对）：
  <HOME>/ws/截图-2026-11-16.png     用户随消息发出的图片附件（真 PNG）
  <HOME>/ws/季度报告.md             present_files 交付的成品（中文正文，>2 KB）
  <HOME>/ws/数据汇总.xlsx            present_files 交付的成品（5 KB）
  <HOME>/ws/build.py                交付的脚本（非白名单 → 打开按钮应为禁用态）
  <HOME>/ws/已移走的报告.md          交付后从磁盘删除 → 应显示「已不存在」

会话 `chat-files`：user[ImagePart, TextPart] → assistant[TextPart, ToolUsePart(present_files)]，
`delivered` 边车经 `tool_results.record_delivered` 真实写入后 `store.save()`。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "app" / "src"
sys.path.insert(0, str(SRC))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HOME = Path(os.environ.get("CHAT_FILES_HOME", "/tmp/chat-files-home"))
WS = HOME / "ws"
WS.mkdir(parents=True, exist_ok=True)

from mvvm.models.chat_models import (  # noqa: E402
    DocumentPart,
    ImagePart,
    Message,
    TextPart,
    ToolResultPart,
    ToolUsePart,
)
from mvvm.services.attachments import AttachmentService  # noqa: E402
from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.tool_results import record_delivered  # noqa: E402
from mvvm.services.workspace_guard import WorkspaceGuard  # noqa: E402
from utils.qt_compat import QtGui  # noqa: E402


def make_png(path: Path, width: int = 96, height: int = 96) -> int:
    """画一张有内容的 PNG（渐变 + 方块），避免全零图看不出缩略图是否正确。"""
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    image = QtGui.QImage(width, height, QtGui.QImage.Format_RGB32)
    for y in range(height):
        for x in range(width):
            image.setPixelColor(
                x,
                y,
                QtGui.QColor(
                    min(255, 40 + x * 2),
                    min(255, 60 + y * 2),
                    180 if (x // 16 + y // 16) % 2 == 0 else 120,
                ),
            )
    assert image.save(str(path), "PNG")
    return path.stat().st_size


def main() -> int:
    png = WS / "截图-2026-11-16.png"
    png_size = make_png(png)

    report = WS / "季度报告.md"
    body = "\n".join(
        "# 季度报告\n\n第 %d 段：本季度交付文件链路核对（附件贴片 / 交付卡 / 打开 / 定位 / 复制路径）。" % i
        for i in range(1, 25)
    )
    report.write_text(body + "\n", encoding="utf-8")

    sheet = WS / "数据汇总.xlsx"
    sheet.write_bytes(b"PK\x03\x04" + bytes(range(256)) * 20)

    script = WS / "build.py"
    script.write_text("print('delivered script must not be openable')\n", encoding="utf-8")

    gone = WS / "已移走的报告.md"
    gone.write_text("这份交付后会被删掉，交付卡应显示「已不存在」。\n", encoding="utf-8")

    data = png.read_bytes()
    import base64

    b64 = base64.b64encode(data).decode("ascii")

    store = ChatSessionStore(HOME)
    store.ensure_session("chat-files")
    store.append_message(
        "chat-files",
        Message(
            role="user",
            content=[
                ImagePart(type="image", mediaType="image/png", name=png.name, data=b64),
                DocumentPart(
                    type="document",
                    mediaType="application/pdf",
                    name="需求说明.pdf",
                    data=base64.b64encode(b"%PDF-1.4 fixture" + b"x" * 300).decode("ascii"),
                ),
                TextPart(text="这两份文件请整理成季度报告"),
            ],
        ),
        title_seed="带附件的消息",
    )
    tool_id = "tu_present_chat_files"
    store.append_message(
        "chat-files",
        Message(
            role="assistant",
            content=[
                TextPart(text="已生成报告并汇总数据。"),
                ToolUsePart(
                    id=tool_id,
                    name="present_files",
                    input={"paths": [str(report), str(sheet), str(script), str(gone)]},
                ),
                ToolResultPart(
                    toolUseId=tool_id,
                    content="delivered",
                    isError=False,
                ),
            ],
        ),
    )

    # 交付后把其中一个文件移走 —— 交付卡必须显示「已不存在」。
    gone.unlink()

    # 真实边车写入路径：tool_results.record_delivered（tool_runtime 的 delivered 字段形状）。
    class _Result:
        delivered = [str(report), str(sheet), str(script), str(gone)]

    session = store.load_session("chat-files")
    session.delivered = record_delivered(session.delivered, tool_id, _Result())
    store.save("chat-files")

    payload = json.loads(store.session_path("chat-files").read_text(encoding="utf-8"))
    print("== 夹具文件 ==")
    for p in (png, report, sheet, script):
        print("   %-40s %6d B" % (p.name, p.stat().st_size))
    print("   %-40s 已删除（用于验证 missing 态）" % gone.name)
    print("== 会话 JSON ==", store.session_path("chat-files"))
    print("   delivered 边车 =", json.dumps(payload.get("delivered"), ensure_ascii=False))
    print("   messages 条数 =", len(payload.get("messages") or []))
    print("   图片附件 =", png.name, "base64 长度 =", len(b64), "原始 =", png_size, "B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
