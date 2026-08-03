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

from collectors import (
    youtube_channel_uploads,
    youtube_comments,
    youtube_details,
    youtube_search,
    youtube_search_query,
)
from youtube_analysis import enrich_comments

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "scanner_config.json").read_text(encoding="utf-8"))
LIVE = ROOT / "data" / "live"
COMMENTS = LIVE / "comments.csv"
VIDEOS = LIVE / "video_snapshots.csv"
META = LIVE / "scan_metadata.json"
CHANNEL_EVALUATION = LIVE / "channel_evaluation.csv"
TOP_CHANNEL_COVERAGE = LIVE / "top_channel_coverage.csv"

def normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

def compact_normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame:
        return pd.Series(default, index=frame.index)
    values = frame[column]
    if values.dtype == bool:
        return values.fillna(default)
    normalized_values = values.astype(str).str.strip().str.lower()
    parsed = normalized_values.map({
        "true": True,
        "1": True,
        "yes": True,
        "y": True,
        "false": False,
        "0": False,
        "no": False,
        "n": False,
        "nan": default,
        "none": default,
        "": default,
    })
    return parsed.fillna(default).astype(bool)

def text_contains_alias(text: object, alias: object) -> bool:
    spaced_text = f" {normalized(text)} "
    spaced_alias = normalized(alias)
    if spaced_alias and f" {spaced_alias} " in spaced_text:
        return True
    compact_alias = compact_normalized(alias)
    min_compact = int(CFG.get("min_compact_alias_length", 6))
    return bool(
        compact_alias
        and len(compact_alias) >= min_compact
        and compact_alias in compact_normalized(text)
    )

def generated_title_aliases(title: object) -> list[str]:
    """Create conservative title variants for YouTube spacing/punctuation drift."""
    raw = str(title or "").strip()
    spaced = normalized(raw)
    if not spaced:
        return []
    variants = [raw, spaced, compact_normalized(raw)]
    connector_variants = {
        spaced.replace(" and ", " & "),
        spaced.replace(" & ", " and "),
        spaced.replace(" part ", " "),
    }
    variants.extend(connector_variants)
    tokens = spaced.split()
    if len(tokens) > 1:
        variants.append("".join(tokens))
    return list(dict.fromkeys(alias for alias in variants if str(alias).strip()))

def title_matches_film(video: dict | pd.Series) -> bool:
    film = str(video.get("film", "")).strip()
    aliases = film_aliases(film)
    return any(text_contains_alias(video.get("title", ""), alias) for alias in aliases)

def film_aliases(film: str) -> list[str]:
    aliases = generated_title_aliases(film)
    aliases.extend(CFG.get("film_title_aliases", {}).get(film, []))
    for item in CFG.get("manual_films", []):
        if str(item.get("title", "")).strip() == film:
            aliases.extend(item.get("aliases", []))
    expanded: list[str] = []
    for alias in aliases:
        expanded.extend(generated_title_aliases(alias))
    return list(dict.fromkeys(alias for alias in expanded if str(alias).strip()))

def video_mentions_film(video: dict | pd.Series, film: str) -> bool:
    text = f"{video.get('title', '')} {video.get('description', '')}"
    return any(text_contains_alias(text, alias) for alias in film_aliases(film))

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

def source_profile_name(channel: object) -> str:
    return str(source_profile(channel).get("name") or channel or "Open YouTube")

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
        evidence = bool_series(frame, "review_evidence", True)
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

def top_channel_profiles() -> list[dict]:
    configured = [str(name).strip() for name in CFG.get("top_channel_coverage_channels", []) if str(name).strip()]
    profiles = CFG.get("source_channels", [])
    if not configured:
        return profiles[:8]
    by_name = {str(profile.get("name", "")).strip(): profile for profile in profiles}
    selected = [by_name[name] for name in configured if name in by_name]
    missing = [name for name in configured if name not in by_name]
    for name in missing:
        selected.append({"name": name, "aliases": [name], "source_category": "unknown"})
    return selected

