"""Public Reddit JSON and official YouTube Data API collectors."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import html
import re
import time
import xml.etree.ElementTree as ET
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


def _collect_reddit_json_only(film: str, forums: list[str], posts_per_forum: int = 12) -> pd.DataFrame:
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



ATOM = {"atom": "http://www.w3.org/2005/Atom"}

def _plain_html(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def _rss_entries(url: str, params=None) -> list[dict]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, application/rss+xml, text/xml;q=0.9",
    }
    candidates = [url]
    if "://www.reddit.com/" in url:
        candidates.extend([
            url.replace("://www.reddit.com/", "://old.reddit.com/"),
            url.replace("://www.reddit.com/", "://reddit.com/"),
        ])
    last_error = None
    for candidate in candidates:
        try:
            response = requests.get(candidate, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            break
        except (requests.RequestException, ET.ParseError) as exc:
            last_error = exc
    else:
        raise last_error or RuntimeError("Reddit RSS unavailable")
    entries = []
    for entry in root.findall("atom:entry", ATOM):
        link = entry.find("atom:link", ATOM)
        author = entry.find("atom:author/atom:name", ATOM)
        content = entry.find("atom:content", ATOM)
        entries.append({
            "id": entry.findtext("atom:id", default="", namespaces=ATOM),
            "title": entry.findtext("atom:title", default="", namespaces=ATOM),
            "body": _plain_html(content.text if content is not None else ""),
            "url": link.get("href", "") if link is not None else "",
            "author": author.text if author is not None else "",
            "created_at": entry.findtext("atom:updated", default=datetime.now(timezone.utc).isoformat(), namespaces=ATOM),
        })
    return entries

def _reddit_rss(film: str, forums: list[str], posts_per_forum: int) -> pd.DataFrame:
    rows = []
    needle = re.sub(r"\W+", " ", film).lower().strip()
    for forum in forums:
        entries = _rss_entries(
            f"https://www.reddit.com/r/{forum}/search.rss",
            {"q": f'"{film}"', "restrict_sr": "on", "sort": "new", "t": "year"},
        )[:posts_per_forum]
        # If Reddit search RSS returns nothing, inspect the recent community feed.
        if not entries:
            entries = _rss_entries(f"https://www.reddit.com/r/{forum}/new/.rss")[:100]
            entries = [x for x in entries if needle in re.sub(r"\W+", " ", f"{x['title']} {x['body']}").lower()]
        for post in entries[:posts_per_forum]:
            post_id = post["id"].rsplit("/", 1)[-1].replace("t3_", "")
            rows.append({
                "film": film, "platform": "Reddit", "source": f"r/{forum}",
                "text": f"{post['title']}. {post['body']}".strip(". "),
                "created_at": post["created_at"], "likes": 0, "author": post["author"],
                "url": post["url"], "source_id": f"reddit:{post_id}",
                "content_type": "post", "parent_id": "",
            })
            if post["url"]:
                try:
                    comments = _rss_entries(post["url"].rstrip("/") + "/.rss")
                    for comment in comments:
                        comment_id = comment["id"].rsplit("/", 1)[-1]
                        if comment_id == post_id or not comment["body"]:
                            continue
                        rows.append({
                            "film": film, "platform": "Reddit", "source": f"r/{forum}",
                            "text": comment["body"], "created_at": comment["created_at"],
                            "likes": 0, "author": comment["author"], "url": comment["url"] or post["url"],
                            "source_id": f"reddit:{comment_id}", "content_type": "comment",
                            "parent_id": post_id,
                        })
                except (requests.RequestException, ET.ParseError):
                    pass
            time.sleep(.8)
        time.sleep(1)
    return pd.DataFrame(rows)

def _archive_rows(film: str, forum: str, items: dict) -> list[dict]:
    rows = []
    for item_id, post in (items or {}).items():
        post_id = str(post.get("id") or item_id).replace("t3_", "")
        title = post.get("title", "")
        body = post.get("selftext", "")
        permalink = post.get("permalink", "")
        created = post.get("created_utc", 0)
        if isinstance(created, (int, float)):
            created = datetime.fromtimestamp(created, timezone.utc).isoformat()
        rows.append({
            "film": film, "platform": "Reddit", "source": f"r/{forum}",
            "text": f"{title}. {body}".strip(". "), "created_at": created,
            "likes": max(post.get("score", 0) or 0, 0), "author": post.get("author", ""),
            "url": f"https://reddit.com{permalink}" if permalink else f"https://reddit.com/comments/{post_id}",
            "source_id": f"reddit:{post_id}", "content_type": "post", "parent_id": "",
        })
        for comment in post.get("comments", []) or []:
            comment_id = str(comment.get("id", ""))
            comment_body = comment.get("body", "")
            if not comment_id or not comment_body or comment_body in ("[deleted]", "[removed]"):
                continue
            comment_created = comment.get("created_utc", created)
            if isinstance(comment_created, (int, float)):
                comment_created = datetime.fromtimestamp(comment_created, timezone.utc).isoformat()
            rows.append({
                "film": film, "platform": "Reddit", "source": f"r/{forum}",
                "text": comment_body, "created_at": comment_created,
                "likes": max(comment.get("score", 0) or 0, 0), "author": comment.get("author", ""),
                "url": f"https://reddit.com{comment.get('permalink', permalink)}",
                "source_id": f"reddit:{comment_id}", "content_type": "comment", "parent_id": post_id,
            })
    return rows

async def _reddit_archive_async(film: str, forums: list[str], posts_per_forum: int) -> pd.DataFrame:
    from BAScraper.BAScraper_async import ArcticShiftAsync, PullPushAsync
    # BAScraper recommends PullPush for complex full-text searches. Keep one worker
    # and a conservative delay because both community archive services are shared.
    pullpush = PullPushAsync(
        log_stream_level="WARNING", task_num=1, sleep_sec=4,
        backoff_sec=10, max_retries=3, timeout=60,
    )
    arctic = ArcticShiftAsync(
        log_stream_level="WARNING", task_num=1, sleep_sec=5,
        backoff_sec=12, max_retries=2, timeout=60,
    )
    after = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
    rows = []
    for forum in forums:
        result = {}
        try:
            result = await pullpush.fetch(
                mode="submissions", subreddit=forum, q=f'"{film}"',
                get_comments=True, after=after, size=min(posts_per_forum, 100),
                sort="desc", sort_type="created_utc", file_name=None,
            )
        except Exception:
            # Arctic Shift fallback is intentionally lighter: retrieving large
            # comment trees together with full-text search causes server 422 timeouts.
            result = await arctic.fetch(
                mode="submissions_search", subreddit=forum, query=f'"{film}"',
                get_comments=False, after=after, limit=min(posts_per_forum, 25),
                sort="desc", file_name=None,
            )
        rows.extend(_archive_rows(film, forum, result))
    return pd.DataFrame(rows)

def collect_reddit_json(film: str, forums: list[str], posts_per_forum: int = 12) -> pd.DataFrame:
    """BAScraper/Arctic Shift first; direct JSON and public RSS are fallbacks."""
    archive_error = None
    try:
        archived = asyncio.run(_reddit_archive_async(film, forums, posts_per_forum))
        if not archived.empty:
            return archived
    except Exception as exc:
        archive_error = exc
    try:
        return _collect_reddit_json_only(film, forums, posts_per_forum)
    except (requests.RequestException, ValueError):
        try:
            return _reddit_rss(film, forums, posts_per_forum)
        except Exception:
            if archive_error:
                raise RuntimeError(f"BAScraper/Arctic Shift failed: {archive_error}")
            raise

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
