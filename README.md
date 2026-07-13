# Tamil Cinema YouTube Radar

A Streamlit dashboard that discovers recent Tamil films and monitors public YouTube review videos and comments every 30 minutes.

## What it tracks

- recent Tamil releases and posters from TMDB
- selected Tamil cinema review channels and relevant public-review videos
- public video views, likes and comment totals as timestamped snapshots
- recent top-level comments through the official YouTube Data API
- an open-source `youtube-comment-downloader` fallback when API comment retrieval is unavailable
- language mix, discussion topics, questions, participation depth and low-information filtering
- comment arrival, film momentum, view velocity and comment velocity over time

The dashboard deliberately does not calculate a film-quality or sentiment score.

## Collection schedule

The GitHub workflow runs at **:10 and :40 UTC every hour**. To stay within the standard YouTube quota:

- known videos, statistics and recent comments refresh every 30 minutes
- searches for newly published review videos run every six hours
- up to four active videos per film are monitored each cycle
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

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run one scan with:

```bash
python scanner.py
```

## Processing method

The transparent processing layer:

- distinguishes Tamil script, Tanglish, mixed Tamil-English and English/other
- labels story, acting, direction, music, visuals, pacing, comedy, emotion and release discussion
- separates questions, detailed discussion, short opinions and quick reactions
- filters extremely short, link-promotional and non-text reactions from analytical plots
- retains source links and raw public comment text for verification

## Responsible use

Counts describe the collected public sample. They are not unique viewers, representative polling, box-office estimates or objective film ratings.
