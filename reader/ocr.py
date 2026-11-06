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

from . import paths

_ENGINE = None
_ENGINE_KEY = None


def resolve_pdf(pdf_path: str | None) -> str | None:
    """Resolve a source PDF from the data folder, inbox, or an env override."""
    env = os.environ.get("READHISTORY_PDF")
    raw = env or pdf_path or ""
    if raw:
        p = Path(raw)
        candidates = [p] if p.is_absolute() else [
            paths.HOME / p,
            paths.APP_ROOT / p,
            paths.DATA / p,
            paths.DATA / "inbox" / p.name,
        ]
        for cand in candidates:
            if cand.exists() and cand.is_file():
                return str(cand)
    inbox = paths.DATA / "inbox"
    for name in ("jinshu.pdf", "晉書.pdf", "晋书.pdf"):
        p = inbox / name
        if p.exists():
            return str(p)
    pdfs = sorted(paths.APP_ROOT.glob("*.pdf"))
    if len(pdfs) == 1:
        return str(pdfs[0])
    if inbox.exists():
        found = sorted(inbox.glob("*.pdf"))
        if len(found) == 1:
            return str(found[0])
    return None


def pdf_info(pdf_path: str) -> dict[str, Any]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        pages = len(pdf)
        width = height = 0
        if pages:
            width, height = pdf[0].get_size()
        meta: dict[str, Any] = {}
        try:
            meta = pdf.get_metadata_dict() or {}
        except Exception:
            meta = {}
        return {
            "pages": pages,
            "width": round(width, 1),
            "height": round(height, 1),
            "title": (meta.get("Title") or "").strip(),
            "author": (meta.get("Author") or "").strip(),
        }
    finally:
        pdf.close()


def render_page(pdf_path: str, page_no: int, dpi: int = 170) -> Image.Image:
    """Render one 1-based PDF page at a readable resolution."""
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


def _line_orientation(img: Image.Image) -> str:
    """Return ``vertical`` when text lines run down the page, else horizontal."""
    small = img.copy()
    small.thumbnail((900, 900))
    gray = np.asarray(small.convert("L"), dtype=np.uint8)
    h, w = gray.shape
    crop = gray[int(h * 0.07) : int(h * 0.93), int(w * 0.06) : int(w * 0.94)]
    ink = (crop < 175).astype(np.float32)
    row = ink.sum(axis=1)
    col = ink.sum(axis=0)
    row_var = float(np.var(np.clip(row, 0, np.percentile(row, 99))))
    col_var = float(np.var(np.clip(col, 0, np.percentile(col, 99))))
    return "vertical" if col_var > row_var * 1.2 else "horizontal"


def estimate_rotation(img: Image.Image, layout: str = "horizontal") -> int:
    """Return the PIL counter-clockwise angle that makes the page upright.

    ``layout`` is the writing direction of the *content*: a vertically set
    book has vertical columns when upright, a horizontally set book has
    horizontal rows. If the observed line direction disagrees, the scan was
    turned by 90 degrees.
    """
    orient = _line_orientation(img)
    if layout == "vertical":
        return 90 if orient == "horizontal" else 0
    return 90 if orient == "vertical" else 0


def _clean_text(text: str) -> str:
    text = text.strip()
    text = text.replace("\u3000", "").replace(" ", "")
    text = text.replace("‘", "「").replace("’", "」")
    text = re.sub(r"[·•]+", "，", text)
    text = text.replace("°", "。")
    text = re.sub(r"([，。；：！？])\1+", r"\1", text)
    text = re.sub(r"^[，。；：]+", "", text)
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
            "Global.text_score": 0.3,
            "Global.max_side_len": 2300,
            "Rec.rec_batch_num": 12,
        }
    )
    _ENGINE_KEY = lang_rec
    return _ENGINE


def _rows_from_engine(result) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if getattr(result, "boxes", None) is None:
        return rows
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
    return rows


def _ocr_horizontal(img: Image.Image, lang_rec: str):
    engine = _engine(lang_rec)
    arr = np.asarray(img.convert("RGB"))[:, :, ::-1].copy()
    result = engine(arr)
    rows = _rows_from_engine(result)
    rows.sort(key=lambda r: (r["box"][1], r["box"][0]))
    return rows, img


# ---------- vertical (traditional) typesetting ----------


def _binarize(img: Image.Image):
    import cv2

    gray = np.asarray(img.convert("L"), dtype=np.uint8)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return gray, bw


