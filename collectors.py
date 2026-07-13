"""Public Reddit JSON and official YouTube Data API collectors."""
from __future__ import annotations

from datetime import datetime, timezone
import time
from urllib.parse import quote
import pandas as pd
import requests

USER_AGENT = "tamil-film-pulse/2.0 public-discussion-research"


def _reddit_get(url: str, params=None):
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=30)
    if response.status_code == 429:
        time.sleep(20)
        response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.json()


def _flatten_comments(children, film, forum, post_url, rows, post_id):
    for child in children or []:
        if child.get("kind") != "t1":
            continue
        data = child.get("data", {})
        body = data.get("body", "")
        if body and body not in ("[deleted]", "[removed]"):
            rows.append({"film": film, "platform": "Reddit", "source": f"r/{forum}", "text": body,
                "created_at": datetime.fromtimestamp(data.get("created_utc", 0), timezone.utc).isoformat(),
                "likes": max(data.get("score", 0), 0), "author": data.get("author", ""),
                "url": f"https://reddit.com{data.get('permalink', post_url)}", "source_id": f"reddit:{data.get('id')}",
                "content_type": "comment", "parent_id": post_id})
        replies = data.get("replies")
        if isinstance(replies, dict):
            _flatten_comments(replies.get("data", {}).get("children", []), film, forum, post_url, rows, post_id)


def collect_reddit_json(film: str, forums: list[str], posts_per_forum: int = 12) -> pd.DataFrame:
    rows = []
    for forum in forums:
        listing = _reddit_get(f"https://www.reddit.com/r/{forum}/search.json", {
            "q": f'"{film}"', "restrict_sr": "on", "sort": "new", "t": "year", "limit": posts_per_forum, "raw_json": 1})
        for child in listing.get("data", {}).get("children", []):
            post = child.get("data", {})
            post_id = post.get("id")
            title, body = post.get("title", ""), post.get("selftext", "")
            permalink = post.get("permalink", "")
            rows.append({"film": film, "platform": "Reddit", "source": f"r/{forum}", "text": f"{title}. {body}".strip(),
                "created_at": datetime.fromtimestamp(post.get("created_utc", 0), timezone.utc).isoformat(),
                "likes": max(post.get("score", 0), 0), "author": post.get("author", ""),
                "url": f"https://reddit.com{permalink}", "source_id": f"reddit:{post_id}", "content_type": "post", "parent_id": ""})
            thread = _reddit_get(f"https://www.reddit.com{permalink}.json", {"limit": 500, "depth": 8, "raw_json": 1})
            if isinstance(thread, list) and len(thread) > 1:
                _flatten_comments(thread[1].get("data", {}).get("children", []), film, forum, permalink, rows, post_id)
            time.sleep(1.2)
        time.sleep(1.5)
    return pd.DataFrame(rows)


def youtube_search(film: str, api_key: str, max_results: int = 12) -> list[dict]:
    response = requests.get("https://www.googleapis.com/youtube/v3/search", params={"key": api_key, "part": "snippet",
        "type": "video", "maxResults": max_results, "q": f"{film} Tamil movie review", "relevanceLanguage": "ta",
        "regionCode": "IN", "order": "relevance"}, timeout=30)
    response.raise_for_status()
    return [{"video_id": item["id"]["videoId"], **item["snippet"]} for item in response.json().get("items", [])]


def youtube_details(video_ids: list[str], api_key: str) -> pd.DataFrame:
    if not video_ids:
        return pd.DataFrame()
    response = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"key": api_key, "part": "snippet,statistics",
        "id": ",".join(video_ids)}, timeout=30)
    response.raise_for_status()
    rows=[]
    for item in response.json().get("items", []):
        stats, snippet = item.get("statistics", {}), item.get("snippet", {})
        rows.append({"video_id": item["id"], "channel": snippet.get("channelTitle", ""), "title": snippet.get("title", ""),
            "published_at": snippet.get("publishedAt"), "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)), "comments": int(stats.get("commentCount", 0))})
    return pd.DataFrame(rows)


def youtube_comments(video_id: str, film: str, channel: str, api_key: str, limit: int = 120) -> pd.DataFrame:
    rows=[]; token=None
    while len(rows) < limit:
        params={"key": api_key,"part":"snippet","videoId":video_id,"maxResults":min(100,limit-len(rows)),"order":"relevance","textFormat":"plainText"}
        if token: params["pageToken"]=token
        response=requests.get("https://www.googleapis.com/youtube/v3/commentThreads",params=params,timeout=30)
        if response.status_code in (403,404): break
        response.raise_for_status(); payload=response.json()
        for item in payload.get("items",[]):
            comment=item["snippet"]["topLevelComment"]; top=comment["snippet"]
            rows.append({"film":film,"platform":"YouTube","source":channel,"text":top["textDisplay"],"created_at":top["publishedAt"],
                "likes":top.get("likeCount",0),"author":top.get("authorDisplayName",""),"url":f"https://youtube.com/watch?v={video_id}",
                "source_id":f"youtube:{comment['id']}","content_type":"comment","parent_id":video_id})
        token=payload.get("nextPageToken")
        if not token: break
    return pd.DataFrame(rows)
