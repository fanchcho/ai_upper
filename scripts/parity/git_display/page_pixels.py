"""Actual screenshot samples; no image scaling, compositing or color replacement."""
import json
from pathlib import Path
from PySide6.QtGui import QImage


def sample(image, x, y):
    return {'xy': [x, y], 'hex': image.pixelColor(x, y).name()}


def ink(image, color, bounds):
    left, top, right, bottom = bounds
    for y in range(top, bottom):
        for x in range(left, right):
            if image.pixelColor(x, y).name() == color:
                return sample(image, x, y)
    raise AssertionError((color, bounds))


def luminance(color):
    values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(v * w for v, w in zip(values, (.2126, .7152, .0722)))


def contrast(a, b):
    low, high = sorted([luminance(a['hex']), luminance(b['hex'])])
    return round((high + .05) / (low + .05), 3)


root = Path('docs/audit/git-upstream')
result = {}
for phase in ('before', 'final'):
    result[phase] = {}
    for theme in ('dark', 'light'):
        folder = root / f'style-{phase}'
        im = QImage(str(folder / f'{theme}-commit.png'))
        warn = QImage(str(folder / f'{theme}-warning.png'))
        menu = QImage(str(folder / f'{theme}-menu.png'))
        fg = '#e4e4e7' if theme == 'dark' else '#1f1f24'
        muted = '#a1a1aa' if theme == 'dark' else '#5c5c66'
        warning = '#fcc419' if theme == 'dark' else '#d9860b'
        data = {
            'size': [im.width(), im.height()],
            'backdrop': sample(im, 900, 200),
            'dialog_surface': sample(im, 420, 500),
            'dialog_border': sample(im, 410, 500),
            'input_surface': sample(im, 600, 550),
            'input_border': sample(im, 431 if phase == 'final' else 430, 550),
            'placeholder': ink(im, muted, (440, 483, 550, 525)),
            'heading': ink(im, fg, (430, 405, 510, 445)),
            'menu_surface': sample(menu, 543, 808),
            'menu_separator': sample(menu, 560, 920),
            'warning_surface': sample(warn, 550, 422),
            'warning_border': sample(warn, 550, 416),
            'warning_text': ink(warn, warning, (510, 413, 880, 445)),
        }
        data['heading_contrast'] = contrast(data['heading'], data['dialog_surface'])
        data['placeholder_contrast'] = contrast(data['placeholder'], data['input_surface'])
        data['warning_contrast'] = contrast(data['warning_text'], data['warning_surface'])
        result[phase][theme] = data
(root / 'page-samples.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
