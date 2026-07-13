"""Quota-aware YouTube monitor for recent Tamil films."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import re
from pathlib import Path

import pandas as pd
import requests

from collectors import youtube_comments, youtube_details, youtube_search
from youtube_analysis import enrich_comments

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "scanner_config.json").read_text(encoding="utf-8"))
LIVE = ROOT / "data" / "live"
COMMENTS = LIVE / "comments.csv"
VIDEOS = LIVE / "video_snapshots.csv"
META = LIVE / "scan_metadata.json"

def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value

def discover_films(key: str) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=CFG["lookback_days"])
    response = requests.get(
        "https://api.themoviedb.org/3/discover/movie",
        params={
            "api_key": key, "with_original_language": "ta", "region": "IN",
            "release_date.gte": start, "release_date.lte": today,
            "sort_by": "popularity.desc", "include_adult": "false",
        },
        timeout=30,
    )
    response.raise_for_status()
    catalog = []
    for item in response.json().get("results", [])[:CFG["max_films"]]:
        details = {}
        try:
            detail_response = requests.get(
                f"https://api.themoviedb.org/3/movie/{item['id']}",
                params={"api_key": key, "append_to_response": "credits", "language": "en-IN"},
                timeout=30,
            )
            detail_response.raise_for_status()
            details = detail_response.json()
        except Exception:
            pass
        credits = details.get("credits", {})
        director = next(
            (person.get("name") for person in credits.get("crew", []) if person.get("job") == "Director"),
            None,
        )
        catalog.append({
            "title": item["title"],
            "original_title": details.get("original_title") or item.get("original_title"),
            "release_date": details.get("release_date") or item.get("release_date"),
            "poster_url": (
                f"https://image.tmdb.org/t/p/w500{details.get('poster_path') or item.get('poster_path')}"
                if (details.get("poster_path") or item.get("poster_path")) else None
            ),
            "backdrop_url": (
                f"https://image.tmdb.org/t/p/w1280{details.get('backdrop_path')}"
                if details.get("backdrop_path") else None
            ),
            "tmdb_id": item.get("id"),
            "overview": details.get("overview") or item.get("overview") or "",
            "runtime": details.get("runtime"),
            "genres": [genre.get("name") for genre in details.get("genres", [])],
            "director": director,
            "cast": [person.get("name") for person in credits.get("cast", [])[:10]],
        })
    return catalog

def duration_seconds(value: object) -> int:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(value or ""))
    if not match:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds

def content_format(row: pd.Series) -> str:
    seconds = duration_seconds(row.get("duration"))
    title = str(row.get("title", "")).lower()
    return "Short" if (0 < seconds <= 60 or "#shorts" in title or "#short" in title) else "Video"

def quality(video: dict) -> tuple[int, bool, bool]:
    text = f"{video.get('title', '')} {video.get('description', '')}".lower()
    channel = video.get("channelTitle", video.get("channel", ""))
    review = any(term in text for term in CFG["review_terms"])
    promo = any(term in text for term in CFG["promotion_terms"])
    trusted = any(term.lower() in channel.lower() for term in CFG["youtube_review_channels"])
    return (3 if trusted else 0) + (2 if review else 0) - (4 if promo else 0), trusted, promo

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def load_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

def discovery_due(metadata: dict, known_videos: pd.DataFrame, now: pd.Timestamp) -> bool:
    if known_videos.empty:
        return True
    last = pd.to_datetime(metadata.get("last_video_discovery"), errors="coerce", utc=True)
    if pd.isna(last):
        return True
    return now - last >= pd.Timedelta(hours=int(CFG["video_discovery_hours"]))

def merge_comments(fresh: pd.DataFrame, now: pd.Timestamp) -> tuple[pd.DataFrame, int]:
    old = load_csv(COMMENTS)
    if not old.empty and "platform" in old:
        old = old[old["platform"].eq("YouTube")].copy()
    old_ids = set(old.get("source_id", pd.Series(dtype=str)).dropna().astype(str))
    new_count = int((~fresh["source_id"].astype(str).isin(old_ids)).sum()) if not fresh.empty else 0
    combined = pd.concat([old, fresh], ignore_index=True)
    if combined.empty:
        return combined, 0
    combined = combined.drop_duplicates("source_id", keep="last")
    combined["created_at"] = pd.to_datetime(combined["created_at"], errors="coerce", utc=True)
    cutoff = now - pd.Timedelta(days=int(CFG["keep_history_days"]))
    combined = combined[combined["created_at"].ge(cutoff)].sort_values("created_at")
    return combined, new_count

def merge_snapshots(fresh: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    old = load_csv(VIDEOS)
    combined = pd.concat([old, fresh], ignore_index=True)
    if combined.empty:
        return combined
    combined["scanned_at"] = pd.to_datetime(combined["scanned_at"], errors="coerce", utc=True)
    combined = combined.drop_duplicates(["video_id", "scanned_at"], keep="last")
    cutoff = now - pd.Timedelta(days=int(CFG["keep_history_days"]))
    return combined[combined["scanned_at"].ge(cutoff)].sort_values("scanned_at")

def main() -> None:
    youtube_key = require("YOUTUBE_API_KEY")
    tmdb_key = require("TMDB_API_KEY")
    now = pd.Timestamp.now(tz="UTC")
    now_iso = now.isoformat()
    LIVE.mkdir(parents=True, exist_ok=True)

    metadata = load_json(META)
    known = load_csv(VIDEOS)
    if not known.empty:
        known["published_at"] = pd.to_datetime(known.get("published_at"), errors="coerce", utc=True)
        known["scanned_at"] = pd.to_datetime(known.get("scanned_at"), errors="coerce", utc=True)
        known = known.sort_values("scanned_at").drop_duplicates("video_id", keep="last")
    do_discovery = discovery_due(metadata, known, now)
    previous_catalog = metadata.get("movie_catalog", [])
    catalog_needs_details = not previous_catalog or any("cast" not in item for item in previous_catalog)
    catalog = discover_films(tmdb_key) if (do_discovery or catalog_needs_details) else previous_catalog
    films = [item["title"] for item in catalog]

    comment_batches: list[pd.DataFrame] = []
    snapshot_batches: list[pd.DataFrame] = []
    errors: list[str] = []
    monitored_video_ids: set[str] = set()

    for film in films:
        candidates: list[dict] = []
        if not known.empty and "film" in known:
            for row in known[known["film"].eq(film)].to_dict("records"):
                candidates.append({
                    "video_id": row.get("video_id"),
                    "signal_score": row.get("signal_score", 1),
                    "trusted_channel": row.get("trusted_channel", False),
                    "promotional": row.get("promotional", False),
                })

        if do_discovery:
            try:
                for item in youtube_search(film, youtube_key, CFG["youtube_videos_per_film"]):
                    score, trusted, promo = quality(item)
                    if score >= 1:
                        candidates.append({
                            "video_id": item["video_id"], "signal_score": score,
                            "trusted_channel": trusted, "promotional": promo,
                        })
            except Exception as exc:
                errors.append(f"Discovery/{film}: {exc}")

        candidate_map = {
            str(item["video_id"]): item for item in candidates if item.get("video_id")
        }
        if not candidate_map:
            continue

        try:
            details = youtube_details(list(candidate_map), youtube_key)
            if details.empty:
                continue
            details["film"] = film
            details["signal_score"] = details["video_id"].map(
                lambda video_id: candidate_map[video_id].get("signal_score", 1)
            )
            details["trusted_channel"] = details["video_id"].map(
                lambda video_id: bool(candidate_map[video_id].get("trusted_channel", False))
            )
            details["promotional"] = details["video_id"].map(
                lambda video_id: bool(candidate_map[video_id].get("promotional", False))
            )
            details["published_at"] = pd.to_datetime(details["published_at"], errors="coerce", utc=True)
            details["content_format"] = details.apply(content_format, axis=1)
            details = details.sort_values(
                ["trusted_channel", "signal_score", "comments", "published_at"],
                ascending=[False, False, False, False],
            )
            # Relevance/ranking decisions belong to the once-daily discovery pass.
            # Every intervening 30-minute run keeps every already selected ID so
            # the raw counter series cannot disappear because its rank changed.
            if do_discovery:
                standard_videos = details[details["content_format"].eq("Video")].head(
                    int(CFG["active_videos_per_film"])
                )
                shorts = details[details["content_format"].eq("Short")].head(
                    int(CFG["active_shorts_per_film"])
                )
                details = pd.concat([standard_videos, shorts], ignore_index=True)
            details["scanned_at"] = now_iso
            snapshot_batches.append(details)

            for row in details.itertuples():
                monitored_video_ids.add(row.video_id)
                try:
                    batch = youtube_comments(
                        row.video_id, film, row.channel, row.title, row.content_format,
                        youtube_key, int(CFG["comments_per_video"]),
                    )
                    if not batch.empty:
                        comment_batches.append(batch)
                except Exception as exc:
                    errors.append(f"Comments/{row.video_id}: {exc}")
        except Exception as exc:
            errors.append(f"Video statistics/{film}: {exc}")

    comments = (
        pd.concat(comment_batches, ignore_index=True)
        if comment_batches else pd.DataFrame()
    )
    snapshots = (
        pd.concat(snapshot_batches, ignore_index=True)
        if snapshot_batches else pd.DataFrame()
    )

    if not comments.empty:
        comments["scanned_at"] = now_iso
        comments = enrich_comments(comments)
    stored_comments, new_comments = merge_comments(comments, now)
    stored_snapshots = merge_snapshots(snapshots, now)

    if not stored_comments.empty:
        stored_comments.to_csv(COMMENTS, index=False)
    if not stored_snapshots.empty:
        stored_snapshots.to_csv(VIDEOS, index=False)

    last_discovery = now_iso if do_discovery else metadata.get("last_video_discovery")
    status = "healthy" if not errors else "partial"
    META.write_text(json.dumps({
        "status": status,
        "last_scan": now_iso,
        "last_video_discovery": last_discovery,
        "scan_interval_minutes": 30,
        "video_discovery_hours": CFG["video_discovery_hours"],
        "keep_history_days": CFG["keep_history_days"],
        "films": films,
        "comments_fetched": int(len(comments)),
        "new_comments_added": new_comments,
        "stored_comments": int(len(stored_comments)),
        "videos_monitored": len(monitored_video_ids),
        "standard_videos_monitored": int(
            snapshots[snapshots["content_format"].eq("Video")]["video_id"].nunique()
        ) if not snapshots.empty else 0,
        "shorts_monitored": int(
            snapshots[snapshots["content_format"].eq("Short")]["video_id"].nunique()
        ) if not snapshots.empty else 0,
        "movie_catalog": catalog,
        "youtube_channels": CFG["youtube_review_channels"],
        "collectors": ["YouTube Data API", "youtube-comment-downloader fallback"],
        "errors": errors,
    }, indent=2), encoding="utf-8")
    print(
        f"YouTube scan complete: {len(films)} films, {len(monitored_video_ids)} videos, "
        f"{len(comments)} fetched comments, {new_comments} new comments"
    )

if __name__ == "__main__":
    main()
