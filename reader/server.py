from __future__ import annotations

import json
import mimetypes
import re
import shutil
import threading
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
        candidates = []
        for page_no in (start, start + 1, start + 2):
            if 1 <= page_no <= meta["pages"] and page_no not in candidates:
                candidates.append(page_no)
        for page_no in (1, 2, 3):
            if page_no <= meta["pages"] and page_no not in candidates:
                candidates.append(page_no)

        results = []
        for page_no in candidates:
            try:
                probe = ocr.probe_page(str(pdf), page_no, forced_layout=forced)
            except Exception:
                traceback.print_exc()
                continue
            if probe:
                results.append(probe)
            # Front matter and plates often contain only a few glyphs; skip
            # them and look at the next page before deciding.
            if len(results) >= 2 and all((r.get("chars") or 0) >= 20 for r in results):
                break
        if not results:
            return self.send_error_json("這幾頁沒有找到可識別的文字，請換一個頁碼或手動指定版式", 422)
        good = [r for r in results if (r.get("chars") or 0) >= 20] or results
        layouts = [r["layout"] for r in good]
        layout = max(set(layouts), key=layouts.count)
        rotations = [r["rotation"] for r in good if r["layout"] == layout]
        rotation = max(set(rotations), key=rotations.count) if rotations else 0
        confidence = max((r.get("confidence") or 0) for r in good)
        warning = ""
        if max((r.get("chars") or 0) for r in results) < 20:
            warning = "這幾頁文字太少，自動判斷可能不準；請換一個正文頁碼，或手動選擇豎排 / 橫排。"
        return self.send_json(
            {
                "suggestion": {
                    "layout": layout,
                    "rotation": rotation,
                    "confidence": round(float(confidence), 3),
                    "pages": results,
                    "warning": warning,
                },
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
        quality = "high" if payload.get("quality") == "high" else "fast"

        book_id = "b-" + uuid.uuid4().hex[:10]
        chapter_id = f"{book_id}-01"
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
        chapter = db.create_chapter(
            {
                "id": chapter_id,
                "book_id": book_id,
                "volume": "卷一",
                "title": chapter_title,
                "subtitle": "掃描本",
                "order_no": 1,
                "page_start": start,
                "page_end": end,
                "status": "importing",
                "page_count": end - start + 1,
            }
        )
        job_id = f"ocr-{uuid.uuid4().hex[:8]}"
        job = {
            "id": job_id,
            "kind": "import",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "start": start,
            "end": end,
            "quality": quality,
            "layout": layout,
            "rotation": int(payload.get("rotation") or 0),
            "status": "queued",
            "done": 0,
            "total": end - start + 1,
            "current": start,
            "message": "等待開始",
            "cancel": False,
        }
        OCR_JOBS[job_id] = job
        threading.Thread(target=run_ocr_job, args=(job,), daemon=True).start()
        return self.send_json({"book": book, "chapter": chapter, "job": job}, 202)

    # ---------- ocr ----------
    def start_ocr(self, payload: dict):
        book = db.get_book(payload.get("book_id") or "jinshu")
        if not book:
            return self.send_error_json("书籍不存在", 404)
        start = int(payload.get("start") or 1)
        end = int(payload.get("end") or start)
        end = max(start, min(end, start + 199, int(book.get("total_pages") or end)))
        quality = "high" if payload.get("quality") == "high" else "fast"
        chapter_id = None
        if book.get("imported"):
            chapters = db.get_chapters(book["id"])
            if chapters:
                chapter_id = chapters[0]["id"]
                start = max(start, int(chapters[0]["page_start"] or 1))
                end = min(end, int(chapters[0]["page_end"] or end))
        job_id = f"ocr-{uuid.uuid4().hex[:8]}"
        rotation = book.get("orientation")
        job = {
            "id": job_id,
            "kind": "import" if book.get("imported") else "ocr",
            "book_id": book["id"],
            "chapter_id": chapter_id,
            "start": start,
            "end": end,
            "quality": quality,
            "layout": book.get("layout") or "horizontal",
            "rotation": int(rotation) if rotation is not None else None,
            "status": "queued",
            "done": 0,
            "total": end - start + 1,
            "current": start,
            "message": "等待開始",
            "cancel": False,
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
    if job["quality"] == "high" and not high_ocr_available():
        job["quality"] = "fast"
        job["message"] = "精校模型未包含在此版本中，已改用快速模式"
    lang = "ch_doc_server" if job["quality"] == "high" else "chinese_cht_mobile"
    layout = job.get("layout") or book.get("layout") or "horizontal"
    rotation = job.get("rotation")
    if rotation is None and book.get("orientation") is not None:
        rotation = int(book["orientation"])
    chapter_id = job.get("chapter_id")
    importing = job.get("kind") == "import" and chapter_id
    try:
        if importing:
            db.delete_paragraphs_for_pages(chapter_id, job["start"], job["end"])
        for n in range(job["start"], job["end"] + 1):
            if job.get("cancel"):
                job["status"] = "cancelled"
                job["message"] = "已取消"
                if importing:
                    db.update_chapter(chapter_id, status="ready")
                    db.update_book(job["book_id"], status="ready")
                return
            job["current"] = n
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
                db.store_ocr_page(
                    job["book_id"],
                    n,
                    "done",
                    result.get("average_confidence"),
                    result.get("lines", []),
                )
                if importing:
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
                job["done"] += 1
                job["message"] = f"第 {n} 頁完成"
            except Exception as exc:
                traceback.print_exc()
                db.store_ocr_page(job["book_id"], n, "error", None, [])
                job["message"] = f"第 {n} 頁失敗：{exc}"
        job["status"] = "done"
        job["message"] = f"完成 {job['done']} 頁"
        if importing:
            db.update_chapter(chapter_id, status="ready")
            db.update_book(job["book_id"], status="ready")
    except Exception as exc:
        traceback.print_exc()
        job["status"] = "error"
        job["message"] = f"任务失败：{exc}"
        if importing:
            db.update_chapter(chapter_id, status="ready")
            db.update_book(job["book_id"], status="ready")


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
