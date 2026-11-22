import sys
import collections
sys.path.insert(0, 'scripts/parity')
from pngread import read_png

D = 'out/latest-parity/deva'
Q = 'out/latest-parity/qml'

print('=== 1. dark-chat 差异的 97.82% 这个数字来自哪张表 ===')
print('   criterion4-stub-scan.log 里 dark-chat 的「墨迹占比」= 97.82%（深色页几乎全部像素 sum<420），')
print('   这不是差异百分比。page_diff18 的差异百分比见下一步。')

print()
print('=== 2. 浅色页 composer 外沿是否有投影（chat.png，y640..660）===')
W, H, A = read_png(D + '/chat-deva.png')
_, _, B = read_png(Q + '/chat.png')
for y in (630, 640, 645, 650, 655):
    print('  y=%d deva=%s qml=%s' % (y, A[y * W + 800][:3], B[y * W + 800][:3]))

print()
print('=== 3. 深色页 composer 内底色：deva #2a2a2e(bg-elevated) vs qml #1e1e20(bg) ===')
Wd, Hd, Ad = read_png(D + '/dark-chat-deva.png')
_, _, Bd = read_png(Q + '/dark-chat.png')
print('  (500,690) deva=%s qml=%s' % (Ad[690 * Wd + 500][:3], Bd[690 * Wd + 500][:3]))
print('  (900,780) deva=%s qml=%s' % (Ad[780 * Wd + 900][:3], Bd[780 * Wd + 900][:3]))
print('  (800,700) deva=%s qml=%s' % (Ad[700 * Wd + 800][:3], Bd[700 * Wd + 800][:3]))

print()
print('=== 4. 量化：若 composer 底色改为 (42,42,46)，该页可减少多少差异像素 ===')
# composer 内矩形：边框 x440..1195，y658..803
inner = 0
for y in range(660, 802):
    for x in range(442, 1194):
        a = Ad[y * Wd + x][:3]
        b = Bd[y * Wd + x][:3]
        if a != b and b == (30, 30, 32):
            inner += 1
print('  composer 内「deva!=qml 且 qml=#1e1e20」像素 = %d' % inner)

# 投影带：composer 外、deva 介于 20..29 的像素
shadow = 0
for y in range(600, 820):
    for x in range(400, 1240):
        a = Ad[y * Wd + x][:3]
        b = Bd[y * Wd + x][:3]
        if a != b and a[0] < 30 and b == (30, 30, 32):
            shadow += 1
print('  composer 外「deva<30 灰度、qml=#1e1e20」像素 = %d（投影缺失）' % shadow)

# 侧栏底部 hover 带
hover = 0
for y in range(600, 720):
    for x in range(60, 340):
        a = Ad[y * Wd + x][:3]
        b = Bd[y * Wd + x][:3]
        if a == (50, 50, 53) and b != (50, 50, 53):
            hover += 1
print('  侧栏底部 deva=(50,50,53) 而 qml 不是 的像素 = %d（悬停带缺失）' % hover)

tot = sum(1 for k in range(Wd * Hd) if Ad[k][:3] != Bd[k][:3])
print('  当前整页差异 = %d (%.2f%%)' % (tot, tot * 100.0 / (Wd * Hd)))
print('  若只修 composer 底色 + 投影：约剩 %d (%.2f%%)' %
      (tot - inner - shadow, (tot - inner - shadow) * 100.0 / (Wd * Hd)))

print()
print('=== 5. 源码：composer 与 deva 的取色对照 ===')
print('  deva apps/desktop/src/renderer/src/styles/app.css:2813-2820  .composer__box { background: var(--bg-elevated) }')
print('  deva tokens.css:112  --bg-elevated: #2a2a2e（dark） / :43  #ffffff（light）')
