#!/usr/bin/env python3
"""Draft a submission-ready proposal for one entity in data/results.json.

Usage: build_proposal.py --entity-id ID [--proposal-type auto|conference|funding|media]
                         [--instructions "extra guidance"]

Fetches the opportunity's live page (real requirements, word limits, criteria),
loads everything in /context (project, team, exemplars), and asks Claude Sonnet
for a draft. Writes proposals/<id>-<date>.md and marks the record "drafted".
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests
from anthropic import Anthropic
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results.json"
MODEL = os.environ.get("PROPOSAL_MODEL", "claude-sonnet-4-6")
UA = {"User-Agent": "decolonialist-monitor/1.0 (+https://decolonial.ist)"}


def page_text(url: str, limit: int = 15000) -> str:
    try:
        r = requests.get(url, headers=UA, timeout=45)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style"]):
            t.decompose()
        return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:limit]
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] fetch {url}: {exc}", file=sys.stderr)
        return "(live page could not be fetched — draft from the record only, "\
               "and list what must be verified manually)"


def load_context() -> str:
    parts = []
    for p in sorted((ROOT / "context").rglob("*.md")):
        if p.name == "README.md":
            continue
        parts.append(f"<file name='{p.relative_to(ROOT)}'>\n{p.read_text()}\n</file>")
    return "\n\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entity-id", required=True)
    ap.add_argument("--proposal-type", default="auto")
    ap.add_argument("--instructions", default="")
    args = ap.parse_args()

    results = json.loads(RESULTS.read_text())
    rec = next((r for r in results if r["id"] == args.entity_id), None)
    if rec is None:
        print(f"[error] no entity {args.entity_id} in results.json", file=sys.stderr)
        return 1

    ptype = rec["type"] if args.proposal_type == "auto" else args.proposal_type
    live = page_text(rec["url"])
    context = load_context()

    prompt = f"""You are drafting on behalf of DECOLONIAL.IST, using the project
context files below. Draft a **{ptype}** submission for the opportunity below.

<project_context>
{context}
</project_context>

<opportunity_record>
{json.dumps(rec, indent=2, ensure_ascii=False)}
</opportunity_record>

<live_page_text>
{live}
</live_page_text>

<extra_instructions>{args.instructions or "(none)"}</extra_instructions>

Requirements:
1. Mirror the opportunity's OWN structure and constraints from the live page:
   required sections, word/character limits, evaluation criteria, formats.
   If the page states a limit, obey it exactly and note it in a comment.
2. conference → abstract (at stated length; default 300 words), title options
   (3), speaker bio (100w), A/V or format needs, and a one-paragraph "why this
   venue" note for internal use.
3. funding → concept note: summary, problem, objectives, activities, outcomes
   & indicators, timeline, team, budget sketch (line items with realistic EUR
   ranges), sustainability, and an eligibility checklist marking anything
   uncertain with ⚠ TODO.
4. media → pitch email (150-250w), three angle options, suggested artifacts
   (matrix screenshots, technique pages), and a short Q&A prep list.
5. Ground every claim in the context files; NEVER invent partnerships, staff,
   registration status, publications, or numbers. Anything unknown becomes
   ⚠ TODO with a note on who/what can resolve it.
6. Write in the opportunity's language if clearly not English; otherwise
   English. Use British spelling for European funders.
7. Begin with a metadata block: opportunity, deadline, submission URL/route,
   estimated effort, and the top 3 things the human editor must fix.

Output pure Markdown, no preamble."""

    client = Anthropic()
    resp = client.messages.create(model=MODEL, max_tokens=8000,
                                  messages=[{"role": "user", "content": prompt}])
    draft = "".join(b.text for b in resp.content if b.type == "text")

    out = ROOT / "proposals" / f"{rec['id']}-{dt.date.today().isoformat()}.md"
    out.parent.mkdir(exist_ok=True)
    header = (f"---\nentity: {rec['id']}\ntitle: \"{rec['title']}\"\n"
              f"type: {ptype}\ngenerated: {dt.datetime.now(dt.timezone.utc).isoformat()}\n"
              f"model: {MODEL}\nstatus: draft — HUMAN REVIEW REQUIRED\n---\n\n")
    out.write_text(header + draft)

    rec["status"] = "drafted"
    rec["proposal"] = str(out.relative_to(ROOT))
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[done] {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
