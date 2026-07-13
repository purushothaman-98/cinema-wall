"""Weekly Tamil-film discovery and public-comment scanner."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import requests

from collectors import collect_reddit, collect_youtube
from sentiment import add_sentiment

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "scanner_config.json").read_text())
LIVE_DIR = ROOT / "data" / "live"
LIVE_FILE = LIVE_DIR / "comments.csv"
META_FILE = LIVE_DIR / "scan_metadata.json"


def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def discover_films(tmdb_key: str) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=CONFIG["lookback_days"])
    response = requests.get(
        "https://api.themoviedb.org/3/discover/movie",
        params={"api_key": tmdb_key, "with_original_language": "ta", "region": "IN",
                "release_date.gte": start.isoformat(), "release_date.lte": today.isoformat(),
                "sort_by": "popularity.desc", "include_adult": "false", "page": 1}, timeout=30,
    )
    response.raise_for_status()
    films = [{"title": item["title"], "release_date": item.get("release_date", ""), "tmdb_id": item["id"]}
             for item in response.json().get("results", [])[:CONFIG["max_films"]]]
    for title in CONFIG.get("manual_films", []):
        if title and title not in {film["title"] for film in films}:
            films.append({"title": title, "release_date": "", "tmdb_id": None})
    return films


def youtube_video_ids(title: str, api_key: str) -> list[str]:
    response = requests.get("https://www.googleapis.com/youtube/v3/search", params={
        "key": api_key, "part": "snippet", "type": "video", "maxResults": CONFIG["youtube_videos_per_film"],
        "q": f'{title} Tamil movie review', "relevanceLanguage": "ta", "regionCode": "IN", "order": "relevance"
    }, timeout=30)
    response.raise_for_status()
    return [item["id"]["videoId"] for item in response.json().get("items", [])]


def stable_id(row) -> str:
    existing = str(row.get("source_id", "")).strip()
    if existing and existing != "nan":
        return f'{row.get("platform", "unknown")}:{existing}'
    raw = f'{row.get("film", "")}|{row.get("platform", "")}|{row.get("text", "")}'
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def main():
    youtube_key = require("YOUTUBE_API_KEY")
    films = discover_films(require("TMDB_API_KEY"))
    reddit = {"client_id": require("REDDIT_CLIENT_ID"), "client_secret": require("REDDIT_CLIENT_SECRET"),
              "user_agent": require("REDDIT_USER_AGENT")}
    scanned_at = datetime.now(timezone.utc)
    batches, errors = [], []
    for film in films:
        title = film["title"]
        try:
            ids = youtube_video_ids(title, youtube_key)
            if ids:
                batches.append(collect_youtube(ids, youtube_key, title, CONFIG["comments_per_platform"]))
        except Exception as exc:
            errors.append(f"YouTube/{title}: {exc}")
        try:
            batches.append(collect_reddit(f'{title} {CONFIG["reddit_query_suffix"]}', title,
                           reddit["client_id"], reddit["client_secret"], reddit["user_agent"], CONFIG["comments_per_platform"]))
        except Exception as exc:
            errors.append(f"Reddit/{title}: {exc}")
    fresh = pd.concat([batch for batch in batches if not batch.empty], ignore_index=True) if batches else pd.DataFrame()
    if fresh.empty:
        raise RuntimeError("The scan returned no comments. " + "; ".join(errors))
    fresh["scanned_at"] = scanned_at.isoformat()
    fresh["source_id"] = fresh.apply(stable_id, axis=1)
    combined = pd.concat([pd.read_csv(LIVE_FILE), fresh], ignore_index=True) if LIVE_FILE.exists() else fresh
    combined["created_at"] = pd.to_datetime(combined.created_at, errors="coerce", utc=True)
    combined = combined[combined.created_at >= scanned_at - timedelta(days=CONFIG["keep_history_days"])]
    combined = combined.drop_duplicates("source_id", keep="last")
    combined = add_sentiment(combined).sort_values("created_at", ascending=False)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(LIVE_FILE, index=False)
    META_FILE.write_text(json.dumps({"status": "healthy" if not errors else "partial", "last_scan": scanned_at.isoformat(),
        "next_scan": (scanned_at + timedelta(days=7)).isoformat(), "films": len(films), "comments": len(combined),
        "discovered_films": films, "errors": errors}, indent=2), encoding="utf-8")
    print(f"Saved {len(combined)} comments across {len(films)} films; {len(errors)} source errors")


if __name__ == "__main__":
    main()
