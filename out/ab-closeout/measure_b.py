from PIL import Image, ImageChops
from pathlib import Path
import hashlib
images = [("deva", "out/ab-closeout/deva-image-live.png"),
          ("before", "out/ab-closeout/b-before/chat.png"),
          ("after", "out/ab-closeout/b-after/chat.png")]
for label, name in images:
    p = Path(name)
    im = Image.open(p).convert("RGB")
    pixels = im.load()
    points = []
    for y in range(570, 640):
        for x in range(475, 530):
            r, g, b = pixels[x, y]
            if g > r+18 and g > b+10:
                points.append((x, y))
    bbox = (min(x for x,y in points), min(y for x,y in points),
            max(x for x,y in points), max(y for x,y in points)) if points else None
    print(label, "bytes="+str(p.stat().st_size), "md5="+hashlib.md5(p.read_bytes()).hexdigest(),
          "green_pixels="+str(len(points)), "green_bbox="+str(bbox))
    im.crop((475, 590, 565, 640)).save("out/ab-closeout/"+label+"-image-detail.png")
a = Image.open(images[1][1]).convert("RGB")
b = Image.open(images[2][1]).convert("RGB")
diff = ImageChops.difference(a, b)
print("before_after_changed_pixels="+str(sum(1 for c in diff.getdata() if max(c))),
      "bbox="+str(diff.getbbox()))
