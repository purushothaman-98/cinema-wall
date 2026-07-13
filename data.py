from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

REQUIRED = {"film", "platform", "text"}


def load_demo() -> pd.DataFrame:
    return pd.read_csv(Path(__file__).parent / "data" / "sample_comments.csv", parse_dates=["created_at"])


def load_upload(uploaded) -> pd.DataFrame:
    raw = uploaded.getvalue()
    frame = pd.read_csv(BytesIO(raw))
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    for column, default in {"created_at": pd.Timestamp.now(tz="UTC"), "likes": 0, "author": "", "url": ""}.items():
        if column not in frame:
            frame[column] = default
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
    frame["platform"] = frame["platform"].astype(str).str.title()
    return frame.dropna(subset=["film", "text"])


def aggregate(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby("film", as_index=False).agg(
        score=("sentiment_score", "mean"), mentions=("text", "size"),
        positive=("sentiment", lambda s: (s == "Positive").mean() * 100),
        neutral=("sentiment", lambda s: (s == "Neutral").mean() * 100),
        negative=("sentiment", lambda s: (s == "Negative").mean() * 100),
    )
    return grouped.sort_values(["score", "mentions"], ascending=False).reset_index(drop=True)
