"""Rich-text worker results must remain safe to lay out and dispose on the GUI thread."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor


def test_prepared_images_cross_threads_without_qobject_warnings(qapp):
    from PySide6 import QtCore, QtGui
    from markdown.document import BodyStyle
    from markdown.prepare import prepare_document

    warnings = []
    previous = QtCore.qInstallMessageHandler(lambda kind, context, message: warnings.append(message))
    try:
        image = QtGui.QImage(8, 8, QtGui.QImage.Format_RGB32)
        image.fill(QtGui.QColor('red'))
        with ThreadPoolExecutor(max_workers=1) as worker:
            prepared, images = worker.submit(
                prepare_document, '![probe](probe.png)\n\n**retained text**',
                False, BodyStyle(), 300, lambda *_: image,
            ).result()
        assert prepared.thread() == qapp.thread()
        fragment = QtGui.QTextDocumentFragment(prepared)
        target = QtGui.QTextDocument()
        QtGui.QTextCursor(target).insertFragment(fragment)
        for url, resource in images:
            target.addResource(QtGui.QTextDocument.ImageResource, url, resource)
        assert 'retained text' in target.toPlainText()
        assert images
        assert target.size().height() > 0
        prepared.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        qapp.processEvents()
        assert not [m for m in warnings if 'thread' in m.lower() or 'timer' in m.lower()], warnings
    finally:
        QtCore.qInstallMessageHandler(previous)


import pytest


@pytest.fixture(scope='module')
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def test_timezone_data_without_system_database(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys

    source = Path(__file__).resolve().parents[1] / 'src'
    code = (
        'import sys; sys.path.insert(0, sys.argv[1]); '
        'from mvvm.services.scheduled_tasks import next_run; '
        'from datetime import datetime, timezone; '
        'at="2030-01-01T00:00:00+00:00"; '
        'result=next_run({"kind":"once","at":at,"tz":"Asia/Shanghai"},now=0); '
        'assert result==datetime.fromisoformat(at).timestamp(); print(result)'
    )
    env = dict(os.environ, PYTHONTZPATH='', AI_UPPER_HOME=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', code, str(source)], env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == '1893456000.0'
