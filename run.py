from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for dep in (".ocr2", ".ocrdeps", ".pdfium"):
    p = str(ROOT / dep)
    if p not in sys.path:
        sys.path.insert(0, p)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reader.server import serve  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="青简 · 二十四史阅读器")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = parser.parse_args()
    if args.open:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
