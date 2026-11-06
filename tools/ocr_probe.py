import json
import sys
import time
from pathlib import Path

sys.path[:0] = [".ocrdeps", ".pdfium"]
from rapidocr_onnxruntime import RapidOCR

img = sys.argv[1]
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("samples/ocr-out.json")
ocr = RapidOCR()
t0 = time.time()
result, elapse = ocr(img)
rows = []
for box, text, score in result or []:
    rows.append(
        {
            "box": [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in box],
            "text": text,
            "score": round(float(score), 3),
        }
    )
rows.sort(key=lambda z: (z["box"][0][1], z["box"][0][0]))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
out.with_suffix(".txt").write_text("\n".join(r["text"] for r in rows), encoding="utf-8")
print("lines", len(rows), "elapsed", round(time.time() - t0, 2), elapse)
for r in rows:
    print(f"{r['box'][0][1]:6.0f} {r['score']:.2f} {r['text']}")

