from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for dep in (".ocr2", ".ocrdeps", ".pdfium"):
    p = str(ROOT / dep)
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
from PIL import Image

_ENGINE = None
_ENGINE_KEY = None


def resolve_pdf(pdf_path: str | None) -> str | None:
    """Resolve the source PDF without hard-coding a user's absolute path."""
    env = os.environ.get("READHISTORY_PDF")
    raw = env or pdf_path or ""
    if raw:
        p = Path(raw)
        candidates = [p] if p.is_absolute() else [ROOT / p, ROOT / "data" / "inbox" / p.name]
        for cand in candidates:
            if cand.exists() and cand.is_file():
                return str(cand)
    inbox = ROOT / "data" / "inbox"
    for name in ("jinshu.pdf", "晉書.pdf", "晋书.pdf"):
        p = inbox / name
        if p.exists():
            return str(p)
    pdfs = sorted(ROOT.glob("*.pdf"))
    if len(pdfs) == 1:
        return str(pdfs[0])
    if inbox.exists():
        found = sorted(inbox.glob("*.pdf"))
        if len(found) == 1:
            return str(found[0])
    return None


def render_page(pdf_path: str, page_no: int, dpi: int = 170) -> Image.Image:
    """Render one 1-based PDF page at a readable resolution.

    pypdfium2 is used instead of PyMuPDF so the project can remain MIT
    licensed (PDFium is Apache-2.0 / BSD-3-Clause).
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        if page_no < 1 or page_no > len(pdf):
            raise ValueError(f"页码超出范围：{page_no}")
        page = pdf[page_no - 1]
        bmp = page.render(scale=dpi / 72)
        img = bmp.to_pil()
        return img.convert("RGB") if img.mode != "RGB" else img
    finally:
        pdf.close()


def estimate_rotation(img: Image.Image) -> int:
    """Return the PIL rotation needed to make text lines horizontal.

    The scanned 1974 edition has body pages stored 90° clockwise. Text lines
    therefore appear as tall vertical strips. We compare ink projection
    variance, which is high across the line direction.
    """
    small = img.copy()
    small.thumbnail((900, 900))
    gray = np.asarray(small.convert("L"), dtype=np.uint8)
    h, w = gray.shape
    crop = gray[int(h * 0.07) : int(h * 0.93), int(w * 0.06) : int(w * 0.94)]
    ink = (crop < 175).astype(np.float32)
    row = ink.sum(axis=1)
    col = ink.sum(axis=0)
    # Ignore a few huge values from scanner edges.
    row_var = float(np.var(np.clip(row, 0, np.percentile(row, 99))))
    col_var = float(np.var(np.clip(col, 0, np.percentile(col, 99))))
    if col_var > row_var * 1.35:
        return 90
    return 0


def _clean_text(text: str) -> str:
    text = text.strip()
    text = text.replace("\u3000", "").replace(" ", "")
    text = text.replace("‘", "「").replace("’", "」")
    text = re.sub(r"[·•]+", "，", text)
    text = text.replace("°", "。")
    text = re.sub(r"([，。；：！？])\1+", r"\1", text)
    text = re.sub(r"^[，。；：]+", "", text)
    # Common traditional-character OCR confusions in this edition.
    fixes = [
        (r"韶日", "詔曰"),
        (r"韶", "詔"),
        (r"帝日", "帝曰"),
        (r"謂日", "謂曰"),
        (r"答日", "答曰"),
        (r"對日", "對曰"),
        (r"禁鋼", "禁錮"),
        (r"大放", "大赦"),
        (r"用祭", "弔祭"),
        (r"丙成", "丙戌"),
        (r"皇石", "皇后"),
        (r"辛王", "辛丑"),
        (r"黃鐵", "黃鉞"),
        (r"黄鐵", "黃鉞"),
        (r"於郡國", "于郡國"),
    ]
    for pattern, repl in fixes:
        text = re.sub(pattern, repl, text)
    return text.strip()


def _box_xy(box) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    return min(xs), min(ys), max(xs), max(ys)


def _engine(lang_rec: str = "chinese_cht_mobile"):
    global _ENGINE, _ENGINE_KEY
    if _ENGINE is not None and _ENGINE_KEY == lang_rec:
        return _ENGINE
    from rapidocr import RapidOCR

    _ENGINE = RapidOCR(
        params={
            "Global.lang_det": "ch_mobile",
            "Global.lang_rec": lang_rec,
            "Global.text_score": 0.35,
            "Global.max_side_len": 2300,
            "Rec.rec_batch_num": 8,
        }
    )
    _ENGINE_KEY = lang_rec
    return _ENGINE


def ocr_image(img: Image.Image, lang_rec: str = "chinese_cht_mobile", rotate: bool | None = None):
    if rotate is None:
        angle = estimate_rotation(img)
        if angle:
            img = img.rotate(angle, expand=True)
    engine = _engine(lang_rec)
    arr = np.asarray(img.convert("RGB"))[:, :, ::-1].copy()
    result = engine(arr)
    rows: list[dict[str, Any]] = []
    if result.boxes is None:
        return rows, img
    for box, text, score in zip(result.boxes, result.txts, result.scores):
        cleaned = _clean_text(str(text))
        if not cleaned:
            continue
        x0, y0, x1, y1 = _box_xy(box)
        rows.append(
            {
                "text": cleaned,
                "box": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                "score": round(float(score), 3),
            }
        )
    rows.sort(key=lambda r: (r["box"][1], r["box"][0]))
    return rows, img


def _is_running_head(text: str) -> bool:
    compact = text.replace(" ", "")
    if re.fullmatch(r"[一二三四五六七八九十百千〇零\dⅠⅡⅢIVX]+", compact):
        return True
    if len(compact) <= 12 and re.search(r"晉書|晋书|帝紀|帝纪|列傳|列传|志第|卷[一二三四五六七八九十百]", compact):
        return True
    return False


def analyze_page(
    pdf_path: str,
    page_no: int,
    book_id: str = "jinshu",
    dpi: int = 170,
    lang_rec: str = "chinese_cht_mobile",
    save_image: bool = True,
) -> dict[str, Any]:
    raw = render_page(pdf_path, page_no, dpi=dpi)
    angle = estimate_rotation(raw)
    img = raw.rotate(angle, expand=True) if angle else raw
    lines, img = ocr_image(img, lang_rec=lang_rec, rotate=False)
    w, h = img.size
    body = [ln for ln in lines if 0.065 * h < (ln["box"][1] + ln["box"][3]) / 2 < 0.93 * h]
    heads = [ln for ln in lines if ln not in body]
    body.sort(key=lambda ln: (ln["box"][1], ln["box"][0]))

    heights = [ln["box"][3] - ln["box"][1] for ln in body] or [1]
    char_h = float(np.median(heights))
    left = float(np.percentile([ln["box"][0] for ln in body], 18)) if body else 0.0

    paragraphs: list[dict[str, Any]] = []
    current = ""
    current_boxes: list[list[float]] = []
    current_scores: list[float] = []
    for ln in body:
        x0, y0, x1, y1 = ln["box"]
        indent = x0 - left
        starts_new = indent > char_h * 0.85
        if current and (starts_new or (y1 - y0) > char_h * 1.35):
            paragraphs.append(
                {
                    "text": current,
                    "box": [
                        min(b[0] for b in current_boxes),
                        min(b[1] for b in current_boxes),
                        max(b[2] for b in current_boxes),
                        max(b[3] for b in current_boxes),
                    ],
                    "confidence": round(sum(current_scores) / len(current_scores), 3),
                    "page": page_no,
                }
            )
            current = ""
            current_boxes = []
            current_scores = []
        current += ln["text"]
        current_boxes.append(ln["box"])
        current_scores.append(ln["score"])
    if current:
        paragraphs.append(
            {
                "text": current,
                "box": [
                    min(b[0] for b in current_boxes),
                    min(b[1] for b in current_boxes),
                    max(b[2] for b in current_boxes),
                    max(b[3] for b in current_boxes),
                ],
                "confidence": round(sum(current_scores) / len(current_scores), 3),
                "page": page_no,
            }
        )

    running_head = " ".join(ln["text"] for ln in heads if _is_running_head(ln["text"]))[:60]
    page_label = ""
    for ln in heads:
        if re.fullmatch(r"[一二三四五六七八九十百千〇零\d]+", ln["text"].replace(" ", "")):
            page_label = ln["text"].replace(" ", "")
    kind = "body"
    if len(body) < 4:
        kind = "cover" if len(lines) < 4 else "plate"
    if any((ln["box"][3] - ln["box"][1]) > char_h * 1.45 for ln in body[:4]):
        kind = "chapter-head" if kind == "body" else kind

    if save_image:
        out_dir = ROOT / "data" / "pages" / book_id
        out_dir.mkdir(parents=True, exist_ok=True)
        img.save(out_dir / f"{page_no:04d}.jpg", quality=86, optimize=True)

    return {
        "page": page_no,
        "rotation": angle,
        "width": w,
        "height": h,
        "kind": kind,
        "running_head": running_head,
        "page_label": page_label,
        "lines": lines,
        "head_lines": heads,
        "paragraphs": paragraphs,
        "average_confidence": round(
            sum(ln["score"] for ln in body) / len(body), 3
        )
        if body
        else None,
    }


def render_cover(pdf_path: str, page_no: int = 1, out_path: str | None = None) -> str:
    img = render_page(pdf_path, page_no, dpi=150)
    img.thumbnail((900, 1200))
    dest = Path(out_path) if out_path else ROOT / "data" / "assets" / "cover-jinshu.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, quality=88, optimize=True)
    return str(dest)


def to_json(result: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
