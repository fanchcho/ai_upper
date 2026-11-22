"""ctx-menu / delete-confirm 的可观测判据探针（真实鼠标事件，不直接调槽位）。

判据 1：右键会话 → 菜单 5 项，标签顺序与原版一致；第 5 项 Delete 的文字像素是危险色
        （浅色 Theme.danger = #e5484d），而不是普通前景色 Theme.fg。
判据 2：三处分别注入真实 QTest.mouseClick——
        a) 取消按钮中心 → 确认层关闭、会话数不变；
        b) 确认按钮中心 → 确认层关闭、会话数 -1、活跃会话回退、会话文件消失；
        c) 遮罩空白处   → 确认层关闭、会话数不变。
        每次点击坐标都从控件 mapToScene(中心) 取，不写死截图常量。

用法（AI_UPPER_HOME 指向 /tmp 下的独立目录，不改仓库）：
    .venv/bin/python out/latest-parity/probes/c5_ctx_confirm.py
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path('/home/agent/shared_workspace/ai_upper')
HOME = Path('/tmp/ctx-confirm-probe-home')

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
os.environ['AI_UPPER_HEADLESS'] = '1'
os.environ['AI_UPPER_HOME'] = str(HOME)
os.environ['DEVA_ASSETS_DIR'] = str(ROOT / 'app' / 'assets')
os.environ['DEVA_SECRETS_BACKEND'] = 'file'
os.chdir(ROOT)

if HOME.exists():
    shutil.rmtree(HOME)
HOME.mkdir(parents=True)

sys.path.insert(0, str(ROOT / 'app' / 'src'))
sys.path.insert(0, str(ROOT / 'app' / 'tests'))
sys.path.insert(0, str(ROOT / 'scripts' / 'parity'))

from PySide6.QtCore import QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from mvvm.models.chat_models import Message  # noqa: E402
from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.persona_store import PersonaStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402
from mvvm.services.skill_store import SkillStore  # noqa: E402
from mvvm.services.workspace_guard import WorkspaceGuard  # noqa: E402
from mvvm.webui.assembly import build_chat_host  # noqa: E402

from qml_shell import (  # noqa: E402
    ShellBridge, _plain_mode, _pump, _start_ticker, qml_main,
)
from qml_shell_sessions import session_rows  # noqa: E402
from test_qml_shell import MODELS, text_stream  # noqa: E402

app = QGuiApplication.instance() or QGuiApplication([])

MENU_LABELS = ['New chat', 'Rename', 'Select', 'Archive', 'Delete']


def seed(store: ChatSessionStore, count: int = 120) -> None:
    now = int(time.time() * 1000)
    for index in range(count):
        sid = 'parity-%03d' % index
        session = store.ensure_session(sid)
        session.messages = [Message(role='user', content='对比用会话：一条完整回合')]
        session.title = ('对比用会话：一条完整回合' if index == 0
                         else '会话 %03d：准备发布说明' % index)
        session.updatedAt = now - index * 1000
        store.save(sid)


settings = SettingsService(HOME)
settings.set_config({'models': MODELS})
vault = SecretsVault(HOME)
vault.set_secret('p1', 'sk-test')
store = ChatSessionStore(HOME)
seed(store)
PersonaStore(HOME).ensure_seeded()

box: dict = {}


def emit(payload):
    box['bridge'].emit(payload)


host, _gw = build_chat_host(
    settings=settings, vault=vault, store=store, guard=WorkspaceGuard(), home=HOME,
    emit=emit, emit_sessions_changed=lambda: None, transport=text_stream('x'),
)
bridge = ShellBridge(host=host, store=store, plain=_plain_mode(), settings=settings,
                     vault=vault, skills=SkillStore(HOME))
box['bridge'] = bridge

engine = QQmlApplicationEngine()
bridge._engine = engine
engine.rootContext().setContextProperty('shellBridge', bridge)
engine.load(QUrl.fromLocalFile(str(qml_main())))
window = engine.rootObjects()[0]
bridge.bind_window(window)
bridge.initial()
window.setProperty('page', 'chat')
window.show()
ticker = _start_ticker(bridge)
_pump(app, lambda: False, 0.6)


def find_item(root, name):
    try:
        if root.objectName() == name:
            return root
    except Exception:
        pass
    for child in root.childItems():
        got = find_item(child, name)
        if got is not None:
            return got
    return None


def center(item):
    p = item.mapToScene(QPointF(item.property('width') / 2.0,
                                item.property('height') / 2.0))
    return p.x(), p.y()


def bbox(item):
    tl = item.mapToScene(QPointF(0, 0))
    br = item.mapToScene(QPointF(item.property('width'), item.property('height')))
    return tl.x(), tl.y(), br.x(), br.y()


def label_of(item):
    for child in item.childItems():
        for grandchild in child.childItems():
            text = grandchild.property('text')
            if isinstance(text, str) and text:
                return text
    return ''


def click(item, button=Qt.LeftButton):
    x, y = center(item)
    QTest.mouseClick(window, button, Qt.NoModifier, QPoint(round(x), round(y)), 100)


def click_point(x, y, button=Qt.LeftButton):
    QTest.mouseClick(window, button, Qt.NoModifier, QPoint(int(x), int(y)), 100)


def pixel_reader():
    """返回 (w, h, px)；px(x, y) -> (r, g, b)。按实际 format 取通道，不猜。"""
    image = window.grabWindow()
    w, h = image.width(), image.height()
    bits = image.constBits()
    stride = image.bytesPerLine()
    fmt = image.format()

    def px(x, y):
        off = y * stride + x * 4
        c0, c1, c2 = bits[off], bits[off + 1], bits[off + 2]
        if fmt in (image.Format.Format_RGB32, image.Format.Format_ARGB32,
                   image.Format.Format_ARGB32_Premultiplied):
            return c2, c1, c0          # BGRA 存储
        return c0, c1, c2              # RGBA8888
    return w, h, px


print('=== 判据 1：右键菜单 5 项 + Delete 危险色 ===')
print('  起始页=chat，ctxMenu 可见=%s（应为 False）'
      % find_item(window.contentItem(), 'ctxMenu').property('visible'))
row0 = find_item(window.contentItem(), 'threadRow0')
print('  对会话行 threadRow0 中心 %s 注入右键'
      % (tuple(round(v, 1) for v in center(row0)),))
click(row0, Qt.RightButton)
_pump(app, lambda: False, 0.35)
print('  右键后 ctxMenu 可见=%s' % find_item(window.contentItem(), 'ctxMenu').property('visible'))
items = [find_item(window.contentItem(), 'ctxMenuItem%d' % i) for i in range(5)]
labels = [label_of(it) for it in items]
print('  labels        = %s' % labels)
print('  labels==deva  = %s' % (labels == MENU_LABELS))
for i, it in enumerate(items):
    cx, cy = center(it)
    print('  item%d %-9s 中心=(%.1f, %.1f) bbox=%s'
          % (i, labels[i], cx, cy, tuple(round(v, 1) for v in bbox(it))))

W, H, PX = pixel_reader()
print('  抓图尺寸 = %dx%d' % (W, H))
print('  Theme.danger(浅 #e5484d) = (229, 72, 77)')
print('  Theme.fg(浅 #1e1e20)     = (30, 30, 32)')


def color_stats(item):
    x0, y0, x1, y1 = bbox(item)
    red = dark = 0
    for y in range(int(y0), int(y1)):
        for x in range(int(x0), int(x1)):
            r, g, b = PX(x, y)
            if r > 150 and r > g + 60 and r > b + 50:
                red += 1
            if r + g + b < 320:
                dark += 1
    return red, dark


stats = []
for i, it in enumerate(items):
    red, dark = color_stats(it)
    stats.append((red, dark))
    print('  item%d %-9s 红色像素=%-4d 深色文字像素=%-4d' % (i, labels[i], red, dark))

red5 = stats[4][0]


def deva_compare():
    """同一 bbox、同一判据，在 deva 参考图上量一遍，证明危险色取值与参考一致。"""
    from pngread import read_png
    dw, dh, D = read_png(str(ROOT / 'out/latest-parity/deva/ctx-menu-deva.png'))
    rows = []
    for i, it in enumerate(items):
        x0, y0, x1, y1 = [int(v) for v in bbox(it)]
        red = dark = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                r, g, b = D[y * dw + x][:3]
                if r > 150 and r > g + 60 and r > b + 50:
                    red += 1
                if r + g + b < 320:
                    dark += 1
        rows.append((labels[i], red, dark))
    return rows


print()
print('  同一 bbox 在 deva 参考图上的同判据计数：')
for name, red, dark in deva_compare():
    print('    deva %-9s 红色像素=%-4d 深色文字像素=%-4d' % (name, red, dark))
print('  结论1a：项数=%d，标签顺序=%s'
      % (len(items), '与原版一致' if labels == MENU_LABELS else '不一致'))
print('  结论1b：Delete 红色像素=%d（%s）；其余四项红色像素=%s'
      % (red5, '危险色' if red5 > 20 else '非危险色', [s[0] for s in stats[:4]]))

print()
print('=== 判据 2：三处真实鼠标点击 ===')
confirm = find_item(window.contentItem(), 'confirmLayer')
before = len(session_rows(store))
print('  起点：sessions=%d active=%s parity-000 文件存在=%s'
      % (before, bridge._active, store.session_path('parity-000').exists()))

# a) Cancel 中心
click(items[4])
_pump(app, lambda: False, 0.35)
cancel_btn = find_item(window.contentItem(), 'confirmCancel')
delete_btn = find_item(window.contentItem(), 'confirmDelete')
print('  点菜单 Delete 后：confirm visible=%s' % confirm.property('visible'))
print('  confirmCancel 中心=%s   bbox=%s'
      % (tuple(round(v, 1) for v in center(cancel_btn)),
         tuple(round(v, 1) for v in bbox(cancel_btn))))
print('  confirmDelete 中心=%s   bbox=%s'
      % (tuple(round(v, 1) for v in center(delete_btn)),
         tuple(round(v, 1) for v in bbox(delete_btn))))
click(cancel_btn)
_pump(app, lambda: False, 0.35)
n_after_cancel = len(session_rows(store))
print('  [a] 点取消中心后：confirm visible=%s confirmOpen=%s sessions=%d active=%s 文件存在=%s'
      % (confirm.property('visible'), window.property('confirmOpen'),
         n_after_cancel, bridge._active, store.session_path('parity-000').exists()))

# b) Delete 中心
click(find_item(window.contentItem(), 'threadRow0'), Qt.RightButton)
_pump(app, lambda: False, 0.35)
items = [find_item(window.contentItem(), 'ctxMenuItem%d' % i) for i in range(5)]
click(items[4])
_pump(app, lambda: False, 0.35)
click(find_item(window.contentItem(), 'confirmDelete'))
_pump(app, lambda: False, 0.6)
n_after_confirm = len(session_rows(store))
print('  [b] 点确认中心后：confirm visible=%s confirmOpen=%s sessions=%d active=%s parity-000 文件存在=%s'
      % (confirm.property('visible'), window.property('confirmOpen'),
         n_after_confirm, bridge._active, store.session_path('parity-000').exists()))

# c) 遮罩空白
click(find_item(window.contentItem(), 'threadRow0'), Qt.RightButton)
_pump(app, lambda: False, 0.35)
items = [find_item(window.contentItem(), 'ctxMenuItem%d' % i) for i in range(5)]
click(items[4])
_pump(app, lambda: False, 0.35)
bx0, by0, bx1, by1 = bbox(find_item(window.contentItem(), 'confirmDialog'))
print('  confirmDialog bbox=%s' % (tuple(round(v, 1) for v in (bx0, by0, bx1, by1)),))
click_point(100, 700)
_pump(app, lambda: False, 0.35)
n_after_backdrop = len(session_rows(store))
print('  [c] 点遮罩空白 (100,700) 后：confirm visible=%s confirmOpen=%s sessions=%d active=%s'
      % (confirm.property('visible'), window.property('confirmOpen'),
         n_after_backdrop, bridge._active))

print()
print('=== 结果摘要 ===')
ok1 = len(items) == 5 and labels == MENU_LABELS and red5 > 20
ok2a = n_after_cancel == before
ok2b = n_after_confirm == before - 1 and not store.session_path('parity-000').exists()
ok2c = confirm.property('visible') is False and n_after_backdrop == n_after_confirm
print('  判据1（5 项 + Delete 危险色）= %s' % ok1)
print('  判据2a（取消关闭不删）= %s   [%d -> %d]' % (ok2a, before, n_after_cancel))
print('  判据2b（确认关闭并删）= %s   [%d -> %d]' % (ok2b, n_after_cancel, n_after_confirm))
print('  判据2c（遮罩关闭不删）= %s   [%d -> %d]' % (ok2c, n_after_confirm, n_after_backdrop))
print('  ALL = %s' % (ok1 and ok2a and ok2b and ok2c))

ticker.stop()
window.close()
engine.deleteLater()
