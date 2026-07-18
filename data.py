from __future__ import annotations

import json
import re
from pathlib import Path
import pandas as pd
import requests

from youtube_analysis import enrich_comments

ROOT = Path(__file__).parent
LIVE_FILE = ROOT / "data" / "live" / "comments.csv"
META_FILE = ROOT / "data" / "live" / "scan_metadata.json"
VIDEO_FILE = ROOT / "data" / "live" / "video_snapshots.csv"
RAW_ROOT = "https://raw.githubusercontent.com/purushothaman-98/cinema-wall/main/data/live"

def _format_from_duration(duration: object, title: object) -> str:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(duration or ""))
    seconds = 0
    if match:
        hours, minutes, secs = (int(part or 0) for part in match.groups())
        seconds = hours * 3600 + minutes * 60 + secs
    lowered = str(title or "").lower()
    return "Short" if (0 < seconds <= 60 or "#shorts" in lowered or "#short" in lowered) else "Video"

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
    frame["created_at"] = pd.to_datetime(frame.get("created_at"), format="mixed", errors="coerce", utc=True)
    frame["scanned_at"] = pd.to_datetime(frame.get("scanned_at"), format="mixed", errors="coerce", utc=True)
    frame["likes"] = pd.to_numeric(frame["likes"], errors="coerce").fillna(0) if "likes" in frame else 0
    frame["reply_count"] = pd.to_numeric(frame["reply_count"], errors="coerce").fillna(0) if "reply_count" in frame else 0
    if "channel" not in frame:
        frame["channel"] = frame["source"] if "source" in frame else "Unknown"
    if "video_id" not in frame:
        frame["video_id"] = frame["parent_id"] if "parent_id" in frame else ""
    if "video_title" not in frame:
        frame["video_title"] = ""
    if "content_format" not in frame:
        frame["content_format"] = "Unknown"
    frame["content_format"] = frame["content_format"].fillna("Unknown")
    if "source_category" not in frame:
        frame["source_category"] = "open_youtube"
    if "video_intent" not in frame:
        frame["video_intent"] = "film_discussion"
    frame["source_category"] = frame["source_category"].fillna("open_youtube")
    frame["video_intent"] = frame["video_intent"].fillna("film_discussion")
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
    frame["scanned_at"] = pd.to_datetime(frame.get("scanned_at"), format="mixed", errors="coerce", utc=True)
    frame["published_at"] = pd.to_datetime(frame.get("published_at"), format="mixed", errors="coerce", utc=True)
    for column in ("views", "likes", "comments", "signal_score"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0) if column in frame else 0
    inferred_format = frame.apply(
        lambda row: _format_from_duration(row.get("duration"), row.get("title")), axis=1
    )
    if "content_format" not in frame:
        frame["content_format"] = inferred_format
    else:
        frame["content_format"] = frame["content_format"].astype("object")
        missing_format = frame["content_format"].isna() | ~frame["content_format"].isin(["Video", "Short"])
        frame.loc[missing_format, "content_format"] = inferred_format[missing_format]
    if "description" not in frame:
        frame["description"] = ""
    frame["description"] = frame["description"].fillna("").replace({"nan": "", "None": ""})
    for column, default in {
        "source_category": "open_youtube",
        "source_profile": "Open YouTube",
        "video_intent": "film_discussion",
        "review_evidence": True,
    }.items():
        if column not in frame:
            frame[column] = default
        else:
            frame[column] = frame[column].fillna(default)
    if "thumbnail_url" not in frame:
        frame["thumbnail_url"] = ""
    frame["thumbnail_url"] = frame["thumbnail_url"].fillna("")
    missing_thumbnail = ~frame["thumbnail_url"].astype(str).str.startswith("http")
    frame.loc[missing_thumbnail, "thumbnail_url"] = (
        "https://i.ytimg.com/vi/" + frame.loc[missing_thumbnail, "video_id"].astype(str) + "/hqdefault.jpg"
    )
    frame = frame.dropna(subset=["video_id", "film", "scanned_at"])
    return frame
