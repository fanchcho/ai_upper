"""Compare before/after RGB pixels and each image against the retained deva reference."""
import sys
from pathlib import Path
from PySide6.QtGui import QImage

root = Path(sys.argv[1])
for page in ('chat', 'settings-general'):
    paths = [root / f'controlled-{phase}-{page}.png' for phase in ('before', 'after')]
    paths.append(Path('out/latest-parity/deva') / f'{page}-deva.png')
    images = [QImage(str(p)).convertToFormat(QImage.Format_RGB32) for p in paths]
    assert all((i.width(), i.height()) == (1280, 820) for i in images)
    before, after, reference = [i.constBits().cast('I') for i in images]

    def difference(a, b):
        return 100 * sum(x != y for x, y in zip(a, b)) / len(a)

    old, new = difference(before, reference), difference(after, reference)
    print(f'{page}: 1280x820; deva difference {old:.9f}% -> {new:.9f}%; '
          f'before/after {difference(before, after):.9f}%')
    assert new <= old
