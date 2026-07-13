from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import requests

from youtube_analysis import enrich_comments

ROOT = Path(__file__).parent
LIVE_FILE = ROOT / "data" / "live" / "comments.csv"
META_FILE = ROOT / "data" / "live" / "scan_metadata.json"
VIDEO_FILE = ROOT / "data" / "live" / "video_snapshots.csv"
RAW_ROOT = "https://raw.githubusercontent.com/purushothaman-98/cinema-wall/main/data/live"

def _csv(local: Path, remote_name: str) -> pd.DataFrame:
    try:
        return pd.read_csv(local if local.exists() else f"{RAW_ROOT}/{remote_name}")
    except Exception:
        return pd.DataFrame()

def load_live() -> pd.DataFrame:
    frame = _csv(LIVE_FILE, "comments.csv")
    if frame.empty:
        return frame
    if "platform" in frame:
        frame = frame[frame["platform"].eq("YouTube")].copy()
    frame["created_at"] = pd.to_datetime(frame.get("created_at"), errors="coerce", utc=True)
    frame["scanned_at"] = pd.to_datetime(frame.get("scanned_at"), errors="coerce", utc=True)
    frame["likes"] = pd.to_numeric(frame.get("likes", 0), errors="coerce").fillna(0)
    frame["reply_count"] = pd.to_numeric(frame.get("reply_count", 0), errors="coerce").fillna(0)
    frame = frame.dropna(subset=["film", "text", "created_at"])
    return enrich_comments(frame)

def load_metadata() -> dict:
    try:
        if META_FILE.exists():
            return json.loads(META_FILE.read_text(encoding="utf-8"))
        response = requests.get(f"{RAW_ROOT}/scan_metadata.json", timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"status": "waiting", "last_scan": None, "films": [], "errors": []}

def load_video_snapshots() -> pd.DataFrame:
    frame = _csv(VIDEO_FILE, "video_snapshots.csv")
    if frame.empty:
        return frame
    frame["scanned_at"] = pd.to_datetime(frame.get("scanned_at"), errors="coerce", utc=True)
    frame["published_at"] = pd.to_datetime(frame.get("published_at"), errors="coerce", utc=True)
    for column in ("views", "likes", "comments", "signal_score"):
        frame[column] = pd.to_numeric(frame.get(column, 0), errors="coerce").fillna(0)
    frame = frame.dropna(subset=["video_id", "film", "scanned_at"])
    return frame
