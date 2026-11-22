import sys
import hashlib
sys.path.insert(0, 'scripts/parity')
from pngread import read_png

Q = 'out/latest-parity/qml'
pages = ['chat', 'long-mid', 'long-bottom']

imgs = {}
for p in pages:
    path = '%s/%s.png' % (Q, p)
    with open(path, 'rb') as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    W, H, P = read_png(path)
    imgs[p] = (W, H, P)
    print('%-12s md5=%s  %dx%d' % (p, md5, W, H))

print()
print('=== 判据1：三页 md5 两两不同 + 逐像素差 ===')
print('比较函数：像素 (r,g,b) 三通道任一不同即计为差异像素；max = 该像素最大通道差。')
for i in range(len(pages)):
    for j in range(i + 1, len(pages)):
        a, b = pages[i], pages[j]
        W, H, A = imgs[a]
        _, _, B = imgs[b]
        diff = 0
        mx = 0
        for k in range(W * H):
            ca = A[k]
            cb = B[k]
            d = max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1]), abs(ca[2] - cb[2]))
            if d:
                diff += 1
                if d > mx:
                    mx = d
        print('  %-12s vs %-12s diffpx=%d  pct=%.4f%%  max=%d' % (a, b, diff, diff * 100.0 / (W * H), mx))

print()
print('=== 判据1 附加：三页侧栏末尾可见会话标题文字带（证明滚动位置不同）===')
for p in pages:
    W, H, P = imgs[p]
    rows = []
    for y in range(40, 720):
        n = sum(1 for x in range(64, 336) if sum(P[y * W + x][:3]) < 400)
        rows.append(n)
    bands = []
    cur = None
    for y, n in zip(range(40, 720), rows):
        if n > 3:
            if cur and y - cur[-1] <= 3:
                cur.append(y)
            else:
                cur = [y]
                bands.append(cur)
    print('  %-12s 会话标题文字带 n=%d  首个=%s 末个=%s' %
          (p, len(bands), (bands[0][0], bands[0][-1]) if bands else None,
           (bands[-1][0], bands[-1][-1]) if bands else None))
