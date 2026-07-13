# Tamil Film Pulse

An automated Streamlit wall that discovers recent Tamil films and refreshes public YouTube and Reddit sentiment every day.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The dashboard reads the timestamped dataset produced by the scheduled scanner.

## Weekly scanner

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and add credentials:

```toml
TMDB_API_KEY = "..."
YOUTUBE_API_KEY = "..."
```

Add the two values as GitHub Actions repository secrets. The daily workflow discovers recent Tamil releases through TMDb, prioritizes selected review channels, removes promotional videos, reads YouTube comments through the official API, and scans configured public Reddit `.json` listings without OAuth. It stores video-counter snapshots so day/week/month/year view growth becomes available over time.

Public Reddit JSON is intentionally treated as best-effort: cloud requests can be throttled or blocked. The scanner records partial failures instead of inventing missing data.

## Sentiment method

The analysis layer detects Tamil script, Tanglish and mixed Tamil-English comments; normalizes spelling emphasis; handles local cinema slang, negation, intensifiers and emoji; scores confidence; suppresses low-information comments; caps engagement weighting; and calculates aspect sentiment for story, acting, direction, music, visuals, pacing, comedy and emotion. This transparent hybrid is lightweight enough for free hosting. For publication-grade results, validate it against a manually labelled Tamil/Tanglish set before adding a fine-tuned MuRIL, IndicBERT or TamilBERT classifier.

## Deploy

Push the repository to GitHub, create an app at [Streamlit Community Cloud](https://streamlit.io/cloud), select `app.py`, and add credentials through the deployment secrets panel. Never commit real keys.

## Responsible use

Only public comments are collected. The dashboard reports aggregate conversation patterns, not box-office performance or objective film quality.
