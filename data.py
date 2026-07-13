from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
LIVE_FILE = ROOT / "data" / "live" / "comments.csv"
META_FILE = ROOT / "data" / "live" / "scan_metadata.json"
VIDEO_FILE = ROOT / "data" / "live" / "video_snapshots.csv"


def load_live() -> pd.DataFrame:
    if not LIVE_FILE.exists():
        return pd.DataFrame()
    frame = pd.read_csv(LIVE_FILE)
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
    frame["scanned_at"] = pd.to_datetime(frame.get("scanned_at"), errors="coerce", utc=True)
    frame["likes"] = pd.to_numeric(frame.get("likes", 0), errors="coerce").fillna(0)
    return frame.dropna(subset=["film", "platform", "text"])


def load_metadata() -> dict:
    if not META_FILE.exists():
        return {"status": "waiting", "last_scan": None, "next_scan": None, "films": 0, "comments": 0}
    return json.loads(META_FILE.read_text(encoding="utf-8"))


def load_video_snapshots() -> pd.DataFrame:
    if not VIDEO_FILE.exists():
        return pd.DataFrame()
    frame = pd.read_csv(VIDEO_FILE)
    frame["scanned_at"] = pd.to_datetime(frame["scanned_at"], errors="coerce", utc=True)
    frame["published_at"] = pd.to_datetime(frame["published_at"], errors="coerce", utc=True)
    for column in ("views", "likes", "comments", "signal_score"):
        frame[column] = pd.to_numeric(frame.get(column, 0), errors="coerce").fillna(0)
    return frame


def aggregate(frame: pd.DataFrame) -> pd.DataFrame:
    current = frame.groupby("film", as_index=False).agg(
        score=("sentiment_score", "mean"), mentions=("text", "size"),
        positive=("sentiment", lambda s: (s == "Positive").mean() * 100),
        neutral=("sentiment", lambda s: (s == "Neutral").mean() * 100),
        negative=("sentiment", lambda s: (s == "Negative").mean() * 100),
        last_seen=("created_at", "max"), last_scanned=("scanned_at", "max"),
    )
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
    previous_start = cutoff - pd.Timedelta(days=7)
    this_week = frame[frame.created_at >= cutoff].groupby("film").sentiment_score.mean()
    last_week = frame[(frame.created_at >= previous_start) & (frame.created_at < cutoff)].groupby("film").sentiment_score.mean()
    current["weekly_change"] = current.film.map(this_week).sub(current.film.map(last_week)).fillna(0)
    return current.sort_values(["score", "mentions"], ascending=False).reset_index(drop=True)
