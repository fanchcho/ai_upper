"""dark-chat 输入卡片修复的前后对照：只读 PNG，不改仓库。

改前图取自 `git show HEAD:out/latest-parity/qml/dark-chat.png`（写入临时目录），
改后图为工作区当前 `out/latest-parity/qml/dark-chat.png`。

用法：
    git show HEAD:out/latest-parity/qml/dark-chat.png > /tmp/pre/dark-chat.png
    python out/latest-parity/probes/dark_composer_ab.py /tmp/pre/dark-chat.png
"""
import sys

sys.path.insert(0, 'scripts/parity')
from pngread import read_png  # noqa: E402

DEVA = 'out/latest-parity/deva/dark-chat-deva.png'
POST = 'out/latest-parity/qml/dark-chat.png'
PRE = sys.argv[1]

W, H, A = read_png(DEVA)
_, _, P = read_png(PRE)
_, _, B = read_png(POST)


def whole(X):
    n = sum(1 for k in range(W * H) if A[k][:3] != X[k][:3])
    return n, n * 100.0 / (W * H)


def region(X, x0, x1, y0, y1):
    n = tot = 0
    for y in range(y0, min(y1, H)):
        for x in range(x0, min(x1, W)):
            tot += 1
            if A[y * W + x][:3] != X[y * W + x][:3]:
                n += 1
    return n, tot, 100.0 * n / tot


print('=== 整页差异 ===')
for tag, X in (('改前', P), ('改后', B)):
    n, pct = whole(X)
    print('  %s %6d px  %5.2f%%' % (tag, n, pct))

print()
print('=== 分区差异（同一判据，仅换统计窗口）===')
for name, box in (
    ('输入卡片 440..1195 × 658..804', (440, 1195, 658, 804)),
    ('卡片+投影 400..1240 × 620..820', (400, 1240, 620, 820)),
    ('左侧栏 0..400（未触及）', (0, 400, 0, 820)),
    ('正文 400..1240 × 60..620（未触及）', (400, 1240, 60, 620)),
):
    a = region(P, *box)
    b = region(B, *box)
    print('  %-34s 改前 %6d/%6d %6.2f%%   改后 %6d/%6d %6.2f%%'
          % (name, a[0], a[1], a[2], b[0], b[1], b[2]))

print()
print('=== 卡面底色探针 (deva / 改前 / 改后) ===')
for x, y in ((500, 690), (800, 700), (900, 780)):
    print('  (%d,%d) %s %s %s'
          % (x, y, tuple(A[y * W + x][:3]), tuple(P[y * W + x][:3]), tuple(B[y * W + x][:3])))

print()
print('=== 卡下投影探针 x=800 (deva / 改前 / 改后) ===')
for y in (805, 808, 812, 816, 819):
    print('  y=%d %s %s %s'
          % (y, tuple(A[y * W + 800][:3]), tuple(P[y * W + 800][:3]), tuple(B[y * W + 800][:3])))

print()
print('=== 卡左投影探针 y=700 (deva / 改前 / 改后) ===')
for x in range(400, 437, 4):
    print('  x=%d %s %s %s'
          % (x, tuple(A[700 * W + x][:3]), tuple(P[700 * W + x][:3]), tuple(B[700 * W + x][:3])))
