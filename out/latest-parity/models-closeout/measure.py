"""Compare only Models using the repository PNG decoder; never changes inputs."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts/parity'))
from page_diff18 import load, diff

folder = Path(__file__).resolve().parent
reference = ROOT / 'out/latest-parity/deva/settings-models-deva.png'
a, width, height, digest, size = load(str(reference))
result = {'reference': {'path': str(reference.relative_to(ROOT)), 'md5': digest, 'bytes': size}}
print(f'deva bytes={size} md5={digest}')
for stage in ('before', 'after'):
    path = folder / f'settings-models-{stage}.png'
    pixels, w, h, md5, length = load(str(path))
    assert (w, h) == (width, height) == (1280, 820)
    count, maximum = diff(a, pixels, w, h)
    percent = count * 100 / (w * h)
    result[stage] = {'diff_pixels': count, 'percent': percent, 'max_channel_delta': maximum,
                     'bytes': length, 'md5': md5}
    print(f'{stage} diff={count} percent={percent:.9f}% bytes={length} md5={md5}')
(folder / 'metrics.json').write_text(json.dumps(result, indent=2) + '\n')
