# decolonial.ist — opportunity monitor

Zero-server pipeline that finds conference CFPs, funding calls, and media
pitch windows for DECOLONIAL.IST, scores them with Claude against RUBRIC.md,
stores everything in-repo, and serves a triage UI from /docs via GitHub Pages.

## How it finds things — two engines
1. **Watchers** (`scripts/watch.py` + `sources.yaml`): tripwires on ~38 known
   pages (aggregators, foundations, associations). Daily. "New" = appeared
   since the last run (diff vs `data/snapshots/`).
2. **Web discovery** (`scripts/discover.py` + `queries.yaml`): searches the
   open web via Claude's web-search tool with a multilingual query battery
   (EN/UK/RU/DE/FR). Mondays automatically, or on demand.

Both feed `scripts/score.py`: keyword prefilter (multilingual; discovery
items skip it) → Claude Haiku scores 5 dimensions per RUBRIC.md → EVERY item
is recorded in `data/results.json` with a `stage` (filtered / scored / error)
and `status` (new / fetched / shortlisted / drafted / pitched / submitted /
won / rejected / dismissed). Nothing fetched is ever silently discarded.

## Daily use
- UI: https://yudanin.github.io/decolonialist-monitor/ — filters, pagination,
  per-row Delete, status commits, **Run scan** (diff-only), **Build the
  proposal** (drafts via Claude Sonnet into `/proposals`).
- Actions → monitor → Run workflow: tick **backfill** to score sources'
  current contents (delete a snapshot first to replay a source); tick
  **discover** to run the search battery now.
- Git habit: this repo has three writers (you, monitor-bot, the UI).
  `git pull` before editing and before pushing. `data/` is the bots' lane.

## Tuning
- What counts as relevant → `RUBRIC.md` (+ worked examples = calibration).
- What the model knows about the project → `context/project.md`.
- Where to look → `sources.yaml` (pages) and `queries.yaml` (searches).
- Proposal quality → `context/team.md` (fill the TODO!) and
  `context/exemplars/` (add every submitted proposal).
- Threshold → MIN_TOTAL env in monitor.yml (default 12).

## Setup (already done for this deployment)
Secrets: ANTHROPIC_API_KEY. Pages: main /docs. Workflow permissions:
read+write. UI Settings: owner/repo/branch + fine-grained PAT (Contents RW +
Actions RW on this repo only).
