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

def normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

def title_matches_film(video: dict | pd.Series) -> bool:
    film = str(video.get("film", "")).strip()
    title = f" {normalized(video.get('title', ''))} "
    configured = CFG.get("film_title_aliases", {}).get(film, [])
    aliases = configured or [film]
    return any(f" {normalized(alias)} " in title for alias in aliases if normalized(alias))

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

def out_of_scope(video: dict | pd.Series) -> bool:
    """Reject formats that are not review/discussion coverage of the film."""
    text = f"{video.get('title', '')} {video.get('description', '')}".lower()
    return any(term.lower() in text for term in CFG.get("scope_exclusion_terms", []))

def prune_out_of_scope_archive(
    snapshots: pd.DataFrame, comments: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, set[str]]:
    """Remove clearly irrelevant videos and their attached comments from storage."""
    if snapshots.empty or "video_id" not in snapshots:
        return snapshots, comments, set()
    latest = snapshots.sort_values("scanned_at").drop_duplicates("video_id", keep="last")
    rejected = {
        str(row.get("video_id")) for _, row in latest.iterrows()
        if (out_of_scope(row) or not title_matches_film(row)) and row.get("video_id")
    }
    if not rejected:
        return snapshots, comments, rejected
    snapshots = snapshots[~snapshots["video_id"].astype(str).isin(rejected)].copy()
    if not comments.empty and "video_id" in comments:
        comments = comments[~comments["video_id"].astype(str).isin(rejected)].copy()
        retained_ids = set(snapshots["video_id"].dropna().astype(str))
        comments = comments[comments["video_id"].astype(str).isin(retained_ids)].copy()
    return snapshots, comments, rejected

def build_film_insights(comments: pd.DataFrame) -> dict[str, dict]:
    """Create conservative, traceable audience summaries from analyzed comments."""
    insights: dict[str, dict] = {}
    if comments.empty or "film" not in comments:
        return insights
    for film, frame in comments.groupby("film"):
        useful = frame[~frame.get("low_information", False).fillna(False).astype(bool)].copy()
        if useful.empty:
            continue
        explicit = useful[useful.get("reaction_signal", "Mixed / unclear").ne("Mixed / unclear")]
        reactions = explicit["reaction_signal"].value_counts()
        appreciative = int(reactions.get("Appreciative", 0))
        critical = int(reactions.get("Critical", 0))
        explicit_total = appreciative + critical
        aspect_counts = useful[~useful["topic"].eq("General reaction")]["topic"].value_counts()
        top_aspects = [
            {"name": str(name), "comments": int(count)}
            for name, count in aspect_counts.head(3).items()
        ]
        depth = useful["comment_kind"].isin(["Detailed discussion", "Question"]).mean()
        if explicit_total >= 10:
            positive_share = appreciative / explicit_total
            balance = (
                "appreciative signals clearly outweigh critical signals"
                if positive_share >= .7 else
                "critical signals outweigh appreciative signals"
                if positive_share <= .3 else
                "appreciative and critical signals are mixed"
            )
            reaction_sentence = (
                f"Of {explicit_total:,} comments with detectable reaction wording, "
                f"{appreciative:,} were appreciative and {critical:,} were critical; {balance}."
            )
        else:
            reaction_sentence = "Too few comments contain clear reaction wording to describe an audience balance reliably."
        aspect_sentence = (
            "Beyond general reactions, viewers most often discuss "
            + ", ".join(item["name"].lower() for item in top_aspects)
            + "."
            if top_aspects else
            "Most collected comments are general reactions rather than discussion of a specific film aspect."
        )
        reviewers = []
        for channel, channel_frame in useful.groupby("channel"):
            if len(channel_frame) < 10:
                continue
            channel_explicit = channel_frame[
                channel_frame["reaction_signal"].ne("Mixed / unclear")
            ]["reaction_signal"].value_counts()
            app = int(channel_explicit.get("Appreciative", 0))
            crit = int(channel_explicit.get("Critical", 0))
            reviewers.append({
                "channel": str(channel),
                "useful_comments": int(len(channel_frame)),
                "appreciative_signals": app,
                "critical_signals": crit,
                "questions": int(channel_frame.get("is_question", False).fillna(False).astype(bool).sum()),
                "leading_topic": str(channel_frame["topic"].value_counts().index[0]),
            })
        reviewers.sort(key=lambda item: item["useful_comments"], reverse=True)
        insights[str(film)] = {
            "summary": f"Based on {len(useful):,} useful public comments. {reaction_sentence} {aspect_sentence}",
            "useful_comments": int(len(useful)),
            "explicit_reaction_comments": int(explicit_total),
            "appreciative_signals": appreciative,
            "critical_signals": critical,
            "substantive_share": round(float(depth), 4),
            "top_aspects": top_aspects,
            "reviewers": reviewers,
        }
    return insights

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
    if int(metadata.get("selection_version", 0)) != int(CFG.get("selection_version", 1)):
        return True
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
    combined["created_at"] = pd.to_datetime(
        combined["created_at"], format="mixed", errors="coerce", utc=True
    )
    cutoff = now - pd.Timedelta(days=int(CFG["keep_history_days"]))
    combined = combined[combined["created_at"].ge(cutoff)].sort_values("created_at")
    return combined, new_count

