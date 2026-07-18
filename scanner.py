"""Quota-aware YouTube monitor for recent Tamil films."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

from collectors import youtube_comments, youtube_details, youtube_search, youtube_search_query
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
    aliases = film_aliases(film)
    return any(f" {normalized(alias)} " in title for alias in aliases if normalized(alias))

def film_aliases(film: str) -> list[str]:
    aliases = [film]
    aliases.extend(CFG.get("film_title_aliases", {}).get(film, []))
    for item in CFG.get("manual_films", []):
        if str(item.get("title", "")).strip() == film:
            aliases.extend(item.get("aliases", []))
    return list(dict.fromkeys(alias for alias in aliases if str(alias).strip()))

def video_mentions_film(video: dict | pd.Series, film: str) -> bool:
    text = f" {normalized(video.get('title', ''))} {normalized(video.get('description', ''))} "
    return any(f" {normalized(alias)} " in text for alias in film_aliases(film) if normalized(alias))

def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value

def safe_error(exc: Exception) -> str:
    text = str(exc)
    text = re.sub(r"([?&]key=)[^&\\s]+", r"\1***", text)
    text = re.sub(r"(Authorization:\\s*Bearer\\s+)[^\\s]+", r"\1***", text, flags=re.I)
    return text

def pause_after_search() -> None:
    delay = float(CFG.get("youtube_search_pause_seconds", 0))
    if delay > 0:
        time.sleep(delay)

def discover_films(key: str) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=CFG["lookback_days"])
    raw_items: dict[int, dict] = {}
    pages = max(1, int(CFG.get("tmdb_discovery_pages", 1)))
    sort_orders = CFG.get("tmdb_sort_orders", ["popularity.desc"])
    for sort_order in sort_orders:
        for page in range(1, pages + 1):
            response = requests.get(
                "https://api.themoviedb.org/3/discover/movie",
                params={
                    "api_key": key, "with_original_language": "ta", "region": "IN",
                    "release_date.gte": start, "release_date.lte": today,
                    "sort_by": sort_order, "include_adult": "false", "page": page,
                },
                timeout=30,
            )
            response.raise_for_status()
            for item in response.json().get("results", []):
                if item.get("id") and item["id"] not in raw_items:
                    raw_items[item["id"]] = item
    candidates = list(raw_items.values())
    candidates.sort(
        key=lambda item: (
            item.get("release_date") or "",
            float(item.get("popularity") or 0),
            int(item.get("vote_count") or 0),
        ),
        reverse=True,
    )
    catalog = []
    for item in candidates[:CFG["max_films"]]:
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
    manual = []
    known_titles = {item["title"] for item in catalog}
    for item in CFG.get("manual_films", []):
        title = str(item.get("title", "")).strip()
        if not title or title in known_titles:
            continue
        manual.append({
            "title": title,
            "original_title": item.get("original_title") or title,
            "release_date": item.get("release_date"),
            "poster_url": item.get("poster_url"),
            "backdrop_url": item.get("backdrop_url"),
            "tmdb_id": item.get("tmdb_id"),
            "overview": item.get("overview", "Manual watchlist film awaiting TMDB enrichment."),
            "runtime": item.get("runtime"),
            "genres": item.get("genres", []),
            "director": item.get("director"),
            "cast": item.get("cast", []),
            "source": "manual_watchlist",
        })
    return catalog + manual

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

def source_profile(channel: object) -> dict:
    channel_text = normalized(channel)
    for profile in CFG.get("source_channels", []):
        aliases = [profile.get("name", ""), *profile.get("aliases", [])]
        if any(normalized(alias) and normalized(alias) in channel_text for alias in aliases):
            return profile
    return {
        "name": str(channel or "Open YouTube"),
        "source_category": "open_youtube",
        "critic_weight": 0.5,
        "engagement_weight": 0.6,
    }

def video_intent(row: dict | pd.Series) -> str:
    text = f"{row.get('title', '')} {row.get('description', '')}".lower()
    fmt = str(row.get("content_format", "Video"))
    if any(term in text for term in ["official trailer", "official teaser", "lyric video", "sneak peek"]):
        return "promo_material"
    if any(term.lower() in text for term in CFG.get("interview_terms", [])):
        return "interview_archive"
    if "public review" in text or "people review" in text or "audience review" in text:
        return "public_review"
    if any(term.lower() in text for term in CFG.get("news_terms", [])):
        return "news_update"
    if "roast" in text or "troll" in text or "comedy" in text:
        return "roast_commentary"
    if "analysis" in text or "breakdown" in text or "explained" in text or "hidden details" in text:
        return "deep_analysis"
    if any(term in text for term in CFG["review_terms"]):
        return "short_review" if fmt == "Short" else "review"
    profile = source_profile(row.get("channelTitle", row.get("channel", "")))
    if profile.get("source_category") == "roast_commentary":
        return "roast_commentary"
    return "film_discussion"

def review_evidence(row: dict | pd.Series) -> bool:
    return str(row.get("video_intent", video_intent(row))) in {
        "review", "short_review", "public_review", "deep_analysis",
        "roast_commentary", "film_discussion",
    }

def quality(video: dict) -> tuple[int, bool, bool]:
    text = f"{video.get('title', '')} {video.get('description', '')}".lower()
    channel = video.get("channelTitle", video.get("channel", ""))
    profile = source_profile(channel)
    intent = video_intent(video)
    review = any(term in text for term in CFG["review_terms"])
    promo = any(term in text for term in CFG["promotion_terms"])
    trusted = profile.get("source_category") in {
        "critic_review", "general_review", "deep_analysis", "roast_commentary"
    }
    intent_bonus = {
        "review": 3,
        "short_review": 2,
        "public_review": 3,
        "deep_analysis": 2,
        "roast_commentary": 1,
        "film_discussion": 1,
        "interview_archive": 0,
        "news_update": -1,
        "promo_material": -5,
    }.get(intent, 0)
    return (3 if trusted else 0) + (2 if review else 0) + intent_bonus - (4 if promo else 0), trusted, promo

def public_review_video(row: pd.Series) -> bool:
    return str(row.get("video_intent", video_intent(row))) == "public_review"

def select_daily_videos(details: pd.DataFrame) -> pd.DataFrame:
    """Keep a balanced daily set without changing 30-minute monitor behavior."""
    if details.empty:
        return details
    standard = details[details["content_format"].eq("Video")].copy()
    shorts = details[details["content_format"].eq("Short")].copy()
    review_pool = standard[standard["review_evidence"]].copy()
    trusted = review_pool[review_pool["trusted_channel"]].head(int(CFG.get("trusted_videos_per_film", 5)))
    selected_ids = set(trusted["video_id"].dropna().astype(str))
    public = standard[
        ~standard["video_id"].astype(str).isin(selected_ids) & standard.apply(public_review_video, axis=1)
    ].head(int(CFG.get("public_review_videos_per_film", 3)))
    selected_ids.update(public["video_id"].dropna().astype(str))
    organic = review_pool[
        ~review_pool["video_id"].astype(str).isin(selected_ids)
    ].head(int(CFG.get("organic_videos_per_film", 2)))
    standard_selected = pd.concat([trusted, public, organic], ignore_index=True)
    selected_ids.update(organic["video_id"].dropna().astype(str))
    if len(standard_selected) < int(CFG["active_videos_per_film"]):
        fill = review_pool[
            ~review_pool["video_id"].astype(str).isin(selected_ids)
        ].head(int(CFG["active_videos_per_film"]) - len(standard_selected))
        standard_selected = pd.concat([standard_selected, fill], ignore_index=True)
        selected_ids.update(fill["video_id"].dropna().astype(str))
    standard_selected = standard_selected.head(int(CFG["active_videos_per_film"]))
    context = standard[
        ~standard["video_id"].astype(str).isin(selected_ids)
        & standard["video_intent"].isin(["interview_archive", "news_update"])
    ].head(int(CFG.get("context_videos_per_film", 0)))
    shorts_selected = shorts[shorts["review_evidence"]].head(int(CFG["active_shorts_per_film"]))
    return pd.concat([standard_selected, context, shorts_selected], ignore_index=True)

def out_of_scope(video: dict | pd.Series) -> bool:
    """Reject formats that are not review/discussion coverage of the film."""
    text = f"{video.get('title', '')} {video.get('description', '')}".lower()
    if str(video.get("video_intent", video_intent(video))) == "promo_material":
        return True
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

def latest_public_comment_counts(snapshots: pd.DataFrame) -> dict[str, int]:
    if snapshots.empty or "video_id" not in snapshots or "comments" not in snapshots:
        return {}
    latest = snapshots.sort_values("scanned_at").drop_duplicates("video_id", keep="last")
    counts = pd.to_numeric(latest.get("comments"), errors="coerce")
    return {
        str(video_id): int(count)
        for video_id, count in zip(latest["video_id"], counts)
        if str(video_id) and pd.notna(count)
    }

def latest_comment_fetch_times(comments: pd.DataFrame) -> dict[str, pd.Timestamp]:
    if comments.empty or "video_id" not in comments or "scanned_at" not in comments:
        return {}
    frame = comments.copy()
    frame["scanned_at"] = pd.to_datetime(
        frame["scanned_at"], format="mixed", errors="coerce", utc=True
    )
    latest = frame.dropna(subset=["scanned_at"]).groupby("video_id")["scanned_at"].max()
    return {str(video_id): timestamp for video_id, timestamp in latest.items()}

def review_video_counts_by_film(known: pd.DataFrame) -> dict[str, int]:
    if known.empty or "film" not in known:
        return {}
    frame = known.copy()
    if "content_format" not in frame:
        frame["content_format"] = "Video"
    if "review_evidence" in frame:
        evidence = frame["review_evidence"].fillna(True).astype(bool)
    elif "video_intent" in frame:
        evidence = frame["video_intent"].fillna("film_discussion").isin(
            ["review", "short_review", "public_review", "deep_analysis", "roast_commentary", "film_discussion"]
        )
    else:
        evidence = pd.Series(True, index=frame.index)
    frame = frame[evidence & frame["content_format"].eq("Video")].copy()
    if frame.empty:
        return {}
    return frame.groupby("film")["video_id"].nunique().astype(int).to_dict()

def channel_matrix_profiles() -> list[dict]:
    allowed = set(CFG.get("channel_matrix_source_categories", []))
    profiles = [
        profile for profile in CFG.get("source_channels", [])
        if profile.get("source_category") in allowed
    ]
    profiles.sort(
        key=lambda item: (
            float(item.get("critic_weight", 0)),
            float(item.get("engagement_weight", 0)),
        ),
        reverse=True,
    )
    return profiles

def film_channel_queries(films: list[str], known: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Build a quota-bounded audit matrix: weak films first, then trusted channels."""
    if not CFG.get("channel_matrix_enabled", True):
        return []
    counts = review_video_counts_by_film(known)
    min_reviews = int(CFG.get("channel_matrix_min_review_videos", 4))
    channels_per_film = int(CFG.get("channel_matrix_channels_per_film", 3))
    max_queries = int(CFG.get("channel_matrix_max_queries", 60))
    profiles = channel_matrix_profiles()
    prioritized_films = sorted(
        films,
        key=lambda film: (counts.get(film, 0), normalized(film)),
    )
    queries: list[tuple[str, str, str]] = []
    for film in prioritized_films:
        if counts.get(film, 0) >= min_reviews and len(queries) >= max_queries // 2:
            continue
        aliases = film_aliases(film)
        film_query = aliases[0]
        for profile in profiles[:channels_per_film]:
            channel_name = profile.get("name", "")
            query = f'"{film_query}" "{channel_name}" tamil movie review'
            queries.append((film, channel_name, query))
            if len(queries) >= max_queries:
                return queries
    return queries

