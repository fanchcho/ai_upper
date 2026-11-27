"""F30：工具调用/工具结果/思考/子代理活动在 QML 正文真实渲染。

原版依据：deva features/chat/blocks.tsx（timeline/tool/thinking cards）、
redesign/ChatFirstShell.tsx:39-44。移植版用 blockquote 卡承载同一信息，不依赖 WebEngine。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _msgs():
    from mvvm.models.chat_models import Message, TextPart, ToolResultPart, ToolUsePart

    return [
        Message(role="user", content="检查文件"),
        Message(role="assistant", content=[
            TextPart(text="先读文件。"),
            ToolUsePart(id="t1", name="read_file", input={"path": "/tmp/spec.md"}),
        ]),
        Message(role="user", content=[ToolResultPart(toolUseId="t1", content="文件内容 ABC", isError=False)]),
        Message(role="assistant", content=[ToolUsePart(id="t2", name="run_subagent", input={"task": "审查"})]),
        Message(role="user", content=[ToolResultPart(toolUseId="t2", content="子代理完成", isError=False)]),
        Message(role="assistant", content="完成。"),
    ]


def test_transcript_includes_activity_only_when_requested():
    from qml_shell_sessions import transcript_markdown

    plain = transcript_markdown(_msgs())
    assert "read_file" not in plain and "文件内容 ABC" not in plain
    rich = transcript_markdown(_msgs(), include_activity=True)
    assert "工具调用" in rich or "read_file" in rich
    assert "`read_file`" in rich and "/tmp/spec.md" in rich
    assert "文件内容 ABC" in rich
    assert "子智能体" in rich or "run_subagent" in rich
    assert "文件内容 ABC" in rich


def test_qml_body_renders_tool_and_subagent_cards(qapp, tmp_path, monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt, QPointF
    from qml_shell import _pump
    from test_qml_sidebar_collapse import _build

    window, bridge, _settings, ticker, engine = _build(tmp_path, monkeypatch)
    try:
        store = bridge._store
        session = store.load_session("s-1")
        session.messages = _msgs()
        store.save("s-1")
        assert bridge.openSession("s-1") is True
        _pump(qapp, lambda: False, 0.8)
        body = None
        def walk(item):
            nonlocal body
            if item.objectName() == "bodyView":
                body = item
            for child in item.childItems():
                walk(child)
        walk(window.contentItem())
        assert body is not None
        text = body.property("textDocument").textDocument().toPlainText()
        assert "read_file" in text
        assert "/tmp/spec.md" in text
        assert "文件内容 ABC" in text
        assert "run_subagent" in text
        # 暗亮截图由 scripts/parity/feature_parity_evidence.py activity 生成。
    finally:
        ticker.stop(); window.close(); engine.deleteLater()
