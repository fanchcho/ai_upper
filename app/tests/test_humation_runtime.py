import json
from urllib.parse import unquote
from PySide6.QtGui import QGuiApplication
from mvvm.services.humation import Humation


def test_dynamic_seed_spec_and_composition(qapp):
    renderer = Humation()
    a = renderer.image('reviewer', '', False)
    assert a == renderer.image('reviewer', '', False)
    assert a != renderer.image('writer', '', False)
    spec = json.dumps({'colors': {'hair': 'ff0000'}, 'selections': {'head': 'hm1-p-000005'}})
    b = renderer.image('reviewer', spec, False)
    assert b != a and '#ff0000' in unquote(b)
    assert renderer.image('reviewer', json.dumps({'shape':'cloud'}), False) != a
    assert renderer.image('reviewer', json.dumps({'shape':'auto'}), False) != a
    assert renderer.image('writer', '', True) != renderer.image('writer', '', False)


import pytest
@pytest.fixture
def qapp():
    return QGuiApplication.instance() or QGuiApplication([])
