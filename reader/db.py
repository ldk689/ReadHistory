from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from . import paths

DATA = paths.DATA
DB_PATH = paths.DB_PATH
SEED_PATH = paths.SEED / "jinshu_vol1.json"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    dynasty TEXT,
    edition TEXT,
    description TEXT,
    total_pages INTEGER DEFAULT 0,
    source_pdf TEXT,
    cover TEXT,
    accent TEXT,
    layout TEXT DEFAULT 'horizontal',
    orientation INTEGER,
    imported INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ready',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    volume TEXT,
    title TEXT NOT NULL,
    subtitle TEXT,
    order_no INTEGER NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    status TEXT DEFAULT 'locked'
);

CREATE TABLE IF NOT EXISTS paragraphs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    order_no INTEGER NOT NULL,
    text TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    ocr_confidence REAL,
    reviewed INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS footnotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    paragraph_id INTEGER REFERENCES paragraphs(id) ON DELETE CASCADE,
    marker TEXT NOT NULL,
    text TEXT NOT NULL,
    page INTEGER
);

CREATE TABLE IF NOT EXISTS annotations (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    paragraph_id INTEGER NOT NULL REFERENCES paragraphs(id) ON DELETE CASCADE,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    quote TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'highlight',
    color TEXT NOT NULL DEFAULT 'ochre',
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS progress (
    book_id TEXT PRIMARY KEY,
    chapter_id TEXT,
    paragraph_id INTEGER,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS ocr_pages (
    book_id TEXT NOT NULL,
    page_no INTEGER NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    lines_json TEXT,
    updated_at TEXT,
    PRIMARY KEY (book_id, page_no)
);

CREATE INDEX IF NOT EXISTS idx_chapters_book ON chapters(book_id, order_no);
CREATE INDEX IF NOT EXISTS idx_paragraphs_chapter ON paragraphs(chapter_id, order_no);
CREATE INDEX IF NOT EXISTS idx_footnotes_chapter ON footnotes(chapter_id);
CREATE INDEX IF NOT EXISTS idx_annotations_chapter ON annotations(chapter_id);
CREATE INDEX IF NOT EXISTS idx_annotations_paragraph ON annotations(paragraph_id);
"""


def _migrate(con: sqlite3.Connection) -> None:
    """Add columns introduced after 0.1.0 without touching existing data."""
    wanted = {
        "books": [
            ("layout", "TEXT DEFAULT 'horizontal'"),
            ("orientation", "INTEGER"),
            ("imported", "INTEGER DEFAULT 0"),
            ("status", "TEXT DEFAULT 'ready'"),
            ("created_at", "TEXT"),
        ],
        "chapters": [("page_count", "INTEGER DEFAULT 0")],
    }
    for table, columns in wanted.items():
        have = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns:
            if name not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    # The 0.1.0 sample PDF is stored rotated; let the OCR layer detect the
    # angle per page instead of inheriting a migration default of 0.
    con.execute(
        "UPDATE books SET orientation=NULL WHERE id='jinshu' AND imported=0 AND orientation=0"
    )
    # OCR jobs live in memory. If the process was closed mid-import, make the
    # already-recognised pages readable instead of leaving a permanent
    # "importing" badge.
    con.execute("UPDATE chapters SET status='ready' WHERE status='importing'")
    con.execute("UPDATE books SET status='ready' WHERE status='importing'")


def init_db() -> None:
    paths.ensure_dirs()
    with connect() as con:
        con.executescript(SCHEMA)
        _migrate(con)
        if con.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
            seed(con)


def seed(con: sqlite3.Connection) -> None:
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    book = data["book"]
    con.execute(
        """INSERT INTO books
           (id,title,author,dynasty,edition,description,total_pages,source_pdf,cover,accent,
            layout,orientation,imported,status,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            book["id"],
            book["title"],
            book.get("author"),
            book.get("dynasty"),
            book.get("edition"),
            book.get("description"),
            book.get("total_pages", 0),
            book.get("source_pdf"),
            book.get("cover"),
            book.get("accent"),
            book.get("layout", "horizontal"),
            book.get("orientation"),
            0,
            "ready",
            now(),
        ),
    )
    for ch in data["chapters"]:
        con.execute(
            """INSERT INTO chapters (id,book_id,volume,title,subtitle,order_no,page_start,page_end,status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                ch["id"],
                book["id"],
                ch.get("volume"),
                ch["title"],
                ch.get("subtitle"),
                ch["order_no"],
                ch.get("page_start"),
                ch.get("page_end"),
                ch.get("status", "locked"),
            ),
        )
        for para in ch.get("paragraphs", []):
            cur = con.execute(
                """INSERT INTO paragraphs (chapter_id,order_no,text,page_start,page_end,reviewed)
                   VALUES (?,?,?,?,?,1)""",
                (
                    ch["id"],
                    para["order_no"],
                    para["text"],
                    para.get("page_start"),
                    para.get("page_end"),
                ),
            )
            pid = cur.lastrowid
            # Seed a couple of discreet example marks so the interaction is visible on first run.
            if ch["id"] == "jinshu-01" and para["order_no"] == 1:
                quote = "少有奇節，聰朗多大略"
                start = para["text"].find(quote)
                if start >= 0:
                    con.execute(
                        """INSERT INTO annotations
                           (id,book_id,chapter_id,paragraph_id,start_offset,end_offset,quote,kind,color,note,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            "demo-note-1",
                            book["id"],
                            ch["id"],
                            pid,
                            start,
                            start + len(quote),
                            quote,
                            "note",
                            "cinnabar",
                            "儒教與權謀，是司馬懿一生的兩面。此處先寫「奇節」，後文再寫「猜忍」，一褒一貶，正是《晉書》的筆法。",
                            now(),
                            now(),
                        ),
                    )
            if ch["id"] == "jinshu-01" and para["order_no"] == 6:
                quote = "既示敵以弱"
                start = para["text"].find(quote)
                if start >= 0:
                    con.execute(
                        """INSERT INTO annotations
                           (id,book_id,chapter_id,paragraph_id,start_offset,end_offset,quote,kind,color,note,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            "demo-mark-1",
                            book["id"],
                            ch["id"],
                            pid,
                            start,
                            start + len(quote),
                            quote,
                            "underline",
                            "ochre",
                            "",
                            now(),
                            now(),
                        ),
                    )

        marker_to_id: dict[str, int] = {}
        for note in ch.get("notes", []):
            pid = con.execute(
                "SELECT id FROM paragraphs WHERE chapter_id=? AND order_no=?",
                (ch["id"], note.get("paragraph_no")),
            ).fetchone()
            cur = con.execute(
                "INSERT INTO footnotes (chapter_id,paragraph_id,marker,text,page) VALUES (?,?,?,?,?)",
                (ch["id"], pid["id"] if pid else None, note["marker"], note["text"], note.get("page")),
            )
            marker_to_id[note["marker"]] = cur.lastrowid

    con.execute(
        "INSERT OR REPLACE INTO progress (book_id,chapter_id,paragraph_id,updated_at) VALUES (?,?,?,?)",
        (book["id"], "jinshu-01", None, now()),
    )
    con.execute(
        "INSERT OR REPLACE INTO settings (key,value) VALUES ('reader',?)",
        (
            json.dumps(
                {
                    "layout": "vertical",
                    "theme": "paper",
                    "fontSize": 21,
                    "fontFamily": "song",
                },
                ensure_ascii=False,
            ),
        ),
    )
    con.commit()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def get_library() -> list[dict[str, Any]]:
    with connect() as con:
        books = rows_to_dicts(con.execute("SELECT * FROM books ORDER BY title").fetchall())
        for b in books:
            b["chapter_count"] = con.execute(
                "SELECT COUNT(*) FROM chapters WHERE book_id=?", (b["id"],)
            ).fetchone()[0]
            b["ready_count"] = con.execute(
                "SELECT COUNT(*) FROM chapters WHERE book_id=? AND status='ready'", (b["id"],)
            ).fetchone()[0]
            b["annotation_count"] = con.execute(
                "SELECT COUNT(*) FROM annotations WHERE book_id=?", (b["id"],)
            ).fetchone()[0]
            prog = con.execute("SELECT * FROM progress WHERE book_id=?", (b["id"],)).fetchone()
            b["progress"] = dict(prog) if prog else None
        return books


def get_book(book_id: str) -> dict[str, Any] | None:
    with connect() as con:
        row = con.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        return dict(row) if row else None


def create_book(book: dict[str, Any]) -> dict[str, Any]:
    with connect() as con:
        con.execute(
            """INSERT INTO books
               (id,title,author,dynasty,edition,description,total_pages,source_pdf,cover,accent,
                layout,orientation,imported,status,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                book["id"],
                book["title"],
                book.get("author") or "",
                book.get("dynasty") or "",
                book.get("edition") or "導入掃描本",
                book.get("description") or "",
                int(book.get("total_pages") or 0),
                book.get("source_pdf"),
                book.get("cover"),
                book.get("accent") or "#a33b2b",
                book.get("layout") or "horizontal",
                int(book.get("orientation") or 0),
                1 if book.get("imported") else 0,
                book.get("status") or "importing",
                now(),
            ),
        )
        con.commit()
        row = con.execute("SELECT * FROM books WHERE id=?", (book["id"],)).fetchone()
        return dict(row)


def update_book(book_id: str, **fields: Any) -> None:
    allowed = {
        "title", "author", "dynasty", "edition", "description", "total_pages",
        "source_pdf", "cover", "accent", "layout", "orientation", "status",
    }
    pairs = [(k, v) for k, v in fields.items() if k in allowed]
    if not pairs:
        return
    with connect() as con:
        con.execute(
            "UPDATE books SET " + ",".join(f"{k}=?" for k, _ in pairs) + " WHERE id=?",
            [v for _, v in pairs] + [book_id],
        )
        con.commit()


def create_chapter(chapter: dict[str, Any]) -> dict[str, Any]:
    with connect() as con:
        con.execute(
            """INSERT INTO chapters
               (id,book_id,volume,title,subtitle,order_no,page_start,page_end,status,page_count)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                chapter["id"],
                chapter["book_id"],
                chapter.get("volume") or "卷一",
                chapter["title"],
                chapter.get("subtitle") or "",
                int(chapter.get("order_no") or 1),
                chapter.get("page_start"),
                chapter.get("page_end"),
                chapter.get("status") or "importing",
                int(chapter.get("page_count") or 0),
            ),
        )
        con.commit()
        row = con.execute("SELECT * FROM chapters WHERE id=?", (chapter["id"],)).fetchone()
        return dict(row)


def update_chapter(chapter_id: str, **fields: Any) -> None:
    allowed = {"title", "subtitle", "status", "page_start", "page_end", "page_count"}
    pairs = [(k, v) for k, v in fields.items() if k in allowed]
    if not pairs:
        return
    with connect() as con:
        con.execute(
            "UPDATE chapters SET " + ",".join(f"{k}=?" for k, _ in pairs) + " WHERE id=?",
            [v for _, v in pairs] + [chapter_id],
        )
        con.commit()


def add_paragraph(
    chapter_id: str,
    order_no: int,
    text: str,
    page_start: int | None = None,
    page_end: int | None = None,
    confidence: float | None = None,
) -> int:
    with connect() as con:
        cur = con.execute(
            """INSERT INTO paragraphs
               (chapter_id,order_no,text,page_start,page_end,ocr_confidence,reviewed)
               VALUES (?,?,?,?,?,?,0)""",
            (chapter_id, order_no, text, page_start, page_end, confidence),
        )
        con.commit()
        return int(cur.lastrowid)


def delete_paragraphs_for_pages(chapter_id: str, start: int, end: int) -> None:
    with connect() as con:
        con.execute(
            """DELETE FROM paragraphs
               WHERE chapter_id=? AND page_start>=? AND page_end<=?""",
            (chapter_id, start, end),
        )
        con.commit()


def next_paragraph_order(chapter_id: str) -> int:
    with connect() as con:
        row = con.execute(
            "SELECT COALESCE(MAX(order_no),0)+1 FROM paragraphs WHERE chapter_id=?",
            (chapter_id,),
        ).fetchone()
        return int(row[0])


def get_chapters(book_id: str) -> list[dict[str, Any]]:
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM chapters WHERE book_id=? ORDER BY order_no", (book_id,)
        ).fetchall()
        return rows_to_dicts(rows)


def _parse_annotations(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return rows_to_dicts(rows)


def get_chapter(book_id: str, chapter_id: str) -> dict[str, Any] | None:
    with connect() as con:
        book = con.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        ch = con.execute(
            "SELECT * FROM chapters WHERE id=? AND book_id=?", (chapter_id, book_id)
        ).fetchone()
        if not book or not ch:
            return None
        paras = con.execute(
            "SELECT * FROM paragraphs WHERE chapter_id=? ORDER BY order_no", (chapter_id,)
        ).fetchall()
        notes = con.execute(
            "SELECT * FROM footnotes WHERE chapter_id=? ORDER BY id", (chapter_id,)
        ).fetchall()
        anns = con.execute(
            "SELECT * FROM annotations WHERE chapter_id=? ORDER BY created_at", (chapter_id,)
        ).fetchall()
        prev = con.execute(
            "SELECT id,volume,title,subtitle FROM chapters WHERE book_id=? AND order_no<? ORDER BY order_no DESC LIMIT 1",
            (book_id, ch["order_no"]),
        ).fetchone()
        nxt = con.execute(
            "SELECT id,volume,title,subtitle FROM chapters WHERE book_id=? AND order_no>? ORDER BY order_no ASC LIMIT 1",
            (book_id, ch["order_no"]),
        ).fetchone()
        progress = con.execute("SELECT * FROM progress WHERE book_id=?", (book_id,)).fetchone()
        return {
            "book": dict(book),
            "chapter": dict(ch),
            "paragraphs": rows_to_dicts(paras),
            "footnotes": rows_to_dicts(notes),
            "annotations": _parse_annotations(anns),
            "prev": dict(prev) if prev else None,
            "next": dict(nxt) if nxt else None,
            "progress": dict(progress) if progress else None,
        }


def get_paragraph(paragraph_id: int) -> dict[str, Any] | None:
    with connect() as con:
        row = con.execute(
            """SELECT p.*, c.book_id, c.volume, c.title AS chapter_title, c.subtitle
               FROM paragraphs p JOIN chapters c ON c.id=p.chapter_id WHERE p.id=?""",
            (paragraph_id,),
        ).fetchone()
        return dict(row) if row else None


def get_annotations(book_id: str, chapter_id: str | None = None) -> list[dict[str, Any]]:
    with connect() as con:
        if chapter_id:
            rows = con.execute(
                "SELECT * FROM annotations WHERE book_id=? AND chapter_id=? ORDER BY created_at DESC",
                (book_id, chapter_id),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM annotations WHERE book_id=? ORDER BY created_at DESC", (book_id,)
            ).fetchall()
        return rows_to_dicts(rows)


def create_annotation(payload: dict[str, Any]) -> dict[str, Any]:
    with connect() as con:
        para = con.execute(
            "SELECT * FROM paragraphs WHERE id=?", (payload["paragraph_id"],)
        ).fetchone()
        if not para:
            raise ValueError("段落不存在")
        text = para["text"]
        start = int(payload["start_offset"])
        end = int(payload["end_offset"])
        if start < 0 or end > len(text) or start >= end:
            raise ValueError("选区无效")
        quote = text[start:end]
        if payload.get("quote") and payload["quote"] != quote:
            raise ValueError("选区与原文不一致，请重新选择")
        kind = payload.get("kind", "highlight")
        if kind not in {"highlight", "underline", "note"}:
            raise ValueError("批注类型无效")
        color = payload.get("color") or ("cinnabar" if kind == "note" else "ochre")
        note = (payload.get("note") or "").strip()
        if kind == "note" and not note:
            raise ValueError("批注内容不能为空")
        ann_id = payload.get("id") or f"a-{uuid.uuid4().hex[:12]}"
        ts = now()
        con.execute(
            """INSERT INTO annotations
               (id,book_id,chapter_id,paragraph_id,start_offset,end_offset,quote,kind,color,note,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ann_id,
                payload["book_id"],
                payload["chapter_id"],
                payload["paragraph_id"],
                start,
                end,
                quote,
                kind,
                color,
                note,
                ts,
                ts,
            ),
        )
        con.commit()
        row = con.execute("SELECT * FROM annotations WHERE id=?", (ann_id,)).fetchone()
        return dict(row)


def update_annotation(ann_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with connect() as con:
        row = con.execute("SELECT * FROM annotations WHERE id=?", (ann_id,)).fetchone()
        if not row:
            raise ValueError("批注不存在")
        note = payload.get("note", row["note"])
        color = payload.get("color", row["color"])
        kind = payload.get("kind", row["kind"])
        con.execute(
            "UPDATE annotations SET note=?,color=?,kind=?,updated_at=? WHERE id=?",
            (note, color, kind, now(), ann_id),
        )
        con.commit()
        return dict(con.execute("SELECT * FROM annotations WHERE id=?", (ann_id,)).fetchone())


def delete_annotation(ann_id: str) -> None:
    with connect() as con:
        con.execute("DELETE FROM annotations WHERE id=?", (ann_id,))
        con.commit()


def save_progress(book_id: str, chapter_id: str, paragraph_id: int | None) -> None:
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO progress (book_id,chapter_id,paragraph_id,updated_at) VALUES (?,?,?,?)",
            (book_id, chapter_id, paragraph_id, now()),
        )
        con.commit()


def search(book_id: str, query: str, limit: int = 30) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    with connect() as con:
        rows = con.execute(
            """SELECT p.id, p.chapter_id, p.order_no, p.text, c.volume, c.title, c.subtitle
               FROM paragraphs p JOIN chapters c ON c.id=p.chapter_id
               WHERE p.chapter_id IN (SELECT id FROM chapters WHERE book_id=?) AND p.text LIKE ?
               LIMIT ?""",
            (book_id, like, limit),
        ).fetchall()
        out = []
        for r in rows:
            text = r["text"]
            idx = text.find(q)
            start = max(0, idx - 36)
            end = min(len(text), idx + len(q) + 60)
            snippet = ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
            out.append(
                {
                    "paragraph_id": r["id"],
                    "chapter_id": r["chapter_id"],
                    "chapter": f"{r['volume']} {r['title']} {r['subtitle']}",
                    "snippet": snippet,
                    "offset": idx,
                }
            )
        return out


def get_setting(key: str, default: str | None = None) -> str | None:
    with connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
        con.commit()


def store_ocr_page(
    book_id: str, page_no: int, status: str, confidence: float | None, lines: list[dict[str, Any]]
) -> None:
    with connect() as con:
        con.execute(
            """INSERT OR REPLACE INTO ocr_pages (book_id,page_no,status,confidence,lines_json,updated_at)
               VALUES (?,?,?,?,?,?)""",
            (book_id, page_no, status, confidence, json.dumps(lines, ensure_ascii=False), now()),
        )
        con.commit()


def ocr_status(book_id: str) -> dict[str, Any]:
    with connect() as con:
        rows = con.execute(
            "SELECT page_no,status,confidence,updated_at FROM ocr_pages WHERE book_id=? ORDER BY page_no",
            (book_id,),
        ).fetchall()
        pages = rows_to_dicts(rows)
        done = [p for p in pages if p["status"] in {"done", "reviewed"}]
        avg = sum((p["confidence"] or 0) for p in done) / len(done) if done else None
        return {"pages": pages, "done": len(done), "average_confidence": avg}


def get_ocr_page(book_id: str, page_no: int) -> dict[str, Any] | None:
    with connect() as con:
        row = con.execute(
            "SELECT * FROM ocr_pages WHERE book_id=? AND page_no=?", (book_id, page_no)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["lines"] = json.loads(data.pop("lines_json") or "[]")
        except json.JSONDecodeError:
            data["lines"] = []
        return data


def save_ocr_text(book_id: str, page_no: int, text: str) -> None:
    with connect() as con:
        lines = [{"text": text, "box": None, "score": 1.0}]
        con.execute(
            """UPDATE ocr_pages SET lines_json=?, status='reviewed', updated_at=?
               WHERE book_id=? AND page_no=?""",
            (json.dumps(lines, ensure_ascii=False), now(), book_id, page_no),
        )
        con.commit()
