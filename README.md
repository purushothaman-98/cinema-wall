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

The included scorer is a transparent baseline designed for Tamil-cinema vocabulary. It handles common English, Tamil and Tanglish expressions, negation, repeated emphasis and emoji. It is suitable for an MVP and research inspection, but not presented as a definitive opinion poll. For publication-grade results, validate it on a manually labelled Tamil/Tanglish corpus and replace or ensemble it with a fine-tuned multilingual transformer.

## Deploy

Push the repository to GitHub, create an app at [Streamlit Community Cloud](https://streamlit.io/cloud), select `app.py`, and add credentials through the deployment secrets panel. Never commit real keys.

## Responsible use

Only public comments are collected. The dashboard reports aggregate conversation patterns, not box-office performance or objective film quality.
