import sys
from pathlib import Path

sys.path.insert(0, ".")
from reader.ocr import estimate_rotation, render_page

pdf = next(Path(".").glob("*.pdf"))
for n in (1, 49, 101):
    img = render_page(str(pdf), n, 110)
    print(n, img.size, img.mode, estimate_rotation(img))
    img.save(f"test-{n}.jpg", quality=70)
