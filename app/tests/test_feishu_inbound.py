"""飞书入站：protobuf 帧编解码与缺凭据真实拒绝。"""
from __future__ import annotations
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_feishu_frame_and_missing_credentials(qapp):
    from mvvm.services.feishu_inbound import decode, encode, connection
    from PySide6.QtCore import QObject
    class Parent(QObject):
        pass
    rows = [(1, 0), (2, 0), (3, 7), (4, 0), (5, encode([(1, b"type"), (2, b"ping")]))]
    assert dict(decode(encode(rows)))[3] == 7
    states = []
    bot = {"id": "feishu-test", "platform": "feishu", "settings": {}}
    class Vault:
        def get_secret(self, key):
            return None
    link = connection(Parent(), bot, Vault(), states.append, lambda event: None)
    assert states and states[0].startswith("未验证：飞书 App ID")
    link.set()
