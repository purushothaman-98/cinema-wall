# Tamil Film Pulse

An open-source Streamlit dashboard for comparing public sentiment around Tamil films across YouTube and Reddit. It supports Tamil, Tanglish and English comments, platform comparison, topic analysis, CSV uploads and optional live collection.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The application starts with clearly labelled demonstration data. Upload your own CSV from the sidebar or configure API credentials for collection.

## CSV format

Required columns:

| Column | Description |
|---|---|
| `film` | Film title |
| `platform` | `YouTube` or `Reddit` |
| `text` | Public comment text |

Optional columns: `created_at`, `likes`, `url`, and `author`.

## Live collectors

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and add credentials:

```toml
YOUTUBE_API_KEY = "..."
REDDIT_CLIENT_ID = "..."
REDDIT_CLIENT_SECRET = "..."
REDDIT_USER_AGENT = "tamil-film-pulse/1.0 by your_username"
```

The YouTube collector uses the official YouTube Data API. The Reddit collector uses PRAW and OAuth. API limits and platform terms still apply.

## Sentiment method

The included scorer is a transparent baseline designed for Tamil-cinema vocabulary. It handles common English, Tamil and Tanglish expressions, negation, repeated emphasis and emoji. It is suitable for an MVP and research inspection, but not presented as a definitive opinion poll. For publication-grade results, validate it on a manually labelled Tamil/Tanglish corpus and replace or ensemble it with a fine-tuned multilingual transformer.

## Deploy

Push the repository to GitHub, create an app at [Streamlit Community Cloud](https://streamlit.io/cloud), select `app.py`, and add credentials through the deployment secrets panel. Never commit real keys.

## Responsible use

Only public comments are collected. The dashboard reports aggregate conversation patterns, not box-office performance or objective film quality. Demo data is explicitly marked in the interface.
