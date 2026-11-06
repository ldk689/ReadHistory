"""Filesystem layout for 青简 / ReadHistory.

The application can run in three shapes:

* from a source checkout (data lives next to ``run.py``);
* from the one-file Windows launcher, which sets ``READHISTORY_HOME`` to a
  writable per-user folder and unpacks the read-only application files into
  ``READHISTORY_HOME/app``;
* from the portable zip, where ``READHISTORY_HOME`` is unset and everything
  stays beside the executable.

Keeping the writable data directory separate from the application directory
means an upgrade can replace the program without touching a reader's
annotations, imported PDFs or OCR drafts.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent


def _home() -> Path:
    raw = os.environ.get("READHISTORY_HOME")
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except OSError:
            pass
    return APP_ROOT


HOME = _home()
DATA = Path(os.environ.get("READHISTORY_DATA") or (HOME / "data"))
SEED = APP_ROOT / "data" / "seed"
ASSETS = APP_ROOT / "data" / "assets"
WEB = APP_ROOT / "web"

DB_PATH = DATA / "reader.db"
PAGES = DATA / "pages"
IMPORTS = DATA / "imports"
LIBRARY = DATA / "library"
USER_ASSETS = DATA / "assets"
LOGS = HOME / "logs"


def ensure_dirs() -> None:
    for path in (DATA, DATA / "inbox", PAGES, IMPORTS, LIBRARY, USER_ASSETS, LOGS):
        path.mkdir(parents=True, exist_ok=True)
