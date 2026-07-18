"""Optional DeepSeek post-processing for cached Tamil film audience reports.

This script never participates in YouTube collection. It reads already stored
comments and writes cached JSON summaries for Streamlit to display later.
If DEEPSEEK_API_KEY is missing, it exits successfully without changing data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parent
LIVE = ROOT / "data" / "live"
COMMENTS = LIVE / "comments.csv"
REPORTS = LIVE / "ai_film_reports.json"


def load_comments() -> pd.DataFrame:
    try:
        frame = pd.read_csv(COMMENTS)
    except Exception:
        return pd.DataFrame()
    if frame.empty:
        return frame
    frame["created_at"] = pd.to_datetime(frame.get("created_at"), errors="coerce", utc=True)
    frame["likes"] = pd.to_numeric(frame.get("likes", 0), errors="coerce").fillna(0)
    frame["word_count"] = pd.to_numeric(frame.get("word_count", 0), errors="coerce").fillna(0)
    return frame


def representative_comments(frame: pd.DataFrame, limit: int = 120) -> list[dict]:
    useful = frame[~frame.get("low_information", False).fillna(False).astype(bool)].copy()
    if useful.empty:
        useful = frame.copy()
    useful = useful.sort_values(["likes", "word_count", "created_at"], ascending=[False, False, False]).head(limit)
    rows = []
    for _, row in useful.iterrows():
        rows.append({
            "channel": str(row.get("channel", ""))[:80],
            "format": str(row.get("content_format", "")),
            "topic": str(row.get("topic", "")),
            "reaction_signal": str(row.get("reaction_signal", "")),
            "likes": int(row.get("likes", 0)),
            "text": str(row.get("text", ""))[:500],
        })
    return rows


def call_deepseek(api_key: str, film: str, comments: list[dict]) -> dict:
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    prompt = {
        "task": "Summarize Tamil/Tanglish/English YouTube audience comments for a Tamil film.",
        "film": film,
        "rules": [
            "Use only the comments provided.",
            "Do not rate the movie.",
            "Separate praise, criticism, useful questions, sarcasm/comedy cues, promotion/scam risk, and low-effort patterns.",
            "Sarcasm must be reported as possible cues, not as certain author intent.",
            "Return strict JSON only."
        ],
        "schema": {
            "audience_summary": "string",
            "main_praise": ["string"],
            "main_criticism": ["string"],
            "useful_questions": ["string"],
            "sarcasm_or_comedy_cues": ["string"],
            "promotion_or_scam_patterns": ["string"],
            "reviewer_audience_differences": ["string"],
            "sample_size_warning": "string"
        },
        "comments": comments,
    }
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a cautious corpus analyst. Return JSON only."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1400,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def main() -> None:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("DeepSeek analysis skipped: DEEPSEEK_API_KEY is not configured")
        return
    comments = load_comments()
    if comments.empty or "film" not in comments:
        print("DeepSeek analysis skipped: no comments available")
        return
    reports = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "method": "Cached DeepSeek summaries from representative stored YouTube comments",
        "films": {},
        "errors": [],
    }
    for film, frame in comments.groupby("film"):
        sample = representative_comments(frame)
        if len(sample) < 20:
            reports["films"][str(film)] = {
                "sample_size_warning": "Too few representative comments for reliable AI summary.",
                "audience_summary": "Not enough comment evidence yet.",
            }
            continue
        try:
            reports["films"][str(film)] = call_deepseek(api_key, str(film), sample)
            reports["films"][str(film)]["comments_sampled"] = len(sample)
        except Exception as exc:
            reports["errors"].append(f"{film}: {exc}")
    REPORTS.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"DeepSeek analysis complete: {len(reports['films'])} films")


if __name__ == "__main__":
    main()
