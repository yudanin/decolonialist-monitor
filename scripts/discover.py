#!/usr/bin/env python3
"""Web discovery: run the queries.yaml battery through Claude's web-search
tool and feed new finds into the scoring pipeline.

Unlike watch.py (a tripwire on known pages), this searches the open web —
it can find venues and calls nobody put on the source list.

Mechanics:
  - one API call per query, with the server-side web_search tool enabled
  - result URLs are collected from web_search tool-result blocks AND from a
    JSON list the model is asked to emit (belt and braces)
  - dedup against data/snapshots/discovery.json (by normalized URL)
  - new finds are APPENDED to data/new_items.json with source_id
    "discovery" — score.py sends these straight to the LLM, bypassing the
    keyword prefilter, since the query already selected for relevance

Env:
  ANTHROPIC_API_KEY   (required)
  DISCOVER_MODEL      default claude-haiku-4-5
  MAX_QUERIES         cap per run (default 30)
  RESULTS_PER_QUERY   cap per query (default 5)
"""

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml
from anthropic import Anthropic

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshots" / "discovery.json"
NEW_ITEMS = ROOT / "data" / "new_items.json"

MODEL = os.environ.get("DISCOVER_MODEL", "claude-haiku-4-5")
MAX_QUERIES = int(os.environ.get("MAX_QUERIES", "30"))
RESULTS_PER_QUERY = int(os.environ.get("RESULTS_PER_QUERY", "5"))

SKIP_DOMAINS = (  # login walls / platforms we can't fetch or score usefully
    "facebook.com", "instagram.com", "x.com", "twitter.com", "t.me",
    "linkedin.com", "youtube.com", "tiktok.com")


def norm_url(u: str) -> str:
    p = urlsplit(u.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(),
                       p.path.rstrip("/"), p.query, ""))


def item_id(url: str) -> str:
    return hashlib.sha1(f"discovery|{norm_url(url)}".encode()).hexdigest()[:16]


def run_query(client: Anthropic, q: str) -> list[dict]:
    """Return [{title,url,snippet}] for one search query."""
    prompt = (
        f"Search the web for: {q}\n\n"
        "From the results, list every distinct page that looks like a "
        "conference/CFP, grant/fellowship/funding call, or an outlet's pitch/"
        "submission page. Exclude social-media posts and generic homepages. "
        "Respond with ONLY a JSON array: "
        '[{"title": "...", "url": "...", "snippet": "one line on what it is"}]'
        " — empty array if nothing fits."
    )
    resp = client.messages.create(
        model=MODEL, max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search",
                "max_uses": 2}],
        messages=[{"role": "user", "content": prompt}])

    found: dict[str, dict] = {}
    for block in resp.content:
        # harvest raw search results if the SDK exposes them
        if getattr(block, "type", "") == "web_search_tool_result":
            for r in getattr(block, "content", []) or []:
                url = getattr(r, "url", None)
                if url:
                    found.setdefault(norm_url(url), {
                        "title": (getattr(r, "title", "") or "")[:300],
                        "url": url, "snippet": ""})
    text = "".join(b.text for b in resp.content
                   if getattr(b, "type", "") == "text")
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            for r in json.loads(m.group(0)):
                if isinstance(r, dict) and r.get("url"):
                    found[norm_url(r["url"])] = {
                        "title": (r.get("title") or "")[:300],
                        "url": r["url"],
                        "snippet": (r.get("snippet") or "")[:500]}
        except json.JSONDecodeError:
            pass
    out = [v for k, v in found.items()
           if not any(d in k for d in SKIP_DOMAINS) and v["title"]]
    return out[:RESULTS_PER_QUERY]


def main() -> int:
    year = dt.date.today().year
    queries = yaml.safe_load((ROOT / "queries.yaml").read_text())[:MAX_QUERIES]
    seen = set(json.loads(SNAP.read_text())) if SNAP.exists() else set()
    items = json.loads(NEW_ITEMS.read_text()) if NEW_ITEMS.exists() else []
    client = Anthropic()
    now, added = int(time.time()), 0

    for spec in queries:
        q = spec["q"].replace("{year}", str(year)).replace("{year2}", str(year + 1))
        try:
            results = run_query(client, q)
        except Exception as exc:  # noqa: BLE001 — per-query resilience
            print(f"[warn] query '{q}': {exc}", file=sys.stderr)
            continue
        fresh = 0
        for r in results:
            iid = item_id(r["url"])
            if iid in seen:
                continue
            seen.add(iid)
            items.append({**r, "id": iid, "source_id": "discovery",
                          "source_name": f"web discovery: {q}",
                          "type": spec.get("type", "other"), "seen_at": now})
            fresh += 1
            print(f"    new: {r['title'][:100]}")
        added += fresh
        print(f"[ok] '{q}': {len(results)} results, {fresh} new")
        time.sleep(1)

    SNAP.parent.mkdir(parents=True, exist_ok=True)
    SNAP.write_text(json.dumps(sorted(seen), indent=0))
    NEW_ITEMS.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    print(f"[done] discovery added {added} new items "
          f"-> {NEW_ITEMS.relative_to(ROOT)} ({len(items)} queued for scoring)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
