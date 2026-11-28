import time
import pytest


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    yield app


def test_install_ticket_ttl_and_pair_cancel_are_independent(qapp, tmp_path):
    from test_web_pairing import Settings
    from mvvm.services.remote_bots import RemoteBots
    from mvvm.services.secrets_vault import SecretsVault
    from PySide6.QtCore import QObject
    class Shell(QObject):
        def __init__(self):
            super().__init__();self._settings=Settings(tmp_path);self._vault=SecretsVault(tmp_path)
    controller=RemoteBots(Shell())
    try:
        controller.webPairTicket();server=next(iter(controller.workers.values()))
        before=time.time();ticket=server.install_ticket('lan');identity=ticket.split('.')[0]
        assert server.tickets[identity]['kind']=='install'
        assert before+3599 < server.tickets[identity]['expires'] < time.time()+3601
        controller.cancelPhoneQr()
        assert identity in server.tickets
        assert server.holds['lan']['link']>=server.tickets[identity]['expires']
    finally:controller.close()
