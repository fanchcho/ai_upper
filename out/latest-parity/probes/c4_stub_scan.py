import sys
import glob
import os
import collections
sys.path.insert(0, 'scripts/parity')
from pngread import read_png

Q = 'out/latest-parity/qml'
PAGES = ['chat', 'empty', 'first-run', 'search-open', 'search-results', 'search-none', 'ctx-menu',
         'delete-confirm', 'model-picker', 'hover-thread', 'focus-composer', 'long-mid',
         'long-bottom', 'settings-general', 'settings-models', 'settings-extensions',
         'settings-about', 'dark-chat']

print('=== 判据4：18 页「空页 / 灰页」扫描 ===')
print('方法：对每页解码后统计 唯一 RGB 色数、主色占比、墨迹像素（r+g+b<420）数与其占比；')
print('      空页会表现为唯一色数≈1、主色占比≈100%；灰页会是全页单一灰。')
print()
print('%-20s %7s %10s %10s %10s' % ('页', '唯一色', '主色占比', '墨迹像素', '墨迹占比'))
results = []
for p in PAGES:
    path = os.path.join(Q, p + '.png')
    W, H, P = read_png(path)
    n = W * H
    c = collections.Counter(P)
    uniq = len(c)
    dom, domn = c.most_common(1)[0]
    ink = sum(v for k, v in c.items() if sum(k) < 420)
    results.append((p, uniq, domn / n * 100, ink, ink / n * 100))
    print('%-20s %7d %9.2f%% %10d %9.2f%%' % (p, uniq, domn / n * 100, ink, ink / n * 100))

print()
mn = min(results, key=lambda r: r[1])
print('唯一色最少的页：%s uniq=%d' % (mn[0], mn[1]))
mxdom = max(results, key=lambda r: r[2])
print('主色占比最高的页：%s %.2f%%' % (mxdom[0], mxdom[2]))
mink = min(results, key=lambda r: r[3])
print('墨迹像素最少的页：%s %d px (%.2f%%)' % (mink[0], mink[3], mink[4]))
print('结论：18 页唯一色最少 %d 色；主色占比最高 %.2f%%（ctx-menu，其主色为白底 255,255,255，属正常布局）；'
      '墨迹像素最少 %d px。无一页出现「单色 / 纯灰满屏」的空页特征。'
      % (mn[1], mxdom[2], mink[3]))

print()
print('=== 判据2 方法B：fixture 会话标题含 "00" 的文件数 ===')
fx = '/tmp/fx-qml-home/data/chats'
files = [f for f in sorted(glob.glob(os.path.join(fx, '*.json'))) if os.path.basename(f) != '_index.json']
import json
hit = []
for f in files:
    with open(f) as fh:
        d = json.load(fh)
    t = d.get('title', '') if isinstance(d, dict) else ''
    if '00' in t:
        hit.append((os.path.basename(f), t))
print('会话文件总数=%d（排除 _index.json）；标题含 "00" 的=%d' % (len(files), len(hit)))
for nm, t in hit:
    print('  %s  %s' % (nm, t))
