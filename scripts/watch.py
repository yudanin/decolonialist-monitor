#!/usr/bin/env python3
"""Fetch sources.yaml, extract candidate items, diff against data/snapshots/.

Output: data/new_items.json  — items never seen before, for score.py.
State:  data/snapshots/<source_id>.json — set of seen item hashes.

Deliberately dumb and robust: a source failing (site down, layout change)
logs a warning and never kills the run.
"""

import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = ROOT / "data" / "snapshots"
NEW_ITEMS = ROOT / "data" / "new_items.json"
UA = {"User-Agent": "decolonialist-monitor/1.0 (+https://decolonial.ist; contact@decolonial.ist)"}

MIN_TITLE_LEN = 15  # drop nav junk like "Home", "Read more"


def item_id(source_id: str, url: str, title: str) -> str:
    return hashlib.sha1(f"{source_id}|{url}|{title}".encode()).hexdigest()[:16]


def fetch_rss(source: dict) -> list[dict]:
    feed = feedparser.parse(source["url"], request_headers=UA)
    out = []
    for e in feed.entries[:100]:
        title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        if not title or not link:
            continue
        out.append({"title": title, "url": link,
                    "snippet": BeautifulSoup(e.get("summary", ""), "html.parser")
                               .get_text(" ", strip=True)[:500]})
    return out


def fetch_html(source: dict) -> list[dict]:
    r = requests.get(source["url"], headers=UA, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    scope = None
    for sel in [s.strip() for s in source.get("selector", "main,body").split(",")]:
        scope = soup.select_one(sel)
        if scope:
            break
    if scope is None:
        scope = soup
    out, seen = [], set()
    for a in scope.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = urljoin(source["url"], a["href"]).split("#")[0]
        if len(title) < MIN_TITLE_LEN or href in seen or href.startswith("javascript:"):
            continue
        seen.add(href)
        out.append({"title": title[:300], "url": href, "snippet": ""})
    return out[:200]


def main() -> int:
    sources = yaml.safe_load((ROOT / "sources.yaml").read_text())
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    new_items, now = [], int(time.time())

    for src in sources:
        try:
            items = fetch_rss(src) if src["method"] == "rss" else fetch_html(src)
        except Exception as exc:  # noqa: BLE001 — per-source resilience is the point
            print(f"[warn] {src['id']}: {exc}", file=sys.stderr)
            continue

        snap_path = SNAP_DIR / f"{src['id']}.json"
        seen = set(json.loads(snap_path.read_text())) if snap_path.exists() else set()
        first_run = not snap_path.exists()

        fresh = []
        for it in items:
            iid = item_id(src["id"], it["url"], it["title"])
            if iid in seen:
                continue
            seen.add(iid)
            fresh.append({**it, "id": iid, "source_id": src["id"],
                          "source_name": src["name"], "type": src["type"],
                          "seen_at": now})

        # On a source's first run, record state but don't flood the scorer
        # with the entire historical page — only genuinely *new* items later.
        if not first_run:
            new_items.extend(fresh)
        snap_path.write_text(json.dumps(sorted(seen), indent=0))
        print(f"[ok] {src['id']}: {len(items)} items, "
              f"{len(fresh)} new{' (baseline run, not scored)' if first_run else ''}")

    NEW_ITEMS.write_text(json.dumps(new_items, indent=2, ensure_ascii=False))
    print(f"[done] {len(new_items)} new items -> {NEW_ITEMS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
