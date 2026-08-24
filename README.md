# Tamil Cinema YouTube Radar

A dashboard that discovers recent Tamil films and monitors public YouTube review videos and comments every 30 minutes.

## What it tracks

- recent Tamil releases and posters from TMDB
- selected Tamil cinema review channels and relevant public-review videos
- public video views, likes and comment totals as timestamped snapshots
- recent top-level comments through the official YouTube Data API
- an open-source `youtube-comment-downloader` fallback when API comment retrieval is unavailable
- language mix, discussion topics, questions, participation depth and low-information filtering
- comment arrival, film momentum, view velocity and comment velocity over time

The dashboard deliberately does not calculate a film-quality or sentiment score.

## Architecture

Three independent pieces, each doing one job:

- **Collector** (`scanner.py`, `collectors.py`, `youtube_analysis.py`) — a Python script run on a GitHub Actions
  schedule. It talks to the TMDB and YouTube Data APIs, enriches and dedupes what it finds, and commits the result
  straight to `data/live/*.csv` and `data/live/scan_metadata.json`. This is the only piece with API keys or write
  access; it has no knowledge of how the data is displayed.
- **API** (`server/`) — a small Node/Express + TypeScript service that reads those CSVs, derives the dashboard's
  insights (momentum, evidence strength, comment composition, arrival patterns, channel rankings, etc.) and serves
  them as JSON. It re-reads a file only when its mtime changes, so it stays cheap to run continuously.
- **Dashboard** (`web/`) — a React + TypeScript + Tailwind single-page app (built with Vite) that renders the API's
  output. In production the API server also serves the built frontend, so the whole thing is one deployable Node
  process pointed at `PORT`.

The raw CSVs and `scan_metadata.json` stay the source of truth and are still readable directly — from a clone, from
GitHub's file viewer, or via `https://raw.githubusercontent.com/purushothaman-98/cinema-wall/main/data/live/…` — independent of whether the API/dashboard are running.

## Collection schedule

The GitHub workflow runs at **:10 and :40 UTC every hour**. To stay within the standard YouTube quota:

- known videos, statistics and recent comments refresh every 30 minutes
- searches for newly published review videos and Shorts run once every 24 hours
- up to four standard videos and three Shorts per film are monitored each cycle
- 30-minute view-growth charts show only the change between the two latest snapshots, with standard videos and Shorts shown separately
- every fetched 30-minute counter snapshot is retained without dashboard filters; relevance ranking is applied only during the daily discovery pass
- lifetime analysis separates current public YouTube totals from growth actually observed after monitoring began
- raw snapshots, the derived 30-minute time series, comments and scan metadata are always readable straight from `data/live/` (see Architecture)
- the dashboard separates every historically analyzed film ("Historical") from films actively monitored on the current radar ("On radar")
- live scans request the newest 50 top-level comments per video; the daily discovery/backfill requests up to 500, while YouTube's public counter can also include comments not individually retrievable by the collector
- counter gaps outside 20–70 minutes remain visible as fetch coverage but are excluded from half-hour growth charts
- stored records are deduplicated and retained for up to 730 days

GitHub may delay scheduled jobs slightly during periods of high Actions load.

## Required secrets

Add these under **Repository → Settings → Secrets and variables → Actions**:

```text
TMDB_API_KEY
YOUTUBE_API_KEY
```

Do not commit real keys.

## Run locally

Collector (needs `TMDB_API_KEY` and `YOUTUBE_API_KEY` in the environment; writes into `data/live/`):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scanner.py
```

API + dashboard, as two dev processes:

```bash
cd server && npm install && npm run dev     # http://localhost:4000
cd web && npm install && npm run dev        # http://localhost:5173 (proxies /api to :4000)
```

Or as one production build served by the API alone:

```bash
cd web && npm install && npm run build      # writes web/dist
cd ../server && npm install && npm run build && npm start   # http://localhost:4000
```

The dashboard reads only what's already in `data/live/` — it never calls TMDB or YouTube itself, so it works fine
even without either API key, as long as the collector has run at least once (locally or via the GitHub workflow).

## Processing method

The transparent processing layer:

- distinguishes Tamil script, Tanglish, mixed Tamil-English and English/other
- labels story, acting, direction, music, visuals, pacing, comedy, emotion and release discussion
- separates questions, detailed discussion, short opinions and quick reactions
- filters extremely short, link-promotional and non-text reactions from analytical plots
- retains source links and raw public comment text for verification

## Responsible use

Counts describe the collected public sample. They are not unique viewers, representative polling, box-office estimates or objective film ratings.
