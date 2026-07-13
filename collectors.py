"""YouTube collectors: official Data API with an open-source comment fallback."""
from __future__ import annotations

from datetime import datetime, timezone
import itertools
import re
import pandas as pd
import requests

def _youtube_get(endpoint: str, params: dict) -> dict:
    response = requests.get(f"https://www.googleapis.com/youtube/v3/{endpoint}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def youtube_search(film: str, api_key: str, max_results: int = 12) -> list[dict]:
    payload = _youtube_get("search", {
        "key": api_key, "part": "snippet", "type": "video",
        "maxResults": min(max_results, 50),
        "q": f'"{film}" Tamil movie review public review',
        "relevanceLanguage": "ta", "regionCode": "IN", "order": "date",
        "safeSearch": "none",
    })
    return [{"video_id": item["id"]["videoId"], **item["snippet"]} for item in payload.get("items", [])]

def youtube_details(video_ids: list[str], api_key: str) -> pd.DataFrame:
    unique_ids = list(dict.fromkeys(video_ids))
    rows = []
    for start in range(0, len(unique_ids), 50):
        batch = unique_ids[start:start + 50]
        if not batch:
            continue
        payload = _youtube_get("videos", {
            "key": api_key, "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch),
        })
        for item in payload.get("items", []):
            stats, snippet = item.get("statistics", {}), item.get("snippet", {})
            rows.append({
                "video_id": item["id"],
                "channel": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "published_at": snippet.get("publishedAt"),
                "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url")
                    or snippet.get("thumbnails", {}).get("medium", {}).get("url"),
                "duration": item.get("contentDetails", {}).get("duration", ""),
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            })
    return pd.DataFrame(rows)

def _api_comments(video_id: str, film: str, channel: str, title: str,
                  api_key: str, limit: int) -> pd.DataFrame:
    rows, token = [], None
    while len(rows) < limit:
        params = {
            "key": api_key, "part": "snippet", "videoId": video_id,
            "maxResults": min(100, limit - len(rows)), "order": "time",
            "textFormat": "plainText",
        }
        if token:
            params["pageToken"] = token
        payload = _youtube_get("commentThreads", params)
        for item in payload.get("items", []):
            thread = item.get("snippet", {})
            comment = thread.get("topLevelComment", {})
            top = comment.get("snippet", {})
            rows.append({
                "film": film, "platform": "YouTube", "source": channel,
                "channel": channel, "video_id": video_id, "video_title": title,
                "text": top.get("textDisplay", ""),
                "created_at": top.get("publishedAt"),
                "updated_at": top.get("updatedAt"),
                "likes": top.get("likeCount", 0),
                "reply_count": thread.get("totalReplyCount", 0),
                "author": top.get("authorDisplayName", ""),
                "url": f"https://youtube.com/watch?v={video_id}&lc={comment.get('id', '')}",
                "source_id": f"youtube:{comment.get('id', '')}",
                "content_type": "comment", "parent_id": video_id,
                "collector": "YouTube Data API",
            })
        token = payload.get("nextPageToken")
        if not token:
            break
    return pd.DataFrame(rows)

def _downloaded_comments(video_id: str, film: str, channel: str,
                         title: str, limit: int) -> pd.DataFrame:
    """Fallback powered by egbertbouman/youtube-comment-downloader (MIT)."""
    from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_RECENT
    downloader = YoutubeCommentDownloader()
    iterator = downloader.get_comments_from_url(
        f"https://www.youtube.com/watch?v={video_id}", sort_by=SORT_BY_RECENT
    )
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for item in itertools.islice(iterator, limit):
        comment_id = str(item.get("cid") or item.get("id") or "")
        votes = re.sub(r"[^0-9]", "", str(item.get("votes", "0")))
        rows.append({
            "film": film, "platform": "YouTube", "source": channel,
            "channel": channel, "video_id": video_id, "video_title": title,
            "text": item.get("text", ""), "created_at": item.get("time_parsed") or now,
            "updated_at": item.get("time_parsed") or now,
            "likes": int(votes or 0), "reply_count": 0,
            "author": item.get("author", ""),
            "url": f"https://youtube.com/watch?v={video_id}&lc={comment_id}",
            "source_id": f"youtube:{comment_id}", "content_type": "comment",
            "parent_id": video_id, "collector": "youtube-comment-downloader",
        })
    return pd.DataFrame(rows)

def youtube_comments(video_id: str, film: str, channel: str, title: str,
                     api_key: str, limit: int = 100) -> pd.DataFrame:
    try:
        return _api_comments(video_id, film, channel, title, api_key, limit)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status not in (403, 404, 429):
            raise
        try:
            return _downloaded_comments(video_id, film, channel, title, limit)
        except Exception:
            return pd.DataFrame()