def _char_size(bw, fallback: int = 24) -> int:
    import cv2

    h, w = bw.shape
    n, _labels, stats, _cent = cv2.connectedComponentsWithStats(bw, 8)
    sizes: list[float] = []
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if area < (h * w) * 2e-6 or area > (h * w) * 0.02:
            continue
        if hh > h * 0.45 or ww > w * 0.45:
            continue
        if 0.3 <= ww / max(hh, 1) <= 3.2:
            sizes.append((ww + hh) / 2)
    if not sizes:
        return fallback
    return max(10, int(np.median(sizes)))


def _find_columns(bw, char_size: int):
    import cv2

    h, w = bw.shape
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(3, char_size // 6), max(7, int(char_size * 1.15)))
    )
    merged = cv2.dilate(bw, kernel, iterations=1)
    merged = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[list[int]] = []
    for contour in contours:
        x, y, ww, hh = cv2.boundingRect(contour)
        if hh < char_size * 1.7:
            continue
        if hh < ww * 1.15:
            continue
        if ww < char_size * 0.25 or ww > char_size * 3.2:
            continue
        if hh > h * 0.96 and ww > w * 0.3:
            continue
        boxes.append([x, y, x + ww, y + hh])
    # Merge overlapping fragments that belong to the same column.
    boxes.sort(key=lambda b: b[0])
    merged_boxes: list[list[int]] = []
    for box in boxes:
        merged_into = None
        for target in merged_boxes:
            overlap = min(target[2], box[2]) - max(target[0], box[0])
            if overlap > 0.55 * min(target[2] - target[0], box[2] - box[0]):
                merged_into = target
                break
        if merged_into is None:
            merged_boxes.append(box)
        else:
            merged_into[0] = min(merged_into[0], box[0])
            merged_into[1] = min(merged_into[1], box[1])
            merged_into[2] = max(merged_into[2], box[2])
            merged_into[3] = max(merged_into[3], box[3])
    merged_boxes = [b for b in merged_boxes if b[3] - b[1] >= char_size * 1.7]
    merged_boxes.sort(key=lambda b: b[0], reverse=True)
    return merged_boxes


def _projection_columns(bw, char_size: int):
    """Fallback column finder based on vertical ink projection."""
    h, w = bw.shape
    ink = bw.sum(axis=0).astype(np.float32)
    if ink.max() <= 0:
        return []
    win = max(3, int(char_size * 0.35)) | 1
    smooth = np.convolve(ink, np.ones(win) / win, mode="same")
    thr = max(smooth.max() * 0.12, 1.0)
    active = smooth > thr
    boxes: list[list[int]] = []
    x = 0
    while x < w:
        if not active[x]:
            x += 1
            continue
        start = x
        while x < w and active[x]:
            x += 1
        if x - start >= max(3, char_size * 0.25):
            col = bw[:, start:x]
            ys = np.where(col.sum(axis=1) > max(1, char_size * 0.4))[0]
            if len(ys) > char_size * 1.5:
                boxes.append([start, int(ys[0]), x, int(ys[-1])])
    boxes.sort(key=lambda b: b[0], reverse=True)
    return boxes


def _split_column_chars(bw_col, char_size: int):
    """Split one column into character cells by fitting the whitespace grid.

    A fixed ``height / width`` estimate drifts when the printed glyphs are
    narrower or wider than their cell. We therefore try the plausible cell
    counts and keep the grid whose boundaries fall in the whitest rows; the
    boundaries are then nudged onto the local ink minimum.
    """
    h = bw_col.shape[0]
    row = bw_col.sum(axis=1).astype(np.float32)
    if row.max() <= 0:
        return []
    ys = np.where(row > max(row.max() * 0.05, 1))[0]
    if not len(ys):
        return []
    top, bottom = int(ys[0]), int(ys[-1]) + 1
    height = max(1, bottom - top)
    nominal = max(1.0, height / max(char_size, 1))
    low = max(1, int(np.floor(nominal * 0.78)))
    high = max(low + 1, int(np.ceil(nominal * 1.28)))
    peak = float(row.max()) or 1.0

    def boundary_ink(count: int) -> float:
        step = height / count
        total = 0.0
        for i in range(1, count):
            y = int(round(top + i * step))
            window = row[max(0, y - 2) : min(h, y + 3)]
            if len(window):
                total += float(window.min()) / peak
        return total / max(1, count - 1)

    best_count = max(1, int(round(nominal)))
    best_score = float("inf")
    for count in range(low, high + 1):
        score = boundary_ink(count) + abs(count - nominal) / max(nominal, 1.0) * 0.06
        if score < best_score:
            best_score = score
            best_count = count

    step = height / best_count
    cells = []
    for i in range(best_count):
        y0 = int(round(top + i * step))
        y1 = int(round(top + (i + 1) * step))
        if i + 1 < best_count:
            expected = top + (i + 1) * step
            lo = max(y0 + 2, int(expected - step * 0.22))
            hi = min(bottom - 2, int(expected + step * 0.22))
            if hi > lo:
                window = row[lo:hi]
                y1 = lo + int(np.argmin(window))
        if y1 - y0 >= 3:
            cells.append((y0, y1))
    return cells


