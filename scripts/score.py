#!/usr/bin/env python3
"""Record ALL new items from data/new_items.json into data/results.json,
scoring prefilter survivors with Claude Haiku against RUBRIC.md.

Every fetched item is persisted with a `stage` explaining its journey:
  filtered  — failed the keyword prefilter (never sent to the LLM)
  scored    — scored by the LLM (see scores/total/rationale)
  error     — LLM call failed; retried next time it appears (it won't — kept for audit)

`status` starts as:
  new       — scored, relevant, total >= MIN_TOTAL  (surfaces in default UI view)
  fetched   — everything else (visible with widened filters)

Env:
  ANTHROPIC_API_KEY  (required when there are items to score)
  MIN_TOTAL          threshold for status "new" (default 12)
  SCORE_MODEL        default claude-haiku-4-5
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
import anthropic
from anthropic import Anthropic
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
NEW_ITEMS = ROOT / "data" / "new_items.json"
RESULTS = ROOT / "data" / "results.json"
UA = {"User-Agent": "decolonialist-monitor/1.0 (+https://decolonial.ist)"}

MIN_TOTAL = int(os.environ.get("MIN_TOTAL", "12"))
MODEL = os.environ.get("SCORE_MODEL", "claude-haiku-4-5")

# Cheap gate before any API call. Deliberately broad — the LLM does the
# thinking; this only removes the obviously-unrelated bulk.
PREFILTER = re.compile(
    # English
    r"decoloni|coloni|imperial|empire|russia|soviet|post-soviet|ussr|ukrain|"
    r"belarus|caucasus|central asia|siberia|indigenous|eastern europ|baltic|"
    r"crimea|genocide|memory|nationalis|diaspora|disinformation|propaganda|"
    r"authoritarian|totalitarian|human rights|civil society|grant|fellowship|"
    r"funding|call for|"
    # Ukrainian / Russian (Cyrillic)
    r"росі|росси|русск|радянськ|советск|срср|ссср|імпер|импер|колоні|колони|"
    r"деколон|україн|украин|білорус|белорус|кавказ|сибір|сибир|крим|крым|"
    r"геноцид|пам.ят|память|нації|наций|діаспор|диаспор|пропаганд|"
    r"тоталітар|тоталитар|громадянськ|гражданск|грант|стипенді|стипенди|"
    r"конкурс|фінансуванн|финансиров|заявк|"
    # German
    r"russland|sowjet|kolonial|dekoloni|osteuropa|imperium|belarus|ukraine|"
    r"gedenk|erinnerung|völkermord|genozid|zivilgesellschaft|stipendi|"
    r"förder|ausschreibung|antragsfrist|"
    # French
    r"russie|soviétiq|décolon|colonial|impéri|ukraine|génocide|mémoire|"
    r"société civile|bourse|subvention|appel à|"
    # Polish
    r"rosj|sowieck|dekoloniz|imperi|ukrain|białoru|ludobójstw|pamię|"
    r"stypendi|dotacj|nabór|"
    # Central Asia (Latin + Cyrillic)
    r"kazakh|qazaq|казах|kyrgyz|kirghiz|кыргыз|киргиз|uzbek|узбек|"
    r"tajik|таджик|turkmen|туркмен|karakalpak|каракалпак|"
    # Caucasus (Latin + Cyrillic; bare "georgia" omitted — US-state noise)
    r"georgian|tbilisi|грузи|сакартвело|armenia|армян|вірмен|"
    r"azerbaijan|азербайдж|abkhaz|абхаз|osset|осет|chechen|чечен|"
    r"ingush|ингуш|інгуш|dagestan|дагестан|circassian|cherkess|черкес|адыг|"
    # Idel-Ural, Siberia, and indigenous peoples of Russia
    r"tatar|татар|bashkir|башкир|buryat|бурят|kalmyk|калмы|"
    r"chuvash|чуваш|udmurt|удмурт|mordvin|мордов|yakut|якут|tuvan|тувин|"
    r"idel.ural|идель.урал|"
    # Eastern Europe additions
    r"moldov|молдов|transnistr|приднестров|gagauz|гагауз",
    re.IGNORECASE)


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


class FatalAPIError(Exception):
    """Billing/auth problems that no retry will fix — stop, save state, fail loudly."""


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
    try:
        resp = client.messages.create(model=MODEL, max_tokens=800,
                                      messages=[{"role": "user", "content": prompt}])
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        raise FatalAPIError(str(exc)) from exc
    except anthropic.BadRequestError as exc:
        if "credit" in str(exc).lower() or "billing" in str(exc).lower():
            raise FatalAPIError(str(exc)) from exc
        print(f"[warn] API rejected {item['id']}: {exc}", file=sys.stderr)
        return None
    except anthropic.APIError as exc:  # transient (rate limit, overload, 5xx)
        print(f"[warn] API error for {item['id']}: {exc}", file=sys.stderr)
        time.sleep(10)
        return None
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

    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else []
    known_ids = {r["id"] for r in results}
    to_score = [i for i in items
                if i["id"] not in known_ids
                and (i.get("source_id") == "discovery"  # query already selected
                     or PREFILTER.search(f"{i['title']} {i.get('snippet','')}"))]
    print(f"[prefilter] {len(items)} new -> {len(to_score)} to score")

    client = None
    rubric = (ROOT / "RUBRIC.md").read_text()
    project = (ROOT / "context" / "project.md").read_text()
    n_hit = n_low = n_filtered = 0

    fatal = None
    remaining = list(items)
    for item in items:
        remaining.remove(item)
        if item["id"] in known_ids:
            continue
        rec = {
            "id": item["id"], "title": item["title"], "url": item["url"],
            "source": item["source_name"], "type": item["type"],
            "scores": {}, "total": 0, "deadline": None,
            "summary": "", "rationale": "", "stage": "filtered",
            "status": "fetched", "found_at": item["seen_at"], "proposal": None,
        }
        if item in to_score:
            if client is None:
                client = Anthropic()  # reads ANTHROPIC_API_KEY
            try:
                verdict = score_item(client, rubric, project, item)
            except FatalAPIError as exc:
                fatal = str(exc)
                remaining.insert(0, item)  # this one wasn't scored — requeue it
                break
            time.sleep(1)  # be polite to the API and target sites
            if verdict is None:
                rec["stage"] = "error"
            else:
                total = int(verdict.get("total") or
                            sum(verdict.get("scores", {}).values()))
                rec.update(stage="scored",
                           type=verdict.get("kind", item["type"]),
                           scores=verdict.get("scores", {}), total=total,
                           deadline=verdict.get("deadline"),
                           summary=verdict.get("summary", ""),
                           rationale=verdict.get("rationale", ""))
                if verdict.get("relevant") and total >= MIN_TOTAL:
                    rec["status"] = "new"
                    n_hit += 1
                    print(f"[hit {total:2d}] {item['title'][:70]}")
                else:
                    n_low += 1
                    print(f"[scored {total:2d}] {item['title'][:70]}")
        else:
            n_filtered += 1
        results.append(rec)
        known_ids.add(item["id"])

    results.sort(key=lambda r: (-r.get("found_at", 0), -r.get("total", 0)))
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    NEW_ITEMS.write_text(json.dumps(remaining, indent=2, ensure_ascii=False))
    print(f"[done] recorded {n_hit + n_low + n_filtered} "
          f"(hits {n_hit}, low {n_low}, filtered {n_filtered}) "
          f"-> {RESULTS.relative_to(ROOT)} ({len(results)} total)")
    if fatal:
        print(f"\n[FATAL] scoring stopped: {fatal}\n"
              f"Progress saved; {len(remaining)} items remain queued in "
              f"data/new_items.json and will be scored on the next run "
              f"(no need to re-backfill).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
