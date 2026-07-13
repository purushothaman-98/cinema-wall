"""Official API collectors. Credentials are supplied by Streamlit secrets."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


def collect_youtube(video_ids: list[str], api_key: str, film: str, max_comments: int = 300) -> pd.DataFrame:
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
    rows = []
    for video_id in video_ids:
        token = None
        while len(rows) < max_comments:
            response = youtube.commentThreads().list(
                part="snippet", videoId=video_id, maxResults=min(100, max_comments - len(rows)),
                order="relevance", pageToken=token, textFormat="plainText"
            ).execute()
            for item in response.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                rows.append({"film": film, "platform": "YouTube", "text": top["textDisplay"],
                             "created_at": top["publishedAt"], "likes": top.get("likeCount", 0),
                             "author": top.get("authorDisplayName", ""),
                             "url": f"https://youtube.com/watch?v={video_id}"})
            token = response.get("nextPageToken")
            if not token:
                break
    return pd.DataFrame(rows)


def collect_reddit(query: str, film: str, client_id: str, client_secret: str,
                   user_agent: str, max_comments: int = 300) -> pd.DataFrame:
    import praw

    reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)
    rows = []
    for submission in reddit.subreddit("kollywood").search(query, sort="new", limit=25):
        submission.comments.replace_more(limit=0)
        for comment in submission.comments.list():
            rows.append({"film": film, "platform": "Reddit", "text": comment.body,
                         "created_at": datetime.fromtimestamp(comment.created_utc, timezone.utc).isoformat(),
                         "likes": max(comment.score, 0), "author": str(comment.author or ""),
                         "url": f"https://reddit.com{comment.permalink}"})
            if len(rows) >= max_comments:
                return pd.DataFrame(rows)
    return pd.DataFrame(rows)
