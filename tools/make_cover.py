from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path("data/assets/cover-jinshu.jpg")
OUT.parent.mkdir(parents=True, exist_ok=True)

W, H = 817, 1200
base = Image.new("RGB", (W, H), (162, 181, 134))
px = base.load()
# subtle paper grain
for y in range(H):
    for x in range(W):
        n = ((x * 13 + y * 7 + (x * y) % 17) % 11) - 5
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
draw = ImageDraw.Draw(base)
# cloth-like vertical weave
for x in range(0, W, 4):
    draw.line([(x, 0), (x, H)], fill=(156, 175, 128), width=1)

# inner frame
draw.rectangle([36, 36, W - 36, H - 36], outline=(62, 82, 55), width=2)
draw.rectangle([46, 46, W - 46, H - 46], outline=(204, 212, 178), width=1)

font_path = "C:/Windows/Fonts/STSONG.TTF"
if not Path(font_path).exists():
    font_path = "C:/Windows/Fonts/simsun.ttc"
font = ImageFont.truetype(font_path, 148)
small = ImageFont.truetype(font_path, 34)
seal_font = ImageFont.truetype(font_path, 30)

# vertical title: 晉 / 書
for i, ch in enumerate("晉書"):
    bbox = draw.textbbox((0, 0), ch, font=font)
    draw.text((213, 173 + i * 168), ch, font=font, fill=(76, 89, 63))
    draw.text((210, 170 + i * 168), ch, font=font, fill=(28, 27, 22))

# small label
draw.text((520, 880), "青简", font=small, fill=(238, 235, 215))
draw.text((520, 930), "ReadHistory", font=ImageFont.truetype(font_path, 20), fill=(220, 219, 196))
# seal
draw.rectangle([520, 985, 596, 1061], fill=(140, 50, 38))
draw.text((535, 1002), "青", font=seal_font, fill=(245, 234, 214))

base.save(OUT, quality=90, optimize=True)
print(OUT, base.size)
