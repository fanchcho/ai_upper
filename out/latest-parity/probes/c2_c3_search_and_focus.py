import sys
sys.path.insert(0, 'scripts/parity')
from pngread import read_png

Q = 'out/latest-parity/qml'
D = 'out/latest-parity/deva'


def is_purpleish(c):
    r, g, b = c
    return abs(r - 138) <= 25 and abs(g - 56) <= 25 and abs(b - 245) <= 25


def clusters(ys, gap=20):
    out = []
    cur = None
    for y in ys:
        if cur and y - cur[-1] <= gap:
            cur.append(y)
        else:
            cur = [y]
            out.append(cur)
    return [(c[0], c[-1]) for c in out]


print('=== 判据2：search-results 命中行数（头像列 x70..108 的紫色头像簇）===')
for tag, path in (('qml', f'{Q}/search-results.png'), ('deva', f'{D}/search-results-deva.png')):
    W, H, P = read_png(path)
    ys = [y for y in range(40, 780) if any(is_purpleish(P[y * W + x][:3]) for x in range(70, 108))]
    cl = clusters(ys)
    ns = [sum(1 for y in range(a, b + 1) for x in range(70, 108) if is_purpleish(P[y * W + x][:3])) for a, b in cl]
    print('  %s 簇数=%2d  tops=%s' % (tag, len(cl), [a for a, b in cl]))
    print('     每簇像素数=%s' % ns)
    print('     簇高=%s' % [b - a + 1 for a, b in cl])

print()
print('=== 判据3：focus-composer 输入卡片四边取色 ===')
pts = [('上', 800, 658), ('下', 800, 803), ('左', 428, 740), ('右', 1207, 740)]
for tag, path in (('qml focus', f'{Q}/focus-composer.png'), ('qml chat(未聚焦)', f'{Q}/chat.png'),
                  ('deva focus', f'{D}/focus-composer-deva.png'), ('deva chat(未聚焦)', f'{D}/chat-deva.png')):
    W, H, P = read_png(path)
    vals = []
    for name, x, y in pts:
        c = P[y * W + x][:3]
        vals.append('%s(%d,%d)=(%d,%d,%d)' % (name, x, y, c[0], c[1], c[2]))
    print('  %-16s %s' % (tag, '  '.join(vals)))

print()
print('=== 判据3 补充：沿输入卡片上边横扫，找连续的高饱和边框像素段 ===')
for tag, path in (('qml focus', f'{Q}/focus-composer.png'), ('qml chat', f'{Q}/chat.png'),
                  ('deva focus', f'{D}/focus-composer-deva.png')):
    W, H, P = read_png(path)
    for y in (657, 658, 659):
        xs = [x for x in range(420, 1215) if P[y * W + x][2] - P[y * W + x][0] > 40]
        if xs:
            print('  %-11s y=%d 紫蓝像素数=%d x=%d..%d 首色=%s' %
                  (tag, y, len(xs), xs[0], xs[-1], P[y * W + xs[0]][:3]))
        else:
            print('  %-11s y=%d 紫蓝像素数=0' % (tag, y))