def review_snapshot_frame(snapshots: pd.DataFrame) -> pd.DataFrame:
    if snapshots.empty or "film" not in snapshots or "channel" not in snapshots:
        return pd.DataFrame()
    frame = snapshots.copy()
    if "scanned_at" in frame:
        frame["scanned_at"] = pd.to_datetime(frame["scanned_at"], format="mixed", errors="coerce", utc=True)
        frame = frame.sort_values("scanned_at").drop_duplicates("video_id", keep="last")
    if "content_format" not in frame:
        frame["content_format"] = "Video"
    if "review_evidence" in frame:
        evidence = bool_series(frame, "review_evidence", True)
    else:
        evidence = pd.Series(True, index=frame.index)
    frame = frame[evidence & frame["content_format"].eq("Video")].copy()
    if frame.empty:
        return frame
    frame["source_profile"] = frame["channel"].map(source_profile_name)
    return frame

def build_top_channel_coverage(
    films: list[str],
    snapshots: pd.DataFrame,
    comments: pd.DataFrame,
    checked_channels: set[str] | None = None,
) -> pd.DataFrame:
    def latest_datetime_text(frame: pd.DataFrame, column: str) -> str:
        if frame.empty or column not in frame:
            return ""
        values = pd.to_datetime(frame[column], format="mixed", errors="coerce", utc=True)
        latest = values.max()
        if pd.isna(latest):
            return ""
        return latest.isoformat()

    checked_channels = checked_channels or set()
    review_frame = review_snapshot_frame(snapshots)
    comment_frame = comments.copy() if not comments.empty else pd.DataFrame()
    if not comment_frame.empty and "channel" in comment_frame:
        comment_frame["source_profile"] = comment_frame["channel"].map(source_profile_name)
    rows = []
    profiles = top_channel_profiles()
    for film in films:
        film_reviews = review_frame[review_frame["film"].eq(film)] if not review_frame.empty else pd.DataFrame()
        film_comments = comment_frame[comment_frame["film"].eq(film)] if not comment_frame.empty and "film" in comment_frame else pd.DataFrame()
        present_channels = set(film_reviews.get("source_profile", pd.Series(dtype=str)).dropna().astype(str))
        present_channels.update(film_comments.get("source_profile", pd.Series(dtype=str)).dropna().astype(str))
        coverage_count = len(present_channels.intersection({str(profile.get("name")) for profile in profiles}))
        for order, profile in enumerate(profiles, start=1):
            channel = str(profile.get("name", "")).strip()
            channel_reviews = film_reviews[film_reviews["source_profile"].eq(channel)] if not film_reviews.empty else pd.DataFrame()
            channel_comments = film_comments[film_comments.get("source_profile", pd.Series(dtype=str)).eq(channel)] if not film_comments.empty else pd.DataFrame()
            tracked_videos = int(channel_reviews["video_id"].nunique()) if not channel_reviews.empty else 0
            stored_comments = int(len(channel_comments)) if not channel_comments.empty else 0
            if stored_comments:
                status = "fetched_with_comments"
                note = "Comment evidence from this channel is stored."
            elif tracked_videos:
                status = "tracked_no_comments"
                note = "Review evidence tracked, but no stored comments yet."
            elif not profile.get("channel_id"):
                status = "needs_channel_id"
                note = "Add exact YouTube channel ID before low-quota upload-feed checks."
            elif channel in checked_channels and coverage_count > 0:
                status = "checked_needs_search_retry"
                note = (
                    "Upload feed was checked, but other top channels already show coverage; "
                    "targeted search should keep retrying this pair."
                )
            elif channel in checked_channels:
                status = "checked_no_recent_match"
                note = "Exact upload feed checked in this discovery run; no recent matching title found."
            else:
                status = "missing_needs_retry"
                note = "Targeted film-channel search should retry this pair."
            latest_published = ""
            latest_scanned = ""
            if not channel_reviews.empty:
                latest_published = latest_datetime_text(channel_reviews, "published_at")
                latest_scanned = latest_datetime_text(channel_reviews, "scanned_at")
            rows.append({
                "film": film,
                "channel": channel,
                "channel_rank": order,
                "channel_id": profile.get("channel_id", ""),
                "source_category": profile.get("source_category", ""),
                "status": status,
                "top_channels_present_for_film": coverage_count,
                "top_channels_total": len(profiles),
                "tracked_review_videos": tracked_videos,
                "stored_comments": stored_comments,
                "latest_published_at": latest_published,
                "latest_scanned_at": latest_scanned,
                "retry_priority": (len(profiles) - coverage_count) * 10 + order,
                "note": note,
            })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["retry_priority", "film", "channel_rank"], ascending=[False, True, True])