def direct_discovery_films(films: list[str], known: pd.DataFrame) -> list[str]:
    """Search specific film names only for the weakest covered films."""
    max_queries = int(CFG.get("direct_film_discovery_max_queries", len(films)))
    counts = review_video_counts_by_film(known)
    prioritized = sorted(
        films,
        key=lambda film: (counts.get(film, 0), normalized(film)),
    )
    return prioritized[:max(0, max_queries)]

def should_fetch_comments(
    row: pd.Series,
    previous_counts: dict[str, int],
    previous_fetch_times: dict[str, pd.Timestamp],
    now: pd.Timestamp,
    do_discovery: bool,
) -> tuple[bool, str]:
    """Fetch comment bodies only when useful; always keep video counters live."""
    if do_discovery:
        return True, "daily_discovery_refresh"
    video_id = str(row.get("video_id", ""))
    current_count = pd.to_numeric(row.get("comments"), errors="coerce")
    previous_count = previous_counts.get(video_id)
    if previous_count is None or pd.isna(current_count):
        return True, "new_or_unknown_video"
    if int(current_count) > int(previous_count):
        return True, "public_comment_count_increased"
    last_fetch = previous_fetch_times.get(video_id)
    refresh_hours = int(CFG.get("comment_refresh_hours", 6))
    if last_fetch is None or now - last_fetch >= pd.Timedelta(hours=refresh_hours):
        return True, "periodic_comment_refresh"
    return False, "public_comment_count_unchanged"

