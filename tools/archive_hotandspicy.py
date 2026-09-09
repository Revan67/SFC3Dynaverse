"""Resumably archive public Hot & Spicy Starfleet Command forum HTML."""

from __future__ import annotations

import hashlib
import html.parser
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path


BASE = "https://hotandspicyforums.com"
SEED = f"{BASE}/starfleet-command-f3/"
ROOT = Path(__file__).resolve().parents[1] / "reference" / "forum-archive" / "hotandspicy"
RAW = ROOT / "raw"
STATE = ROOT / "crawl-state.json"
MANIFEST = ROOT / "manifest.jsonl"
MEDIA = ROOT / "media-links.txt"
EXTERNAL = ROOT / "external-links.txt"
USER_AGENT = "Mozilla/5.0 (compatible; SFCResearchArchive/1.0; personal archival)"
DELAY_SECONDS = 0.4
MAX_PAGES = 2500

FORUM_RE = re.compile(r"(?:^|-)f(?P<id>\d+)(?:/|\.html)?$")
TOPIC_RE = re.compile(r"(?:^|-)t\d+(?:-s\d+)?(?:/|\.html)?$")


class Links(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.media: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag in {"img", "video", "audio", "source"} and values.get("src"):
            self.media.append(values["src"])


def normalize(url: str, parent: str = SEED) -> str | None:
    absolute = urllib.parse.urljoin(parent, url)
    parts = urllib.parse.urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return None
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key.casefold() != "sid"]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc.casefold(), parts.path, urllib.parse.urlencode(query), ""))


def forum_id(url: str) -> int | None:
    path = urllib.parse.urlsplit(url).path.rstrip("/")
    match = FORUM_RE.search(path)
    if match:
        return int(match.group("id"))
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    return int(query["f"]) if query.get("f", "").isdigit() else None


def is_topic(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    return bool(TOPIC_RE.search(parts.path.rstrip("/"))) or (
        parts.path.endswith("viewtopic.php") and dict(urllib.parse.parse_qsl(parts.query)).get("t", "").isdigit()
    )


def output_path(url: str) -> Path:
    parts = urllib.parse.urlsplit(url)
    label = re.sub(r"[^A-Za-z0-9._-]+", "_", parts.path.strip("/") or "index")[:140]
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return RAW / f"{label}-{digest}.html"


def load_state() -> tuple[deque[str], set[str], set[int]]:
    if not STATE.exists():
        return deque((SEED,)), set(), {3}
    state = json.loads(STATE.read_text(encoding="utf-8"))
    return deque(state["queue"]), set(state["visited"]), set(state["forum_ids"])


def save_state(queue: deque[str], visited: set[str], forum_ids: set[int]) -> None:
    STATE.write_text(json.dumps({
        "queue": list(queue), "visited": sorted(visited), "forum_ids": sorted(forum_ids),
    }, indent=2) + "\n", encoding="utf-8")


def fetch(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"refusing non-HTML content type {content_type}")
        return response.read(), response.geturl()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    queue, visited, forum_ids = load_state()
    media_links = set(MEDIA.read_text(encoding="utf-8").splitlines()) if MEDIA.exists() else set()
    external_links = set(EXTERNAL.read_text(encoding="utf-8").splitlines()) if EXTERNAL.exists() else set()
    fetched = 0
    while queue and len(visited) < MAX_PAGES:
        url = queue.popleft()
        if url in visited:
            continue
        try:
            body, final_url = fetch(url)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            with MANIFEST.open("a", encoding="utf-8") as manifest:
                manifest.write(json.dumps({"url": url, "error": str(exc), "time": time.time()}) + "\n")
            visited.add(url)
            save_state(queue, visited, forum_ids)
            time.sleep(DELAY_SECONDS)
            continue

        final_url = normalize(final_url) or url
        path = output_path(final_url)
        path.write_bytes(body)
        visited.add(url)
        visited.add(final_url)
        fetched += 1
        parser = Links()
        parser.feed(body.decode("utf-8", errors="replace"))

        for raw_link in parser.links:
            link = normalize(raw_link, final_url)
            if not link:
                continue
            host = urllib.parse.urlsplit(link).netloc
            candidate_forum = forum_id(link)
            if host != urllib.parse.urlsplit(BASE).netloc:
                external_links.add(link)
                continue
            if "download/file.php" in link or "/attachment" in urllib.parse.urlsplit(link).path:
                media_links.add(link)
                continue
            if candidate_forum is not None and (url == SEED or candidate_forum in forum_ids):
                forum_ids.add(candidate_forum)
                if link not in visited:
                    queue.append(link)
            elif is_topic(link) and (candidate_forum is None or candidate_forum in forum_ids):
                if link not in visited:
                    queue.append(link)

        for raw_link in parser.media:
            link = normalize(raw_link, final_url)
            if link:
                media_links.add(link)

        with MANIFEST.open("a", encoding="utf-8") as manifest:
            manifest.write(json.dumps({
                "url": final_url, "file": str(path.relative_to(ROOT)), "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(), "time": time.time(),
            }) + "\n")
        MEDIA.write_text("\n".join(sorted(media_links)) + "\n", encoding="utf-8")
        EXTERNAL.write_text("\n".join(sorted(external_links)) + "\n", encoding="utf-8")
        save_state(queue, visited, forum_ids)
        if fetched % 25 == 0:
            print(f"fetched={fetched} total={len(visited)} queued={len(queue)}", flush=True)
        time.sleep(DELAY_SECONDS)
    print(f"complete fetched_this_run={fetched} total_urls={len(visited)} remaining={len(queue)}")


if __name__ == "__main__":
    main()