def missing_top_channel_pairs(
    films: list[str],
    known: pd.DataFrame,
    comments: pd.DataFrame,
    max_pairs: int,
) -> list[tuple[str, dict]]:
    ledger = build_top_channel_coverage(films, known, comments)
    if ledger.empty:
        return []
    retryable_statuses = {"missing_needs_retry", "checked_needs_search_retry"}
    retryable = ledger[ledger["status"].isin(retryable_statuses)].copy()
    if retryable.empty:
        return []
    interest = pd.DataFrame(columns=["film", "public_comments", "public_views"])
    review_frame = review_snapshot_frame(known)
    if not review_frame.empty:
        for column in ["comments", "views"]:
            if column not in review_frame:
                review_frame[column] = 0
            review_frame[column] = pd.to_numeric(review_frame[column], errors="coerce").fillna(0)
        interest = review_frame.groupby("film", as_index=False).agg(
            public_comments=("comments", "sum"),
            public_views=("views", "sum"),
        )
    retryable = retryable.merge(interest, on="film", how="left").fillna({"public_comments": 0, "public_views": 0})
    retryable["has_some_top_channel_coverage"] = retryable["top_channels_present_for_film"].gt(0)
    profile_by_name = {str(profile.get("name", "")): profile for profile in top_channel_profiles()}
    pairs: list[tuple[str, dict]] = []
    retryable = retryable.sort_values(
        ["has_some_top_channel_coverage", "public_comments", "public_views", "top_channels_present_for_film", "channel_rank", "film"],
        ascending=[False, False, False, True, True, True],
    )
    for _, row in retryable.iterrows():
        profile = profile_by_name.get(str(row["channel"]))
        if profile:
            pairs.append((str(row["film"]), profile))
        if len(pairs) >= max_pairs:
            break
    return pairs

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

def source_channel_discovery_profiles() -> list[dict]:
    allowed = set(CFG.get("source_channel_discovery_source_categories", []))
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
    return profiles[: int(CFG.get("source_channel_discovery_max_queries", 0))]

def upload_feed_profiles() -> list[dict]:
    """Known channel-ID sources whose recent uploads can be checked cheaply."""
    allowed = set(CFG.get("upload_feed_source_categories", []))
    profiles = [
        profile for profile in CFG.get("source_channels", [])
        if profile.get("channel_id")
        and (
            not allowed
            or profile.get("source_category") in allowed
        )
    ]
    profiles.sort(
        key=lambda item: (
            float(item.get("critic_weight", 0)),
            float(item.get("engagement_weight", 0)),
        ),
        reverse=True,
    )
    return profiles[: int(CFG.get("upload_feed_max_channels", len(profiles)))]

def source_channel_query(profile: dict) -> str:
    aliases = [profile.get("name", ""), *profile.get("aliases", [])]
    channel_name = next((str(alias).strip() for alias in aliases if str(alias).strip()), "")
    return f'"{channel_name}" tamil movie review'

def film_channel_queries(
    films: list[str],
    known: pd.DataFrame,
    comments: pd.DataFrame | None = None,
) -> list[tuple[str, str, str]]:
    """Build a quota-bounded audit matrix from missing top-channel coverage."""
    if not CFG.get("channel_matrix_enabled", True):
        return []
    queries: list[tuple[str, str, str]] = []
    max_queries = int(CFG.get("top_channel_retry_max_queries", CFG.get("channel_matrix_max_queries", 60)))
    comments = comments if comments is not None else pd.DataFrame()
    for film, profile in missing_top_channel_pairs(films, known, comments, max_queries):
        aliases = film_aliases(film)
        film_query = aliases[0]
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

