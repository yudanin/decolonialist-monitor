#!/usr/bin/env python3
"""Prefilter data/new_items.json by keyword, score survivors with Claude Haiku
against RUBRIC.md + context/project.md, append hits to data/results.json.

Env:
  ANTHROPIC_API_KEY  (required)
  MIN_TOTAL          score threshold to enter results.json (default 12)
  SCORE_MODEL        default claude-haiku-4-5
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from anthropic import Anthropic
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
NEW_ITEMS = ROOT / "data" / "new_items.json"
RESULTS = ROOT / "data" / "results.json"
UA = {"User-Agent": "decolonialist-monitor/1.0 (+https://decolonial.ist)"}

MIN_TOTAL = int(os.environ.get("MIN_TOTAL", "12"))
MODEL = os.environ.get("SCORE_MODEL", "claude-haiku-4-5")

# Cheap gate before any API call. Deliberately broad — the LLM does the
# thinking; this only removes the obviously-unrelated 90%.
PREFILTER = re.compile(
    r"decoloni|coloni|imperial|empire|russia|soviet|post-soviet|ussr|ukrain|"
    r"belarus|caucasus|central asia|siberia|indigenous|eastern europ|baltic|"
    r"crimea|genocide|memory|nationalis|diaspora|disinformation|propaganda|"
    r"authoritarian|totalitarian|human rights|civil society|grant|fellowship|"
    r"funding|call for", re.IGNORECASE)


def page_text(url: str, limit: int = 6000) -> str:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "footer", "header"]):
            t.decompose()
        return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:limit]
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] fetch {url}: {exc}", file=sys.stderr)
        return ""


def score_item(client: Anthropic, rubric: str, project: str, item: dict) -> dict | None:
    body = page_text(item["url"])
    prompt = (
        f"<project_summary>\n{project}\n</project_summary>\n\n"
        f"<rubric>\n{rubric}\n</rubric>\n\n"
        f"<opportunity>\nSource: {item['source_name']} (type hint: {item['type']})\n"
        f"Title: {item['title']}\nURL: {item['url']}\n"
        f"Snippet: {item.get('snippet','')}\n\nPage text:\n{body}\n</opportunity>\n\n"
        "Score this opportunity per the rubric. Respond with ONLY the JSON object."
    )
    resp = client.messages.create(model=MODEL, max_tokens=800,
                                  messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        print(f"[warn] no JSON for {item['id']}", file=sys.stderr)
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        print(f"[warn] bad JSON for {item['id']}: {exc}", file=sys.stderr)
        return None


def main() -> int:
    items = json.loads(NEW_ITEMS.read_text()) if NEW_ITEMS.exists() else []
    if not items:
        print("[done] no new items")
        return 0

    kept = [i for i in items if PREFILTER.search(f"{i['title']} {i.get('snippet','')}")]
    print(f"[prefilter] {len(items)} -> {len(kept)}")
    if not kept:
        return 0

    client = Anthropic()  # reads ANTHROPIC_API_KEY
    rubric = (ROOT / "RUBRIC.md").read_text()
    project = (ROOT / "context" / "project.md").read_text()
    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else []
    known_ids = {r["id"] for r in results}
    added = 0

    for item in kept:
        if item["id"] in known_ids:
            continue
        verdict = score_item(client, rubric, project, item)
        time.sleep(1)  # be polite to the API and target sites
        if not verdict or not verdict.get("relevant"):
            continue
        total = int(verdict.get("total") or sum(verdict.get("scores", {}).values()))
        if total < MIN_TOTAL:
            print(f"[skip<{MIN_TOTAL}] {total:2d} {item['title'][:70]}")
            continue
        results.append({
            "id": item["id"], "title": item["title"], "url": item["url"],
            "source": item["source_name"],
            "type": verdict.get("kind", item["type"]),
            "scores": verdict.get("scores", {}), "total": total,
            "deadline": verdict.get("deadline"),
            "summary": verdict.get("summary", ""),
            "rationale": verdict.get("rationale", ""),
            "status": "new", "found_at": item["seen_at"], "proposal": None,
        })
        added += 1
        print(f"[hit {total:2d}] {item['title'][:70]}")

    results.sort(key=lambda r: (-r["total"], -r["found_at"]))
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    NEW_ITEMS.write_text("[]")
    print(f"[done] +{added} -> {RESULTS.relative_to(ROOT)} ({len(results)} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
