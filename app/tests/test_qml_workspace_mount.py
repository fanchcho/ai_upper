"""Workspace picker events, persistence, trust boundary and icon clipping regression."""
from pathlib import Path
import os
import pytest
from PySide6.QtCore import QObject, QUrl, QMetaObject
from test_qml_context_menu import qapp, _build_window, _find_item, _click, _pump
from mvvm.services.chat_session_store import ChatSessionStore


def test_mount_picker_mouse_persist_cancel_and_reject(qapp, tmp_path, monkeypatch):
    w, b, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        # This scenario asserts Chinese application errors; select that locale explicitly.
        assert b.setLanguage('zh-CN')
        w.setProperty('page', 'chat')
        _pump(qapp)
        sid = w.property('activeId')
        folder = tmp_path / 'chosen workspace'
        folder.mkdir()
        dialog = w.findChild(QObject, 'workspaceDialog')
        chip = _find_item(w.contentItem(), 'mountChip')
        before = store.session_path(sid).read_bytes()
        _click(w, chip); _pump(qapp)
        assert dialog.property('visible')
        assert len(w.findChildren(QObject, 'workspaceDialog')) == 1
        assert b.beginWorkspace() == '目录选择框已打开'
        QMetaObject.invokeMethod(dialog, 'reject'); _pump(qapp)
        assert store.session_path(sid).read_bytes() == before
        assert not b._mount_session
        dialog.setProperty('currentFolder', QUrl.fromLocalFile(str(tmp_path)))
        dialog.setProperty('selectedFolder', QUrl.fromLocalFile(str(folder)))
        _click(w, chip); _pump(qapp)
        from PySide6.QtGui import QGuiApplication
        picker_windows = [win for win in QGuiApplication.allWindows() if win.isVisible() and win != w]
        assert len(picker_windows) == 1
        picker = picker_windows[0]
        if os.environ.get('MOUNT_EVIDENCE'):
            assert picker.grabWindow().save(os.environ['MOUNT_EVIDENCE'] + '/dialog.png')
        def open_button(item):
            if item.property('text') == 'Open' and 'Button' in item.metaObject().className():
                return item
            for child in item.childItems():
                found = open_button(child)
                if found is not None:
                    return found
            return None
        button = open_button(picker.contentItem())
        assert button is not None
        _click(picker, button); _pump(qapp)
        assert not dialog.property('visible')
        assert w.property('focusRoot') == str(folder.resolve())
        assert ChatSessionStore(home).load_session(sid).focusRoot == str(folder.resolve())
        b.openSession('parity-001'); b.openSession(sid)
        assert w.property('focusRoot') == str(folder.resolve())
        assert b._host.guard.assert_inside(folder) == folder.resolve()
        outside = tmp_path / 'outside'; outside.mkdir()
        with pytest.raises(PermissionError):
            b._host.guard.assert_inside(outside)
        link = folder / 'escape'; link.symlink_to(outside, target_is_directory=True)
        with pytest.raises(PermissionError):
            b._host.guard.assert_inside(link)
        saved = store.session_path(sid).read_bytes()
        assert b.acceptWorkspace(QUrl.fromLocalFile(str(outside)))
        bad = tmp_path / 'file'; bad.write_text('x')
        for url in [QUrl.fromLocalFile(str(bad)), QUrl('https://example.com'), QUrl.fromLocalFile(str(tmp_path / 'absent'))]:
            assert b.beginWorkspace() == ''
            assert b.acceptWorkspace(url)
            assert store.session_path(sid).read_bytes() == saved
        with monkeypatch.context() as denied:
            denied.setattr(os, 'access', lambda *_args: False)
            assert b.beginWorkspace() == ''
            assert b.acceptWorkspace(QUrl.fromLocalFile(str(folder))) == '无权访问该目录'
            assert store.session_path(sid).read_bytes() == saved
        assert b.beginWorkspace() == ''
        b.openSession('parity-001')
        assert b.acceptWorkspace(QUrl.fromLocalFile(str(outside)))
        b._active = ''
        assert '会话' in b.beginWorkspace()
        # New bridge restores persisted user-selected roots, as on application restart.
        from qml_shell import ShellBridge
        b._host.guard.untrust_root(folder)
        restored = ShellBridge(host=b._host, store=ChatSessionStore(home), plain=True)
        assert restored._host.guard.is_inside_root(folder)
        print('mouse dialog=visible; singleton=1; cancel=unchanged; disk/reopen/restart=ok; unauthorized/symlink/file/remote/missing/switch/no-session=rejected')
    finally:
        ticker.stop(); w.close(); engine.deleteLater(); _pump(qapp,.05)


def test_scrolled_delivery_icons_do_not_paint_over_composer(qapp, tmp_path, monkeypatch):
    w, b, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        w.setProperty('page', 'chat'); w.setWidth(1200); w.setHeight(800)
        rows = [dict(path=f'/fixture/{i}',name='Patch.java',dir='/Users/fanchunchun/ekko_workspace/app/charles/work',sizeText='5.9 MB',missing=False,openable=False,toolUseId='t') for i in range(24)]
        w.setProperty('deliveries', rows); _pump(qapp)
        scroll = w.findChild(QObject, 'bodyScroll')
        for y in range(0,480,17):
            scroll.setProperty('contentY', y); _pump(qapp,.02)
        image = w.grabWindow()
        # Three columns previously left dark icon trails in this empty composer band.
        for x in [478,1088,1118]:
            for y in range(685,725):
                color = image.pixelColor(x,y)
                assert min(color.red(),color.green(),color.blue()) > 235, (x,y,color.name())
        # Retain the actual row icons: dark pixels at the first fully visible folder.
        assert any(image.pixelColor(x,y).red() < 150 for x in range(469,487) for y in range(76,93))
        print('24 rows; three composer columns clean; visible folder retained')
    finally:
        ticker.stop(); w.close(); engine.deleteLater(); _pump(qapp,.05)