def _rec_cells(engine, crops: list[np.ndarray]):
    from rapidocr.ch_ppocr_rec import TextRecInput

    if not crops:
        return [], []
    out = engine.text_rec(TextRecInput(img=crops))
    return list(out.txts or []), [float(s) for s in (out.scores or [])]


def _row_from_crops(crops: list[np.ndarray], height: int = 56) -> np.ndarray | None:
    """Lay upright character crops out horizontally.

    Reading a whole column as one line gives the recogniser the word context
    that single-character recognition lacks, while keeping every glyph
    upright (rotating a native vertical column would turn the glyphs sideways).
    """
    import cv2

    if not crops:
        return None
    pieces = []
    for crop in crops:
        h, w = crop.shape[:2]
        if h < 2 or w < 2:
            continue
        nw = max(6, int(round(w * height / h)))
        pieces.append(cv2.resize(crop, (nw, height), interpolation=cv2.INTER_CUBIC))
    if not pieces:
        return None
    gap = 4
    width = sum(p.shape[1] for p in pieces) + gap * (len(pieces) - 1)
    row = np.full((height, max(1, width), 3), 255, dtype=np.uint8)
    x = 0
    for piece in pieces:
        row[:, x : x + piece.shape[1]] = piece
        x += piece.shape[1] + gap
    return row


