"""Sample the unscaled QML branch-menu screenshots at fixed coordinates."""
import json
from pathlib import Path

from PySide6.QtGui import QImage


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))


out = Path('docs/audit/git-upstream')
result = {}
for phase in ('before', 'after'):
    for theme in ('dark', 'light'):
        image = QImage(str(out / f'{phase}-{theme}-branches.png'))
        assert not image.isNull()
        samples = {key: {'xy': point, 'hex': image.pixelColor(*point).name()}
                   for key, point in {'surface': (543, 750), 'border': (540, 750),
                                      'text': (599, 719)}.items()}
        a, b = sorted([luminance(samples[key]['hex']) for key in ('surface', 'text')])
        result[f'{phase}-{theme}'] = {'size': [image.width(), image.height()],
                                     'samples': samples, 'text_contrast': round((b + .05) / (a + .05), 3)}
(out / 'branch-samples.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
