# decolonial.ist — opportunity monitor

A zero-server pipeline that watches conference CFPs, media, and funding sources,
scores new items with Claude Haiku against `RUBRIC.md`, stores results in-repo
(`data/results.json`), and serves a triage UI from `/docs` via GitHub Pages.
A **Build the proposal** button in the UI dispatches a workflow that drafts a
submission-ready document with Claude Sonnet into `/proposals`.

```
.
├── .github/workflows/
│   ├── monitor.yml           # daily: fetch → diff → prefilter → Haiku scoring → commit
│   └── build-proposal.yml    # workflow_dispatch: Sonnet drafts a proposal → commit
├── scripts/
│   ├── watch.py              # fetch sources, diff against data/snapshots/
│   ├── score.py              # keyword prefilter + Haiku scoring per RUBRIC.md
│   └── build_proposal.py     # live-fetch guidelines + /context → proposal draft
├── context/                  # everything Sonnet knows about the project
│   ├── project.md            # mission, matrix explainer, boilerplate
│   ├── team.md               # bios
│   └── exemplars/            # your best past proposals (best ROI in the repo)
├── data/
│   ├── results.json          # THE table (versioned database)
│   └── snapshots/            # per-source seen-item state
├── proposals/                # generated drafts (Markdown, human-edited before submission)
├── docs/index.html           # static UI (GitHub Pages)
├── sources.yaml              # what to watch
└── RUBRIC.md                 # scoring rubric (edit this to tune the classifier)
```

## Setup (once)

1. **Create the repo** (public, under your org) and push this tree.
2. **Secret:** repo → Settings → Secrets and variables → Actions →
   `ANTHROPIC_API_KEY`.
3. **Pages:** Settings → Pages → Deploy from branch → `main` / `/docs`.
4. **Workflow permissions:** Settings → Actions → General → Workflow
   permissions → "Read and write permissions".
5. **PAT for the UI button** (each collaborator, once): create a
   *fine-grained* personal access token scoped to **this repo only** with
   permissions **Actions: Read and write** and **Contents: Read and write**.
   Paste it into the UI's Settings panel; it is stored in your browser's
   localStorage only and sent only to `api.github.com`.
6. Open the UI, set `owner/repo` in Settings.

## Daily flow

- `monitor.yml` runs at 06:23 UTC (plus manual runs from the Actions tab).
  New relevant items appear in the UI with status `new`.
- Triage in the UI: change status (`shortlisted`, `pitched`, `submitted`,
  `rejected`, `won`, `dismissed`) — each change is a commit.
- Click **Build the proposal** on a shortlisted item → edit the draft in
  `/proposals` → submit it yourself.

## Tuning

- Relevance quality lives in `RUBRIC.md` and `context/project.md`, not in code.
- Add sources in `sources.yaml` (RSS preferred; HTML link-scrape supported).
- Score threshold: `MIN_TOTAL` env in `monitor.yml` (default 12 of 25).
- Add every submitted proposal to `context/exemplars/` — generation quality
  compounds with each one.

## Notes

- Public repo ⇒ unlimited Actions minutes, free Pages. If you make it private,
  Pages requires a paid plan and your target list becomes non-public — see the
  tradeoff discussion in your notes.
- Scheduled runs on GitHub can lag 10–30 min; irrelevant at daily cadence.
- The monitor's own commits keep the repo "active", so the 60-day scheduled
  workflow auto-disable never triggers.