def build_channel_evaluation(snapshots: pd.DataFrame, comments: pd.DataFrame) -> pd.DataFrame:
    """Rank YouTube sources by useful review/comment evidence already collected."""
    if snapshots.empty or "channel" not in snapshots:
        return pd.DataFrame()
    latest = snapshots.sort_values("scanned_at").drop_duplicates("video_id", keep="last").copy()
    for column, default in {
        "source_category": "open_youtube",
        "video_intent": "film_discussion",
        "content_format": "Video",
    }.items():
        if column not in latest:
            latest[column] = default
        latest[column] = latest[column].fillna(default)
    latest["public_comments"] = pd.to_numeric(latest.get("comments"), errors="coerce").fillna(0)
    latest["views"] = pd.to_numeric(latest.get("views"), errors="coerce").fillna(0)
    review_intents = {
        "review", "short_review", "public_review", "deep_analysis",
        "roast_commentary", "film_discussion",
    }
    context_intents = {"interview_archive", "news_update"}
    channel_rows = []
    comment_counts = pd.DataFrame()
    if not comments.empty and "channel" in comments:
        comment_frame = comments.copy()
        comment_frame["low_information"] = bool_series(comment_frame, "low_information", False)
        comment_frame["is_question"] = bool_series(comment_frame, "is_question", False)
        comment_counts = comment_frame.groupby("channel").agg(
            stored_comments=("text", "count"),
            useful_comments=("low_information", lambda values: int((~values).sum())),
            questions=("is_question", "sum"),
        )
    for channel, frame in latest.groupby("channel"):
        profile = source_profile(channel)
        comments_row = comment_counts.loc[channel] if channel in comment_counts.index else {}
        stored_comments = int(comments_row.get("stored_comments", 0)) if len(comment_counts) else 0
        useful_comments = int(comments_row.get("useful_comments", 0)) if len(comment_counts) else 0
        questions = int(comments_row.get("questions", 0)) if len(comment_counts) else 0
        items = int(frame["video_id"].nunique())
        review_items = int(frame["video_intent"].isin(review_intents).sum())
        context_items = int(frame["video_intent"].isin(context_intents).sum())
        shorts = int(frame["content_format"].eq("Short").sum())
        films = int(frame["film"].nunique()) if "film" in frame else 0
        public_comments = int(frame["public_comments"].sum())
        useful_share = useful_comments / stored_comments if stored_comments else 0.0
        review_share = review_items / items if items else 0.0
        comments_per_item = public_comments / items if items else 0.0
        tracker_value = (
            2.0 * films
            + 1.5 * review_items
            + 0.4 * shorts
            + 0.015 * min(public_comments, 5000)
            + 3.0 * float(profile.get("critic_weight", 0.5))
            + 2.0 * useful_share
            - 1.0 * context_items
        )
        channel_rows.append({
            "channel": channel,
            "source_profile": profile.get("name", channel),
            "source_category": profile.get("source_category", "open_youtube"),
            "films_covered": films,
            "items_tracked": items,
            "full_videos": int(frame["content_format"].eq("Video").sum()),
            "shorts": shorts,
            "review_discussion_items": review_items,
            "context_items": context_items,
            "review_share_pct": round(review_share * 100, 1),
            "stored_comments": stored_comments,
            "useful_comments": useful_comments,
            "useful_share_pct": round(useful_share * 100, 1),
            "questions": questions,
            "public_comments": public_comments,
            "views": int(frame["views"].sum()),
            "comments_per_item": round(comments_per_item, 1),
            "tracker_value": round(tracker_value, 2),
        })
    if not channel_rows:
        return pd.DataFrame()
    return pd.DataFrame(channel_rows).sort_values(
        ["tracker_value", "films_covered", "public_comments"],
        ascending=False,
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
    source_channel_hits = 0
    source_channel_matches = 0
    upload_feed_hits = 0
    upload_feed_matches = 0
    upload_feed_queries: list[dict] = []
    source_channel_queries: list[dict] = []
    channel_matrix_candidates: dict[str, list[dict]] = {film: [] for film in films}
    channel_matrix_hits = 0
    channel_matrix_queries: list[dict] = []
    if do_discovery:
        direct_films = set(direct_discovery_films(films, known))
        for profile in upload_feed_profiles():
            channel_id = str(profile.get("channel_id", "")).strip()
            if not channel_id:
                continue
            query_hits = 0
            matched_hits = 0
            try:
                for item in youtube_channel_uploads(
                    channel_id,
                    youtube_key,
                    int(CFG.get("upload_feed_videos_per_channel", 25)),
                ):
                    query_hits += 1
                    upload_feed_hits += 1
                    for film in films:
                        if video_mentions_film(item, film):
                            matched_hits += 1
                            upload_feed_matches += 1
                            broad_candidates.setdefault(film, []).append(item)
            except Exception as exc:
                errors.append(f"Upload feed/{profile.get('name', 'unknown')}: {safe_error(exc)}")
            upload_feed_queries.append({
                "channel": profile.get("name"),
                "channel_id": channel_id,
                "hits": query_hits,
                "matched_hits": matched_hits,
            })
        for profile in source_channel_discovery_profiles():
            query = source_channel_query(profile)
            if not query.strip('" '):
                continue
            query_hits = 0
            matched_hits = 0
            try:
                for item in youtube_search_query(query, youtube_key, CFG["youtube_videos_per_film"]):
                    query_hits += 1
                    source_channel_hits += 1
                    for film in films:
                        if video_mentions_film(item, film):
                            matched_hits += 1
                            source_channel_matches += 1
                            broad_candidates.setdefault(film, []).append(item)
                pause_after_search()
            except Exception as exc:
                errors.append(f"Source channel/{profile.get('name', 'unknown')}: {safe_error(exc)}")
            source_channel_queries.append({
                "channel": profile.get("name"),
                "query": query,
                "hits": query_hits,
                "matched_hits": matched_hits,
            })
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
        for film, channel_name, query in film_channel_queries(films, known, archive_comments):
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
        for seed in CFG.get("manual_video_seeds", []):
            if str(seed.get("film", "")).strip() == film and str(seed.get("video_id", "")).strip():
                candidates.append({
                    "video_id": str(seed["video_id"]).strip(),
                    "signal_score": seed.get("signal_score", 5),
                    "trusted_channel": seed.get("trusted_channel", True),
                    "promotional": seed.get("promotional", False),
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
            if details.empty:
                continue
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
            if quality_rows.empty:
                continue
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
    channel_evaluation = build_channel_evaluation(stored_snapshots, stored_comments)
    if not channel_evaluation.empty:
        channel_evaluation.to_csv(CHANNEL_EVALUATION, index=False)

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
    checked_top_channels = (
        {str(item.get("channel", "")).strip() for item in upload_feed_queries if item.get("channel")}
        if do_discovery else set()
    )
    top_channel_coverage = build_top_channel_coverage(
        all_films_analyzed,
        stored_snapshots,
        stored_comments,
        checked_top_channels,
    )
    if not top_channel_coverage.empty:
        top_channel_coverage.to_csv(TOP_CHANNEL_COVERAGE, index=False)
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
        "broad_discovery_queries_run": (
            min(
                len(CFG.get("youtube_discovery_queries", [])),
                int(CFG.get("broad_discovery_max_queries", 8)),
            )
            if do_discovery else 0
        ),
        "source_channel_queries_run": len(source_channel_queries),
        "source_channel_video_hits": source_channel_hits,
        "source_channel_matched_hits": source_channel_matches,
        "source_channel_queries": source_channel_queries,
        "upload_feed_channels_run": len(upload_feed_queries),
        "upload_feed_video_hits": upload_feed_hits,
        "upload_feed_matched_hits": upload_feed_matches,
        "upload_feed_queries": upload_feed_queries,
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
        "channel_evaluation_rows": int(len(channel_evaluation)),
        "top_channel_coverage_channels": [profile.get("name") for profile in top_channel_profiles()],
        "top_channel_coverage_rows": int(len(top_channel_coverage)),
        "top_channel_missing_pairs": (
            int(top_channel_coverage["status"].isin(["missing_needs_retry", "needs_channel_id"]).sum())
            if not top_channel_coverage.empty else 0
        ),
        "top_channel_retry_queries_run": len(channel_matrix_queries),
        "collectors": ["YouTube Data API", "youtube-comment-downloader fallback"],
        "errors": errors,
    }, indent=2), encoding="utf-8")
    print(
        f"YouTube scan complete: {len(films)} films, {len(monitored_video_ids)} videos, "
        f"{len(comments)} fetched comments, {new_comments} new comments"
    )

if __name__ == "__main__":
    main()