def merge_snapshots(fresh: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    old = load_csv(VIDEOS)
    combined = pd.concat([old, fresh], ignore_index=True)
    if combined.empty:
        return combined
    combined["scanned_at"] = pd.to_datetime(
        combined["scanned_at"], format="mixed", errors="coerce", utc=True
    )
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
    archive_snapshots = load_csv(VIDEOS)
    archive_comments = load_csv(COMMENTS)
    if not archive_snapshots.empty:
        archive_snapshots["published_at"] = pd.to_datetime(
            archive_snapshots.get("published_at"), errors="coerce", utc=True
        )
        archive_snapshots["scanned_at"] = pd.to_datetime(
            archive_snapshots.get("scanned_at"), format="mixed", errors="coerce", utc=True
        )
    archive_snapshots, archive_comments, pruned_ids = prune_out_of_scope_archive(
        archive_snapshots, archive_comments
    )
    known = archive_snapshots.sort_values("scanned_at").drop_duplicates("video_id", keep="last") if not archive_snapshots.empty else archive_snapshots
    do_discovery = discovery_due(metadata, known, now)
    active_ids = {str(value) for value in metadata.get("active_video_ids", []) if value}
    if not do_discovery:
        if active_ids:
            known = known[known["video_id"].astype(str).isin(active_ids)].copy()
        elif not archive_snapshots.empty:
            latest_archive_scan = archive_snapshots["scanned_at"].max()
            latest_ids = set(
                archive_snapshots.loc[archive_snapshots["scanned_at"].eq(latest_archive_scan), "video_id"]
                .dropna().astype(str)
            )
            known = known[known["video_id"].astype(str).isin(latest_ids)].copy()
    previous_catalog = metadata.get("movie_catalog", [])
    previous_history = metadata.get("movie_catalog_history", previous_catalog)
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
            details = details[details.apply(title_matches_film, axis=1)].copy()
            quality_rows = details.apply(
                lambda row: quality(row.to_dict()), axis=1, result_type="expand"
            )
            details[["signal_score", "trusted_channel", "promotional"]] = quality_rows
            details = details[~details.apply(out_of_scope, axis=1)].copy()
            details = details[details["signal_score"].ge(1)].copy()
            if details.empty:
                continue
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
                    comment_limit = int(
                        CFG["comments_per_video_daily"] if do_discovery
                        else CFG["comments_per_video_live"]
                    )
                    batch = youtube_comments(
                        row.video_id, film, row.channel, row.title, row.content_format,
                        youtube_key, comment_limit,
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
    # Feed the already-pruned frames into the merge functions without losing
    # their cleanup when they reload the on-disk archive.
    if not archive_comments.empty:
        archive_comments.to_csv(COMMENTS, index=False)
    elif pruned_ids and COMMENTS.exists():
        COMMENTS.unlink()
    if not archive_snapshots.empty:
        archive_snapshots.to_csv(VIDEOS, index=False)
    elif pruned_ids and VIDEOS.exists():
        VIDEOS.unlink()
    stored_comments, new_comments = merge_comments(comments, now)
    stored_snapshots = merge_snapshots(snapshots, now)

    # A successful statistics fetch must always leave rows carrying this run's
    # timestamp. Fail loudly instead of silently publishing metadata without
    # the half-hour snapshot needed by the dashboard.
    if not snapshots.empty:
        stored_times = pd.to_datetime(stored_snapshots["scanned_at"], errors="coerce", utc=True)
        current_rows = int(stored_times.eq(now).sum())
        expected_current = int(snapshots["video_id"].nunique())
        if current_rows < expected_current:
            raise RuntimeError(
                f"Snapshot persistence check failed: expected {expected_current} current rows, found {current_rows}"
            )

    if not stored_comments.empty:
        stored_comments.to_csv(COMMENTS, index=False)
    if not stored_snapshots.empty:
        stored_snapshots.to_csv(VIDEOS, index=False)

    last_discovery = now_iso if do_discovery else metadata.get("last_video_discovery")
    status = "healthy" if not errors else "partial"
    catalog_history_map = {
        item.get("title"): item
        for item in [*previous_history, *catalog]
        if isinstance(item, dict) and item.get("title")
    }
    all_films_analyzed = sorted(
        set(stored_comments.get("film", pd.Series(dtype=str)).dropna().astype(str))
        | set(films)
    )
    film_insights = build_film_insights(stored_comments)
    META.write_text(json.dumps({
        "status": status,
        "last_scan": now_iso,
        "last_video_discovery": last_discovery,
        "scan_interval_minutes": 30,
        "video_discovery_hours": CFG["video_discovery_hours"],
        "keep_history_days": CFG["keep_history_days"],
        "selection_version": CFG.get("selection_version", 1),
        "active_video_ids": sorted(monitored_video_ids),
        "out_of_scope_videos_pruned": len(pruned_ids),
        "film_insights": film_insights,
        "insight_method": "Rule-based language, topic, depth and reaction-signal aggregation; no review score inferred",
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
        "movie_catalog_history": list(catalog_history_map.values()),
        "all_films_analyzed": all_films_analyzed,
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
