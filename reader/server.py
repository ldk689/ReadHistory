from __future__ import annotations

import json
import mimetypes
import re
import shutil
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import db, ocr, paths
from . import __version__

WEB = paths.WEB
ASSETS = paths.ASSETS
PAGES = paths.PAGES
IMPORTS = paths.IMPORTS
LIBRARY = paths.LIBRARY
USER_ASSETS = paths.USER_ASSETS

OCR_JOBS: dict[str, dict] = {}
OCR_LOCK = threading.Lock()
IMPORT_META = "meta.json"
HIGH_OCR_MODEL = (
    paths.APP_ROOT
    / ".ocr2"
    / "rapidocr"
    / "models"
    / "ch_doc_PP-OCRv4_rec_server_infer.onnx"
)


def high_ocr_available() -> bool:
    return HIGH_OCR_MODEL.exists()


def json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def _book_source(book: dict) -> str | None:
    return ocr.resolve_pdf(book.get("source_pdf"))


class Handler(BaseHTTPRequestHandler):
    server_version = f"QingJian/{__version__}"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    # ---------- helpers ----------
    def send_json(self, obj, status: int = 200):
        body = json_bytes(obj)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: int = 400):
        self.send_json({"error": message}, status)

    def read_json(self, limit: int = 2_000_000) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > limit:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def send_file(self, path: Path, cache: bool = True):
        if not path.exists() or not path.is_file():
            self.send_error_json("文件不存在", 404)
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400" if cache else "no-store")
        self.end_headers()
        self.wfile.write(data)

    # ---------- routes ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            if path.startswith("/api/"):
                return self.api_get(path, query)
            return self.static_get(path)
        except BrokenPipeError:
            pass
        except Exception as exc:
            traceback.print_exc()
            try:
                self.send_error_json(f"服务器错误：{exc}", 500)
            except Exception:
                pass

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            return self.api_post(unquote(parsed.path), parse_qs(parsed.query))
        except BrokenPipeError:
            pass
        except Exception as exc:
            traceback.print_exc()
            try:
                self.send_error_json(f"服务器错误：{exc}", 500)
            except Exception:
                pass

    def do_PATCH(self):
        try:
            parsed = urlparse(self.path)
            return self.api_patch(unquote(parsed.path))
        except BrokenPipeError:
            pass
        except Exception as exc:
            traceback.print_exc()
            try:
                self.send_error_json(f"服务器错误：{exc}", 500)
            except Exception:
                pass

    def do_DELETE(self):
        try:
            parsed = urlparse(self.path)
            return self.api_delete(unquote(parsed.path))
        except BrokenPipeError:
            pass
        except Exception as exc:
            traceback.print_exc()
            try:
                self.send_error_json(f"服务器错误：{exc}", 500)
            except Exception:
                pass

    def static_get(self, path: str):
        if path in ("/", "/index.html"):
            return self.send_file(WEB / "index.html", cache=False)
        if path.startswith("/assets/"):
            name = path[len("/assets/") :]
            for base in (WEB / "assets", ASSETS, USER_ASSETS):
                p = (base / name).resolve()
                try:
                    p.relative_to(base.resolve())
                except ValueError:
                    continue
                if p.exists():
                    return self.send_file(p, cache=True)
            return self.send_error_json("资源不存在", 404)
        p = (WEB / path.lstrip("/")).resolve()
        try:
            p.relative_to(WEB.resolve())
        except ValueError:
            return self.send_error_json("页面不存在", 404)
        if p.exists() and p.is_file():
            return self.send_file(p, cache=path.startswith("/fonts/"))
        return self.send_error_json("页面不存在", 404)

    def api_get(self, path: str, query: dict):
        if path == "/api/health":
            return self.send_json(
                {"ok": True, "name": "青简", "name_en": "ReadHistory", "version": __version__}
            )
        if path == "/api/library":
            return self.send_json({"books": db.get_library()})
        m = re.fullmatch(r"/api/books/([^/]+)", path)
        if m:
            book = db.get_book(m.group(1))
            if not book:
                return self.send_error_json("书籍不存在", 404)
            return self.send_json({"book": book, "chapters": db.get_chapters(book["id"])})
        m = re.fullmatch(r"/api/books/([^/]+)/chapters/([^/]+)", path)
        if m:
            data = db.get_chapter(m.group(1), m.group(2))
            if not data:
                return self.send_error_json("篇章不存在", 404)
            return self.send_json(data)
        m = re.fullmatch(r"/api/books/([^/]+)/annotations", path)
        if m:
            return self.send_json({"annotations": db.get_annotations(m.group(1))})
        if path == "/api/search":
            book_id = (query.get("book") or ["jinshu"])[0]
            q = (query.get("q") or [""])[0]
            return self.send_json({"results": db.search(book_id, q)})
        if path == "/api/settings":
            reader = db.get_setting("reader", "{}")
            try:
                reader_cfg = json.loads(reader or "{}")
            except json.JSONDecodeError:
                reader_cfg = {}
            return self.send_json({"reader": reader_cfg})
        if path == "/api/ocr/status":
            book_id = (query.get("book") or ["jinshu"])[0]
            return self.send_json({"ocr": db.ocr_status(book_id), "jobs": list(OCR_JOBS.values())})
        m = re.fullmatch(r"/api/ocr/jobs/([^/]+)", path)
        if m:
            job = OCR_JOBS.get(m.group(1))
            if not job:
                return self.send_error_json("任务不存在", 404)
            return self.send_json({"job": job})
        m = re.fullmatch(r"/api/ocr/pages/([^/]+)/(\d+)", path)
        if m:
            page = db.get_ocr_page(m.group(1), int(m.group(2)))
            if not page:
                return self.send_error_json("该页尚未识别", 404)
            return self.send_json({"page": page})
        m = re.fullmatch(r"/api/page/([^/]+)/(\d+)", path)
        if m:
            return self.page_image(m.group(1), int(m.group(2)))
        m = re.fullmatch(r"/api/imports/([^/]+)/preview", path)
        if m:
            name = re.fullmatch(r"[a-f0-9]{6,16}", m.group(1))
            if not name:
                return self.send_error_json("导入编号无效", 400)
            return self.send_file(IMPORTS / f"{name.group(0)}-cover.jpg", cache=False)
        return self.send_error_json("接口不存在", 404)

    def api_post(self, path: str, query: dict):
        if path == "/api/annotations":
            payload = self.read_json()
            try:
                ann = db.create_annotation(payload)
            except ValueError as exc:
                return self.send_error_json(str(exc), 400)
            return self.send_json({"annotation": ann}, 201)
        if path == "/api/progress":
            payload = self.read_json()
            db.save_progress(payload["book_id"], payload["chapter_id"], payload.get("paragraph_id"))
            return self.send_json({"ok": True})
        if path == "/api/settings/reader":
            payload = self.read_json()
            current = db.get_setting("reader", "{}")
            try:
                cfg = json.loads(current or "{}")
            except json.JSONDecodeError:
                cfg = {}
            cfg.update(payload)
            db.set_setting("reader", json.dumps(cfg, ensure_ascii=False))
            return self.send_json({"reader": cfg})
        if path == "/api/import/upload":
            return self.import_upload()
        if path == "/api/import/analyze":
            payload = self.read_json()
            return self.import_analyze(payload)
        if path == "/api/import/commit":
            payload = self.read_json()
            return self.import_commit(payload)
        if path == "/api/shutdown":
            self.send_json({"ok": True})
            threading.Timer(0.2, self.server.shutdown).start()
            return
        m = re.fullmatch(r"/api/ocr/pages/([^/]+)/(\d+)", path)
        if m:
            payload = self.read_json()
            text = (payload.get("text") or "").strip()
            if not text:
                return self.send_error_json("校樣內容不能為空", 400)
            db.save_ocr_text(m.group(1), int(m.group(2)), text)
            return self.send_json({"ok": True})
        if path == "/api/ocr/run":
            payload = self.read_json()
            return self.start_ocr(payload)
        m = re.fullmatch(r"/api/ocr/jobs/([^/]+)/cancel", path)
        if m:
            job = OCR_JOBS.get(m.group(1))
            if not job:
                return self.send_error_json("任务不存在", 404)
            job["cancel"] = True
            job["pause"] = False
            if job.get("status") not in {"done", "error", "cancelled"}:
                job["message"] = "正在停止…"
            return self.send_json({"job": job})
        m = re.fullmatch(r"/api/ocr/jobs/([^/]+)/pause", path)
        if m:
            job = OCR_JOBS.get(m.group(1))
            if not job:
                return self.send_error_json("任务不存在", 404)
            if job.get("status") in {"done", "error", "cancelled"}:
                return self.send_error_json("任務已結束", 409)
            job["pause"] = True
            job["message"] = "正在暫停，當前頁完成後停止…"
            return self.send_json({"job": job})
        m = re.fullmatch(r"/api/ocr/jobs/([^/]+)/resume", path)
        if m:
            job = OCR_JOBS.get(m.group(1))
            if not job:
                return self.send_error_json("任务不存在", 404)
            if job.get("status") in {"done", "error", "cancelled"}:
                return self.send_error_json("任務已結束", 409)
            job["pause"] = False
            job["message"] = "繼續識別"
            return self.send_json({"job": job})
        return self.send_error_json("接口不存在", 404)

    def api_patch(self, path: str):
        m = re.fullmatch(r"/api/annotations/([^/]+)", path)
        if not m:
            return self.send_error_json("接口不存在", 404)
        payload = self.read_json()
        try:
            ann = db.update_annotation(m.group(1), payload)
        except ValueError as exc:
            return self.send_error_json(str(exc), 404)
        return self.send_json({"annotation": ann})

    def api_delete(self, path: str):
        m = re.fullmatch(r"/api/annotations/([^/]+)", path)
        if not m:
            return self.send_error_json("接口不存在", 404)
        db.delete_annotation(m.group(1))
        return self.send_json({"ok": True})

    # ---------- import ----------
    def import_upload(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self.send_error_json("没有收到文件", 400)
        if length > 600 * 1024 * 1024:
            return self.send_error_json("PDF 超过 600 MB，暂不支持", 413)
        raw_name = unquote(self.headers.get("X-Filename") or "book.pdf")
        safe_name = Path(raw_name.replace("\\", "/")).name or "book.pdf"
        import_id = uuid.uuid4().hex[:10]
        dest = IMPORTS / f"{import_id}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        remaining = length
        with dest.open("wb") as fh:
            while remaining > 0:
                chunk = self.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                fh.write(chunk)
                remaining -= len(chunk)
        if remaining > 0 or not dest.exists():
            dest.unlink(missing_ok=True)
            return self.send_error_json("文件上传中断，请重试", 400)
        with dest.open("rb") as fh:
            if not fh.read(5).startswith(b"%PDF"):
                dest.unlink(missing_ok=True)
                return self.send_error_json("不是有效的 PDF 文件", 400)
        try:
            info = ocr.pdf_info(str(dest))
            cover = ocr.render_cover(str(dest), 1, str(IMPORTS / f"{import_id}-cover.jpg"))
        except Exception as exc:
            dest.unlink(missing_ok=True)
            return self.send_error_json(f"无法读取 PDF：{exc}", 400)
        meta = {
            "id": import_id,
            "filename": safe_name,
            "title": info.get("title") or Path(safe_name).stem,
            "author": info.get("author") or "",
            "pages": info["pages"],
            "width": info.get("width"),
            "height": info.get("height"),
            "cover": f"/api/imports/{import_id}/preview",
        }
        (IMPORTS / f"{import_id}.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        meta["portrait"] = bool(
            (info.get("height") or 0) >= (info.get("width") or 0)
        )
        return self.send_json({"import": meta}, 201)

    def _import_meta(self, import_id: str) -> dict | None:
        p = IMPORTS / f"{import_id}.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def import_analyze(self, payload: dict):
        import_id = str(payload.get("id") or "")
        meta = self._import_meta(import_id)
        if not meta:
            return self.send_error_json("導入會話已失效，請重新選擇 PDF", 404)
        pdf = IMPORTS / f"{import_id}.pdf"
        if not pdf.exists():
            return self.send_error_json("PDF 文件不存在", 404)
        forced = payload.get("layout")
        if forced not in ("vertical", "horizontal"):
            forced = None
        start = max(1, int(payload.get("page") or payload.get("start") or 1))
        # Covers, copyright pages and tables of contents often have a different
        # orientation from the body. Sampling only the first pages was why a
        # whole-book import could be locked to a wrong rotation (e.g. page 1 at
        # 0°/270° while the body is 90°). Sample across the first part of the
        # book and keep the page that produces the most confident text.
        candidates = []
        for offset in (0, 10, 40, 80, 160):
            page_no = start + offset
            if 1 <= page_no <= meta["pages"] and page_no not in candidates:
                candidates.append(page_no)
        # Sample deeper into the book so a long preface or table section
        # cannot outvote the actual body.
        for ratio in (0.10, 0.25, 0.50):
            page_no = max(1, int(meta["pages"] * ratio))
            if page_no <= meta["pages"] and page_no not in candidates:
                candidates.append(page_no)
        if not candidates:
            candidates = [1]

        results = []
        for page_no in candidates:
            try:
                probe = ocr.probe_page(str(pdf), page_no, forced_layout=forced)
            except Exception:
                traceback.print_exc()
                continue
            if probe:
                results.append(probe)
        if not results:
            return self.send_error_json("這幾頁沒有找到可識別的文字，請換一個頁碼或手動指定版式", 422)
        # Stay out of the first ~2% of the book when possible: that is where
        # covers, copyright pages and prefaces with a different orientation
        # live. Fall back to every sample for short books.
        body_threshold = max(start, int(meta["pages"] * 0.02))
        eligible = [
            r
            for r in results
            if (r.get("page") or 0) >= body_threshold and (r.get("chars") or 0) >= 20
        ] or results

        def score(r):
            return (r.get("chars") or 0) * max(0.2, r.get("confidence") or 0)

        layout_scores = {}
        for r in eligible:
            layout_scores[r["layout"]] = layout_scores.get(r["layout"], 0) + score(r)
        layout = max(layout_scores, key=layout_scores.get)
        same_layout = [r for r in eligible if r["layout"] == layout]
        rotation_scores = {}
        for r in same_layout:
            rotation_scores[r["rotation"]] = rotation_scores.get(r["rotation"], 0) + score(r)
        rotation = max(rotation_scores, key=rotation_scores.get)
        best = max(same_layout, key=score)
        confidence = best.get("confidence") or 0
        warning = ""
        if (best.get("chars") or 0) < 20:
            warning = "這幾頁文字太少，自動判斷可能不準；請換一個正文頁碼，或手動選擇豎排 / 橫排。"
        try:
            outline = ocr.pdf_outline(str(pdf))
        except Exception:
            outline = []
        return self.send_json(
            {
                "suggestion": {
                    "layout": layout,
                    "rotation": rotation,
                    "confidence": round(float(confidence), 3),
                    "page": best.get("page"),
                    "pages": results,
                    "warning": warning,
                },
                "outline": outline,
                "meta": meta,
            }
        )

    def import_commit(self, payload: dict):
        import_id = str(payload.get("id") or "")
        meta = self._import_meta(import_id)
        if not meta:
            return self.send_error_json("導入會話已失效，請重新選擇 PDF", 404)
        src = IMPORTS / f"{import_id}.pdf"
        if not src.exists():
            return self.send_error_json("PDF 文件不存在", 404)
        layout = payload.get("layout")
        if layout not in ("vertical", "horizontal"):
            return self.send_error_json("請選擇版式：豎排或橫排", 400)
        start = max(1, int(payload.get("start") or 1))
        end = min(int(meta["pages"]), int(payload.get("end") or meta["pages"]))
        if end < start:
            return self.send_error_json("頁碼範圍無效", 400)
        title = (payload.get("title") or meta.get("title") or "未命名史書").strip()[:80]
        author = (payload.get("author") or meta.get("author") or "").strip()[:80]
        chapter_title = (payload.get("chapter_title") or "全書").strip()[:60] or "全書"
        # 0.2.7 always previews in fast mode and then writes the final text
        # with the high-quality model; there is no user-facing quality toggle.
        quality = "high"

        book_id = "b-" + uuid.uuid4().hex[:10]
        LIBRARY.mkdir(parents=True, exist_ok=True)
        dest_pdf = LIBRARY / f"{book_id}.pdf"
        shutil.copyfile(src, dest_pdf)

        cover_name = f"cover-{book_id}.jpg"
        cover_src = IMPORTS / f"{import_id}-cover.jpg"
        if cover_src.exists():
            shutil.copyfile(cover_src, USER_ASSETS / cover_name)
        # The imported copy now lives in data/library; drop the upload and
        # its preview so a large scan is not stored twice.
        for stale in (src, IMPORTS / f"{import_id}.json", cover_src):
            try:
                stale.unlink(missing_ok=True)
            except OSError:
                pass
        book = db.create_book(
            {
                "id": book_id,
                "title": title,
                "author": author,
                "dynasty": "",
                "edition": "導入掃描本",
                "description": f"{meta.get('filename', '')} · {start}–{end} 頁",
                "total_pages": meta["pages"],
                "source_pdf": f"library/{book_id}.pdf",
                "cover": cover_name,
                "layout": layout,
                "orientation": int(payload.get("rotation") or 0),
                "imported": 1,
                "status": "importing",
            }
        )
        try:
            outline = ocr.pdf_outline(str(dest_pdf))
        except Exception:
            outline = []

        volume_specs: list[dict] = []
        if len(outline) >= 2:
            for index, item in enumerate(outline):
                page_start = max(start, int(item.get("page") or start))
                next_page = (
                    int(outline[index + 1].get("page") or (end + 1))
                    if index + 1 < len(outline)
                    else end + 1
                )
                page_end = min(end, next_page - 1)
                if page_start > page_end:
                    continue
                raw_title = ocr.cleaner_outline_title(item.get("title") or "")
                match = re.search(r"第\s*0*(\d+)\s*[册冊]", raw_title)
                volume = f"第{int(match.group(1)):02d}冊" if match else f"卷{index + 1}"
                volume_specs.append(
                    {
                        "volume": volume,
                        "title": raw_title or volume,
                        "page_start": page_start,
                        "page_end": page_end,
                    }
                )
        if len(volume_specs) < 2:
            volume_specs = [
                {
                    "volume": "卷一",
                    "title": chapter_title,
                    "page_start": start,
                    "page_end": end,
                }
            ]

        chapters = []
        for index, spec in enumerate(volume_specs):
            chapters.append(
                db.create_chapter(
                    {
                        "id": f"{book_id}-{index + 1:02d}",
                        "book_id": book_id,
                        "volume": spec["volume"],
                        "title": spec["title"],
                        "subtitle": "掃描本",
                        "order_no": index + 1,
                        "page_start": spec["page_start"],
                        "page_end": spec["page_end"],
                        "status": "importing",
                        "page_count": spec["page_end"] - spec["page_start"] + 1,
                    }
                )
            )
        chapter = chapters[0]
        chapter_id = chapter["id"]
        job_id = f"ocr-{uuid.uuid4().hex[:8]}"
        job = {
            "id": job_id,
            "kind": "import",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "chapters": chapters,
            "start": start,
            "end": end,
            "quality": quality,
            "preview": True,
            "layout": layout,
            "rotation": int(payload.get("rotation") or 0),
            "skip_front_matter": bool(payload.get("skip_front_matter", True)),
            "status": "queued",
            "done": 0,
            "processed": 0,
            "total": end - start + 1,
            "percent": 0,
            "current": start,
            "message": "等待開始",
            "cancel": False,
            "pause": False,
        }
        OCR_JOBS[job_id] = job
        threading.Thread(target=run_ocr_job, args=(job,), daemon=True).start()
        return self.send_json(
            {"book": book, "chapter": chapter, "chapters": chapters, "job": job},
            202,
        )

    # ---------- ocr ----------
    def start_ocr(self, payload: dict):
        book = db.get_book(payload.get("book_id") or "jinshu")
        if not book:
            return self.send_error_json("书籍不存在", 404)
        start = int(payload.get("start") or 1)
        end = int(payload.get("end") or start)
        end = max(start, min(end, start + 199, int(book.get("total_pages") or end)))
        quality = "high"
        chapter_id = None
        job_chapters = []
        if book.get("imported"):
            for chapter in db.get_chapters(book["id"]):
                page_start = max(start, int(chapter.get("page_start") or 1))
                page_end = min(end, int(chapter.get("page_end") or end))
                if page_start <= page_end:
                    job_chapters.append(
                        {
                            "id": chapter["id"],
                            "page_start": page_start,
                            "page_end": page_end,
                            "volume": chapter.get("volume") or "",
                        }
                    )
            if job_chapters:
                chapter_id = job_chapters[0]["id"]
        job_id = f"ocr-{uuid.uuid4().hex[:8]}"
        rotation = book.get("orientation")
        job = {
            "id": job_id,
            "kind": "import" if book.get("imported") else "ocr",
            "book_id": book["id"],
            "chapter_id": chapter_id,
            "chapters": job_chapters,
            "start": start,
            "end": end,
            "quality": quality,
            "preview": bool(book.get("imported")),
            "layout": book.get("layout") or "horizontal",
            "rotation": int(rotation) if rotation is not None else None,
            "skip_front_matter": True,
            "status": "queued",
            "done": 0,
            "processed": 0,
            "total": end - start + 1,
            "percent": 0,
            "current": start,
            "message": "等待開始",
            "cancel": False,
            "pause": False,
        }
        OCR_JOBS[job_id] = job
        threading.Thread(target=run_ocr_job, args=(job,), daemon=True).start()
        return self.send_json({"job": job}, 202)

    def page_image(self, book_id: str, page_no: int):
        book = db.get_book(book_id)
        if not book:
            return self.send_error_json("书籍不存在", 404)
        dest = PAGES / book_id / f"{page_no:04d}.jpg"
        if not dest.exists():
            src = _book_source(book)
            if not src:
                return self.send_error_json(
                    "原始 PDF 不可用。請把 PDF 放入 data/inbox/，或設定 READHISTORY_PDF。", 404
                )
            img = ocr.render_page(src, page_no, dpi=150)
            angle = book.get("orientation")
            if angle is None:
                angle = ocr.estimate_rotation(img, book.get("layout") or "horizontal")
            if angle:
                img = img.rotate(int(angle), expand=True)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, quality=84, optimize=True)
        return self.send_file(dest, cache=True)


