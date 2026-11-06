from __future__ import annotations

import json
import mimetypes
import re
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import db
from . import __version__
from .translate import TranslationError, get_llm_settings, save_llm_settings, translate_text

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
ASSETS = ROOT / "data" / "assets"
PAGES = ROOT / "data" / "pages"

OCR_JOBS: dict[str, dict] = {}
OCR_LOCK = threading.Lock()


def json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = f"QingJian/{__version__}"

    def log_message(self, fmt, *args):  # keep console quiet but informative
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

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2_000_000:
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
            for base in (WEB / "assets", ASSETS):
                p = (base / name).resolve()
                if str(p).startswith(str(base.resolve())) and p.exists():
                    return self.send_file(p, cache=True)
            return self.send_error_json("资源不存在", 404)
        p = (WEB / path.lstrip("/")).resolve()
        if str(p).startswith(str(WEB.resolve())) and p.exists() and p.is_file():
            return self.send_file(p, cache=False)
        return self.send_error_json("页面不存在", 404)

    def api_get(self, path: str, query: dict):
        if path == "/api/health":
            return self.send_json({"ok": True, "name": "青简", "name_en": "ReadHistory", "version": __version__})
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
            return self.send_json({"llm": get_llm_settings(mask=True), "reader": reader_cfg})
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
        if path == "/api/settings/llm":
            payload = self.read_json()
            return self.send_json({"llm": save_llm_settings(payload)})
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
        if path == "/api/translate":
            payload = self.read_json()
            text = (payload.get("text") or "").strip()
            paragraph_id = payload.get("paragraph_id")
            if paragraph_id and not text:
                para = db.get_paragraph(int(paragraph_id))
                if not para:
                    return self.send_error_json("段落不存在", 404)
                text = para["text"]
            try:
                result = translate_text(
                    text,
                    book=payload.get("book") or "晉書",
                    chapter=payload.get("chapter") or "",
                )
            except TranslationError as exc:
                return self.send_error_json(str(exc), 400)
            if paragraph_id:
                db.update_translation(int(paragraph_id), result["translation"], result.get("model"))
            return self.send_json(result)
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
            book = db.get_book(payload.get("book_id") or "jinshu")
            if not book:
                return self.send_error_json("书籍不存在", 404)
            start = int(payload.get("start") or book.get("total_pages") or 1)
            end = int(payload.get("end") or start)
            end = max(start, min(end, start + 199, int(book.get("total_pages") or end)))
            quality = "high" if payload.get("quality") == "high" else "fast"
            job_id = f"ocr-{uuid.uuid4().hex[:8]}"
            job = {
                "id": job_id,
                "book_id": book["id"],
                "start": start,
                "end": end,
                "quality": quality,
                "status": "queued",
                "done": 0,
                "total": end - start + 1,
                "current": start,
                "message": "等待开始",
                "cancel": False,
            }
            OCR_JOBS[job_id] = job
            t = threading.Thread(target=run_ocr_job, args=(job,), daemon=True)
            t.start()
            return self.send_json({"job": job}, 202)
        m = re.fullmatch(r"/api/ocr/jobs/([^/]+)/cancel", path)
        if m:
            job = OCR_JOBS.get(m.group(1))
            if not job:
                return self.send_error_json("任务不存在", 404)
            job["cancel"] = True
            return self.send_json({"ok": True})
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

    def page_image(self, book_id: str, page_no: int):
        book = db.get_book(book_id)
        if not book:
            return self.send_error_json("书籍不存在", 404)
        dest = PAGES / book_id / f"{page_no:04d}.jpg"
        if not dest.exists():
            from . import ocr

            src = ocr.resolve_pdf(book.get("source_pdf"))
            if not src:
                return self.send_error_json("原始 PDF 不可用。請把 PDF 放入 data/inbox/，或設定 READHISTORY_PDF。", 404)
            img = ocr.render_page(src, page_no, dpi=150)
            angle = ocr.estimate_rotation(img)
            if angle:
                img = img.rotate(angle, expand=True)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, quality=84, optimize=True)
        return self.send_file(dest, cache=True)


def run_ocr_job(job: dict):
    from . import ocr

    job["status"] = "running"
    job["message"] = "正在识别"
    book = db.get_book(job["book_id"])
    src = ocr.resolve_pdf(book.get("source_pdf") if book else None)
    if not src:
        job["status"] = "error"
        job["message"] = "原始 PDF 不可用。請把 PDF 放入 data/inbox/，或設定 READHISTORY_PDF。"
        return
    lang = "ch_doc_server" if job["quality"] == "high" else "chinese_cht_mobile"
    try:
        for n in range(job["start"], job["end"] + 1):
            if job.get("cancel"):
                job["status"] = "cancelled"
                job["message"] = "已取消"
                return
            job["current"] = n
            try:
                result = ocr.analyze_page(src, n, book_id=job["book_id"], lang_rec=lang)
                db.store_ocr_page(
                    job["book_id"],
                    n,
                    "done",
                    result.get("average_confidence"),
                    result.get("lines", []),
                )
                job["done"] += 1
                job["message"] = f"第 {n} 页完成"
            except Exception as exc:
                db.store_ocr_page(job["book_id"], n, "error", None, [])
                job["message"] = f"第 {n} 页失败：{exc}"
        job["status"] = "done"
        job["message"] = f"完成 {job['done']} 页"
    except Exception as exc:
        traceback.print_exc()
        job["status"] = "error"
        job["message"] = f"任务失败：{exc}"


def serve(host: str = "127.0.0.1", port: int = 8765):
    db.init_db()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"青简 · ReadHistory {__version__}  http://{host}:{port}")
    print("按 Ctrl+C 停止。")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止…")
    finally:
        httpd.server_close()