def _ocr_vertical(img: Image.Image, lang_rec: str):
    import cv2

    _gray, bw = _binarize(img)
    h, w = bw.shape
    char_size = _char_size(bw, fallback=max(12, int(h * 0.018)))
    columns = _find_columns(bw, char_size)
    if len(columns) < 2:
        columns = _projection_columns(bw, char_size)
    engine = _engine(lang_rec)
    rgb = np.asarray(img.convert("RGB"))

    column_rows: list[tuple[list[int], np.ndarray]] = []
    for x0, y0, x1, y1 in columns:
        pad_x = max(2, int((x1 - x0) * 0.08))
        pad_y = max(2, int(char_size * 0.08))
        cx0 = max(0, x0 - pad_x)
        cx1 = min(w, x1 + pad_x)
        cy0 = max(0, y0 - pad_y)
        cy1 = min(h, y1 + pad_y)
        col_bw = bw[cy0:cy1, cx0:cx1]
        # In vertical typesetting a character is roughly as wide as the
        # column, which is a much better cell estimate than the median of
        # disconnected stroke components.
        cell = max(12, int((x1 - x0) * 1.02))
        cells = _split_column_chars(col_bw, cell)
        crops: list[np.ndarray] = []
        for (a, b) in cells:
            crop = rgb[cy0 + a : cy0 + b, cx0:cx1]
            if crop.size == 0:
                continue
            ch, cw = crop.shape[:2]
            if ch < 4 or cw < 4:
                continue
            # Pad to a square canvas so single glyphs keep their aspect ratio.
            side = max(ch, cw)
            canvas = np.full((side, side, 3), 255, dtype=np.uint8)
            oy = (side - ch) // 2
            ox = (side - cw) // 2
            canvas[oy : oy + ch, ox : ox + cw] = crop
            crops.append(cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
        if crops:
            row_img = _row_from_crops(crops)
            if row_img is not None:
                column_rows.append(([cx0, cy0, cx1, cy1], row_img))

    texts, scores = _rec_cells(engine, [row for _box, row in column_rows])
    rows: list[dict[str, Any]] = []
    for (box, _row), text, score in zip(column_rows, texts, scores):
        cleaned = _clean_text(str(text))
        if not cleaned or float(score) < 0.15:
            continue
        rows.append(
            {
                "text": cleaned,
                "box": [float(box[0]), float(box[1]), float(box[2]), float(box[3])],
                "score": round(float(score), 3),
                "vertical": True,
            }
        )
    rows.sort(key=lambda r: r["box"][0], reverse=True)
    return rows, img


# ---------- reflow ----------


def _union_box(boxes: list[list[float]]) -> list[float]:
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def _paragraphs_horizontal(body: list[dict[str, Any]], page_no: int, char_h: float):
    paragraphs: list[dict[str, Any]] = []
    current = ""
    current_boxes: list[list[float]] = []
    current_scores: list[float] = []
    left = float(np.percentile([ln["box"][0] for ln in body], 18)) if body else 0.0
    for ln in body:
        x0, y0, x1, y1 = ln["box"]
        indent = x0 - left
        starts_new = indent > char_h * 0.85
        if current and (starts_new or (y1 - y0) > char_h * 1.35):
            paragraphs.append(
                {
                    "text": current,
                    "box": _union_box(current_boxes),
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
                "box": _union_box(current_boxes),
                "confidence": round(sum(current_scores) / len(current_scores), 3),
                "page": page_no,
            }
        )
    return paragraphs


def _paragraphs_vertical(lines: list[dict[str, Any]], page_no: int, char_size: float):
    """Group right-to-left columns into paragraphs using indentation/short ends."""
    if not lines:
        return []
    top = min(ln["box"][1] for ln in lines)
    bottom = max(ln["box"][3] for ln in lines)
    paragraphs: list[dict[str, Any]] = []
    current = ""
    current_boxes: list[list[float]] = []
    current_scores: list[float] = []
    previous = None
    for ln in lines:
        indent = ln["box"][1] - top
        new_para = indent > char_size * 0.55
        if previous is not None and previous["box"][3] < bottom - char_size * 1.6:
            new_para = True
        if new_para and current:
            paragraphs.append(
                {
                    "text": current,
                    "box": _union_box(current_boxes),
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
        previous = ln
    if current:
        paragraphs.append(
            {
                "text": current,
                "box": _union_box(current_boxes),
                "confidence": round(sum(current_scores) / len(current_scores), 3),
                "page": page_no,
            }
        )
    return paragraphs


def classify_page(text: str, line_count: int = 0) -> str:
    """Classify a page as cover / copyright / toc / body / other.

    This is intentionally conservative: only pages that clearly look like
    front matter are skipped. A page with little text and few lines is a
    cover or plate; publication metadata and dot-leader page numbers are
    copyright/TOC markers.
    """
    compact = re.sub(r"\s", "", text or "")
    chars = len(compact)
    if chars < 12:
        return "cover"
    cjk = sum(1 for ch in compact if "\u3400" <= ch <= "\u9fff")
    digits = sum(1 for ch in compact if ch.isdigit())
    dots = len(re.findall(r"[…\.．·・]", compact))
    cjk_ratio = cjk / chars
    digit_ratio = digits / chars
    dot_ratio = dots / chars
    if line_count and line_count <= 4 and chars < 80:
        return "cover"
    if re.search(r"目錄|目次|總目|总目|索引", compact):
        return "toc"
    if re.search(
        r"出版|發行|发行|印刷|定價|定价|書號|书号|ISBN|開本|开本|印張|印张|版次|印次|新華書店|新华书店|版權|版权",
        compact,
    ) and (digit_ratio > 0.025 or chars < 260):
        return "copyright"
    if line_count >= 8 and (digit_ratio > 0.16 or dot_ratio > 0.04):
        return "toc"
    if chars >= 40 and cjk_ratio > 0.45 and digit_ratio < 0.18:
        return "body"
    return "other"


def _is_running_head(text: str) -> bool:
    compact = text.replace(" ", "")
    if re.fullmatch(r"[一二三四五六七八九十百千〇零\dⅠⅡⅢIVX]+", compact):
        return True
    if len(compact) <= 12 and re.search(
        r"晉書|晋书|帝紀|帝纪|列傳|列传|志第|卷[一二三四五六七八九十百]", compact
    ):
        return True
    return False


def analyze_page(
    pdf_path: str,
    page_no: int,
    book_id: str = "jinshu",
    dpi: int = 170,
    lang_rec: str = "chinese_cht_mobile",
    save_image: bool = True,
    layout: str = "horizontal",
    rotation: int | None = None,
) -> dict[str, Any]:
    raw = render_page(pdf_path, page_no, dpi=dpi)
    if rotation is None:
        rotation = estimate_rotation(raw, layout)
    img = raw.rotate(int(rotation), expand=True) if rotation else raw
    if layout == "vertical":
        lines, img = _ocr_vertical(img, lang_rec)
        char_size = 24.0
        if lines:
            char_size = float(np.median([ln["box"][2] - ln["box"][0] for ln in lines]))
        paragraphs = _paragraphs_vertical(lines, page_no, char_size)
        heads: list[dict[str, Any]] = []
        running_head = ""
        page_label = ""
    else:
        lines, img = _ocr_horizontal(img, lang_rec)
        w, h = img.size
        body = [
            ln
            for ln in lines
            if 0.08 * h < (ln["box"][1] + ln["box"][3]) / 2 < 0.93 * h
        ]
        heads = [ln for ln in lines if ln not in body]
        body.sort(key=lambda ln: (ln["box"][1], ln["box"][0]))
        heights = [ln["box"][3] - ln["box"][1] for ln in body] or [1]
        char_h = float(np.median(heights))
        paragraphs = _paragraphs_horizontal(body, page_no, char_h)
        running_head = " ".join(
            ln["text"] for ln in heads if _is_running_head(ln["text"])
        )[:60]
        page_label = ""
        for ln in heads:
            if re.fullmatch(
                r"[一二三四五六七八九十百千〇零\d]+", ln["text"].replace(" ", "")
            ):
                page_label = ln["text"].replace(" ", "")
        lines = body + heads

    w, h = img.size
    body_lines = [
        ln
        for ln in lines
        if 0.04 * h < (ln["box"][1] + ln["box"][3]) / 2 < 0.97 * h
    ]
    kind = "body"
    if len(body_lines) < 4:
        kind = "cover" if len(lines) < 4 else "plate"
    if body_lines and any(
        (ln["box"][3] - ln["box"][1]) > 24 * 1.4 for ln in body_lines[:4]
    ):
        kind = "chapter-head" if kind == "body" else kind

    if save_image:
        out_dir = paths.PAGES / book_id
        out_dir.mkdir(parents=True, exist_ok=True)
        img.save(out_dir / f"{page_no:04d}.jpg", quality=86, optimize=True)

    scores = [ln["score"] for ln in body_lines]
    return {
        "page": page_no,
        "rotation": int(rotation),
        "layout": layout,
        "width": w,
        "height": h,
        "kind": kind,
        "running_head": running_head,
        "page_label": page_label,
        "lines": lines,
        "head_lines": heads,
        "paragraphs": paragraphs,
        "average_confidence": round(float(np.mean(scores)), 3) if scores else None,
    }


def probe_page(
    pdf_path: str,
    page_no: int,
    forced_layout: str | None = None,
    dpi: int = 140,
    lang_rec: str = "chinese_cht_mobile",
) -> dict[str, Any] | None:
    """Try candidate rotations and both directions; return the best reading.

    A page of traditional vertical typesetting has upright glyphs in vertical
    columns. Standard OCR line detectors expect horizontal lines, so rotation
    alone cannot tell a rotated horizontal page from an upright vertical one.
    We therefore run both pipelines at the plausible rotations and compare how
    much confident text each produces.
    """
    raw = render_page(pdf_path, page_no, dpi=dpi)
    raw.thumbnail((1600, 1600))
    orient = _line_orientation(raw)
    if forced_layout in ("vertical", "horizontal"):
        candidates = [
            (0, forced_layout), (90, forced_layout),
            (180, forced_layout), (270, forced_layout),
        ]
    elif orient == "vertical":
        candidates = [
            (0, "vertical"), (90, "horizontal"),
            (180, "vertical"), (270, "horizontal"),
        ]
    else:
        candidates = [
            (0, "horizontal"), (90, "vertical"),
            (180, "horizontal"), (270, "vertical"),
        ]

    best: dict[str, Any] | None = None
    best_metric = -1.0
    for angle, layout in candidates:
        img = raw.rotate(angle, expand=True) if angle else raw
        try:
            if layout == "vertical":
                lines, _ = _ocr_vertical(img, lang_rec)
            else:
                lines, _ = _ocr_horizontal(img, lang_rec)
        except Exception:
            continue
        chars = sum(len(ln["text"]) for ln in lines)
        if not chars:
            continue
        # Confidence matters more than raw character count: a wrong pipeline
        # often produces many low-confidence glyphs (especially when a
        # horizontal scan is treated as vertical columns).
        weighted = sum(
            max(0.0, ln["score"] - 0.35) ** 2 * min(len(ln["text"]), 30)
            for ln in lines
        )
        metric = weighted * (1.0 + min(chars, 400) / 800.0)
        if metric > best_metric:
            best_metric = metric
            scores = [ln["score"] for ln in lines]
            best = {
                "page": page_no,
                "layout": layout,
                "rotation": angle,
                "confidence": round(float(np.mean(scores)), 3),
                "chars": chars,
                "lines": len(lines),
                "sample": "".join(ln["text"] for ln in lines[:4])[:120],
            }
    return best


def render_cover(pdf_path: str, page_no: int = 1, out_path: str | None = None) -> str:
    img = render_page(pdf_path, page_no, dpi=150)
    img.thumbnail((900, 1200))
    dest = Path(out_path) if out_path else paths.ASSETS / "cover-jinshu.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, quality=88, optimize=True)
    return str(dest)


def to_json(result: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
