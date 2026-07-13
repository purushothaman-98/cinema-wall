from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import requests
from sentiment import add_sentiment

ROOT = Path(__file__).parent
LIVE_FILE = ROOT / "data" / "live" / "comments.csv"
META_FILE = ROOT / "data" / "live" / "scan_metadata.json"
RAW_ROOT = "https://raw.githubusercontent.com/purushothaman-98/cinema-wall/main/data/live"
VIDEO_FILE = ROOT / "data" / "live" / "video_snapshots.csv"


def load_live() -> pd.DataFrame:
    try:
        frame = pd.read_csv(LIVE_FILE if LIVE_FILE.exists() else f"{RAW_ROOT}/comments.csv")
    except Exception:
        return pd.DataFrame()
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
    frame["scanned_at"] = pd.to_datetime(frame.get("scanned_at"), errors="coerce", utc=True)
    frame["likes"] = pd.to_numeric(frame.get("likes", 0), errors="coerce").fillna(0)
    frame = frame.dropna(subset=["film", "platform", "text"])
    return add_sentiment(frame)


def load_metadata() -> dict:
    try:
        if META_FILE.exists():
            return json.loads(META_FILE.read_text(encoding="utf-8"))
        response = requests.get(f"{RAW_ROOT}/scan_metadata.json", timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"status": "waiting", "last_scan": None, "films": 0, "comments": 0}


def load_video_snapshots() -> pd.DataFrame:
    try:
        frame = pd.read_csv(VIDEO_FILE if VIDEO_FILE.exists() else f"{RAW_ROOT}/video_snapshots.csv")
    except Exception:
        return pd.DataFrame()
    frame["scanned_at"] = pd.to_datetime(frame["scanned_at"], errors="coerce", utc=True)
    frame["published_at"] = pd.to_datetime(frame["published_at"], errors="coerce", utc=True)
    for column in ("views", "likes", "comments", "signal_score"):
        frame[column] = pd.to_numeric(frame.get(column, 0), errors="coerce").fillna(0)
    return frame


def aggregate(frame: pd.DataFrame) -> pd.DataFrame:
    useful = frame[~frame["low_information"]].copy()
    useful["weighted_score"] = useful.sentiment_score * useful.analysis_weight
    grouped = useful.groupby("film")
    current = grouped.agg(
        weighted_sum=("weighted_score", "sum"), weight_sum=("analysis_weight", "sum"), mentions=("text", "size"),
        positive=("sentiment", lambda s: (s == "Positive").mean() * 100),
        neutral=("sentiment", lambda s: (s == "Neutral").mean() * 100),
        negative=("sentiment", lambda s: (s == "Negative").mean() * 100),
        last_seen=("created_at", "max"), last_scanned=("scanned_at", "max"),
    ).reset_index()
    current["score"] = current.weighted_sum / current.weight_sum.clip(lower=.01)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
    previous_start = cutoff - pd.Timedelta(days=7)
    this_week = frame[frame.created_at >= cutoff].groupby("film").sentiment_score.mean()
    last_week = frame[(frame.created_at >= previous_start) & (frame.created_at < cutoff)].groupby("film").sentiment_score.mean()
    current["weekly_change"] = current.film.map(this_week).sub(current.film.map(last_week)).fillna(0)
    return current.sort_values(["score", "mentions"], ascending=False).reset_index(drop=True)
