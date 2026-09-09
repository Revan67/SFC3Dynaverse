"""Search readable post bodies in the ignored Hot & Spicy forum mirror."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "reference" / "forum-archive" / "hotandspicy" / "raw"
POST = re.compile(
    r'data-tag="post_body_start"[^>]*>(.*?)<i data-tag="post_body_end"', re.DOTALL
)
TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")


def main() -> None:
    # Archived posts contain characters that the legacy Windows console codepage
    # cannot represent.  Preserve the useful context instead of aborting a search.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        raise SystemExit("usage: search_hotandspicy.py REGEX [MAX_RESULTS]")
    pattern = re.compile(sys.argv[1], re.IGNORECASE)
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    found = 0
    for path in sorted(ROOT.glob("*.html")):
        source = path.read_text(encoding="utf-8", errors="replace")
        for index, match in enumerate(POST.finditer(source), start=1):
            text = SPACE.sub(" ", html.unescape(TAG.sub(" ", match.group(1)))).strip()
            hit = pattern.search(text)
            if not hit:
                continue
            start = max(0, hit.start() - 350)
            end = min(len(text), hit.end() + 900)
            print(f"FILE: {path.name} POST: {index}\n{text[start:end]}\n")
            found += 1
            if found >= limit:
                print(f"RESULTS: {found} (limit reached)")
                return
    print(f"RESULTS: {found}")


if __name__ == "__main__":
    main()