def preserve_archive_guard(
    archive_comments: pd.DataFrame,
    archive_snapshots: pd.DataFrame,
    stored_comments: pd.DataFrame,
    stored_snapshots: pd.DataFrame,
    fresh_comments: pd.DataFrame,
    fresh_snapshots: pd.DataFrame,
) -> None:
    """Fail before writing if a run would accidentally erase existing history."""
    if not archive_comments.empty and stored_comments.empty and fresh_comments.empty:
        raise RuntimeError(
            "Archive safety check failed: refusing to replace non-empty comments.csv with empty output"
        )
    if not archive_snapshots.empty and stored_snapshots.empty and fresh_snapshots.empty:
        raise RuntimeError(
            "Archive safety check failed: refusing to replace non-empty video_snapshots.csv with empty output"
        )

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
    prior_comment_counts = latest_public_comment_counts(archive_snapshots)
    prior_comment_fetches = latest_comment_fetch_times(archive_comments)
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
    comment_batches: list[pd.DataFrame] = []
    snapshot_batches: list[pd.DataFrame] = []
    errors: list[str] = []
    monitored_video_ids: set[str] = set()
    comment_fetch_decisions = {
        "daily_discovery_refresh": 0,
        "new_or_unknown_video": 0,
        "public_comment_count_increased": 0,
        "periodic_comment_refresh": 0,
        "public_comment_count_unchanged": 0,
    }

    catalog = discover_films(tmdb_key) if (do_discovery or catalog_needs_details) else previous_catalog
    films = [item["title"] for item in catalog]
    broad_candidates: dict[str, list[dict]] = {film: [] for film in films}
    discovery_video_hits = 0
    channel_matrix_candidates: dict[str, list[dict]] = {film: [] for film in films}
    channel_matrix_hits = 0
    channel_matrix_queries: list[dict] = []
    if do_discovery:
        direct_films = set(direct_discovery_films(films, known))
        for query in CFG.get("youtube_discovery_queries", [])[: int(CFG.get("broad_discovery_max_queries", 8))]:
            try:
                for item in youtube_search_query(query, youtube_key, CFG["youtube_videos_per_film"]):
                    discovery_video_hits += 1
                    for film in films:
                        if video_mentions_film(item, film):
                            broad_candidates.setdefault(film, []).append(item)
                pause_after_search()
            except Exception as exc:
                errors.append(f"Broad discovery/{query}: {safe_error(exc)}")
        for film, channel_name, query in film_channel_queries(films, known):
            query_hits = 0
            matched_hits = 0
            try:
                for item in youtube_search_query(query, youtube_key, max(8, CFG["youtube_videos_per_film"] // 2)):
                    query_hits += 1
                    channel_matrix_hits += 1
                    if video_mentions_film(item, film):
                        matched_hits += 1
                        channel_matrix_candidates.setdefault(film, []).append(item)
                pause_after_search()
            except Exception as exc:
                errors.append(f"Channel matrix/{film}/{channel_name}: {safe_error(exc)}")
            channel_matrix_queries.append({
                "film": film,
                "channel": channel_name,
                "query": query,
                "hits": query_hits,
                "matched_hits": matched_hits,
            })

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
            if film in direct_films:
                try:
                    for item in youtube_search(film, youtube_key, CFG["youtube_videos_per_film"]):
                        score, trusted, promo = quality(item)
                        if score >= 1:
                            candidates.append({
                                "video_id": item["video_id"], "signal_score": score,
                                "trusted_channel": trusted, "promotional": promo,
                            })
                    pause_after_search()
                except Exception as exc:
                    errors.append(f"Discovery/{film}: {safe_error(exc)}")
            for item in broad_candidates.get(film, []):
                score, trusted, promo = quality(item)
                if score >= 1:
                    candidates.append({
                        "video_id": item["video_id"], "signal_score": score,
                        "trusted_channel": trusted, "promotional": promo,
                    })
            for item in channel_matrix_candidates.get(film, []):
                score, trusted, promo = quality(item)
                if score >= 1:
                    candidates.append({
                        "video_id": item["video_id"], "signal_score": score + 1,
                        "trusted_channel": trusted, "promotional": promo,
                    })

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
            details["source_category"] = details["channel"].map(
                lambda channel: source_profile(channel).get("source_category", "open_youtube")
            )
            details["source_profile"] = details["channel"].map(
                lambda channel: source_profile(channel).get("name", channel)
            )
            details["critic_weight"] = details["channel"].map(
                lambda channel: float(source_profile(channel).get("critic_weight", 0.5))
            )
            details["engagement_weight"] = details["channel"].map(
                lambda channel: float(source_profile(channel).get("engagement_weight", 0.6))
            )
            details["video_intent"] = details.apply(video_intent, axis=1)
            details["review_evidence"] = details.apply(review_evidence, axis=1)
            quality_rows = details.apply(
                lambda row: quality(row.to_dict()), axis=1, result_type="expand"
            )
            details[["signal_score", "trusted_channel", "promotional"]] = quality_rows
            details = details[~details.apply(out_of_scope, axis=1)].copy()
            details = details[
                details["signal_score"].ge(1)
                | details["video_intent"].isin(["interview_archive", "news_update"])
            ].copy()
            if details.empty:
                continue
            details = details.sort_values(
                ["review_evidence", "trusted_channel", "signal_score", "comments", "published_at"],
                ascending=[False, False, False, False, False],
            )
            # Relevance/ranking decisions belong to the once-daily discovery pass.
            # Every intervening 30-minute run keeps every already selected ID so
            # the raw counter series cannot disappear because its rank changed.
            if do_discovery:
                details = select_daily_videos(details)
            details["scanned_at"] = now_iso
            snapshot_batches.append(details)

            for row in details.itertuples():
                monitored_video_ids.add(row.video_id)
                row_series = pd.Series(row._asdict())
                fetch_comments, fetch_reason = should_fetch_comments(
                    row_series, prior_comment_counts, prior_comment_fetches, now, do_discovery
                )
                comment_fetch_decisions[fetch_reason] = comment_fetch_decisions.get(fetch_reason, 0) + 1
                if not fetch_comments:
                    continue
                try:
                    comment_limit = int(
                        CFG["comments_per_video_daily"] if do_discovery
                        else CFG["comments_per_video_live"]
                    )
                    batch = youtube_comments(
                        row.video_id, film, row.channel, row.title, row.content_format,
                        youtube_key, comment_limit, row.source_category, row.video_intent,
                    )
                    if not batch.empty:
                        comment_batches.append(batch)
                except Exception as exc:
                    errors.append(f"Comments/{row.video_id}: {safe_error(exc)}")
        except Exception as exc:
            errors.append(f"Video statistics/{film}: {safe_error(exc)}")

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
    # Feed already-pruned frames into the merge functions without deleting the
    # archive when a transient API failure returns no fresh rows.
    if not archive_comments.empty:
        archive_comments.to_csv(COMMENTS, index=False)
    if not archive_snapshots.empty:
        archive_snapshots.to_csv(VIDEOS, index=False)
    stored_comments, new_comments = merge_comments(comments, now)
    stored_snapshots = merge_snapshots(snapshots, now)
    preserve_archive_guard(
        archive_comments, archive_snapshots, stored_comments, stored_snapshots, comments, snapshots
    )

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
        "tmdb_discovery_pages": CFG.get("tmdb_discovery_pages", 1),
        "tmdb_sort_orders": CFG.get("tmdb_sort_orders", ["popularity.desc"]),
        "keep_history_days": CFG["keep_history_days"],
        "selection_version": CFG.get("selection_version", 1),
        "active_video_ids": sorted(monitored_video_ids),
        "out_of_scope_videos_pruned": len(pruned_ids),
        "discovery_mode": "daily_tmdb_plus_broad_youtube" if do_discovery else "monitor_existing_selection",
        "broad_discovery_queries": CFG.get("youtube_discovery_queries", []),
        "broad_discovery_video_hits": discovery_video_hits,
        "broad_discovery_queries_run": min(
            len(CFG.get("youtube_discovery_queries", [])),
            int(CFG.get("broad_discovery_max_queries", 8)),
        ),
        "direct_film_discovery_queries_run": len(direct_discovery_films(films, known)) if do_discovery else 0,
        "direct_film_discovery_films": direct_discovery_films(films, known) if do_discovery else [],
        "channel_matrix_enabled": CFG.get("channel_matrix_enabled", True),
        "channel_matrix_queries_run": len(channel_matrix_queries),
        "channel_matrix_video_hits": channel_matrix_hits,
        "channel_matrix_matched_hits": int(sum(item["matched_hits"] for item in channel_matrix_queries)),
        "channel_matrix_queries": channel_matrix_queries,
        "manual_films_configured": len(CFG.get("manual_films", [])),
        "video_selection_buckets": {
            "trusted_videos_per_film": CFG.get("trusted_videos_per_film"),
            "public_review_videos_per_film": CFG.get("public_review_videos_per_film"),
            "organic_videos_per_film": CFG.get("organic_videos_per_film"),
            "active_shorts_per_film": CFG.get("active_shorts_per_film"),
        },
        "film_insights": film_insights,
        "insight_method": "Rule-based language, topic, depth and reaction-signal aggregation; no review score inferred",
        "films": films,
        "comments_fetched": int(len(comments)),
        "comment_fetch_decisions": comment_fetch_decisions,
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
        "youtube_channels": [profile.get("name") for profile in CFG.get("source_channels", [])],
        "source_taxonomy": CFG.get("source_channels", []),
        "collectors": ["YouTube Data API", "youtube-comment-downloader fallback"],
        "errors": errors,
    }, indent=2), encoding="utf-8")
    print(
        f"YouTube scan complete: {len(films)} films, {len(monitored_video_ids)} videos, "
        f"{len(comments)} fetched comments, {new_comments} new comments"
    )

if __name__ == "__main__":
    main()
