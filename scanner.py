"""Daily source-aware Tamil cinema scanner."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json, os
from pathlib import Path
import pandas as pd
import requests
from collectors import collect_reddit_json, youtube_comments, youtube_details, youtube_search
from sentiment import add_sentiment

ROOT=Path(__file__).parent; CFG=json.loads((ROOT/"scanner_config.json").read_text()); LIVE=ROOT/"data"/"live"
COMMENTS=LIVE/"comments.csv"; VIDEOS=LIVE/"video_snapshots.csv"; META=LIVE/"scan_metadata.json"

def require(name):
    value=os.getenv(name,"").strip()
    if not value: raise RuntimeError(f"Missing {name}")
    return value

def discover(key):
    today=datetime.now(timezone.utc).date(); start=today-timedelta(days=CFG["lookback_days"])
    r=requests.get("https://api.themoviedb.org/3/discover/movie",params={"api_key":key,"with_original_language":"ta","region":"IN",
        "release_date.gte":start,"release_date.lte":today,"sort_by":"popularity.desc","include_adult":"false"},timeout=30); r.raise_for_status()
    return [x["title"] for x in r.json().get("results",[])[:CFG["max_films"]]]

def quality(video):
    text=f"{video.get('title','')} {video.get('description','')}".lower(); channel=video.get("channelTitle","")
    review=any(x in text for x in CFG["review_terms"]); promo=any(x in text for x in CFG["promotion_terms"])
    trusted=any(x.lower() in channel.lower() for x in CFG["youtube_review_channels"])
    return (3 if trusted else 0)+(2 if review else 0)-(4 if promo else 0),trusted,promo

def merge(path,fresh,key,days):
    old=pd.read_csv(path) if path.exists() else pd.DataFrame(); combined=pd.concat([old,fresh],ignore_index=True)
    combined=combined.drop_duplicates(key,keep="last")
    date_col="scanned_at" if "scanned_at" in combined else "created_at"
    combined[date_col]=pd.to_datetime(combined[date_col],errors="coerce",utc=True)
    return combined[combined[date_col]>=pd.Timestamp.now(tz="UTC")-pd.Timedelta(days=int(days))]

def main():
    yt=require("YOUTUBE_API_KEY"); films=discover(require("TMDB_API_KEY")); now=datetime.now(timezone.utc).isoformat()
    comment_batches=[]; snapshot_batches=[]; errors=[]
    for film in films:
        try:
            candidates=youtube_search(film,yt,CFG["youtube_videos_per_film"])
            accepted=[]
            for item in candidates:
                score,trusted,promo=quality(item); item.update(signal_score=score,trusted_channel=trusted,promotional=promo)
                if score>=1: accepted.append(item)
            details=youtube_details([x["video_id"] for x in accepted],yt)
            if not details.empty:
                flags=pd.DataFrame(accepted)[["video_id","signal_score","trusted_channel","promotional"]]
                details=details.merge(flags,on="video_id"); details["film"]=film; details["scanned_at"]=now
                snapshot_batches.append(details)
                for row in details.itertuples(): comment_batches.append(youtube_comments(row.video_id,film,row.channel,yt,CFG["comments_per_video"]))
        except Exception as exc: errors.append(f"YouTube/{film}: {exc}")
        try: comment_batches.append(collect_reddit_json(film,CFG["reddit_forums"],CFG["reddit_posts_per_forum"]))
        except Exception as exc: errors.append(f"Reddit/{film}: {exc}")
    comments=pd.concat([x for x in comment_batches if not x.empty],ignore_index=True) if comment_batches else pd.DataFrame()
    snapshots=pd.concat(snapshot_batches,ignore_index=True) if snapshot_batches else pd.DataFrame()
    if comments.empty: raise RuntimeError("No discussions collected: "+"; ".join(errors))
    comments["scanned_at"]=now; comments=add_sentiment(comments); LIVE.mkdir(parents=True,exist_ok=True)
    merge(COMMENTS,comments,"source_id",CFG["keep_history_days"]).to_csv(COMMENTS,index=False)
    if not snapshots.empty: merge(VIDEOS,snapshots,["video_id","scanned_at"],CFG["keep_history_days"]).to_csv(VIDEOS,index=False)
    META.write_text(json.dumps({"status":"healthy" if not errors else "partial","last_scan":now,"films":films,"comments_added":len(comments),
        "youtube_channels":CFG["youtube_review_channels"],"reddit_forums":CFG["reddit_forums"],"errors":errors},indent=2))
    print(f"Scanned {len(films)} films, {len(comments)} discussions, {len(snapshots)} video snapshots")
if __name__=="__main__": main()