def run_ocr_job(job: dict):
    job["status"] = "running"
    job["message"] = "正在識別"
    book = db.get_book(job["book_id"])
    if not book:
        job["status"] = "error"
        job["message"] = "书籍不存在"
        return
    src = _book_source(book)
    if not src:
        job["status"] = "error"
        job["message"] = "原始 PDF 不可用。請把 PDF 放入 data/inbox/，或設定 READHISTORY_PDF。"
        return
    # The 90 MB ch_doc_server model is accurate but takes minutes per page on
    # ordinary CPUs. Use the PP-OCRv4 mobile recogniser for the final text and
    # keep the traditional mobile model for the 20-page quick preview.
    lang = "ch_mobile" if job.get("quality") == "high" else "chinese_cht_mobile"
    layout = job.get("layout") or book.get("layout") or "horizontal"
    rotation = job.get("rotation")
    if rotation is None and book.get("orientation") is not None:
        rotation = int(book["orientation"])
    chapter_ranges = []
    if job.get("kind") == "import":
        if job.get("chapters"):
            chapter_ranges = job["chapters"]
        elif job.get("chapter_id"):
            chapter_ranges = [
                {
                    "id": job["chapter_id"],
                    "page_start": job["start"],
                    "page_end": job["end"],
                }
            ]
    importing = bool(chapter_ranges)

    def chapter_for(page_no: int):
        for chapter in chapter_ranges:
            if int(chapter.get("page_start") or 0) <= page_no <= int(chapter.get("page_end") or 0):
                return chapter
        return chapter_ranges[0] if chapter_ranges else None

    def finish(status: str = "ready"):
        for chapter in chapter_ranges:
            db.update_chapter(chapter["id"], status=status)
        db.update_book(job["book_id"], status=status)

    def wait_or_cancel() -> bool:
        while job.get("pause") and not job.get("cancel"):
            if job.get("status") != "paused":
                job["status"] = "paused"
                job["message"] = "已暫停"
            time.sleep(0.4)
        if job.get("cancel"):
            job["status"] = "cancelled"
            job["message"] = "已停止"
            if importing:
                finish()
            return False
        if job.get("status") == "paused":
            job["status"] = "running"
            job["message"] = "繼續識別"
        return True

    try:
        if importing:
            for chapter in chapter_ranges:
                db.delete_paragraphs_for_pages(chapter["id"], job["start"], job["end"])
        preview_done = False
        if job.get("kind") == "import" and job.get("preview"):
            preview_total = min(20, job["total"])
            for offset, page_no in enumerate(
                range(job["start"], job["start"] + preview_total)
            ):
                if not wait_or_cancel():
                    return
                job["current"] = page_no
                job["message"] = f"快速預覽 {offset + 1}/{preview_total}"
                job["percent"] = round((offset + 1) / max(1, preview_total) * 10)
                try:
                    ocr.analyze_page(
                        src,
                        page_no,
                        book_id=job["book_id"],
                        dpi=150,
                        lang_rec="chinese_cht_mobile",
                        layout=layout,
                        rotation=int(rotation) if rotation is not None else None,
                    )
                except Exception:
                    traceback.print_exc()
            preview_done = True
            job["percent"] = 10
            job["message"] = "快速預覽完成，開始精校"
        base_percent = 10 if preview_done else 0
        for n in range(job["start"], job["end"] + 1):
            if not wait_or_cancel():
                return
            job["current"] = n
            job["message"] = f"精校第 {n} 頁"
            chapter = chapter_for(n)
            chapter_id = chapter["id"] if chapter else None
            try:
                result = ocr.analyze_page(
                    src,
                    n,
                    book_id=job["book_id"],
                    dpi=170,
                    lang_rec=lang,
                    layout=layout,
                    rotation=int(rotation) if rotation is not None else None,
                )
                # Covers, copyright pages and fold-outs can be rotated
                # differently from the body. If a fixed book orientation
                # produced weak text, retry this page in the other plausible
                # orientations and keep the better result.
                avg = result.get("average_confidence")
                if (
                    importing
                    and job.get("quality") != "high"
                    and rotation is not None
                    and avg is not None
                    and avg < 0.55
                ):
                    try:
                        probe = ocr.probe_page(src, n)
                        if probe and (
                            probe.get("layout") != layout
                            or probe.get("rotation") != int(rotation)
                        ) and (probe.get("confidence") or 0) > avg + 0.05:
                            alt = ocr.analyze_page(
                                src,
                                n,
                                book_id=job["book_id"],
                                dpi=170,
                                lang_rec=lang,
                                layout=probe.get("layout") or layout,
                                rotation=int(probe["rotation"]),
                            )
                            if (alt.get("average_confidence") or 0) > avg:
                                result = alt
                    except Exception:
                        traceback.print_exc()

                skipped_label = ""
                page_kind = None
                if importing:
                    page_text = "".join(
                        (para.get("text") or "") for para in result.get("paragraphs", [])
                    )
                    page_kind = ocr.classify_page(page_text, len(result.get("lines", [])))
                    skip = job.get("skip_front_matter", True) and page_kind in {
                        "cover",
                        "copyright",
                        "toc",
                    }
                    if skip:
                        labels = {"cover": "封面", "copyright": "版權頁", "toc": "目錄"}
                        skipped_label = labels.get(page_kind, "前置頁")
                    elif chapter_id:
                        for para in result.get("paragraphs", []):
                            text = (para.get("text") or "").strip()
                            if len(text) < 2:
                                continue
                            db.add_paragraph(
                                chapter_id,
                                db.next_paragraph_order(chapter_id),
                                text,
                                page_start=n,
                                page_end=n,
                                confidence=para.get("confidence"),
                            )
                db.store_ocr_page(
                    job["book_id"],
                    n,
                    "done",
                    result.get("average_confidence"),
                    result.get("lines", []),
                    kind=page_kind,
                )
                job["done"] += 1
                job["processed"] = job.get("processed", 0) + 1
                job["percent"] = base_percent + round(
                    job["processed"] / max(1, job["total"]) * (100 - base_percent)
                )
                chapter_label = f"{chapter.get('volume', '')}" if chapter else ""
                job["message"] = (
                    f"第 {n} 頁：{skipped_label}，已略過"
                    if skipped_label
                    else f"{chapter_label} 第 {n} 頁完成"
                )
            except Exception as exc:
                traceback.print_exc()
                db.store_ocr_page(job["book_id"], n, "error", None, [])
                job["processed"] = job.get("processed", 0) + 1
                job["percent"] = base_percent + round(
                    job["processed"] / max(1, job["total"]) * (100 - base_percent)
                )
                job["message"] = f"第 {n} 頁失敗：{exc}"
        job["status"] = "done"
        job["percent"] = 100
        job["message"] = f"完成 {job['done']} 頁"
        if importing:
            finish()
    except Exception as exc:
        traceback.print_exc()
        job["status"] = "error"
        job["message"] = f"任务失败：{exc}"
        if importing:
            finish()


def serve(host: str = "127.0.0.1", port: int = 8765):
    db.init_db()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"青简 · ReadHistory {__version__}  http://{host}:{port}", flush=True)
    print("按 Ctrl+C 停止。", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止…")
    finally:
        httpd.server_close()
